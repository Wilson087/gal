"""
Canvas 渲染模块
===============
提供在 Canvas 上绘制背景、角色立绘、过渡遮罩等纯渲染函数。
所有函数均为无状态的工具函数，不维护任何游戏状态。
"""

import tkinter as tk
import random
from typing import Optional

from .constants import (
    CHAR_HEIGHT,
    COLOR_TEXT_ACCENT,
    COLOR_TEXT_PRIMARY,
    COLOR_OVERLAY,
    PLACEHOLDER_COLORS,
    PLACEHOLDER_BG_COLORS,
)
from .vectorgraphics import get_definition, render as vector_render


# ========================================================================
#  查询函数
# ========================================================================

def get_bg_info(bg_id: str) -> tuple[str, str]:
    """根据背景标识符获取占位颜色和显示名称。

    Args:
        bg_id: 背景标识符（如 "__demo_bg_room__"）。

    Returns:
        (颜色十六进制字符串, 中文场景名称)。
    """
    return PLACEHOLDER_BG_COLORS.get(bg_id, ("#34495e", "未知场景"))


def get_char_info(char_id: str) -> tuple[str, str]:
    """根据角色标识符获取占位颜色和显示名称。

    Args:
        char_id: 角色标识符（如 "__demo_char_girl__"）。

    Returns:
        (颜色十六进制字符串, 角色名称)。
    """
    return PLACEHOLDER_COLORS.get(char_id, ("#7f8c8d", "未知"))


# ========================================================================
#  背景绘制
# ========================================================================

def render_background(canvas: tk.Canvas, bg_id: str,
                      width: int, height: int) -> None:
    """在 Canvas 上绘制背景。

    优先使用已注册的矢量图定义；没有时回退到占位纯色背景。

    Args:
        canvas: 目标 Canvas 控件。
        bg_id: 背景标识符。
        width: 绘制区域宽度（像素）。
        height: 绘制区域高度（像素）。
    """
    # 清除旧背景
    canvas.delete("bg")

    # 检查是否有矢量图定义
    vdef = get_definition(bg_id)
    if vdef:
        vector_render(canvas, vdef, 0, 0,
                      width=width, height=height,
                      anchor="nw", tags="bg")
        return

    # 回退：占位纯色背景
    canvas.delete("bg")

    bg_color, bg_name = get_bg_info(bg_id)

    canvas.create_rectangle(
        0, 0, width, height,
        fill=bg_color, outline="", tags="bg",
    )

    random.seed(bg_id)
    for _ in range(30):
        x = random.randint(0, width)
        y = random.randint(0, height)
        r = random.randint(2, 6)
        stipple = random.choice(["gray12", "gray25", "gray50"])
        canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill=COLOR_TEXT_ACCENT, stipple=stipple,
            outline="", tags="bg",
        )

    canvas.create_text(
        60, 30, text=bg_name,
        font=("微软雅黑", 14),
        fill=COLOR_TEXT_PRIMARY, anchor="w", tags="bg",
    )

    canvas.create_line(
        60, 42, 220, 42,
        fill=COLOR_TEXT_ACCENT, width=2, tags="bg",
    )


# ========================================================================
#  角色立绘绘制
# ========================================================================

def draw_character(canvas: tk.Canvas, char_id: str,
                   x_center: int, y_bottom: int) -> list[int]:
    """在 Canvas 上绘制角色立绘。

    优先使用已注册的矢量图定义；没有时回退到几何人形。

    Args:
        canvas: 目标 Canvas 控件。
        char_id: 角色标识符。
        x_center: 角色中心 x 坐标。
        y_bottom: 角色底部 y 坐标（脚底位置）。

    Returns:
        所有绘制项的 Canvas 对象 ID 列表。
    """
    # 检查是否有矢量图定义
    vdef = get_definition(char_id)
    if vdef:
        return vector_render(canvas, vdef, x_center, y_bottom,
                             anchor="s", tags=f"char_{x_center}")

    # 回退：几何人形
    color, char_name = get_char_info(char_id)
    items: list[int] = []
    head_r = 35
    body_w = 100

    body_top = y_bottom - CHAR_HEIGHT + head_r * 2 + 30
    head_center_y = body_top - 10

    shoulder_w = body_w * 0.9
    hip_w = body_w * 0.65
    body = canvas.create_polygon(
        x_center - shoulder_w / 2, body_top,
        x_center + shoulder_w / 2, body_top,
        x_center + hip_w / 2, y_bottom - 30,
        x_center - hip_w / 2, y_bottom - 30,
        fill=color, outline="", tags=f"char_{x_center}",
    )
    items.append(body)

    head = canvas.create_oval(
        x_center - head_r, head_center_y - head_r,
        x_center + head_r, head_center_y + head_r,
        fill=color, outline="", tags=f"char_{x_center}",
    )
    items.append(head)

    hl = canvas.create_oval(
        x_center - head_r * 0.4, head_center_y - head_r * 0.6,
        x_center + head_r * 0.1, head_center_y - head_r * 0.1,
        fill=COLOR_TEXT_PRIMARY, stipple="gray12",
        outline="", tags=f"char_{x_center}",
    )
    items.append(hl)

    name_tag = canvas.create_text(
        x_center, y_bottom - 8,
        text=char_name,
        font=("微软雅黑", 13, "bold"),
        fill=COLOR_TEXT_PRIMARY, anchor="s",
        tags=f"char_{x_center}",
    )
    items.append(name_tag)

    return items


def clear_characters(canvas: tk.Canvas) -> None:
    """清除 Canvas 上所有角色立绘（tag = "left_char" / "right_char"）。

    Args:
        canvas: 目标 Canvas 控件。
    """
    canvas.delete("left_char")
    canvas.delete("right_char")


# ========================================================================
#  过渡遮罩
# ========================================================================

def create_fade_overlay(canvas: tk.Canvas, w: int, h: int) -> int:
    """创建白色背景过渡遮罩矩形（初始为最透明 "gray12"）。

    Args:
        canvas: 目标 Canvas 控件。
        w: 宽度。
        h: 高度。

    Returns:
        遮罩矩形的 Canvas 对象 ID。
    """
    return canvas.create_rectangle(
        0, 0, w, h,
        fill=COLOR_OVERLAY, stipple="gray12",
        outline="", tags="overlay",
    )


def remove_overlay(canvas: tk.Canvas, overlay_id: Optional[int]) -> None:
    """移除过渡遮罩。

    Args:
        canvas: 目标 Canvas 控件。
        overlay_id: 遮罩对象的 Canvas ID，为 None 时不做任何操作。
    """
    if overlay_id is not None:
        try:
            canvas.delete(overlay_id)
        except tk.TclError:
            pass


# ========================================================================
#  通知文字
# ========================================================================

def show_notification(canvas: tk.Canvas, text: str,
                      color: str = "#f1c40f", duration: int = 1500) -> None:
    """在 Canvas 中央显示短暂的通知文字。

    Args:
        canvas: 目标 Canvas 控件。
        text: 通知文本。
        color: 文字颜色（十六进制）。
        duration: 显示时长（毫秒），到期自动清除。
    """
    w = canvas.winfo_width() or 1280
    h = canvas.winfo_height() or 720

    notif_id = canvas.create_text(
        w // 2, h // 2,
        text=text,
        font=("微软雅黑", 28, "bold"),
        fill=color, anchor="center",
        tags="notification",
    )

    canvas.after(duration, lambda: canvas.delete("notification"))
