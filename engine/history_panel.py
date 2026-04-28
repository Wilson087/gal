"""
历史记录面板模块
================
滚动列表显示全部对话历史，支持鼠标滚轮和点击回溯。
"""

from typing import Optional

from pyglet.graphics import Group
from pyglet.shapes import RoundedRectangle, Rectangle
from pyglet.text import Label

from .constants import FONT_FAMILIES
from .ui_manager import (
    ORDER_PANEL, ORDER_PANEL_BORDER,
    PANEL_BG, PANEL_BORDER, TEXT_NORMAL, TEXT_DIM, TEXT_ACCENT,
    make_label, hit_test,
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
        self._elements: list = []
        self._panel_bg: Optional[RoundedRectangle] = None
        self._panel_border: Optional[Rectangle] = None

    def show(self) -> None:
        self._visible = True
        self._scroll_offset = 0
        self._elements = []

        px = (self.app.width - _PANEL_W) // 2
        py = (self.app.height - _PANEL_H) // 2

        self._panel_bg = RoundedRectangle(px, py, _PANEL_W, _PANEL_H, 8,
                                          color=PANEL_BG[:3],
                                          batch=self._batch, group=self._group)
        self._panel_border = Rectangle(px, py, _PANEL_W, _PANEL_H,
                                       color=PANEL_BORDER[:3],
                                       batch=self._batch, group=self._border_group)

        # 标题
        title = Label("对话历史", font_name=FONT_FAMILIES, font_size=16,
                      color=TEXT_NORMAL, weight="bold",
                      x=px + _PANEL_W // 2, y=py + _PANEL_H - 30,
                      anchor_x="center", anchor_y="center",
                      batch=self._batch, group=self._group)
        self._elements.append(title)

        self._build_list()

    def _build_list(self) -> None:
        """构建历史条目列表。"""
        px = (self.app.width - _PANEL_W) // 2
        py = (self.app.height - _PANEL_H) // 2
        entries = self.app.history_manager.get_entries()
        total = len(entries)
        start_idx = max(0, total - _VISIBLE_LINES - self._scroll_offset)
        end_idx = max(0, total - self._scroll_offset)

        line_top = py + _PANEL_H - 55
        for i in range(start_idx, end_idx):
            if i >= total:
                break
            entry = entries[i]
            y = line_top - (i - start_idx) * _LINE_H
            if y < py + 10:
                break

            speaker = entry.speaker if entry.speaker else "（旁白）"
            sc = TEXT_ACCENT if entry.speaker else TEXT_DIM

            self._elements.append(
                Label(speaker, font_name=FONT_FAMILIES, font_size=11,
                      color=sc, weight="bold" if entry.speaker else "normal",
                      x=px + 20, y=y, anchor_x="left", anchor_y="center",
                      width=80, multiline=False,
                      batch=self._batch, group=self._group))
            self._elements.append(
                Label(entry.text, font_name=FONT_FAMILIES, font_size=11,
                      color=TEXT_NORMAL,
                      x=px + 110, y=y, anchor_x="left", anchor_y="center",
                      width=_PANEL_W - 130, multiline=False,
                      batch=self._batch, group=self._group))

    def hide(self) -> None:
        if self._panel_bg:
            self._panel_bg.delete()
            self._panel_bg = None
        if self._panel_border:
            self._panel_border.delete()
            self._panel_border = None
        for elem in self._elements:
            elem.delete()
        self._elements.clear()
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
        # 重建列表
        self._rebuild()

    def _rebuild(self) -> None:
        """重建列表内容（保留背景）。"""
        # 删除旧条目
        for elem in self._elements[1:]:  # 保留标题
            elem.delete()
        self._elements = self._elements[:1]
        self._build_list()
