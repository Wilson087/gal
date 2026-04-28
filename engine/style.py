"""
样式表系统模块
==============
集中管理所有 UI 控件的样式属性，支持按名称引用和继承。
"""

from typing import Any, Optional

from .constants import FONT_FAMILIES

# ── 样式定义 ──────────────────────────────────────────────

STYLES: dict[str, dict] = {
    # 工具栏按钮
    "toolbar_button": {
        "bg": (255, 255, 255, 25),
        "hover_bg": (255, 255, 255, 51),
        "text_color": (0, 0, 0, 255),
        "font_size": 10,
        "font_name": FONT_FAMILIES,
        "radius": 6,
        "padding": (8, 4),
        "width": 44,
        "height": 32,
    },
    # 面板背景
    "panel_bg": {
        "bg": (18, 18, 18, 191),
        "border": (255, 255, 255, 51),
        "radius": 8,
    },
    # 面板标题文字
    "panel_title": {
        "text_color": (255, 255, 255, 255),
        "font_size": 16,
        "font_name": FONT_FAMILIES,
        "weight": "bold",
    },
    # 常规按钮
    "button": {
        "bg": (255, 255, 255, 25),
        "hover_bg": (255, 255, 255, 51),
        "text_color": (255, 255, 255, 255),
        "font_size": 12,
        "font_name": FONT_FAMILIES,
        "radius": 6,
        "padding": (10, 6),
    },
    # 选中按钮（标签页高亮等）
    "button_active": {
        "bg": (25, 118, 210, 200),
        "text_color": (255, 255, 255, 255),
        "font_size": 12,
        "font_name": FONT_FAMILIES,
        "radius": 6,
        "padding": (10, 6),
    },
    # 存档槽位
    "save_slot": {
        "bg": (255, 255, 255, 30),
        "hover_bg": (255, 255, 255, 51),
        "radius": 6,
        "width": 136,
        "height": 170,
        "padding": (5, 5),
    },
    # 对话框
    "dialogue_frame": {
        "bg": (18, 18, 42, 230),
        "radius": 0,
        "padding": (20, 24),
    },
    # 扬声器标签
    "speaker_label": {
        "text_color": (231, 76, 60, 255),
        "font_size": 16,
        "font_name": FONT_FAMILIES,
        "weight": "bold",
    },
    # 对话文本
    "dialogue_text": {
        "text_color": (236, 240, 241, 255),
        "font_size": 14,
        "font_name": FONT_FAMILIES,
    },
    # 翻页按钮
    "nav_button": {
        "bg": (255, 255, 255, 25),
        "text_color": (255, 255, 255, 255),
        "font_size": 10,
        "font_name": FONT_FAMILIES,
        "radius": 6,
        "padding": (8, 4),
    },
}


def get(name: str) -> dict:
    """获取样式字典的副本。

    Args:
        name: 样式名称。

    Returns:
        样式字典的浅拷贝，修改不影响原样式。
    """
    base = STYLES.get(name)
    if base is None:
        return {}
    return dict(base)


def merge(base: str, overrides: dict) -> dict:
    """合并基础样式和覆盖项。

    Args:
        base: 基础样式名。
        overrides: 要覆盖的属性。

    Returns:
        合并后的样式字典。
    """
    result = get(base)
    result.update(overrides)
    return result


def apply_to_button(btn: dict, style_name: str) -> None:
    """将样式应用到一个 make_button 创建的按钮字典。

    Args:
        btn: make_button 返回的按钮字典。
        style_name: 样式名称。
    """
    s = get(style_name)
    if not s:
        return
    # 背景色
    if "bg" in s and btn.get("rect"):
        btn["rect"].color = s["bg"][:3]
    # 文字颜色
    if "text_color" in s and btn.get("label"):
        btn["label"].color = s["text_color"]
    # 字体大小
    if "font_size" in s and btn.get("label"):
        btn["label"].font_size = s["font_size"]
