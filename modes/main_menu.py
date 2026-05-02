"""
Main Menu — 视觉主菜单
=======================
标题画面的图形化交互按钮，替代脚本驱动的 @choice 文本选项。

背景图 + 标题文字 + 6 个悬停高亮按钮 + 键盘导航。
"""

from __future__ import annotations

import logging
from typing import Any

import pyglet.shapes
import pyglet.text
from pyglet.graphics import Batch, Group

from core.events import EventBus

logger = logging.getLogger(__name__)


def _pctx(pct: float, width: int) -> int:
    return int(width * pct / 100.0)


def _pcty(pct: float, height: int) -> int:
    return int(height * pct / 100.0)


_MENU_ITEMS: list[tuple[str, str]] = [
    ("开始游戏", "new_game"),
    ("继续游戏", "load_game"),
    ("CG 画廊", "cg_gallery"),
    ("音乐欣赏", "music_room"),
    ("立绘鉴赏", "character_viewer"),
    ("退出游戏", "quit"),
]

# ── 颜色常量 ────────────────────────────────────────────────

_COLOR_BTN_NORMAL = (20, 20, 40)
_COLOR_BTN_HOVER = (100, 120, 200)
_COLOR_BTN_SELECTED = (80, 140, 220)
_COLOR_ACCENT = (180, 200, 255)
_ALPHA_BTN = 200
_ALPHA_HIGHLIGHT = 230


class MainMenu:
    """标题画面主菜单。

    在 TITLE 状态下由 Game 直接驱动，不使用脚本系统。
    按钮命中时通过 event_bus 发出 ``"menu_select"`` 事件。
    """

    def __init__(
        self,
        batch: Batch,
        ui_group: Group,
        width: int,
        height: int,
        resource_manager: Any = None,
        event_bus: EventBus | None = None,
        font_name: str | None = None,
    ) -> None:
        self._batch = batch
        self._group = ui_group
        self._width = width
        self._height = height
        self._rm = resource_manager
        self._event_bus = event_bus
        self._font_name = font_name
        self._visible = False

        # 按钮状态
        self._selected_index: int = 0
        self._hover_index: int = -1
        self._buttons: list[dict[str, Any]] = []

        # pyglet 对象
        self._title_label: pyglet.text.Label | None = None
        self._subtitle_label: pyglet.text.Label | None = None
        self._version_label: pyglet.text.Label | None = None

    # ── 生命周期 ──────────────────────────────────────────

    def show(self) -> None:
        """显示主菜单。"""
        self._visible = True
        self._selected_index = 0
        self._hover_index = -1
        self._build_ui()

    def hide(self) -> None:
        """隐藏主菜单并清理所有 UI 对象。"""
        self._visible = False
        self._delete_ui()

    def update(self, dt: float) -> None:
        """更新按钮高亮颜色。"""
        if not self._visible:
            return
        for i, btn in enumerate(self._buttons):
            rect = btn.get("rect")
            accent = btn.get("accent")
            if rect is None:
                continue
            if i == self._hover_index and i == self._selected_index:
                rect.color = _COLOR_BTN_HOVER
                rect.opacity = _ALPHA_HIGHLIGHT
            elif i == self._hover_index:
                rect.color = _COLOR_BTN_HOVER
                rect.opacity = _ALPHA_HIGHLIGHT
            elif i == self._selected_index:
                rect.color = _COLOR_BTN_SELECTED
                rect.opacity = _ALPHA_HIGHLIGHT
            else:
                rect.color = _COLOR_BTN_NORMAL
                rect.opacity = _ALPHA_BTN
            # 高亮条 — 仅在悬停或选中时可见
            if accent is not None:
                accent.visible = i in (self._hover_index, self._selected_index)

    def draw(self) -> None:
        """空 —— Batch 自动绘制。"""

    # ── 输入 ──────────────────────────────────────────────

    def handle_click(self, x: float, y: float) -> None:
        """鼠标点击 —— 命中按钮则发出 menu_select。"""
        for i, btn in enumerate(self._buttons):
            rect = btn.get("rect")
            if rect is None:
                continue
            if rect.x <= x <= rect.x + rect.width and rect.y <= y <= rect.y + rect.height:
                self._select(i)
                return

    def handle_mouse_motion(self, x: float, y: float) -> None:
        """鼠标移动 —— 更新悬停索引。"""
        self._hover_index = -1
        for i, btn in enumerate(self._buttons):
            rect = btn.get("rect")
            if rect is None:
                continue
            if rect.x <= x <= rect.x + rect.width and rect.y <= y <= rect.y + rect.height:
                self._hover_index = i
                return

    def handle_key(self, symbol: int) -> None:
        """键盘上下导航。"""
        import pyglet.window
        k = pyglet.window.key
        if symbol == k.UP:
            self._selected_index = max(0, self._selected_index - 1)
        elif symbol == k.DOWN:
            self._selected_index = min(len(_MENU_ITEMS) - 1, self._selected_index + 1)
        elif symbol in (k.ENTER, k.SPACE):
            self._select(self._selected_index)

    # ── 内部 ──────────────────────────────────────────────

    def _select(self, index: int) -> None:
        """选中某个按钮：发出 menu_select 事件。"""
        if 0 <= index < len(_MENU_ITEMS):
            tag = _MENU_ITEMS[index][1]
            logger.info("主菜单选择: %s", tag)
            if self._event_bus:
                self._event_bus.emit("menu_select", tag=tag, index=index)

    def _build_ui(self) -> None:
        """构建标题文字 + 按钮。"""
        self._delete_ui()

        cx = self._width // 2

        # ── 标题 ──────────────────────────────────────────
        self._title_label = pyglet.text.Label(
            "Visual Novel Engine",
            font_name=self._font_name, font_size=48,
            x=cx, y=_pcty(70, self._height),
            color=(255, 255, 255, 255),
            anchor_x="center", anchor_y="center",
            batch=self._batch, group=self._group,
        )
        self._subtitle_label = pyglet.text.Label(
            "— 春 日 野 穹 —",
            font_name=self._font_name, font_size=24,
            x=cx, y=_pcty(63, self._height),
            color=(200, 200, 220, 255),
            anchor_x="center", anchor_y="center",
            batch=self._batch, group=self._group,
        )

        # ── 按钮 ──────────────────────────────────────────
        n = len(_MENU_ITEMS)
        btn_w = _pctx(30, self._width)
        btn_h = 48
        spacing = 6
        total_h = n * btn_h + (n - 1) * spacing
        start_y = (self._height // 2) + (total_h // 2) - btn_h
        btn_x = _pctx(35, self._width)

        for i, (text, _tag) in enumerate(_MENU_ITEMS):
            by = start_y - i * (btn_h + spacing)

            # 高亮条（按钮左侧）
            accent = pyglet.shapes.Rectangle(
                x=btn_x - 6, y=by + 4,
                width=4, height=btn_h - 8,
                color=_COLOR_ACCENT,
                batch=self._batch, group=self._group,
            )
            accent.visible = (i == 0)

            # 按钮背景
            rect = pyglet.shapes.Rectangle(
                x=btn_x, y=by, width=btn_w, height=btn_h,
                color=_COLOR_BTN_NORMAL,
                batch=self._batch, group=self._group,
            )
            rect.opacity = _ALPHA_BTN

            # 按钮文字
            lbl = pyglet.text.Label(
                text, font_name=self._font_name, font_size=22,
                x=btn_x + btn_w // 2, y=by + btn_h // 2,
                color=(255, 255, 255, 255),
                anchor_x="center", anchor_y="center",
                batch=self._batch, group=self._group,
            )

            self._buttons.append({
                "rect": rect, "label": lbl, "accent": accent,
                "tag": _tag,
            })

        # ── 版本号 ────────────────────────────────────────
        self._version_label = pyglet.text.Label(
            "V2.5",
            font_name=self._font_name, font_size=12,
            x=_pctx(95, self._width), y=_pcty(3, self._height),
            color=(120, 120, 140, 255),
            anchor_x="right", anchor_y="center",
            batch=self._batch, group=self._group,
        )

    def _delete_ui(self) -> None:
        """删除所有 UI 对象。"""
        for obj in (self._title_label, self._subtitle_label, self._version_label):
            if obj is not None:
                obj.delete()
        self._title_label = None
        self._subtitle_label = None
        self._version_label = None
        for btn in self._buttons:
            for key in ("rect", "label", "accent"):
                obj = btn.get(key)
                if obj is not None:
                    obj.delete()
        self._buttons.clear()
        self._selected_index = 0
        self._hover_index = -1
