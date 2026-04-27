"""
富文本标记解析模块
===================
解析对白文本中的内联标记，如 {w=0.5} {shake} {color=#ff0000} {speed=2} 等。

支持标记:
    {w=秒数}       — 暂停指定秒数
    {shake}        — 开启震动文字效果
    {/shake}       — 关闭震动
    {color=#hex}   — 设置文字颜色
    {/color}       — 恢复默认颜色
    {speed=倍率}   — 改变打字速度（如 speed=2 表示两倍速）
    {/speed}       — 恢复默认速度
    {font=字体名}  — 设置字体
    {/font}        — 恢复默认字体
"""

import re
from typing import Optional


__all__ = ["RichSegment", "parse_rich_text", "strip_rich_tags", "RICH_PATTERN"]


# 正则：匹配 {w=数字} {shake} {/shake} {color=#hex} {/color} {speed=数字} {/speed} {font=名} {/font}
RICH_PATTERN = re.compile(
    r"\{"
    r"(?:"
    r"w=([\d.]+)"
    r"|/shake"
    r"|shake(?:=([\d.]+))?"
    r"|color=(#?[0-9a-fA-F]+)"
    r"|/color"
    r"|speed=([\d.]+)"
    r"|/speed"
    r"|font=([^}]+)"
    r"|/font"
    r")"
    r"\}"
)


class RichSegment:
    """富文本段落标记。

    type 取值:
        "text"      — 普通文本（在 text 属性中）
        "wait"      — 等待指定秒数（data 为 float）
        "shake"     — 开启文字震动
        "endshake"  — 结束文字震动
        "color"     — 设置文字颜色（data 为颜色字符串）
        "endcolor"  — 恢复默认颜色
        "speed"     — 改变打字速度倍率（data 为 float，如 2.0 表示 2 倍）
        "endspeed"  — 恢复默认速度
        "font"      — 设置字体（data 为字体名）
        "endfont"   — 恢复默认字体
    """

    __slots__ = ("type", "data", "text")

    def __init__(self, type_: str, data: object = None, text: str = "") -> None:
        self.type = type_
        self.data = data
        self.text = text

    def __repr__(self) -> str:
        return f"RichSegment({self.type}, {self.data!r}, {self.text!r})"


def parse_rich_text(text: str) -> list[RichSegment]:
    """将对白文本解析为富文本片段列表。

    Args:
        text: 含标记的原始文本。

    Returns:
        富文本片段列表，不含标记本身的纯文本标记。
    """
    segments: list[RichSegment] = []
    last_end = 0

    for m in RICH_PATTERN.finditer(text):
        start, end = m.start(), m.end()

        # 标记前的纯文本
        if start > last_end:
            segments.append(RichSegment("text", text=text[last_end:start]))

        full = m.group(0)
        # 闭合标记
        if full.startswith("{/"):
            tag = full[2:-1]
            if tag == "shake":
                segments.append(RichSegment("endshake"))
            elif tag == "color":
                segments.append(RichSegment("endcolor"))
            elif tag == "speed":
                segments.append(RichSegment("endspeed"))
            elif tag == "font":
                segments.append(RichSegment("endfont"))
        else:
            if m.group(1) is not None:  # w=秒数
                segments.append(RichSegment("wait", data=float(m.group(1))))
            elif m.group(2) is not None:  # shake=持续时间
                segments.append(RichSegment("shake", data=float(m.group(2))))
            elif "shake" in full and m.group(2) is None:
                segments.append(RichSegment("shake"))
            elif m.group(3) is not None:  # color=#hex
                segments.append(RichSegment("color", data=m.group(3)))
            elif m.group(4) is not None:  # speed=倍率
                segments.append(RichSegment("speed", data=float(m.group(4))))
            elif m.group(5) is not None:  # font=字体名
                segments.append(RichSegment("font", data=m.group(5)))

        last_end = end

    if last_end < len(text):
        segments.append(RichSegment("text", text=text[last_end:]))

    return segments


def strip_rich_tags(text: str) -> str:
    """移除所有富文本标记，返回纯文本。

    Args:
        text: 含标记的原始文本。

    Returns:
        不含标记的纯文本。
    """
    return RICH_PATTERN.sub("", text)
