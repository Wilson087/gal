"""
对话系统模块
============
打字机效果逐字显示、富文本标记解析渲染、对话 UI 管理。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..app import AVGApplication

import pyglet
from pyglet.graphics import Batch, Group
from pyglet.text import Label

from ..core.constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, DIALOGUE_FRAME_HEIGHT,
    DIALOGUE_PADDING, DIALOGUE_MARGIN_BOTTOM,
    COLOR_DIALOGUE_BG, COLOR_TEXT_PRIMARY, COLOR_TEXT_SPEAKER,
    DEFAULT_SPEAKER_COLOR, DEFAULT_NARRATOR_COLOR,
    FONT_FAMILIES, FONT_SIZE_SPEAKER, FONT_SIZE_DIALOGUE, FONT_SIZE_NEXT_INDICATOR,
    DEFAULT_TEXT_SPEED, CHARACTER_NAME_COLORS,
    DIALOGUE_COLOR_KEY,
)
from ..core.rich_text import parse_rich_text, RichSegment
from ..core.logger import Logger

log = Logger("Dialogue")


class DialogueSystem:
    """对话系统：打字机效果、富文本渲染、推进管理。"""

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        self.ui_batch = app.ui_batch
        self._ui_group = Group(order=10)

        # 文本积累状态
        self._typing: bool = False
        self._skip_type: bool = False
        self._typewriter_timer: float = 0.0
        self._char_interval: float = DEFAULT_TEXT_SPEED
        self._speed_mult: float = 1.0
        self._current_color: tuple[int, int, int, int] = COLOR_TEXT_PRIMARY

        # 富文本处理状态
        self._segments: list[RichSegment] = []
        self._seg_index: int = 0
        self._seg_char_pos: int = 0
        self._accumulated_text: str = ""
        self._seg_rgba: tuple[int, int, int, int] = COLOR_TEXT_PRIMARY

        # 暂停状态（{w=N} 标记）
        self._waiting: bool = False
        self._wait_timer: float = 0.0

        # 震动状态
        self._shake_triggered: bool = False

        # 粗体/斜体状态（富文本标记跟踪）
        self._bold_active: bool = False
        self._italic_active: bool = False
        # 缓存上一次设置的样式，避免每字符重复更新 Label
        self._last_color: Optional[tuple[int, int, int, int]] = None
        self._last_weight: str = "normal"
        self._last_italic: bool = False

        self._build_ui()

    def _build_ui(self) -> None:
        """构建对话 UI 组件。"""
        # 对话底栏背景
        fh = DIALOGUE_FRAME_HEIGHT
        self._bg_rect = pyglet.shapes.Rectangle(
            0, 0, WINDOW_WIDTH, fh,
            color=COLOR_DIALOGUE_BG[:3],
            batch=self.ui_batch,
            group=self._ui_group,
        )

        # 说话人标签
        self._speaker_label = Label(
            "", font_name=FONT_FAMILIES, font_size=FONT_SIZE_SPEAKER,
            weight="bold", color=DEFAULT_SPEAKER_COLOR,
            x=DIALOGUE_PADDING, y=fh - DIALOGUE_PADDING - 24,
            anchor_x="left", anchor_y="top",
            batch=self.ui_batch, group=self._ui_group,
        )

        # 对话文本标签（单行多行显示）
        self._text_label = Label(
            "", font_name=FONT_FAMILIES, font_size=FONT_SIZE_DIALOGUE,
            color=COLOR_TEXT_PRIMARY,
            x=DIALOGUE_PADDING, y=fh - DIALOGUE_PADDING - 24 - 28,
            width=WINDOW_WIDTH - DIALOGUE_PADDING * 2,
            anchor_x="left", anchor_y="top",
            multiline=True,
            batch=self.ui_batch, group=self._ui_group,
        )

        # 推进指示器
        self._next_label = Label(
            "▼", font_name=FONT_FAMILIES, font_size=FONT_SIZE_NEXT_INDICATOR,
            color=COLOR_TEXT_PRIMARY,
            x=WINDOW_WIDTH - DIALOGUE_PADDING, y=DIALOGUE_PADDING,
            anchor_x="right", anchor_y="bottom",
            batch=self.ui_batch, group=self._ui_group,
        )
        self._next_label_visible = False
        self._next_label.opacity = 0

    def show_dialogue(self, text: str, speaker: str, entry: Optional[dict] = None) -> None:
        """显示一句对话。

        解析富文本，重置打字机状态，开始逐字显示。

        Args:
            text: 对话文本（含富文本标记）。
            speaker: 说话角色名（空串=旁白）。
            entry: 原始 dialogue entry dict（用于读取 color 字段等）。
        """
        # 设置说话人
        if speaker:
            speaker_color = CHARACTER_NAME_COLORS.get(
                speaker, DEFAULT_SPEAKER_COLOR)
            self._speaker_label.text = speaker
            self._speaker_label.color = self._parse_color(speaker_color)
            self._speaker_label.visible = True
        else:
            self._speaker_label.text = ""
            self._speaker_label.visible = False

        # 解析富文本
        self._segments = parse_rich_text(text)
        self._seg_index = 0
        self._seg_char_pos = 0
        self._accumulated_text = ""
        self._current_color = COLOR_TEXT_PRIMARY
        self._speed_mult = 1.0
        self._waiting = False
        self._shake_triggered = False

        # 检查 entry 级 color 覆盖
        if entry:
            line_color = entry.get(DIALOGUE_COLOR_KEY)
            if line_color:
                self._current_color = self._parse_color(line_color)

        self._text_label.text = ""
        self._next_label_visible = False
        self._next_label.opacity = 0

        self._bold_active = False
        self._italic_active = False
        self._typing = True
        self._skip_type = False
        self._typewriter_timer = 0.0
        log.debug("显示对话: speaker=%r text_len=%d", speaker, len(text))

    def update(self, dt: float) -> None:
        """打字机帧更新。

        Args:
            dt: 帧间隔秒数。
        """
        if not self._typing:
            # 闪烁推进指示器
            if self._next_label_visible:
                t = self.app._total_time % 1.0
                self._next_label.opacity = 128 + int(127 * math.sin(t * math.pi))
            return

        if self._skip_type:
            self._finish_typing()
            return

        if self._waiting:
            self._wait_timer -= dt
            if self._wait_timer <= 0:
                self._waiting = False
            return

        self._typewriter_timer -= dt
        if self._typewriter_timer > 0:
            return

        # 处理下一个字符
        if self._seg_index < len(self._segments):
            seg = self._segments[self._seg_index]
            self._process_segment(seg)
        else:
            self._finish_typing()

    def _process_segment(self, seg: RichSegment) -> None:
        """处理一个富文本片段。"""
        if seg.type == "text":
            char = seg.text[self._seg_char_pos]
            self._accumulated_text += char
            self._text_label.text = self._accumulated_text

            # 仅当颜色变化时才更新 Label（避免每字符冗余 setter）
            color = self._current_color or COLOR_TEXT_PRIMARY
            if color != self._last_color:
                self._text_label.color = color
                self._last_color = color
            weight = "bold" if self._bold_active else "normal"
            if weight != self._last_weight:
                self._text_label.weight = weight
                self._last_weight = weight
            if self._italic_active != self._last_italic:
                self._text_label.italic = self._italic_active
                self._last_italic = self._italic_active

            self._seg_char_pos += 1
            self._typewriter_timer = self._char_interval / self._speed_mult

            if self._seg_char_pos >= len(seg.text):
                self._seg_index += 1
                self._seg_char_pos = 0

        elif seg.type == "wait":
            self._waiting = True
            self._wait_timer = float(str(seg.data))
            self._seg_index += 1

        elif seg.type == "color":
            rgb = self._parse_color(seg.data)
            if rgb:
                self._current_color = rgb
            self._seg_index += 1

        elif seg.type == "endcolor":
            self._current_color = COLOR_TEXT_PRIMARY
            self._seg_index += 1

        elif seg.type == "speed":
            self._speed_mult = float(str(seg.data)) if seg.data else 1.0
            self._speed_mult = max(0.1, self._speed_mult)
            self._seg_index += 1

        elif seg.type == "endspeed":
            self._speed_mult = 1.0
            self._seg_index += 1

        elif seg.type == "bold":
            self._bold_active = True
            self._seg_index += 1

        elif seg.type == "endbold":
            self._bold_active = False
            self._seg_index += 1

        elif seg.type == "italic":
            self._italic_active = True
            self._seg_index += 1

        elif seg.type == "enditalic":
            self._italic_active = False
            self._seg_index += 1

        elif seg.type == "shake":
            self._shake_triggered = True
            if hasattr(self.app, "effect_system") and self.app.effect_system:
                self.app.effect_system.start_shake(0.3, 4)
            self._seg_index += 1

        elif seg.type == "endshake":
            self._seg_index += 1

        else:
            self._seg_index += 1

    def _finish_typing(self) -> None:
        """完成打字机显示，显示完整文本并显示推进指示器。"""
        self._typing = False
        log.debug("打字机完成")

        # 显示完整文本
        full_text = ""
        self._current_color = COLOR_TEXT_PRIMARY
        self._bold_active = False
        self._italic_active = False
        for seg in self._segments:
            if seg.type == "text":
                full_text += seg.text
            elif seg.type == "color":
                rgb = self._parse_color(seg.data)
                if rgb:
                    self._current_color = rgb
            elif seg.type == "endcolor":
                self._current_color = COLOR_TEXT_PRIMARY
        self._text_label.text = full_text

        self._next_label_visible = True
        self._next_label.opacity = 255

    def advance(self) -> None:
        """推进对话。

        打字中 → 跳过（立即显示全文）
        完成 → 触发场景管理器的 next_dialogue()
        """
        if self._typing:
            # 检查 {w=N} 暂停状态
            if self._waiting:
                self._waiting = False
                self._wait_timer = 0.0
                return
            log.debug("跳过打字机")
            self._skip_type = True
        else:
            if hasattr(self.app, "scene_manager") and self.app.scene_manager:
                self.app.scene_manager.next_dialogue()

    def is_typing(self) -> bool:
        """是否正在打字机输出中。"""
        return self._typing

    def is_waiting(self) -> bool:
        """是否在 {w=N} 暂停中。"""
        return self._waiting

    def is_busy(self) -> bool:
        """对话系统是否繁忙（打字中或暂停中）。"""
        return self._typing or self._waiting

    def _parse_color(self, color_val) -> tuple[int, int, int, int]:
        """将颜色转换为 RGBA 元组。"""
        if isinstance(color_val, tuple):
            if len(color_val) == 3:
                return (*color_val, 255)
            return color_val
        if isinstance(color_val, str):
            color_val = color_val.lstrip("#")
            if len(color_val) == 6:
                r = int(color_val[0:2], 16)
                g = int(color_val[2:4], 16)
                b = int(color_val[4:6], 16)
                return (r, g, b, 255)
        return COLOR_TEXT_PRIMARY

    def set_dialogue_visible(self, visible: bool) -> None:
        """显示/隐藏对话 UI。"""
        self._bg_rect.visible = visible
        self._speaker_label.visible = visible
        self._text_label.visible = visible
        self._next_label.visible = visible and self._next_label_visible

    def clear(self) -> None:
        """清空对话显示。"""
        self._typing = False
        self._waiting = False
        self._text_label.text = ""
        self._speaker_label.text = ""
        self._next_label.opacity = 0
        self._next_label_visible = False
