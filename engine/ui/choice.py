"""
选项系统模块
============
渲染选项分支列表，支持条件过滤、鼠标悬停高亮和点击处理。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..app import AVGApplication

import pyglet
from pyglet.graphics import Batch, Group
from pyglet.text import Label

from ..core.constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT,
    COLOR_CHOICE_BG, COLOR_CHOICE_HOVER, COLOR_CHOICE_TEXT,
    FONT_FAMILIES, FONT_SIZE_CHOICE,
    DIALOGUE_FRAME_HEIGHT,
)
from ..core.logger import Logger

log = Logger("Choice")


class ChoiceSystem:
    """选项系统：渲染、交互、跳转。"""

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        self._group = Group(order=13)
        self._active = False
        self._choices: list[dict] = []
        self._choice_data: list[dict] = []  # items with text/rect/state
        self._hover_index: int = -1

    def show_choices(self, choices: list[dict]) -> None:
        """根据条件过滤并显示选项。

        Args:
            choices: 原始 choices 列表。
        """
        # 条件过滤
        valid = []
        for c in choices:
            condition = c.get("if", "")
            if self.app.variable_bank.evaluate_condition(condition):
                valid.append(c)

        if not valid:
            # 无可用选项，直接结束场景
            log.debug("无可用选项（条件过滤后为空），结束场景")
            self.app.scene_manager.end_scene()
            return

        log.debug("显示选项: %d 个", len(valid))
        self._active = True
        self._choices = valid
        self._hover_index = -1
        self._choice_data = []

        batch = self.app.ui_batch
        count = len(valid)
        total_h = count * 50 + (count - 1) * 10
        start_y = (WINDOW_HEIGHT - DIALOGUE_FRAME_HEIGHT - total_h) // 2 + total_h

        for i, choice in enumerate(valid):
            y = start_y - i * 60
            rect = pyglet.shapes.Rectangle(
                WINDOW_WIDTH // 2 - 200, y - 20, 400, 40,
                color=COLOR_CHOICE_BG[:3], batch=batch, group=self._group,
            )
            label = Label(
                choice["text"], font_name=FONT_FAMILIES, font_size=FONT_SIZE_CHOICE,
                color=COLOR_CHOICE_TEXT,
                x=WINDOW_WIDTH // 2, y=y + 4,
                anchor_x="center", anchor_y="center",
                batch=batch, group=self._group,
            )
            self._choice_data.append({
                "choice": choice,
                "rect": rect,
                "label": label,
                "rect_bounds": (WINDOW_WIDTH // 2 - 200, y - 20, 400, 40),
            })

    def on_click(self, x: int, y: int) -> bool:
        """处理鼠标点击。

        Args:
            x, y: 鼠标坐标。

        Returns:
            是否点击到了选项。
        """
        if not self._active:
            return False

        for item in self._choice_data:
            rx, ry, rw, rh = item["rect_bounds"]
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                choice = item["choice"]
                log.debug("选项点击: text=%r next=%s", choice.get("text", "")[:30], choice.get("next_scene"))
                # 设置变量
                set_var = choice.get("set_var", {})
                if set_var:
                    self.app.variable_bank.bulk_apply(set_var)
                # 隐藏选项
                self.hide()
                # 跳转场景
                next_scene = choice.get("next_scene", "")
                if next_scene:
                    self.app.scene_manager.jump_to_scene(next_scene)
                return True

        return False

    def update(self, dt: float) -> None:
        """帧更新：检测鼠标悬停高亮。"""
        if not self._active:
            return
        # 获取鼠标位置
        x, y = self._get_mouse_pos()
        found = False
        for i, item in enumerate(self._choice_data):
            rx, ry, rw, rh = item["rect_bounds"]
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                if self._hover_index != i:
                    self._hover_index = i
                    item["rect"].color = COLOR_CHOICE_HOVER[:3]
                found = True
            else:
                item["rect"].color = COLOR_CHOICE_BG[:3]
        if not found:
            self._hover_index = -1

    def _get_mouse_pos(self) -> tuple[int, int]:
        """获取当前鼠标位置。"""
        try:
            return self.app._mouse_x, self.app._mouse_y
        except AttributeError:
            return 0, 0

    def hide(self) -> None:
        """隐藏所有选项。"""
        for item in self._choice_data:
            item["rect"].delete()
            item["label"].delete()
        self._choice_data = []
        self._choices = []
        self._active = False
        self._hover_index = -1

    def get_branch_info(self) -> str:
        """返回当前分支变量信息（用于工具栏"分支"按钮显示）。"""
        variables = self.app.variable_bank.variables
        if not variables:
            return "无分支变量"
        return " | ".join(f"{k}={v}" for k, v in variables.items())
