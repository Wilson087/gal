"""
UI 编排器模块
=============
管理导航栏、弹出面板、通知提示等所有 UI 覆盖层。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from ..app import AVGApplication

import pyglet
from pyglet.graphics import Group, Batch
from pyglet.window import key, mouse
from pyglet.shapes import RoundedRectangle, Rectangle, Circle
from pyglet.text import Label

from ..core.constants import FONT_FAMILIES
from ..core.logger import Logger

log = Logger("UI")

# ── UI 层级 order ──────────────────────────────────────────
ORDER_NAV_BAR = 30      # 底部导航栏
ORDER_NOTIFICATION = 40  # 提示通知
ORDER_PANEL = 50        # 弹出面板
ORDER_PANEL_BORDER = 51 # 面板边框
ORDER_TOOLTIP = 70      # 按钮提示文字
ORDER_OVERLAY = 90      # 全局遮罩

# ── 颜色 ───────────────────────────────────────────────────
PANEL_BG = (18, 18, 18, 191)        # #121212 BF (75% opacity)
PANEL_BORDER = (255, 255, 255, 51)  # white, 20% opacity
BTN_BG = (255, 255, 255, 25)        # white, 10% opacity
BTN_HOVER = (255, 255, 255, 51)     # white, 20% opacity
BTN_ACTIVE = (255, 255, 255, 76)    # white, 30% opacity
TEXT_NORMAL = (255, 255, 255, 255)
TEXT_DIM = (170, 170, 170, 255)
TEXT_ACCENT = (25, 118, 210, 255)   # #1976D2
TEXT_BLACK = (0, 0, 0, 255)         # 按钮黑色文字（提高可读性）
NAV_BG = (18, 18, 18, 204)          # nav bar background

_RADIUS = 8


# ====================================================================
#  UI 控件辅助函数
# ====================================================================

def make_button(x: int, y: int, w: int, h: int,
                label: str, batch: Batch, group: Group,
                shortcut: str = "",
                callback: Optional[Callable] = None) -> dict:
    """创建一个 RoundedRectangle 按钮。

    Returns:
        dict: 包含 "rect"(RoundedRectangle), "label"(Label),
              "shortcut"(Label可选), "bounds"(x,y,w,h), "callback"
    """
    rect = RoundedRectangle(x, y, w, h, _RADIUS,
                            color=BTN_BG[:3], batch=batch, group=group)
    lbl = Label(label, font_name=FONT_FAMILIES, font_size=12,
                color=TEXT_NORMAL,
                x=x + w // 2, y=y + h // 2,
                anchor_x="center", anchor_y="center",
                batch=batch, group=group)
    sc_lbl = None
    if shortcut:
        sc_lbl = Label(shortcut, font_name=FONT_FAMILIES, font_size=8,
                       color=TEXT_DIM,
                       x=x + w - 4, y=y + 4,
                       anchor_x="right", anchor_y="bottom",
                       batch=batch, group=group)
    return {
        "rect": rect,
        "label": lbl,
        "shortcut": sc_lbl,
        "bounds": (x, y, w, h),
        "callback": callback,
        "hover": False,
    }


def make_label(text: str, x: int, y: int, font_size: int = 12,
               color: tuple = TEXT_NORMAL,
               anchor_x: str = "left",
               anchor_y: str = "center", bold: bool = False,
               batch: Optional[Batch] = None,
               group: Optional[Group] = None) -> Label:
    """创建标准 Label。"""
    return Label(text, font_name=FONT_FAMILIES, font_size=font_size,
                 color=color,
                 x=x, y=y,
                 anchor_x=anchor_x,  # type: ignore[arg-type]
                 anchor_y=anchor_y,  # type: ignore[arg-type]
                 weight="bold" if bold else "normal",
                 batch=batch, group=group)


def hit_test(x: int, y: int, bounds: tuple) -> bool:
    """点是否在矩形区域内。"""
    rx, ry, rw, rh = bounds
    return rx <= x <= rx + rw and ry <= y <= ry + rh


# ====================================================================
#  通知系统
# ====================================================================

class Notification:
    """淡入淡出通知（例如"已快速保存"）。"""

    FADE_IN = 0.3
    HOLD = 1.5
    FADE_OUT = 0.5

    def __init__(self, ui_batch: Batch, group: Group) -> None:
        self._batch = ui_batch
        self._group = group
        self._rect: Optional[RoundedRectangle] = None
        self._label: Optional[Label] = None
        self._timer: float = 0.0
        self._phase: str = "idle"  # idle, fade_in, hold, fade_out
        self._total_duration: float = 0.0

    def show(self, text: str, duration: float = 2.0) -> None:
        """显示一条通知。"""
        self.hide()
        self._total_duration = duration
        w, h = 250, 40
        x = (1280 - w) // 2
        y = 360 - h // 2

        self._rect = RoundedRectangle(x, y, w, h, _RADIUS,
                                       color=(0, 0, 0, 200),
                                       batch=self._batch, group=self._group)
        self._label = Label(text, font_name=FONT_FAMILIES, font_size=14,
                            color=TEXT_NORMAL,
                            x=1280 // 2, y=360,
                            anchor_x="center", anchor_y="center",
                            batch=self._batch, group=self._group)
        self._timer = 0.0
        self._phase = "fade_in"

    def hide(self) -> None:
        if self._rect:
            self._rect.delete()
            self._rect = None
        if self._label:
            self._label.delete()
            self._label = None
        self._phase = "idle"

    def update(self, dt: float) -> None:
        if self._phase == "idle":
            return
        self._timer += dt
        if self._phase == "fade_in":
            progress = min(1.0, self._timer / self.FADE_IN)
            alpha = int(progress * 255)
            if self._rect:
                self._rect.opacity = alpha
            if self._label:
                self._label.color = (*TEXT_NORMAL[:3], alpha)
            if progress >= 1.0:
                self._phase = "hold"
                self._timer = 0.0
        elif self._phase == "hold":
            if self._timer >= self._total_duration:
                self._phase = "fade_out"
                self._timer = 0.0
        elif self._phase == "fade_out":
            progress = min(1.0, self._timer / self.FADE_OUT)
            alpha = int((1.0 - progress) * 255)
            if self._rect:
                self._rect.opacity = alpha
            if self._label:
                self._label.color = (*TEXT_NORMAL[:3], alpha)
            if progress >= 1.0:
                self.hide()

    def is_active(self) -> bool:
        return self._phase != "idle"


# ====================================================================
#  UI 编排器
# ====================================================================

class UIManager:
    """全局 UI 编排器：导航栏、面板管理、通知。"""

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        self._ui_batch = app.ui_batch

        # 层级 Group
        self._nav_group = Group(order=ORDER_NAV_BAR)
        self._notif_group = Group(order=ORDER_NOTIFICATION)
        self._panel_group = Group(order=ORDER_PANEL)
        self._panel_border_group = Group(order=ORDER_PANEL_BORDER)
        self._overlay_group = Group(order=ORDER_OVERLAY)

        # 常驻工具栏
        self._nav_buttons: list[dict] = []
        self._nav_bar_bg: Optional[Rectangle] = None
        self._nav_bar_height = 46  # 更紧凑

        # 面板
        self._overlay: Optional[Rectangle] = None
        self._active_panel: str = ""  # "", "settings", "save", "load", "history"
        self._panel_elements: list = []  # 面板的所有 UI 元素引用

        # 通知
        self.notification = Notification(self._ui_batch, self._notif_group)

        # 当前面板引用（由具体面板模块设置）
        self._settings_panel: Any = None
        self._save_load_panel: Any = None
        self._history_panel: Any = None

        self._build_nav_bar()

    def set_settings_panel(self, panel: Any) -> None:
        self._settings_panel = panel

    def set_save_load_panel(self, panel: Any) -> None:
        self._save_load_panel = panel

    def set_history_panel(self, panel: Any) -> None:
        self._history_panel = panel

    # ── 常驻工具栏（15个按钮，永不隐藏） ────────────────

    BTN_W = 44
    BTN_H = 32
    BTN_SPACING = 4
    BTN_TOP = 8  # 工具栏顶部内边距

    def _build_nav_bar(self) -> None:
        """构建底部常驻工具栏（15个按钮）。"""
        total_w = 15 * self.BTN_W + 14 * self.BTN_SPACING
        start_x = int((1280 - total_w) / 2)

        # 工具栏背景
        self._nav_bar_bg = Rectangle(
            0, 0, 1280, self._nav_bar_height,
            color=NAV_BG[:3], batch=self._ui_batch, group=self._nav_group,
        )

        button_defs = [
            ("存档",  self._on_save),
            ("读档",  self._on_load),
            ("快存",  self._on_quick_save),
            ("快读",  self._on_quick_load),
            ("设置",  self._on_settings),
            ("后退",  self._on_back),
            ("上一个", self._on_prev_choice),
            ("历史",  self._on_history),
            ("下句",  self._on_next),
            ("快进",  self._on_skip),
            ("分支",  self._on_branch),
            ("静音",  self._on_mute),
            ("语音",  self._on_revoice),
            ("截图",  self._on_screenshot),
            ("菜单",  self._on_mainmenu),
        ]

        for i, (label, cb) in enumerate(button_defs):
            x = start_x + i * (self.BTN_W + self.BTN_SPACING)
            btn = make_button(x, self.BTN_TOP, self.BTN_W, self.BTN_H,
                              label, self._ui_batch, self._nav_group,
                              callback=cb)
            # 按钮文字改成黑色，提高在亮色背景上的可读性
            btn["label"].color = TEXT_BLACK
            self._nav_buttons.append(btn)

    def _update_nav_bar(self, dt: float) -> None:
        """更新工具栏：按钮悬停高亮。"""
        mx, my = 0, 0
        try:
            mx, my = self.app._mouse_x, self.app._mouse_y
        except AttributeError:
            pass

        for btn in self._nav_buttons:
            if btn["bounds"]:
                hovering = hit_test(mx, my, btn["bounds"])
                if hovering != btn["hover"]:
                    btn["hover"] = hovering
                    btn["rect"].color = BTN_HOVER[:3] if hovering else BTN_BG[:3]

    # ── 工具栏按钮回调 ─────────────────────────────────

    def _on_save(self) -> None:
        if hasattr(self.app, 'ui_manager'):
            self.show_panel("save")

    def _on_load(self) -> None:
        if hasattr(self.app, 'ui_manager'):
            self.show_panel("load")

    def _on_quick_save(self) -> None:
        if hasattr(self.app, 'save_manager'):
            if self.app.save_manager.quick_save():
                self.notification.show("已快速保存", 1.5)

    def _on_quick_load(self) -> None:
        if hasattr(self.app, 'save_manager'):
            self.app.save_manager.quick_load()

    def _on_settings(self) -> None:
        self.show_panel("settings")

    def _on_back(self) -> None:
        if hasattr(self.app, '_go_back'):
            self.app._go_back()

    def _on_prev_choice(self) -> None:
        if hasattr(self.app, '_previous_choice'):
            self.app._previous_choice()

    def _on_history(self) -> None:
        if self._history_panel:
            self.show_panel("history")

    def _on_next(self) -> None:
        if hasattr(self.app, '_next_dialogue'):
            self.app._next_dialogue()

    def _on_skip(self) -> None:
        if self.app.dialogue_system:
            self.app.dialogue_system._skip_type = True

    def _on_branch(self) -> None:
        """显示当前分支变量信息。"""
        info = ""
        if hasattr(self.app, 'choice_system'):
            info = self.app.choice_system.get_branch_info()
        self.notification.show(info, 2.0)

    def _on_mute(self) -> None:
        if hasattr(self.app, '_toggle_mute'):
            self.app._toggle_mute()

    def _on_revoice(self) -> None:
        if hasattr(self.app, '_replay_voice'):
            self.app._replay_voice()

    def _on_screenshot(self) -> None:
        if hasattr(self.app, '_take_screenshot'):
            self.app._take_screenshot()

    def _on_mainmenu(self) -> None:
        if hasattr(self.app, '_return_to_menu'):
            self.app._return_to_menu()

    # ── 面板管理 ───────────────────────────────────────────

    def show_panel(self, panel_name: str) -> None:
        """显示指定面板，隐藏其他面板。"""
        if self._active_panel == panel_name:
            self.hide_all_panels()
            return

        log.debug("显示面板: %s", panel_name)
        self.hide_all_panels()

        # 创建遮罩
        self._overlay = Rectangle(
            0, 0, self.app.width, self.app.height,
            color=(0, 0, 0, 160),
            batch=self._ui_batch, group=self._overlay_group,
        )
        self._active_panel = panel_name

        # 委托给具体面板
        if panel_name == "settings" and self._settings_panel:
            self._settings_panel.show()
        elif panel_name in ("save", "load") and self._save_load_panel:
            self._save_load_panel.show(panel_name)
        elif panel_name == "history" and self._history_panel:
            self._history_panel.show()

    def hide_all_panels(self) -> None:
        """隐藏所有面板和遮罩。"""
        if self._overlay:
            self._overlay.delete()
            self._overlay = None
        self._active_panel = ""
        if self._settings_panel:
            self._settings_panel.hide()
        if self._save_load_panel:
            self._save_load_panel.hide()
        if self._history_panel:
            self._history_panel.hide()

    def is_any_panel_open(self) -> bool:
        return self._active_panel != ""

    def is_panel_open(self, name: str) -> bool:
        return self._active_panel == name

    # ── 事件转发 ───────────────────────────────────────────

    def on_resize(self, width: int, height: int) -> None:
        """窗口缩放时更新 UI 布局。"""
        if self._nav_bar_bg:
            self._nav_bar_bg.width = width

    def update(self, dt: float) -> None:
        """帧更新。"""
        self._update_nav_bar(dt)
        self.notification.update(dt)

        # 更新面板
        if self._active_panel == "settings" and self._settings_panel:
            self._settings_panel.update(dt)
        elif self._active_panel in ("save", "load") and self._save_load_panel:
            self._save_load_panel.update(dt)
        elif self._active_panel == "history" and self._history_panel:
            self._history_panel.update(dt)

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        """处理 UI 鼠标点击。返回 True 表示已处理。"""
        if button != mouse.LEFT:
            return False

        # 面板打开时，先转发给面板
        if self._active_panel:
            if self._settings_panel and self._active_panel == "settings":
                if self._settings_panel.on_click(x, y):
                    return True
            elif self._save_load_panel and self._active_panel in ("save", "load"):
                if self._save_load_panel.on_click(x, y):
                    return True
            elif self._history_panel and self._active_panel == "history":
                if self._history_panel.on_click(x, y):
                    return True
            # 点击遮罩关闭面板
            self.hide_all_panels()
            return True

        # 导航栏点击检查
        for btn in self._nav_buttons:
            if hit_test(x, y, btn["bounds"]):
                if btn["callback"]:
                    btn["callback"]()
                return True

        return False

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int) -> None:
        """处理鼠标拖拽（转发到面板）。"""
        if self._active_panel == "settings" and self._settings_panel:
            self._settings_panel.on_drag(x, y)

    def on_mouse_release(self, x: int, y: int) -> None:
        """处理鼠标释放（转发到面板）。"""
        if self._active_panel == "settings" and self._settings_panel:
            self._settings_panel.on_mouse_release(x, y)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: float,
                        scroll_y: float) -> bool:
        """处理鼠标滚轮。"""
        if self._active_panel == "history" and self._history_panel:
            self._history_panel.on_scroll(x, y, scroll_x, scroll_y)
            return True
        if self._active_panel == "settings" and self._settings_panel:
            self._settings_panel.on_scroll(x, y, scroll_x, scroll_y)
            return True
        return False

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        """处理键盘事件。返回 True 表示已消费。"""
        return False
