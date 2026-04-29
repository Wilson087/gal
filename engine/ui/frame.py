"""
Frame 容器模块
==============
带背景的自适应容器，类似 Ren'Py 的 frame 语句。
用 RoundedRectangle 绘制背景，自动适应内容尺寸。
"""

from typing import Optional

from pyglet.graphics import Group, Batch
from pyglet.shapes import RoundedRectangle, Rectangle

from .style import get as get_style
from .ui_manager import ORDER_PANEL, PANEL_BG, PANEL_BORDER


class Frame:
    """带背景的自适应容器。

    背景用 RoundedRectangle 绘制（圆角保持），
    内边距自动计算，内容区域自动定位。
    """

    def __init__(self, x: float, y: float,
                 width: float, height: float,
                 style_name: str = "panel_bg",
                 batch: Optional[Batch] = None,
                 group: Optional[Group] = None):
        self._x = x
        self._y = y
        self._width = width
        self._height = height
        self._batch = batch
        self._group = group

        s = get_style(style_name)
        radius = s.get("radius", 8)
        bg_color = s.get("bg", PANEL_BG[:3])
        border_color = s.get("border", PANEL_BORDER[:3])
        self._padding = s.get("padding", (20, 20))
        if isinstance(self._padding, int):
            self._padding = (self._padding, self._padding)

        self._bg = RoundedRectangle(x, y, width, height, radius,
                                    color=bg_color[:3],
                                    batch=batch, group=group)
        self._border = Rectangle(x, y, width, height,
                                 color=border_color[:3],
                                 batch=batch, group=group)

    @property
    def content_x(self) -> float:
        return self._x + self._padding[0]

    @property
    def content_y(self) -> float:
        return self._y + self._padding[1]

    @property
    def content_width(self) -> float:
        return self._width - self._padding[0] * 2

    @property
    def content_height(self) -> float:
        return self._height - self._padding[1] * 2

    @property
    def content_rect(self) -> tuple[float, float, float, float]:
        """返回 (x, y, w, h) 内容区域。"""
        return (self.content_x, self.content_y,
                self.content_width, self.content_height)

    def delete(self) -> None:
        if self._bg:
            self._bg.delete()
        if self._border:
            self._border.delete()
