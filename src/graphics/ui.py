"""
UI Module — 对话框 / 选项菜单 / 对话回看 / 设置面板
====================================================
所有 UI 元素使用 pyglet 基础图形（Rectangle + Label），
通过依赖注入获取 Batch、Group、EventBus 等资源。

百分比定位 + 状态机驱动，交互逻辑与绘制分离，便于测试。

用法::

    from graphics.ui import UIManager

    ui = UIManager(
        batch=layers.batch,
        ui_group=layers.get_group(Layer.UI),
        width=config.width,
        height=config.height,
        event_bus=game.events,
        audio_manager=game.audio,
        window=window,
    )
    game.register("ui_manager", ui)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable

import pyglet.graphics
import pyglet.shapes
import pyglet.text
import pyglet.window
from pyglet.graphics import Batch, Group

from core.events import Event, EventBus

logger = logging.getLogger(__name__)


# ── 百分比定位 ────────────────────────────────────────────────


def pct_x(percent: float, width: int) -> int:
    """将百分比宽度转换为像素 X 坐标。"""
    return int(width * percent / 100.0)


def pct_y(percent: float, height: int) -> int:
    """将百分比高度转换为像素 Y 坐标。"""
    return int(height * percent / 100.0)


# ── UIElement ABC ─────────────────────────────────────────────


class UIElement(ABC):
    """UI 元素抽象基类。

    所有 UI 组件遵循 show/hide/update/draw 生命周期。
    Batch 中的对象由 pyglet 自动绘制，draw() 通常为空。
    """

    def __init__(self) -> None:
        self._visible = False

    @property
    def visible(self) -> bool:
        return self._visible

    @abstractmethod
    def show(self) -> None: ...

    @abstractmethod
    def hide(self) -> None: ...

    @abstractmethod
    def update(self, dt: float) -> None: ...

    @abstractmethod
    def draw(self) -> None: ...


# ── DialogBox ─────────────────────────────────────────────────


class DialogBox(UIElement):
    """底部对话框 — 打字机效果 + 点击继续。

    职责：
    - 显示说话人姓名和逐字符出现的文本
    - 打字完成时闪烁点击指示器
    - 点击：未完成→立即完成，已完成→emit DIALOGUE_NEXT
    - 自动保存对话历史（供 BacklogViewer 回看）
    """

    def __init__(
        self,
        batch: Batch,
        ui_group: Group,
        width: int,
        height: int,
        font_name: str | None = None,
        font_size: int = 22,
        chars_per_second: float = 60.0,
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__()
        self._batch = batch
        self._group = ui_group
        self._width = width
        self._height = height
        self._font_name = font_name
        self._font_size = font_size
        self._chars_per_second = chars_per_second
        self._event_bus = event_bus

        # pyglet 对象（hide 时 delete，show_text 时重建）
        self._box: pyglet.shapes.Rectangle | None = None
        self._name_label: pyglet.text.Label | None = None
        self._text_label: pyglet.text.Label | None = None
        self._indicator: pyglet.text.Label | None = None

        # 打字机状态
        self._current_speaker: str = ""
        self._full_text: str = ""
        self._visible_chars: int = 0
        self._finished: bool = False
        self._indicator_visible: bool = False
        self._indicator_timer: float = 0.0

        # 对话历史
        self._history: list[dict[str, str]] = []

    # ── 公开方法 ──────────────────────────────────────────

    def show_text(self, name: str, text: str, voice: str | None = None) -> None:
        """显示新对话。若已有未保存文本，先保存到历史。

        Args:
            name: 说话人姓名（空字符串表示旁白）。
            text: 对话文本。
            voice: 语音文件名（保留参数，当前不播放）。
        """
        # 保存上一条到历史
        if self._full_text:
            self._history.append({
                "speaker": self._current_speaker,
                "text": self._full_text,
            })

        self._current_speaker = name
        self._full_text = text
        self._visible_chars = 0
        self._finished = False
        self._indicator_timer = 0.0
        self._indicator_visible = False

        self._visible = True
        self._ensure_objects()
        if self._name_label:
            self._name_label.text = name if name else ""
        if self._text_label:
            self._text_label.text = ""
        if self._indicator:
            self._indicator.text = ""

    def update(self, dt: float) -> None:
        """每帧推进打字机或闪烁指示器。"""
        if not self._visible:
            return

        if self._finished:
            self._indicator_timer += dt
            if self._indicator_timer >= 0.5:
                self._indicator_timer -= 0.5
                self._indicator_visible = not self._indicator_visible
                if self._indicator:
                    self._indicator.text = "▼" if self._indicator_visible else ""
        else:
            self._visible_chars += int(dt * self._chars_per_second)
            if self._visible_chars >= len(self._full_text):
                self._visible_chars = len(self._full_text)
                self._finished = True
                if self._indicator:
                    self._indicator_visible = True
                    self._indicator.text = "▼"
                if self._event_bus:
                    self._event_bus.emit(Event.DIALOGUE_COMPLETE)
            if self._text_label:
                self._text_label.text = self._full_text[:self._visible_chars]

    def is_finished(self) -> bool:
        """打字机是否已完成全部文本显示。"""
        return self._finished

    def finish(self) -> None:
        """立即显示完整文本，跳过打字机动画。"""
        self._visible_chars = len(self._full_text)
        self._finished = True
        if self._text_label:
            self._text_label.text = self._full_text
        if self._indicator:
            self._indicator_visible = True
            self._indicator.text = "▼"

    def handle_click(self, x: float, y: float) -> None:
        """处理点击事件。

        - 打字未完成 → 立即完成
        - 已完成 → emit DIALOGUE_NEXT，脚本系统继续
        """
        if not self._finished:
            self.finish()
        elif self._event_bus:
            self._event_bus.emit(Event.DIALOGUE_NEXT)

    def get_history(self) -> list[dict[str, str]]:
        """返回对话历史副本（供 BacklogViewer 使用）。"""
        return list(self._history)

    def set_speed(self, chars_per_second: float) -> None:
        """动态调整打字速度。"""
        self._chars_per_second = chars_per_second

    def show(self) -> None:
        """显示对话框（无操作 —— 由 show_text 控制可见性）。"""
        self._visible = True
        self._ensure_objects()

    def hide(self) -> None:
        """隐藏对话框并清理 pyglet 对象。"""
        # 保存当前文本到历史（防止切换场景时丢失）
        if self._full_text and not self._finished:
            self._history.append({
                "speaker": self._current_speaker,
                "text": self._full_text,
            })
        self._visible = False
        self._delete_objects()

    def draw(self) -> None:
        """空 —— Batch 自动绘制。"""

    # ── 内部 ──────────────────────────────────────────────

    def _ensure_objects(self) -> None:
        """确保 pyglet 对象存在（幂等）。"""
        bw = pct_x(90, self._width)
        bh = pct_y(23, self._height)
        bx = pct_x(5, self._width)
        by = pct_y(3, self._height)

        if self._box is None:
            self._box = pyglet.shapes.Rectangle(
                x=bx, y=by, width=bw, height=bh,
                color=(20, 20, 40), batch=self._batch, group=self._group,
            )
            self._box.opacity = 220

        nx = pct_x(8, self._width)
        ny = by + bh - pct_y(4, self._height)
        if self._name_label is None:
            self._name_label = pyglet.text.Label(
                "", font_name=self._font_name, font_size=self._font_size,
                x=nx, y=ny, color=(180, 200, 255, 255),
                batch=self._batch, group=self._group,
            )

        tx = pct_x(10, self._width)
        ty = by + pct_y(10, self._height)
        if self._text_label is None:
            self._text_label = pyglet.text.Label(
                "", font_name=self._font_name, font_size=self._font_size,
                x=tx, y=ty, color=(255, 255, 255, 255),
                width=bw - pct_x(10, self._width),
                batch=self._batch, group=self._group,
            )

        ix = bx + bw - pct_x(3, self._width)
        iy = by + pct_y(1, self._height)
        if self._indicator is None:
            self._indicator = pyglet.text.Label(
                "", font_name=self._font_name, font_size=16,
                x=ix, y=iy, color=(255, 255, 255, 255),
                anchor_x="right",
                batch=self._batch, group=self._group,
            )

    def _delete_objects(self) -> None:
        """删除所有 pyglet 对象。"""
        for obj in (self._box, self._name_label, self._text_label, self._indicator):
            if obj is not None:
                obj.delete()
        self._box = None
        self._name_label = None
        self._text_label = None
        self._indicator = None


# ── ChoiceMenu ────────────────────────────────────────────────


class ChoiceMenu(UIElement):
    """选项菜单 — 垂直按钮列表，键盘 + 鼠标交互。

    选中某一项时通过 event_bus 发出 ``"choice_selected"`` 事件，
    携带 ``index`` 参数，脚本系统监听此事件跳转到对应分支。
    """

    # 颜色常量
    _COLOR_NORMAL = (60, 60, 80)
    _COLOR_HOVER = (100, 120, 180)
    _COLOR_SELECTED = (80, 140, 200)
    _ALPHA_NORMAL = 200
    _ALPHA_HIGHLIGHT = 220

    def __init__(
        self,
        batch: Batch,
        ui_group: Group,
        width: int,
        height: int,
        font_name: str | None = None,
        font_size: int = 22,
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__()
        self._batch = batch
        self._group = ui_group
        self._width = width
        self._height = height
        self._font_name = font_name
        self._font_size = font_size
        self._event_bus = event_bus

        self._choices: list[tuple[str, Any]] = []
        self._selected_index: int = 0
        self._hover_index: int = -1
        self._buttons: list[tuple[pyglet.shapes.Rectangle, pyglet.text.Label]] = []

    # ── 公开方法 ──────────────────────────────────────────

    def show(self, choices: list[tuple[str, Any]] | None = None) -> None:
        """显示选项菜单。

        Args:
            choices: 选项列表 [(显示文本, tag), ...]。若为 None 则使用上次的。
        """
        if choices is not None:
            self._choices = choices
        self._selected_index = -1
        self._hover_index = -1
        self._visible = True
        self._build_buttons()

    def hide(self) -> None:
        """隐藏并清理按钮。"""
        self._visible = False
        self._delete_buttons()

    def update(self, dt: float) -> None:
        """更新按钮高亮状态。"""
        if not self._visible:
            return
        for i, (rect, _label) in enumerate(self._buttons):
            if i == self._selected_index or i == self._hover_index:
                if i == self._selected_index and i == self._hover_index:
                    rect.color = self._COLOR_SELECTED
                elif i == self._selected_index:
                    rect.color = self._COLOR_SELECTED
                else:
                    rect.color = self._COLOR_HOVER
                rect.opacity = self._ALPHA_HIGHLIGHT
            else:
                rect.color = self._COLOR_NORMAL
                rect.opacity = self._ALPHA_NORMAL

    def handle_key(self, direction: int) -> None:
        """键盘上下选择。

        Args:
            direction: -1 为上，1 为下。
        """
        if not self._choices:
            return
        self._selected_index = max(
            0, min(len(self._choices) - 1, self._selected_index + direction)
        )

    def handle_click(self, x: float, y: float) -> None:
        """鼠标点击 —— 命中选项则选中并发出事件。"""
        for i, (rect, _label) in enumerate(self._buttons):
            if (
                rect.x <= x <= rect.x + rect.width
                and rect.y <= y <= rect.y + rect.height
            ):
                self._on_selected(i)
                return

    def handle_mouse_motion(self, x: float, y: float) -> None:
        """鼠标移动 —— 更新悬停索引。"""
        self._hover_index = -1
        self._selected_index = -1
        for i, (rect, _label) in enumerate(self._buttons):
            if (
                rect.x <= x <= rect.x + rect.width
                and rect.y <= y <= rect.y + rect.height
            ):
                self._hover_index = i
                return

    def draw(self) -> None:
        """空 —— Batch 自动绘制。"""

    # ── 内部 ──────────────────────────────────────────────

    def _on_selected(self, index: int) -> None:
        """选中某个选项：隐藏菜单，发出事件。"""
        tag = self._choices[index][1]
        self.hide()
        if self._event_bus:
            self._event_bus.emit("choice_selected", index=index, tag=tag)

    def _build_buttons(self) -> None:
        """根据 _choices 创建所有按钮矩形 + 标签。"""
        self._delete_buttons()

        n = len(self._choices)
        if n == 0:
            return

        btn_w = pct_x(50, self._width)
        btn_h = 48
        spacing = 8
        total_h = n * btn_h + (n - 1) * spacing
        start_y = (self._height // 2) + (total_h // 2) - btn_h
        start_x = (self._width - btn_w) // 2

        for i, (text, _tag) in enumerate(self._choices):
            by = start_y - i * (btn_h + spacing)
            rect = pyglet.shapes.Rectangle(
                x=start_x, y=by, width=btn_w, height=btn_h,
                color=self._COLOR_NORMAL if i != 0 else self._COLOR_SELECTED,
                batch=self._batch, group=self._group,
            )
            rect.opacity = self._ALPHA_HIGHLIGHT if i == 0 else self._ALPHA_NORMAL

            label = pyglet.text.Label(
                text, font_name=self._font_name, font_size=self._font_size,
                x=start_x + btn_w // 2, y=by + btn_h // 2,
                color=(255, 255, 255, 255),
                anchor_x="center", anchor_y="center",
                batch=self._batch, group=self._group,
            )
            self._buttons.append((rect, label))

    def _delete_buttons(self) -> None:
        """删除所有按钮对象。"""
        for rect, label in self._buttons:
            rect.delete()
            label.delete()
        self._buttons.clear()


# ── BacklogViewer ─────────────────────────────────────────────


class BacklogViewer(UIElement):
    """对话回看 — 全屏半透明遮罩 + 滚动历史记录。

    - 鼠标滚轮上下滚动
    - 点击遮罩空白区域关闭
    - 点击内容区域不关闭（防止误触）
    """

    def __init__(
        self,
        batch: Batch,
        ui_group: Group,
        width: int,
        height: int,
        font_name: str | None = None,
        font_size: int = 18,
    ) -> None:
        super().__init__()
        self._batch = batch
        self._group = ui_group
        self._width = width
        self._height = height
        self._font_name = font_name
        self._font_size = font_size

        self._overlay: pyglet.shapes.Rectangle | None = None
        self._entry_labels: list[pyglet.text.Label] = []
        self._entries: list[dict[str, str]] = []
        self._scroll_offset: float = 0.0
        self._max_scroll: float = 0.0

        # 内容区域（用于判断点击是否在内容区）
        self._content_left = pct_x(10, width)
        self._content_right = pct_x(90, width)
        self._content_top = pct_y(90, height)
        self._content_bottom = pct_y(10, height)

    # ── 公开方法 ──────────────────────────────────────────

    def show(self, history: list[dict[str, str]] | None = None) -> None:
        """显示回看界面。

        Args:
            history: 对话历史列表。若为 None 则使用上次的。
        """
        if history is not None:
            self._entries = history
        self._scroll_offset = 0.0
        self._visible = True
        self._ensure_overlay()
        self._rebuild_labels()

    def hide(self) -> None:
        """关闭回看。"""
        self._visible = False
        self._delete_overlay()
        self._delete_labels()

    def update(self, dt: float) -> None:
        """更新标签位置（滚动时）。"""
        if not self._visible:
            return
        self._apply_scroll()

    def handle_scroll(self, dy: float) -> None:
        """鼠标滚轮滚动。

        Args:
            dy: 滚动方向（正=向上，负=向下）。
        """
        self._scroll_offset = max(
            0.0, min(self._max_scroll, self._scroll_offset + dy * 40)
        )

    def handle_click(self, x: float, y: float) -> bool:
        """点击处理。

        Returns:
            True: 点击在内容区外，已关闭回看。
            False: 点击在内容区内，不关闭。
        """
        if (
            self._content_left <= x <= self._content_right
            and self._content_bottom <= y <= self._content_top
        ):
            return False
        self.hide()
        return True

    def draw(self) -> None:
        """绘制遮罩（overlay 不在 Batch 中，需手动绘制）。"""
        if self._overlay is not None and self._visible:
            self._overlay.draw()

    # ── 内部 ──────────────────────────────────────────────

    def _ensure_overlay(self) -> None:
        if self._overlay is not None:
            return
        self._overlay = pyglet.shapes.Rectangle(
            x=0, y=0, width=self._width, height=self._height,
            color=(0, 0, 0),
        )
        self._overlay.opacity = 180

    def _delete_overlay(self) -> None:
        if self._overlay is not None:
            self._overlay.delete()
            self._overlay = None

    def _rebuild_labels(self) -> None:
        self._delete_labels()

        line_h = self._font_size + 12
        # 内容区域从 content_top 向下排列
        y = self._content_top - line_h

        for entry in self._entries:
            speaker = entry.get("speaker", "")
            text = entry.get("text", "")

            # 说话人标签
            name_label = pyglet.text.Label(
                speaker, font_name=self._font_name, font_size=self._font_size,
                x=self._content_left, y=y,
                color=(180, 200, 255, 255),
                batch=self._batch, group=self._group,
            )
            self._entry_labels.append(name_label)

            # 对话文本标签
            text_x = self._content_left + pct_x(15, self._width)
            text_label = pyglet.text.Label(
                text, font_name=self._font_name, font_size=self._font_size,
                x=text_x, y=y,
                color=(255, 255, 255, 255),
                width=self._content_right - text_x,
                batch=self._batch, group=self._group,
            )
            self._entry_labels.append(text_label)

            y -= line_h

        # 计算可滚动范围
        total_lines = len(self._entry_labels) // 2  # 每条对话有 2 个标签
        total_height = max(0, total_lines * line_h)
        visible_height = self._content_top - self._content_bottom
        self._max_scroll = max(0.0, total_height - visible_height)

    def _apply_scroll(self) -> None:
        """将滚动偏移应用到所有标签。"""
        line_h = self._font_size + 12
        y_base = self._content_top - line_h + self._scroll_offset
        for i, label in enumerate(self._entry_labels):
            entry_idx = i // 2
            label.y = y_base - entry_idx * line_h

    def _delete_labels(self) -> None:
        for label in self._entry_labels:
            label.delete()
        self._entry_labels.clear()


# ── SettingsPanel ─────────────────────────────────────────────


class _Slider:
    """音量 / 速度滑块的内部状态 + pyglet 对象。"""

    __slots__ = (
        "name", "bar", "handle", "label", "value_label",
        "min_val", "max_val", "current", "on_change",
    )

    def __init__(
        self,
        name: str,
        bar: pyglet.shapes.Rectangle,
        handle: pyglet.shapes.Rectangle,
        label: pyglet.text.Label,
        value_label: pyglet.text.Label,
        min_val: float,
        max_val: float,
        current: float,
        on_change: Callable[[float], None],
    ) -> None:
        self.name = name
        self.bar = bar
        self.handle = handle
        self.label = label
        self.value_label = value_label
        self.min_val = min_val
        self.max_val = max_val
        self.current = current
        self.on_change = on_change

    def set_value(self, value: float) -> None:
        self.current = max(self.min_val, min(self.max_val, value))
        self._update_handle()
        self._update_label()
        self.on_change(self.current)

    def set_value_from_x(self, x: float) -> None:
        """根据 x 坐标设置值（拖动时使用，不做范围判断）。"""
        if self.bar.width <= 0:
            return
        t = (x - self.bar.x) / self.bar.width
        self.current = self.min_val + t * (self.max_val - self.min_val)
        self.current = max(self.min_val, min(self.max_val, self.current))
        self._update_handle()
        self._update_label()
        self.on_change(self.current)

    def hit_handle(self, x: float, y: float) -> bool:
        return (
            self.handle.x <= x <= self.handle.x + self.handle.width
            and self.handle.y <= y <= self.handle.y + self.handle.height
        )

    def hit_bar(self, x: float, y: float) -> bool:
        return (
            self.bar.x <= x <= self.bar.x + self.bar.width
            and self.bar.y - 10 <= y <= self.bar.y + self.bar.height + 10
        )

    def delete(self) -> None:
        for obj in (self.bar, self.handle, self.label, self.value_label):
            obj.delete()

    def _update_handle(self) -> None:
        if self.max_val == self.min_val:
            return
        t = (self.current - self.min_val) / (self.max_val - self.min_val)
        self.handle.x = int(self.bar.x + t * self.bar.width - self.handle.width / 2)

    def _update_label(self) -> None:
        if self.max_val <= 1.0:
            self.value_label.text = f"{int(self.current * 100)}%"
        else:
            self.value_label.text = f"{int(self.current)}"


class SettingsPanel(UIElement):
    """设置面板 — 4 个滑块 + 全屏切换按钮。

    模态面板，显示时阻塞其他 UI。构造时注入 AudioManager 和 Window
    以实时调整音量和全屏。
    """

    _PANEL_COLOR = (30, 30, 50)
    _PANEL_ALPHA = 230
    _BUTTON_COLOR = (60, 60, 80)
    _BUTTON_ALPHA = 200

    def __init__(
        self,
        batch: Batch,
        ui_group: Group,
        width: int,
        height: int,
        font_name: str | None = None,
        font_size: int = 20,
        audio_manager: Any = None,
        window: Any = None,
    ) -> None:
        super().__init__()
        self._batch = batch
        self._group = ui_group
        self._width = width
        self._height = height
        self._font_name = font_name
        self._font_size = font_size
        self._audio = audio_manager
        self._window = window

        self._panel_bg: pyglet.shapes.Rectangle | None = None
        self._title_label: pyglet.text.Label | None = None
        self._sliders: dict[str, _Slider] = {}
        self._dragging_slider: str | None = None

        self._fullscreen_btn_rect: pyglet.shapes.Rectangle | None = None
        self._fullscreen_btn_label: pyglet.text.Label | None = None

        # 文本速度回调（由 UIManager 注入）
        self._on_text_speed_change: Callable[[float], None] | None = None
        self._on_overlay_change: Callable[[float], None] | None = None
        self._on_hide_callback: Callable[[], None] | None = None

    def set_text_speed_callback(self, cb: Callable[[float], None]) -> None:
        self._on_text_speed_change = cb

    def set_overlay_callback(self, cb: Callable[[float], None]) -> None:
        """注册回调：设置面板 → 更新菜单遮罩透明度。"""
        self._on_overlay_change = cb

    def set_on_hide_callback(self, cb: Callable[[], None]) -> None:
        """注册回调：面板关闭时回调，用于 re-show 主菜单。"""
        self._on_hide_callback = cb

    # ── 公开方法 ──────────────────────────────────────────

    def show(self) -> None:
        """显示设置面板并创建所有 UI 对象。"""
        self._visible = True
        self._ensure_objects()

    def hide(self) -> None:
        """隐藏设置面板。"""
        self._visible = False
        self._dragging_slider = None
        self._delete_objects()
        if self._on_hide_callback is not None:
            self._on_hide_callback()

    def update(self, dt: float) -> None:
        """空 —— 设置面板是纯交互驱动。"""

    def handle_click(self, x: float, y: float) -> bool:
        """处理点击：全屏按钮 / 滑块 / 滑轨 / 面板外关闭。

        Returns:
            True 表示事件已消费。
        """
        # 1. 全屏按钮
        if self._fullscreen_btn_rect is not None:
            r = self._fullscreen_btn_rect
            if r.x <= x <= r.x + r.width and r.y <= y <= r.y + r.height:
                self._toggle_fullscreen()
                return True

        # 2. 滑块拖动柄
        for name, slider in self._sliders.items():
            if slider.hit_handle(x, y):
                self._dragging_slider = name
                return True

        # 3. 滑轨点击（跳到对应位置）
        for name, slider in self._sliders.items():
            if slider.hit_bar(x, y):
                slider.set_value_from_x(x)
                return True

        # 4. 面板外 → 关闭
        if self._panel_bg is not None:
            pb = self._panel_bg
            if not (
                pb.x <= x <= pb.x + pb.width
                and pb.y <= y <= pb.y + pb.height
            ):
                self.hide()
                return True

        return True  # 面板内但未命中任何控件 —— 仍然消费

    def handle_mouse_drag(self, x: float, y: float) -> None:
        """拖动滑块（不做范围判断，松开前持续响应）。"""
        if self._dragging_slider is not None:
            slider = self._sliders.get(self._dragging_slider)
            if slider is not None:
                slider.set_value_from_x(x)

    def handle_mouse_release(self, x: float, y: float) -> None:
        """结束拖动。"""
        self._dragging_slider = None

    def draw(self) -> None:
        """空 —— Batch 自动绘制。"""

    # ── 内部 ──────────────────────────────────────────────

    def _ensure_objects(self) -> None:
        self._delete_objects()

        pw = pct_x(60, self._width)
        ph = pct_y(72, self._height)
        px = (self._width - pw) // 2
        py = (self._height - ph) // 2

        self._panel_bg = pyglet.shapes.Rectangle(
            x=px, y=py, width=pw, height=ph,
            color=self._PANEL_COLOR, batch=self._batch, group=self._group,
        )
        self._panel_bg.opacity = self._PANEL_ALPHA

        self._title_label = pyglet.text.Label(
            "设  置", font_name=self._font_name, font_size=26,
            x=px + pw // 2, y=py + ph - pct_y(5, self._height),
            color=(255, 255, 255, 255),
            anchor_x="center", anchor_y="center",
            batch=self._batch, group=self._group,
        )

        # 滑块
        slider_defs = [
            ("BGM 音量", "bgm", 0.0, 1.0, 0.8,
             lambda v: self._audio.set_volume("bgm", v) if self._audio else None),
            ("语音音量", "voice", 0.0, 1.0, 1.0,
             lambda v: self._audio.set_volume("voice", v) if self._audio else None),
            ("SE 音量", "se", 0.0, 1.0, 0.6,
             lambda v: self._audio.set_volume("se", v) if self._audio else None),
            ("文本速度", "speed", 10.0, 200.0, 60.0,
             lambda v: self._on_text_speed_change(v) if self._on_text_speed_change else None),
            ("菜单遮罩", "overlay", 0.0, 1.0, 0.55,
             lambda v: self._on_overlay_change(v) if self._on_overlay_change else None),
        ]

        slider_start_y = py + ph - pct_y(15, self._height)
        slider_spacing = pct_y(11, self._height)

        for i, (label_text, key, mn, mx, default, cb) in enumerate(slider_defs):
            # 从 audio_manager 读取当前值（如果有）
            current = default
            if self._audio and hasattr(self._audio, "_volumes") and key in ("bgm", "voice", "se"):
                vol = self._audio._volumes.get(key)
                if vol is not None:
                    current = vol
            elif key == "speed":
                current = default  # 由 DialogBox 提供初始值

            sy = slider_start_y - i * slider_spacing
            self._sliders[key] = self._build_slider(
                label_text, px, sy, pw, mn, mx, current, cb,
            )

        # 全屏按钮
        btn_w = pct_x(20, self._width)
        btn_h = 36
        btn_x = px + (pw - btn_w) // 2
        btn_y = py + pct_y(3, self._height)

        self._fullscreen_btn_rect = pyglet.shapes.Rectangle(
            x=btn_x, y=btn_y, width=btn_w, height=btn_h,
            color=self._BUTTON_COLOR, batch=self._batch, group=self._group,
        )
        self._fullscreen_btn_rect.opacity = self._BUTTON_ALPHA

        fs_text = "全屏: 开" if (self._window and self._window.fullscreen) else "全屏: 关"
        self._fullscreen_btn_label = pyglet.text.Label(
            fs_text, font_name=self._font_name, font_size=self._font_size,
            x=btn_x + btn_w // 2, y=btn_y + btn_h // 2,
            color=(255, 255, 255, 255),
            anchor_x="center", anchor_y="center",
            batch=self._batch, group=self._group,
        )

    def _build_slider(
        self,
        label_text: str,
        px: int, sy: float, pw: int,
        min_val: float, max_val: float, current: float,
        on_change: Callable[[float], None],
    ) -> _Slider:
        """构建一个滑块（bar + handle + label + value_label）。"""
        label_x = px + pct_x(5, pw)
        bar_x = px + pct_x(28, pw)
        bar_w = int(pw * 0.45)
        bar_h = 8
        handle_w = 16
        handle_h = 24

        lbl = pyglet.text.Label(
            label_text, font_name=self._font_name, font_size=self._font_size,
            x=label_x, y=sy + bar_h // 2,
            color=(220, 220, 220, 255),
            anchor_y="center",
            batch=self._batch, group=self._group,
        )

        bar = pyglet.shapes.Rectangle(
            x=bar_x, y=sy, width=bar_w, height=bar_h,
            color=(80, 80, 100), batch=self._batch, group=self._group,
        )

        t = (current - min_val) / (max_val - min_val)
        handle_x = int(bar_x + t * bar_w - handle_w / 2)
        handle_y = sy + (bar_h - handle_h) // 2
        handle = pyglet.shapes.Rectangle(
            x=handle_x, y=handle_y, width=handle_w, height=handle_h,
            color=(160, 180, 220), batch=self._batch, group=self._group,
        )

        val_x = bar_x + bar_w + pct_x(2, pw)
        val_lbl = pyglet.text.Label(
            "", font_name=self._font_name, font_size=self._font_size,
            x=val_x, y=sy + bar_h // 2,
            color=(200, 200, 200, 255),
            anchor_y="center",
            batch=self._batch, group=self._group,
        )

        slider = _Slider(
            name=label_text, bar=bar, handle=handle,
            label=lbl, value_label=val_lbl,
            min_val=min_val, max_val=max_val, current=current,
            on_change=on_change,
        )
        slider._update_handle()
        slider._update_label()
        return slider

    def _toggle_fullscreen(self) -> None:
        if self._window is not None:
            self._window.set_fullscreen(not self._window.fullscreen)
            if self._fullscreen_btn_label:
                self._fullscreen_btn_label.text = (
                    "全屏: 开" if self._window.fullscreen else "全屏: 关"
                )

    def _delete_objects(self) -> None:
        for slider in self._sliders.values():
            slider.delete()
        self._sliders.clear()
        for obj in (
            self._panel_bg, self._title_label,
            self._fullscreen_btn_rect, self._fullscreen_btn_label,
        ):
            if obj is not None:
                obj.delete()
        self._panel_bg = None
        self._title_label = None
        self._fullscreen_btn_rect = None
        self._fullscreen_btn_label = None


# ── UIManager ─────────────────────────────────────────────────


class UIManager:
    """UI 管理器 — 组装 4 个组件，管理生命周期，路由输入事件。

    事件路由优先级（从高到低）：
    1. Settings 可见 → 只路由到 settings
    2. Backlog 可见 → backlog（点击 / 滚轮），停止传播
    3. Choice 可见 → choice（点击 / 键盘），阻塞 dialog
    4. Dialog 可见 → dialog（点击）
    """

    def __init__(
        self,
        batch: Batch,
        ui_group: Group,
        width: int,
        height: int,
        event_bus: EventBus,
        audio_manager: Any = None,
        window: Any = None,
        font_name: str = "Microsoft YaHei",
    ) -> None:
        self._width = width
        self._height = height
        self._event_bus = event_bus

        # 创建 4 个 UI 组件（显式传入 font_name 以避免 DirectWrite bug）
        self.dialog = DialogBox(
            batch, ui_group, width, height, font_name=font_name, event_bus=event_bus,
        )
        self.choice = ChoiceMenu(
            batch, ui_group, width, height, font_name=font_name, event_bus=event_bus,
        )
        self.backlog = BacklogViewer(
            batch, ui_group, width, height, font_name=font_name,
        )
        self.settings = SettingsPanel(
            batch, ui_group, width, height, font_name=font_name,
            audio_manager=audio_manager, window=window,
        )

        # 文本速度回调：设置面板 → 对话框
        self.settings.set_text_speed_callback(self.dialog.set_speed)

        # 订阅事件总线
        event_bus.on(Event.CLICK, self._on_click)
        event_bus.on(Event.KEY_PRESS, self._on_key)
        event_bus.on("scroll", self._on_scroll)

        # 订阅 draw 事件（用于 backlog overlay）
        event_bus.on(Event.DRAW, self._on_draw)

        logger.info("UIManager 已初始化: %dx%d", width, height)

    # ── 公开方法 ──────────────────────────────────────────

    def update(self, dt: float) -> None:
        """每帧更新所有可见组件。"""
        if self.dialog.visible:
            self.dialog.update(dt)
        if self.choice.visible:
            self.choice.update(dt)
        if self.backlog.visible:
            self.backlog.update(dt)
        # settings 是纯交互驱动，不需要 update

    def handle_mouse_motion(self, x: float, y: float) -> None:
        """鼠标移动（由 GameWindow.on_mouse_motion 直接调用）。"""
        if self.settings.visible:
            return
        if self.choice.visible:
            self.choice.handle_mouse_motion(x, y)

    def handle_mouse_drag(self, x: float, y: float) -> None:
        """鼠标拖动（由 GameWindow.on_mouse_drag 直接调用）。"""
        if self.settings.visible:
            self.settings.handle_mouse_drag(x, y)

    def handle_mouse_release(self, x: float, y: float) -> None:
        """鼠标释放（由 GameWindow.on_mouse_release 直接调用）。"""
        if self.settings.visible:
            self.settings.handle_mouse_release(x, y)

    # ── 事件回调 ──────────────────────────────────────────

    def _on_click(self, **kwargs: Any) -> None:
        x = float(kwargs["x"])
        y = float(kwargs["y"])

        # 1. Settings 优先
        if self.settings.visible:
            self.settings.handle_click(x, y)
            return

        # 2. Backlog 可见时只路由给它，停止传播
        if self.backlog.visible:
            self.backlog.handle_click(x, y)
            return

        # 3. Choice 可见时只路由给它
        if self.choice.visible:
            self.choice.handle_click(x, y)
            return

        # 4. Dialog 可见时路由给它
        if self.dialog.visible:
            self.dialog.handle_click(x, y)

    def _on_key(self, **kwargs: Any) -> None:
        symbol = int(kwargs["symbol"])

        _key = pyglet.window.key

        # ESC 优先 —— 关闭 backlog 或 settings
        if symbol == _key.ESCAPE:
            if self.backlog.visible:
                self.backlog.hide()
                return
            if self.settings.visible:
                self.settings.hide()
                return
            return

        # Backlog: 对话可见时 ↑ 打开回看
        if symbol == _key.UP and self.dialog.visible and not self.backlog.visible:
            self.backlog.show(self.dialog.get_history())
            return

        # ChoiceMenu 键盘导航
        if self.choice.visible:
            if symbol == _key.UP:
                self.choice.handle_key(-1)
            elif symbol == _key.DOWN:
                self.choice.handle_key(1)
            elif symbol in (_key.ENTER, _key.SPACE):
                # 确认当前选项 —— 获取选中项的位置并模拟点击
                if self.choice._buttons:
                    idx = self.choice._selected_index
                    if 0 <= idx < len(self.choice._buttons):
                        rect, _ = self.choice._buttons[idx]
                        cx = rect.x + rect.width / 2
                        cy = rect.y + rect.height / 2
                        self.choice.handle_click(cx, cy)

    def _on_scroll(self, **kwargs: Any) -> None:
        if self.backlog.visible:
            dy = float(kwargs.get("scroll_y", 0))
            self.backlog.handle_scroll(dy)

    def _on_draw(self, **kwargs: Any) -> None:
        """在 LayerManager 的 Batch 绘制之后，绘制 backlog overlay。"""
        if self.backlog.visible:
            self.backlog.draw()
