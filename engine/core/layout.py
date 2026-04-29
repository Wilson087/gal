"""
布局容器模块
============
HBox / VBox / Grid 布局辅助类，自动计算子元素位置。
"""

from typing import Optional


class HBox:
    """水平排列容器。

    子元素从左到右排列，超出宽度自动换行。
    """

    def __init__(self, x: float, y: float, width: float = 0,
                 spacing: float = 10, row_height: float = 0):
        self._start_x = x
        self._start_y = y
        self._width = width
        self._spacing = spacing
        self._row_height = row_height
        self._cursor_x = x
        self._cursor_y = y
        self._current_row_height = 0.0

    def next(self, child_w: float, child_h: float) -> tuple[float, float]:
        """获取下一个子元素的 (x, y) 位置。

        Args:
            child_w: 子元素宽度。
            child_h: 子元素高度。

        Returns:
            (x, y) 放置位置。
        """
        # 需要换行？
        if self._width > 0 and self._cursor_x + child_w > self._start_x + self._width:
            self._cursor_x = self._start_x
            self._cursor_y -= (self._row_height if self._row_height > 0
                                else self._current_row_height) + self._spacing
            self._current_row_height = 0.0

        x = self._cursor_x
        y = self._cursor_y - child_h
        self._cursor_x += child_w + self._spacing
        self._current_row_height = max(self._current_row_height, child_h)
        return x, y

    @property
    def x(self) -> float:
        return self._cursor_x

    @property
    def y(self) -> float:
        return self._cursor_y


class VBox:
    """垂直排列容器。

    子元素从上到下排列。
    """

    def __init__(self, x: float, y: float, spacing: float = 10):
        self._x = x
        self._start_y = y
        self._spacing = spacing
        self._cursor_y = y

    def next(self, child_w: float, child_h: float) -> tuple[float, float]:
        """获取下一个子元素的 (x, y) 位置。"""
        y = self._cursor_y - child_h
        self._cursor_y -= child_h + self._spacing
        return self._x, y

    @property
    def y(self) -> float:
        return self._cursor_y

    def reset(self, y: float) -> None:
        self._cursor_y = y


class Grid:
    """网格容器，按行列分配位置。

    适用于存档槽位、设置选项等整齐排列的 UI。
    """

    def __init__(self, x: float, y: float,
                 cols: int, rows: int,
                 cell_w: float, cell_h: float,
                 gap_x: float = 10, gap_y: float = 10):
        self._x = x
        self._y = y
        self._cols = cols
        self._rows = rows
        self._cell_w = cell_w
        self._cell_h = cell_h
        self._gap_x = gap_x
        self._gap_y = gap_y

    def cell(self, col: int, row: int) -> tuple[float, float]:
        """获取指定行列的左上角坐标。

        Args:
            col: 列索引（从 0 开始）。
            row: 行索引（从 0 开始）。

        Returns:
            (x, y) 左上角坐标。
        """
        x = self._x + col * (self._cell_w + self._gap_x)
        y = self._y - row * (self._cell_h + self._gap_y)
        return x, y

    def cell_center(self, col: int, row: int) -> tuple[float, float]:
        """获取指定行列的中心坐标。"""
        x, y = self.cell(col, row)
        return x + self._cell_w / 2, y - self._cell_h / 2

    @property
    def total_width(self) -> float:
        return self._cols * self._cell_w + (self._cols - 1) * self._gap_x

    @property
    def total_height(self) -> float:
        return self._rows * self._cell_h + (self._rows - 1) * self._gap_y
