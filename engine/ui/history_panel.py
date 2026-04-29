"""
历史记录面板模块
================
滚动列表显示全部对话历史，支持鼠标滚轮和点击回溯。
Label 预分配复用，滚动时仅更新文本，避免频繁创建/销毁。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..app import AVGApplication

from pyglet.graphics import Group
from pyglet.shapes import RoundedRectangle, Rectangle
from pyglet.text import Label

from ..core.constants import FONT_FAMILIES
from .ui_manager import (
    ORDER_PANEL, ORDER_PANEL_BORDER,
    PANEL_BG, PANEL_BORDER, TEXT_NORMAL, TEXT_DIM, TEXT_ACCENT,
)

_PANEL_W = 700
_PANEL_H = 500
_LINE_H = 26
_VISIBLE_LINES = 15


class HistoryPanel:
    """对话历史记录面板，带滚轮滚动和点击回溯。"""

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        self._batch = app.ui_batch
        self._group = Group(order=ORDER_PANEL)
        self._border_group = Group(order=ORDER_PANEL_BORDER)
        self._visible = False
        self._scroll_offset = 0

        # 预分配的 Label 槽位，show 时创建，滚动时复用
        self._speaker_labels: list[Label] = []
        self._text_labels: list[Label] = []
        self._panel_bg: Optional[RoundedRectangle] = None
        self._panel_border: Optional[Rectangle] = None
        self._title_label: Optional[Label] = None

    def show(self) -> None:
        self._visible = True
        self._scroll_offset = 0

        px = (self.app.width - _PANEL_W) // 2
        py = (self.app.height - _PANEL_H) // 2

        self._panel_bg = RoundedRectangle(px, py, _PANEL_W, _PANEL_H, 8,
                                          color=PANEL_BG[:3],
                                          batch=self._batch, group=self._group)
        self._panel_border = Rectangle(px, py, _PANEL_W, _PANEL_H,
                                       color=PANEL_BORDER[:3],
                                       batch=self._batch, group=self._border_group)

        self._title_label = Label("对话历史", font_name=FONT_FAMILIES, font_size=16,
                                  color=TEXT_NORMAL, weight="bold",
                                  x=px + _PANEL_W // 2, y=py + _PANEL_H - 30,
                                  anchor_x="center", anchor_y="center",
                                  batch=self._batch, group=self._group)

        self._build_slots()
        self._update_slots()

    def _build_slots(self) -> None:
        """预分配 VISIBLE_LINES 组的 Speaker + Text Label。"""
        for lbl in self._speaker_labels + self._text_labels:
            lbl.delete()
        self._speaker_labels.clear()
        self._text_labels.clear()

        px = (self.app.width - _PANEL_W) // 2
        py = (self.app.height - _PANEL_H) // 2
        line_top = py + _PANEL_H - 55

        for i in range(_VISIBLE_LINES):
            y = line_top - i * _LINE_H
            spk = Label("", font_name=FONT_FAMILIES, font_size=11,
                        color=TEXT_NORMAL,
                        x=px + 20, y=y, anchor_x="left", anchor_y="center",
                        width=80, multiline=False,
                        batch=self._batch, group=self._group)
            txt = Label("", font_name=FONT_FAMILIES, font_size=11,
                        color=TEXT_NORMAL,
                        x=px + 110, y=y, anchor_x="left", anchor_y="center",
                        width=_PANEL_W - 130, multiline=False,
                        batch=self._batch, group=self._group)
            self._speaker_labels.append(spk)
            self._text_labels.append(txt)

    def _update_slots(self) -> None:
        """用当前滚动偏移更新所有 Label 文本。"""
        entries = self.app.history_manager.get_entries()
        total = len(entries)
        start_idx = max(0, total - _VISIBLE_LINES - self._scroll_offset)

        px = (self.app.width - _PANEL_W) // 2
        py = (self.app.height - _PANEL_H) // 2
        line_top = py + _PANEL_H - 55

        for i in range(_VISIBLE_LINES):
            idx = start_idx + i
            spk_lbl = self._speaker_labels[i]
            txt_lbl = self._text_labels[i]
            y = line_top - i * _LINE_H

            if 0 <= idx < total:
                entry = entries[idx]
                speaker = entry.speaker if entry.speaker else "（旁白）"
                spk_lbl.text = speaker
                spk_lbl.color = TEXT_ACCENT if entry.speaker else TEXT_DIM
                spk_lbl.weight = "bold" if entry.speaker else "normal"
                spk_lbl.y = y
                spk_lbl.visible = True

                txt_lbl.text = entry.text
                txt_lbl.color = TEXT_NORMAL
                txt_lbl.y = y
                txt_lbl.visible = True
            else:
                spk_lbl.visible = False
                txt_lbl.visible = False

    def hide(self) -> None:
        if self._panel_bg:
            self._panel_bg.delete()
            self._panel_bg = None
        if self._panel_border:
            self._panel_border.delete()
            self._panel_border = None
        if self._title_label:
            self._title_label.delete()
            self._title_label = None
        for lbl in self._speaker_labels + self._text_labels:
            lbl.delete()
        self._speaker_labels.clear()
        self._text_labels.clear()
        self._visible = False

    def update(self, dt: float) -> None:
        pass

    def on_click(self, x: int, y: int) -> bool:
        if not self._visible:
            return False
        px = (self.app.width - _PANEL_W) // 2
        py = (self.app.height - _PANEL_H) // 2
        if not (px <= x <= px + _PANEL_W and py <= y <= py + _PANEL_H):
            return False

        # 检查点击在某条历史上 → 回溯
        entries = self.app.history_manager.get_entries()
        total = len(entries)
        start_idx = max(0, total - _VISIBLE_LINES - self._scroll_offset)
        line_top = py + _PANEL_H - 55

        clicked_idx = start_idx + int((line_top - y) / _LINE_H)
        if 0 <= clicked_idx < total:
            entry = entries[clicked_idx]
            self.app.history_manager.jump_to_entry(entry)
            self.app.ui_manager.hide_all_panels()

        return True

    def on_scroll(self, x: int, y: int, scroll_x: float,
                  scroll_y: float) -> None:
        if not self._visible:
            return
        self._scroll_offset = max(0, self._scroll_offset + int(-scroll_y * 3))
        self._update_slots()
