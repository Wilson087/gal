"""
存档/读档面板模块
==================
网格展示存档槽位，支持翻页、截图预览、存档/读档操作。
"""

from typing import Any, Optional

from pyglet.graphics import Group, Batch
from pyglet.shapes import RoundedRectangle, Rectangle
from pyglet.text import Label

from .constants import FONT_FAMILIES
from .ui_manager import (
    ORDER_PANEL, ORDER_PANEL_BORDER, ORDER_OVERLAY,
    PANEL_BG, PANEL_BORDER, TEXT_NORMAL, TEXT_DIM, TEXT_ACCENT,
    BTN_BG, BTN_HOVER, make_label, hit_test,
)

_PANEL_W = 780
_PANEL_H = 460
_COLS = 5
_ROWS = 2
_SLOT_W = 136
_SLOT_H = 170
_SLOT_GAP = 16


class SaveLoadPanel:
    """存档/读档面板，2行x5列网格。"""

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        self._batch = app.ui_batch
        self._group = Group(order=ORDER_PANEL)
        self._border_group = Group(order=ORDER_PANEL_BORDER)
        self._visible = False
        self._mode = "save"  # save / load
        self._page = 0
        self._slot_widgets: list[dict] = []
        self._nav_widgets: list[dict] = []
        self._panel_bg: Optional[RoundedRectangle] = None
        self._panel_border: Optional[Rectangle] = None
        self._title_label: Optional[Label] = None

    def show(self, mode: str) -> None:
        """显示面板。mode='save' 或 'load'。"""
        self._mode = mode
        self._page = 0
        self._visible = True
        self._slot_widgets = []
        self._nav_widgets = []

        w, h = _PANEL_W, _PANEL_H
        px = (self.app.width - w) // 2
        py = (self.app.height - h) // 2

        self._panel_bg = RoundedRectangle(px, py, w, h, 8,
                                          color=PANEL_BG[:3],
                                          batch=self._batch, group=self._group)
        self._panel_border = Rectangle(px, py, w, h,
                                       color=PANEL_BORDER[:3],
                                       batch=self._batch, group=self._border_group)

        # 标题
        title = "保存游戏" if mode == "save" else "读取存档"
        self._title_label = Label(title, font_name=FONT_FAMILIES, font_size=16,
                                  color=TEXT_NORMAL, weight="bold",
                                  x=px + w // 2, y=py + h - 30,
                                  anchor_x="center", anchor_y="center",
                                  batch=self._batch, group=self._group)

        self._build_slots()
        self._build_nav()

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
        self._clear_slots()
        self._clear_nav()
        self._visible = False

    def _clear_slots(self) -> None:
        for w in self._slot_widgets:
            for v in w.values():
                if hasattr(v, 'delete'):
                    v.delete()
        self._slot_widgets.clear()

    def _clear_nav(self) -> None:
        for w in self._nav_widgets:
            if hasattr(w, 'delete'):
                w.delete()
        self._nav_widgets.clear()

    def _build_slots(self) -> None:
        """构建当前页的10个槽位。"""
        self._clear_slots()
        w, h = _PANEL_W, _PANEL_H
        px = (self.app.width - w) // 2
        py = (self.app.height - h) // 2
        grid_w = _COLS * _SLOT_W + (_COLS - 1) * _SLOT_GAP
        start_x = px + (w - grid_w) // 2
        start_y = py + h - 70

        sm = self.app.save_manager
        slots = sm.get_slots_for_page(self._page)

        for idx, slot_i in enumerate(slots):
            col = idx % _COLS
            row = idx // _COLS
            sx = start_x + col * (_SLOT_W + _SLOT_GAP)
            sy = start_y - row * (_SLOT_H + _SLOT_GAP)

            info = sm.get_slot_info(slot_i)
            self._draw_slot(sx, sy, slot_i, info)

    def _draw_slot(self, x: int, y: int, slot_index: int,
                   info: Optional[dict]) -> None:
        """绘制单个槽位。"""
        bg = RoundedRectangle(x, y, _SLOT_W, _SLOT_H, 6,
                              color=(255, 255, 255, 30),
                              batch=self._batch, group=self._group)
        self._slot_widgets.append({"bg": bg, "slot": slot_index, "info": info})

        if info and info.get("screenshot_base64"):
            # 有存档：显示时间+场景名
            ts = info.get("timestamp", "")
            scene = info.get("chapter_title", "")
            self._slot_widgets.append(
                Label(ts, font_name=FONT_FAMILIES, font_size=9,
                      color=TEXT_DIM,
                      x=x + 5, y=y + _SLOT_H - 22, anchor_x="left", anchor_y="top",
                      batch=self._batch, group=self._group))
            self._slot_widgets.append(
                Label(f"#{slot_index}", font_name=FONT_FAMILIES, font_size=10,
                      color=TEXT_ACCENT,
                      x=x + 5, y=y + 5, anchor_x="left", anchor_y="bottom",
                      batch=self._batch, group=self._group))
            self._slot_widgets.append(
                Label(scene[:12], font_name=FONT_FAMILIES, font_size=9,
                      color=TEXT_ACCENT,
                      x=x + 5, y=y + 20, anchor_x="left", anchor_y="bottom",
                      batch=self._batch, group=self._group))
        else:
            # 空槽位
            self._slot_widgets.append(
                Label("空", font_name=FONT_FAMILIES, font_size=14,
                      color=TEXT_DIM,
                      x=x + _SLOT_W // 2, y=y + _SLOT_H // 2,
                      anchor_x="center", anchor_y="center",
                      batch=self._batch, group=self._group))

    def _build_nav(self) -> None:
        """构建底部翻页按钮。"""
        w, h = _PANEL_W, _PANEL_H
        px = (self.app.width - w) // 2
        py = (self.app.height - h) // 2
        total = self.app.save_manager.get_page_count()

        # 上一页
        if self._page > 0:
            prev = RoundedRectangle(px + 150, py + 15, 80, 28, 6,
                                    color=BTN_BG[:3],
                                    batch=self._batch, group=self._group)
            lbl = Label("< 上一页", font_name=FONT_FAMILIES, font_size=10,
                        color=TEXT_NORMAL,
                        x=px + 190, y=py + 29,
                        anchor_x="center", anchor_y="center",
                        batch=self._batch, group=self._group)
            self._nav_widgets.extend([prev, lbl])

        # 页码
        page_lbl = Label(f"第 {self._page+1}/{total} 页",
                         font_name=FONT_FAMILIES, font_size=11,
                         color=TEXT_NORMAL,
                         x=px + w // 2, y=py + 29,
                         anchor_x="center", anchor_y="center",
                         batch=self._batch, group=self._group)
        self._nav_widgets.append(page_lbl)

        # 下一页
        if self._page < total - 1:
            nxt = RoundedRectangle(px + w - 230, py + 15, 80, 28, 6,
                                   color=BTN_BG[:3],
                                   batch=self._batch, group=self._group)
            lbl2 = Label("下一页 >", font_name=FONT_FAMILIES, font_size=10,
                         color=TEXT_NORMAL,
                         x=px + w - 190, y=py + 29,
                         anchor_x="center", anchor_y="center",
                         batch=self._batch, group=self._group)
            self._nav_widgets.extend([nxt, lbl2])

    def update(self, dt: float) -> None:
        pass

    def on_click(self, x: int, y: int) -> bool:
        if not self._visible:
            return False

        # 检查点击在面板内
        w, h = _PANEL_W, _PANEL_H
        px = (self.app.width - w) // 2
        py = (self.app.height - h) // 2
        if not (px <= x <= px + w and py <= y <= py + h):
            return False

        # 检查槽位点击
        grid_w = _COLS * _SLOT_W + (_COLS - 1) * _SLOT_GAP
        start_x = px + (w - grid_w) // 2
        start_y = py + h - 70

        for idx, slot_data in enumerate(self._slot_widgets):
            col = idx % _COLS
            row = idx // _COLS
            sx = start_x + col * (_SLOT_W + _SLOT_GAP)
            sy = start_y - row * (_SLOT_H + _SLOT_GAP)
            if sx <= x <= sx + _SLOT_W and sy <= y <= sy + _SLOT_H:
                slot_i = slot_data["slot"]
                if self._mode == "save":
                    self.app.save_manager.save(slot_i)
                    self._build_slots()
                else:
                    self.app.save_manager.load(slot_i)
                    self.app.ui_manager.hide_all_panels()
                return True

        # 翻页按钮
        total = self.app.save_manager.get_page_count()
        if self._page > 0:
            if px + 150 <= x <= px + 230 and py + 15 <= y <= py + 43:
                self._page -= 1
                self._build_slots()
                self._build_nav()
                return True
        if self._page < total - 1:
            if px + w - 230 <= x <= px + w - 150 and py + 15 <= y <= py + 43:
                self._page += 1
                self._build_slots()
                self._build_nav()
                return True

        return True  # 点击在面板内，阻止关闭
