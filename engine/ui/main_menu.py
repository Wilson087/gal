"""
主菜单模块
==========
游戏初始界面，包含新游戏/继续/载入/剧本选择/设置/退出。
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..app import AVGApplication

import pyglet
from pyglet.graphics import Group, Batch
from pyglet.shapes import RoundedRectangle, Rectangle
from pyglet.text import Label
from pyglet.window import mouse

from ..core.constants import FONT_FAMILIES
from ..core.logger import Logger

log = Logger("Menu")

# ── 颜色 ───────────────────────────────────────────────────
_BG = (0, 0, 0, 200)               # 背景遮罩
_BTN_BG = (255, 255, 255, 30)       # 按钮正常
_BTN_HOVER = (255, 255, 255, 60)    # 按钮悬停
_BTN_ACTIVE = (25, 118, 210, 200)   # 选中高亮
_TEXT = (255, 255, 255, 255)
_TEXT_DIM = (170, 170, 170, 255)
_TITLE_COLOR = (255, 255, 255, 255)

_BTN_W = 280
_BTN_H = 44
_BTN_RADIUS = 8
_BTN_SPACING = 12


class MainMenu:
    """主菜单界面。"""

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        self._batch = app.ui_batch
        self._group = Group(order=50)

        # 主菜单状态
        self._visible = False
        self._in_script_selection = False
        self._buttons: list[dict] = []
        self._script_buttons: list[dict] = []
        self._bg_rect: Optional[Rectangle] = None
        self._title_label: Optional[Label] = None
        self._version_label: Optional[Label] = None
        self._subtitle_label: Optional[Label] = None

    # ── 显示/隐藏 ───────────────────────────────────────────

    def show(self) -> None:
        """显示主菜单。"""
        self._visible = True
        self._in_script_selection = False
        self._buttons = []
        self._script_buttons = []
        w, h = self.app.width, self.app.height

        # 背景遮罩
        self._bg_rect = Rectangle(0, 0, w, h, color=_BG[:3],
                                   batch=self._batch, group=self._group)

        # 标题
        sm = self.app.scene_manager
        title = sm.title if sm.title else "Visual Novel"
        self._title_label = Label(title, font_name=FONT_FAMILIES, font_size=36,
                                  color=_TITLE_COLOR, weight="bold",
                                  x=w // 2, y=h - 120,
                                  anchor_x="center", anchor_y="center",
                                  batch=self._batch, group=self._group)

        # 版本号
        ver = sm.script.get("version", "") if sm.script else ""
        if ver:
            self._version_label = Label(f"version {ver}",
                                        font_name=FONT_FAMILIES, font_size=12,
                                        color=_TEXT_DIM,
                                        x=w // 2, y=h - 155,
                                        anchor_x="center", anchor_y="center",
                                        batch=self._batch, group=self._group)

        self._build_main_buttons()

    def _build_main_buttons(self) -> None:
        """构建主菜单按钮列表。"""
        self._clear_buttons()
        w, h = self.app.width, self.app.height
        sm = self.app.scene_manager

        buttons = [("新游戏", self._on_new_game)]

        # 如果有存档，显示"继续游戏"
        if self.app.save_manager.get_latest_slot() is not None:
            buttons.append(("继续游戏", self._on_continue))

        buttons += [
            ("载入存档", self._on_load),
            ("剧本选择", self._on_script_select),
            ("设　置",  self._on_settings),
            ("退　出",  self._on_exit),
        ]

        total_h = len(buttons) * _BTN_H + (len(buttons) - 1) * _BTN_SPACING
        start_y = h // 2 + total_h // 2 - 20

        for i, (label, cb) in enumerate(buttons):
            y = int(start_y - i * (_BTN_H + _BTN_SPACING))
            x = (w - _BTN_W) // 2
            rect = RoundedRectangle(x, y, _BTN_W, _BTN_H, _BTN_RADIUS,
                                    color=_BTN_BG[:3],
                                    batch=self._batch, group=self._group)
            lbl = Label(label, font_name=FONT_FAMILIES, font_size=14,
                        color=_TEXT,
                        x=w // 2, y=y + _BTN_H // 2,
                        anchor_x="center", anchor_y="center",
                        batch=self._batch, group=self._group)
            self._buttons.append({
                "rect": rect, "label": lbl,
                "bounds": (x, y, _BTN_W, _BTN_H),
                "callback": cb, "hover": False,
            })

    def _build_script_list(self) -> None:
        """构建剧本选择列表。"""
        self._clear_buttons()
        w, h = self.app.width, self.app.height
        scripts = self._list_scripts()

        if not scripts:
            # 没有剧本，显示提示
            self._subtitle_label = Label("未找到剧本文件",
                                         font_name=FONT_FAMILIES, font_size=14,
                                         color=_TEXT_DIM,
                                         x=w // 2, y=h // 2,
                                         anchor_x="center", anchor_y="center",
                                         batch=self._batch, group=self._group)
            # 返回按钮
            self._add_back_button()
            return

        total_h = len(scripts) * _BTN_H + (len(scripts) - 1) * _BTN_SPACING
        start_y = min(h // 2 + total_h // 2, h - 180)

        self._subtitle_label = Label("选择剧本", font_name=FONT_FAMILIES,
                                      font_size=16, color=_TEXT,
                                      x=w // 2, y=start_y + 40,
                                      anchor_x="center", anchor_y="center",
                                      batch=self._batch, group=self._group)

        for i, sc in enumerate(scripts):
            y = int(start_y - i * (_BTN_H + _BTN_SPACING))
            x = (w - _BTN_W) // 2
            rect = RoundedRectangle(x, y, _BTN_W, _BTN_H, _BTN_RADIUS,
                                    color=_BTN_BG[:3],
                                    batch=self._batch, group=self._group)
            display = sc["name"][:20] if len(sc["name"]) > 20 else sc["name"]
            lbl = Label(display, font_name=FONT_FAMILIES, font_size=13,
                        color=_TEXT,
                        x=w // 2, y=y + _BTN_H // 2,
                        anchor_x="center", anchor_y="center",
                        batch=self._batch, group=self._group)
            self._script_buttons.append({
                "rect": rect, "label": lbl,
                "bounds": (x, y, _BTN_W, _BTN_H),
                "file": sc["file"],
            })

        self._add_back_button()

    def _add_back_button(self) -> None:
        """添加返回按钮。"""
        lbl = Label("< 返回", font_name=FONT_FAMILIES, font_size=12,
                    color=_TEXT_DIM,
                    x=30, y=30, anchor_x="left", anchor_y="bottom",
                    batch=self._batch, group=self._group)
        self._buttons.append({
            "rect": None, "label": lbl,
            "bounds": (10, 10, 80, 30),
            "callback": self._back_to_main, "hover": False,
        })

    def hide(self) -> None:
        """隐藏主菜单。"""
        self._visible = False
        self._in_script_selection = False
        self._clear_all()
        self._buttons.clear()
        self._script_buttons.clear()

    def _clear_buttons(self) -> None:
        for btn in self._buttons:
            if btn["rect"]:
                btn["rect"].delete()
            btn["label"].delete()
        self._buttons.clear()
        for btn in self._script_buttons:
            btn["rect"].delete()
            btn["label"].delete()
        self._script_buttons.clear()
        if self._subtitle_label:
            self._subtitle_label.delete()
            self._subtitle_label = None

    def _clear_all(self) -> None:
        self._clear_buttons()
        if self._bg_rect:
            self._bg_rect.delete()
            self._bg_rect = None
        if self._title_label:
            self._title_label.delete()
            self._title_label = None
        if self._version_label:
            self._version_label.delete()
            self._version_label = None

    # ── 事件处理 ───────────────────────────────────────────

    def on_mouse_press(self, x: int, y: int) -> bool:
        """处理点击。返回 True 表示消费。"""
        if not self._visible:
            return False

        # 剧本选择模式
        if self._in_script_selection:
            for btn in self._script_buttons:
                rx, ry, rw, rh = btn["bounds"]
                if rx <= x <= rx + rw and ry <= y <= ry + rh:
                    self._load_script(btn["file"])
                    return True
            # 返回按钮
            for btn in self._buttons:
                if btn["bounds"] and btn.get("callback"):
                    rx, ry, rw, rh = btn["bounds"]
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        btn["callback"]()
                        return True
            return True

        # 主菜单
        for btn in self._buttons:
            if not btn["bounds"]:
                continue
            rx, ry, rw, rh = btn["bounds"]
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                if btn.get("callback"):
                    btn["callback"]()
                return True

        return True

    def on_mouse_motion(self, x: int, y: int) -> None:
        """更新按钮悬停高亮。"""
        if not self._visible:
            return
        target = self._script_buttons if self._in_script_selection else self._buttons
        for btn in target:
            if not btn["bounds"]:
                continue
            rx, ry, rw, rh = btn["bounds"]
            hovering = rx <= x <= rx + rw and ry <= y <= ry + rh
            rect = btn.get("rect")
            if rect and hovering != btn.get("hover", False):
                btn["hover"] = hovering
                rect.color = _BTN_HOVER[:3] if hovering else _BTN_BG[:3]

    # ── 按钮回调 ───────────────────────────────────────────

    def _on_new_game(self) -> None:
        """新游戏。"""
        self.hide()
        self.app.start_game()

    def _on_continue(self) -> None:
        """继续游戏：读取最新存档。"""
        self.hide()
        latest = self.app.save_manager.get_latest_slot()
        if latest is not None:
            self.app.save_manager.load(latest)

    def _on_load(self) -> None:
        """打开读档面板。"""
        self.hide()
        self.app.ui_manager.show_panel("load")

    def _on_script_select(self) -> None:
        """进入剧本选择子菜单。"""
        self._clear_buttons()
        self._in_script_selection = True
        self._build_script_list()

    def _on_settings(self) -> None:
        """打开设置面板。"""
        self.hide()
        self.app.ui_manager.show_panel("settings")

    def _on_exit(self) -> None:
        """退出游戏。"""
        self.app.close()

    def _back_to_main(self) -> None:
        """返回主菜单。"""
        self._in_script_selection = False
        self._clear_buttons()
        self._build_main_buttons()

    # ── 工具方法 ───────────────────────────────────────────

    def _list_scripts(self) -> list[dict]:
        """扫描 scripts/ 目录下的所有 JSON 剧本文件。"""
        scripts: list[dict] = []
        if not os.path.isdir("scripts"):
            return scripts
        for f in sorted(os.listdir("scripts")):
            if not f.endswith(".json"):
                continue
            path = os.path.join("scripts", f)
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    title = data.get("title", f)
                scripts.append({"file": path, "name": title, "filename": f})
            except Exception as e:
                log.warning("无法读取剧本 %s: %s", f, e)
                scripts.append({"file": path, "name": f, "filename": f})
        return scripts

    def _load_script(self, path: str) -> None:
        """加载选中的剧本并开始游戏。"""
        try:
            self.hide()
            self.app.load_script(path)
            self.app.start_game()
        except Exception as e:
            log.error("加载剧本失败: %s", e)
