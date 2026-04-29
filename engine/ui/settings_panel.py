"""
设置面板模块
============
5 标签页设置面板，所有控件使用 pyglet 原生 API 实现。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, Optional

# mypy: disable-error-code="func-returns-value"
# setattr 在 lambda 元组表达式中触发的误报，返回值被故意丢弃

if TYPE_CHECKING:
    from ..app import AVGApplication

import pyglet
from pyglet.graphics import Group, Batch
from pyglet.window import key, mouse
from pyglet.shapes import RoundedRectangle, Rectangle, Circle, Box
from pyglet.text import Label

from ..core.constants import FONT_FAMILIES
from .ui_manager import (
    ORDER_PANEL, ORDER_PANEL_BORDER, ORDER_OVERLAY,
    PANEL_BG, PANEL_BORDER, TEXT_NORMAL, TEXT_DIM, TEXT_ACCENT,
    BTN_BG, BTN_HOVER, make_label, hit_test,
)

_PANEL_W = 700
_PANEL_H = 500
_TAB_H = 40
_CONTENT_Y_MARGIN = 60
_RADIUS = 8


# ====================================================================
#  滑块控件
# ====================================================================

class Slider:
    """自定义滑块。"""

    def __init__(self, x: int, y: int, width: int,
                 min_val: float, max_val: float, value: float,
                 label: str, batch: Batch, group: Group,
                 on_change: Optional[Callable[[float], Any]] = None,
                 format_str: str = "{:.0f}%") -> None:
        self._x = x
        self._y = y
        self._width = width
        self._min = min_val
        self._max = max_val
        self._value = value
        self._on_change = on_change
        self._format = format_str
        self._dragging = False

        # 文字标签
        self._label = Label(label, font_name=FONT_FAMILIES, font_size=12,
                            color=TEXT_NORMAL,
                            x=x, y=y + 10, anchor_x="left", anchor_y="bottom",
                            batch=batch, group=group)
        # 数值显示
        self._value_label = Label(self._format_value(value),
                                  font_name=FONT_FAMILIES, font_size=10,
                                  color=TEXT_DIM,
                                  x=x + width, y=y + 10,
                                  anchor_x="right", anchor_y="bottom",
                                  batch=batch, group=group)

        # 轨道
        self._track = Rectangle(x, y - 2, width, 4,
                                color=(80, 80, 80), batch=batch, group=group)

        # 滑块
        thumb_x = self._value_to_x(value)
        self._thumb = Circle(thumb_x, y, 8, color=TEXT_ACCENT[:3],
                             batch=batch, group=group)

    def _format_value(self, val: float) -> str:
        return self._format.format(val)

    def _value_to_x(self, val: float) -> int:
        ratio = (val - self._min) / (self._max - self._min) if self._max > self._min else 0
        return int(self._x + ratio * self._width)

    def _x_to_value(self, x: int) -> float:
        ratio = max(0.0, min(1.0, (x - self._x) / self._width))
        return self._min + ratio * (self._max - self._min)

    def on_mouse_press(self, x: int, y: int) -> bool:
        if abs(x - self._thumb.x) < 20 and abs(y - self._thumb.y) < 20:
            self._dragging = True
            return True
        return False

    def on_mouse_drag(self, x: int, y: int) -> None:
        if self._dragging:
            self._value = max(self._min, min(self._max, self._x_to_value(x)))
            self._update_thumb()

    def on_mouse_release(self) -> None:
        if self._dragging:
            self._dragging = False
            if self._on_change:
                self._on_change(self._value)

    def on_scroll(self, scroll_y: float) -> None:
        step = (self._max - self._min) * 0.05
        self._value = max(self._min, min(self._max, self._value + scroll_y * step))
        self._update_thumb()
        if self._on_change:
            self._on_change(self._value)

    def _update_thumb(self) -> None:
        self._thumb.x = self._value_to_x(self._value)
        self._value_label.text = self._format_value(self._value)

    def set_value(self, value: float) -> None:
        self._value = max(self._min, min(self._max, value))
        self._update_thumb()

    @property
    def value(self) -> float:
        return self._value

    def delete(self) -> None:
        self._label.delete()
        self._value_label.delete()
        self._track.delete()
        self._thumb.delete()


# ====================================================================
#  开关控件
# ====================================================================

class Toggle:
    """自定义开关。"""

    def __init__(self, x: int, y: int, label: str,
                 state: bool, batch: Batch, group: Group,
                 on_change: Optional[Callable[[bool], Any]] = None) -> None:
        self._state = state
        self._on_change = on_change

        self._label = Label(label, font_name=FONT_FAMILIES, font_size=12,
                            color=TEXT_NORMAL,
                            x=x, y=y, anchor_x="left", anchor_y="center",
                            batch=batch, group=group)

        self._bg = Rectangle(x + 200, y - 7, 36, 14,
                             color=(80, 80, 80), batch=batch, group=group)
        self._thumb = Circle(x + 200 + (18 if state else 0), y, 9,
                             color=TEXT_ACCENT[:3], batch=batch, group=group)
        self._toggle_x = x + 200

    def on_click(self, px: int, py: int) -> bool:
        if self._toggle_x - 10 <= px <= self._toggle_x + 46 and \
           self._bg.y - 10 <= py <= self._bg.y + 24:
                self._state = not self._state
                self._thumb.x = self._toggle_x + (18 if self._state else 0)
                self._bg.color = TEXT_ACCENT[:3] if self._state else (80, 80, 80)
                if self._on_change:
                    self._on_change(self._state)
                return True
        return False

    @property
    def state(self) -> bool:
        return self._state

    def delete(self) -> None:
        self._label.delete()
        self._bg.delete()
        self._thumb.delete()


# ====================================================================
#  按钮组控件（独占选择）
# ====================================================================

class ButtonGroup:
    """独占选择按钮组（类似单选按钮）。

    用于窗口模式、背景适配、跳过模式等模式选择。
    点击一个按钮选中它，取消选中其他按钮。
    """

    def __init__(self, x: int, y: int,
                 options: list[str], labels: list[str],
                 current_index: int, batch: Batch, group: Group,
                 callback: Optional[Callable[[int, str], Any]] = None) -> None:
        self._x = x
        self._y = y
        self._options = options
        self._labels = labels
        self._current = current_index
        self._callback = callback
        self._batch = batch
        self._group = group
        self._buttons: list[dict] = []

        btn_w = 90
        btn_h = 30
        spacing = 10

        for i, (opt, lbl) in enumerate(zip(options, labels)):
            bx = x + i * (btn_w + spacing)
            rect = RoundedRectangle(bx, y - btn_h // 2, btn_w, btn_h, 6,
                                    color=TEXT_ACCENT[:3] if i == current_index
                                    else BTN_BG[:3],
                                    batch=batch, group=group)
            label = Label(lbl, font_name=FONT_FAMILIES, font_size=11,
                          color=TEXT_NORMAL,
                          x=bx + btn_w // 2, y=y,
                          anchor_x="center", anchor_y="center",
                          batch=batch, group=group)
            self._buttons.append({
                "rect": rect,
                "label": label,
                "option": opt,
                "bounds": (bx, y - btn_h // 2, btn_w, btn_h),
            })

    def on_click(self, px: int, py: int) -> bool:
        """处理点击。返回 True 表示消费。"""
        for i, btn in enumerate(self._buttons):
            if hit_test(px, py, btn["bounds"]):
                if i != self._current:
                    # 取消旧选中
                    old = self._buttons[self._current]
                    old["rect"].color = BTN_BG[:3]
                    # 高亮新选中
                    btn["rect"].color = TEXT_ACCENT[:3]
                    self._current = i
                    if self._callback:
                        self._callback(i, btn["option"])
                return True
        return False

    def set_current(self, index: int) -> None:
        """编程方式设置当前选中。"""
        if 0 <= index < len(self._buttons) and index != self._current:
            old = self._buttons[self._current]
            old["rect"].color = BTN_BG[:3]
            self._buttons[index]["rect"].color = TEXT_ACCENT[:3]
            self._current = index

    def delete(self) -> None:
        """清理所有按钮资源。"""
        for btn in self._buttons:
            btn["rect"].delete()
            btn["label"].delete()
        self._buttons.clear()


# ====================================================================
#  设置面板
# ====================================================================

TAB_NAMES = ["显示", "音频", "文本", "游戏", "操作"]


class SettingsPanel:
    """5 标签页设置面板。"""

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        self._batch = app.ui_batch
        self._panel_group = Group(order=ORDER_PANEL)
        self._border_group = Group(order=ORDER_PANEL_BORDER)
        self._visible = False
        self._current_tab = 0
        self._tab_buttons: list[dict] = []
        self._controls: list = []
        self._tab_labels: list[Label] = []

        # 面板定位（首次基于默认窗口尺寸，show 时基于实际窗口重新计算）
        self._px = 0
        self._py = 0

        self._build()

    def _build(self) -> None:
        """构建面板框架（标题、标签页、边框）。"""
        pass  # 具体元素在 show() 时创建

    def _build_tabs(self) -> None:
        """创建标签页按钮。"""
        tab_w = _PANEL_W // len(TAB_NAMES)
        for i, name in enumerate(TAB_NAMES):
            x = self._px + i * tab_w
            y = self._py + _PANEL_H - _TAB_H

            rect = Rectangle(x, y, tab_w, _TAB_H,
                            color=PANEL_BG[:3] if i != self._current_tab
                            else TEXT_ACCENT[:3],
                            batch=self._batch, group=self._panel_group)
            lbl = Label(name, font_name=FONT_FAMILIES, font_size=13,
                        color=TEXT_NORMAL,
                        x=x + tab_w // 2, y=y + _TAB_H // 2,
                        anchor_x="center", anchor_y="center",
                        batch=self._batch, group=self._panel_group)
            self._tab_buttons.append({
                "rect": rect,
                "label": lbl,
                "bounds": (x, y, tab_w, _TAB_H),
            })

    def _build_content(self) -> None:
        """根据当前标签页构建内容。"""
        self._clear_content()

        if self._current_tab == 0:
            self._build_display_tab()
        elif self._current_tab == 1:
            self._build_audio_tab()
        elif self._current_tab == 2:
            self._build_text_tab()
        elif self._current_tab == 3:
            self._build_gameplay_tab()
        elif self._current_tab == 4:
            self._build_controls_tab()

    def _clear_content(self) -> None:
        """清除当前内容控件。"""
        for ctrl in self._controls:
            ctrl.delete()
        self._controls.clear()

    # ── 标签页构建（全部带当场生效回调） ─────────────────

    def _build_display_tab(self) -> None:
        app = self.app
        cfg = app.game_config.display
        bgm = app.background_manager
        cy = self._py + _PANEL_H - _TAB_H - 40

        # 窗口模式
        make_label("窗口模式：", self._px + 30, cy, 12, TEXT_NORMAL,
                   batch=self._batch, group=self._panel_group)
        modes = ["windowed", "borderless", "fullscreen"]
        mode_labels = ["窗口化", "无边框", "全屏"]
        current = modes.index(cfg.window_mode) if cfg.window_mode in modes else 0
        group = ButtonGroup(self._px + 120, cy, modes, mode_labels, current,
                            self._batch, self._panel_group,
                            callback=lambda i, v: (
                                setattr(cfg, 'window_mode', v),
                                app.set_window_mode(v) if hasattr(app, 'set_window_mode') else None))
        self._controls.append(group)
        cy -= 50

        # 背景适配模式
        make_label("背景模式：", self._px + 30, cy, 12, TEXT_NORMAL,
                   batch=self._batch, group=self._panel_group)
        fit_modes = ["cover", "fit", "stretch", "original"]
        fit_labels = ["覆盖", "适配", "拉伸", "原图"]
        current_fit = fit_modes.index(cfg.bg_fit_mode) if cfg.bg_fit_mode in fit_modes else 0
        group2 = ButtonGroup(self._px + 120, cy, fit_modes, fit_labels, current_fit,
                             self._batch, self._panel_group,
                             callback=lambda i, v: (
                                 setattr(cfg, 'bg_fit_mode', v),
                                 bgm.set_fit_mode(v)))
        self._controls.append(group2)
        cy -= 40

        # UI 缩放
        slider = Slider(self._px + 30, cy - 20, 200,
                        0.5, 2.0, cfg.ui_scale,
                        "UI 缩放", self._batch, self._panel_group,
                        format_str="{:.1f}x",
                        on_change=lambda v: setattr(cfg, 'ui_scale', v))
        self._controls.append(slider)
        cy -= 40

        # 显示 FPS
        toggle = Toggle(self._px + 30, cy, "显示 FPS",
                        cfg.show_fps, self._batch, self._panel_group,
                        on_change=lambda s: (
                            setattr(cfg, 'show_fps', s),
                            setattr(app, '_show_fps', s)))
        self._controls.append(toggle)

    # ── 音频标签页 ─────────────────────────────────────────

    def _build_audio_tab(self) -> None:
        app = self.app
        cfg = app.game_config.audio
        ae = app.audio_engine
        cy = self._py + _PANEL_H - _TAB_H - 60

        gc = app.game_config
        volumes = [
            ("主音量", cfg.master_volume, 0.0, 1.0,
             lambda v: (setattr(cfg, 'master_volume', v),
                        setattr(ae, 'bgm_volume', gc.effective_bgm_volume),
                        setattr(ae, 'sfx_volume', gc.effective_sfx_volume),
                        setattr(ae, 'voice_volume', gc.effective_voice_volume))),
            ("BGM", cfg.bgm_volume, 0.0, 1.0,
             lambda v: (setattr(cfg, 'bgm_volume', v),
                        setattr(ae, 'bgm_volume', gc.effective_bgm_volume))),
            ("音效", cfg.sfx_volume, 0.0, 1.0,
             lambda v: (setattr(cfg, 'sfx_volume', v),
                        setattr(ae, 'sfx_volume', gc.effective_sfx_volume))),
            ("语音", cfg.voice_volume, 0.0, 1.0,
             lambda v: (setattr(cfg, 'voice_volume', v),
                        setattr(ae, 'voice_volume', gc.effective_voice_volume))),
        ]
        for name, val, vmin, vmax, cb in volumes:
            slider = Slider(self._px + 80, cy, 300, vmin, vmax, val,
                            name, self._batch, self._panel_group,
                            format_str="{:.0f}%",
                            on_change=cb)
            self._controls.append(slider)
            cy -= 60

    # ── 文本标签页 ─────────────────────────────────────────

    def _build_text_tab(self) -> None:
        app = self.app
        cfg = app.game_config.text
        cy = self._py + _PANEL_H - _TAB_H - 60

        # 文本速度
        speed_slider = Slider(self._px + 80, cy, 300, 0.01, 0.2, cfg.text_speed,
                              "文本速度", self._batch, self._panel_group,
                              format_str="{:.2f}s",
                              on_change=lambda v: (
                                  setattr(cfg, 'text_speed', v),
                                  setattr(app.dialogue_system, '_char_interval', v)))
        self._controls.append(speed_slider)
        cy -= 60

        # 自动速度
        auto_slider = Slider(self._px + 80, cy, 300, 1.0, 10.0, cfg.auto_speed,
                             "自动速度", self._batch, self._panel_group,
                             format_str="{:.0f}s",
                             on_change=lambda v: setattr(cfg, 'auto_speed', v))
        self._controls.append(auto_slider)
        cy -= 60

        # 跳过模式
        skip_modes = ["read", "all", "off"]
        skip_labels = ["已读跳过", "全部跳过", "不跳过"]
        current_skip = skip_modes.index(cfg.skip_mode) if cfg.skip_mode in skip_modes else 0
        make_label("跳过模式：", self._px + 30, cy, 12, TEXT_NORMAL,
                   batch=self._batch, group=self._panel_group)
        group3 = ButtonGroup(self._px + 120, cy, skip_modes, skip_labels, current_skip,
                             self._batch, self._panel_group,
                             callback=lambda i, v: setattr(cfg, 'skip_mode', v))
        self._controls.append(group3)

    # ── 游戏性标签页 ───────────────────────────────────────

    def _build_gameplay_tab(self) -> None:
        cfg = self.app.game_config.gameplay
        cy = self._py + _PANEL_H - _TAB_H - 50
        toggles = [
            ("对话回溯", cfg.text_backtrack,
             lambda s: setattr(cfg, 'text_backtrack', s)),
        ]
        for name, state, cb in toggles:
            toggle = Toggle(self._px + 50, cy, name, state,
                            self._batch, self._panel_group,
                            on_change=cb)
            self._controls.append(toggle)
            cy -= 50

    # ── 操作说明标签页 ─────────────────────────────────────

    def _build_controls_tab(self) -> None:
        cy = self._py + _PANEL_H - _TAB_H - 40
        shortcuts = [
            ("空格 / 回车", "推进对话"),
            ("ESC", "打开/关闭设置"),
            ("F5", "快速保存"),
            ("F9", "快速读取"),
            ("Ctrl + S", "打开存档"),
            ("Ctrl + L", "打开读档"),
            ("H", "历史记录"),
            ("A", "切换自动播放"),
            ("按住 Ctrl", "快进文本"),
            ("F11", "全屏切换"),
        ]
        for key_, desc in shortcuts:
            make_label(key_, self._px + 50, cy, 11, TEXT_ACCENT,
                       batch=self._batch, group=self._panel_group)
            make_label(desc, self._px + 280, cy, 11, TEXT_NORMAL,
                       batch=self._batch, group=self._panel_group)
            cy -= 30

    # ── 公共接口 ───────────────────────────────────────────

    def show(self) -> None:
        """显示设置面板。"""
        self._visible = True
        self._px = (self.app.width - _PANEL_W) // 2
        self._py = (self.app.height - _PANEL_H) // 2

        # 面板背景
        self._panel_bg = RoundedRectangle(
            self._px, self._py, _PANEL_W, _PANEL_H, _RADIUS,
            color=PANEL_BG[:3], batch=self._batch, group=self._panel_group)
        # 面板边框
        self._panel_border = Box(
            self._px, self._py, _PANEL_W, _PANEL_H, 1,
            color=PANEL_BORDER[:3], batch=self._batch, group=self._border_group)

        self._build_tabs()
        self._build_content()

    def hide(self) -> None:
        """隐藏设置面板。"""
        if hasattr(self, '_panel_bg'):
            self._panel_bg.delete()
            del self._panel_bg
        if hasattr(self, '_panel_border'):
            self._panel_border.delete()
            del self._panel_border

        self._clear_content()
        for tb in self._tab_buttons:
            tb["rect"].delete()
            tb["label"].delete()
        self._tab_buttons.clear()
        self._visible = False

    def update(self, dt: float) -> None:
        pass

    def on_click(self, x: int, y: int) -> bool:
        """处理点击。返回 True 表示消费。"""
        # 标签页点击
        for i, tb in enumerate(self._tab_buttons):
            if hit_test(x, y, tb["bounds"]):
                if i != self._current_tab:
                    self._current_tab = i
                    self._build_content()
                    # 更新标签页颜色
                    for j, tb2 in enumerate(self._tab_buttons):
                        tb2["rect"].color = TEXT_ACCENT[:3] if j == i else PANEL_BG[:3]
                return True

        # 控件点击
        for ctrl in self._controls:
            if isinstance(ctrl, Slider):
                if ctrl.on_mouse_press(x, y):
                    return True
            elif isinstance(ctrl, Toggle):
                if ctrl.on_click(x, y):
                    return True
            elif isinstance(ctrl, ButtonGroup):
                if ctrl.on_click(x, y):
                    return True

        # 检查点击是否在面板区域内
        if not (self._px <= x <= self._px + _PANEL_W and
                self._py <= y <= self._py + _PANEL_H):
            return False  # 外部点击，让 UIManager 关闭面板

        return True  # 点击在面板内但不处理，阻止关闭

    def on_drag(self, x: int, y: int) -> None:
        """处理鼠标拖拽（用于滑块）。"""
        for ctrl in self._controls:
            if isinstance(ctrl, Slider):
                ctrl.on_mouse_drag(x, y)

    def on_mouse_release(self, x: int, y: int) -> None:
        """处理鼠标释放。"""
        for ctrl in self._controls:
            if isinstance(ctrl, Slider):
                ctrl.on_mouse_release()

    def on_scroll(self, x: int, y: int, scroll_x: float,
                  scroll_y: float) -> bool:
        for ctrl in self._controls:
            if isinstance(ctrl, Slider):
                ctrl.on_scroll(scroll_y)
        return True
