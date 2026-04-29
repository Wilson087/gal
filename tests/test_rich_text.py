"""富文本解析器单元测试。"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.core.rich_text import parse_rich_text, strip_rich_tags, RichSegment


def test_plain_text():
    segs = parse_rich_text("你好，世界。")
    assert len(segs) == 1
    assert segs[0].type == "text"
    assert segs[0].text == "你好，世界。"


def test_wait_tag():
    segs = parse_rich_text("前{w=0.5}后")
    assert len(segs) == 3
    assert segs[0].type == "text"
    assert segs[0].text == "前"
    assert segs[1].type == "wait"
    assert segs[1].data == 0.5
    assert segs[2].type == "text"
    assert segs[2].text == "后"


def test_color_tag():
    segs = parse_rich_text("{color=#ff0000}红字{/color}")
    assert segs[0].type == "color"
    assert segs[0].data == "#ff0000"
    assert segs[1].type == "text"
    assert segs[1].text == "红字"
    assert segs[2].type == "endcolor"


def test_color_tag_without_hash():
    segs = parse_rich_text("{color=ff0000}红字{/color}")
    assert segs[0].type == "color"
    assert segs[0].data == "ff0000"


def test_speed_tag():
    segs = parse_rich_text("{speed=2}快{/speed}")
    assert segs[0].type == "speed"
    assert segs[0].data == 2.0
    assert segs[2].type == "endspeed"


def test_shake_tag():
    segs = parse_rich_text("{shake}震{/shake}")
    assert segs[0].type == "shake"
    assert segs[0].data is None
    assert segs[2].type == "endshake"


def test_shake_with_duration():
    segs = parse_rich_text("{shake=0.5}震")
    assert segs[0].type == "shake"
    assert segs[0].data == 0.5


def test_bold_italic():
    segs = parse_rich_text("{b}粗体{i}粗斜{/i}仅粗{/b}")
    types = [s.type for s in segs]
    assert types == ["bold", "text", "italic", "text", "enditalic", "text", "endbold"]


def test_font_tag():
    segs = parse_rich_text("{font=SimHei}黑体{/font}")
    assert segs[0].type == "font"
    assert segs[0].data == "SimHei"
    assert segs[2].type == "endfont"


def test_mixed_tags():
    segs = parse_rich_text("普通{color=#C39BD3}紫色{w=0.3}暂停{/color}结束")
    types = [s.type for s in segs]
    assert "wait" in types
    assert "color" in types
    assert "endcolor" in types


def test_empty_text():
    segs = parse_rich_text("")
    assert len(segs) == 0


def test_no_tags():
    segs = parse_rich_text("纯文本没有任何标记")
    assert len(segs) == 1
    assert segs[0].type == "text"


def test_tag_only():
    segs = parse_rich_text("{b}")
    assert len(segs) == 1
    assert segs[0].type == "bold"


def test_strip_rich_tags():
    result = strip_rich_tags("{color=#ff0000}红字{/color}普通{w=0.3}后")
    assert result == "红字普通后"


def test_strip_complex():
    result = strip_rich_tags("{b}粗{/b}{i}斜{/i}{shake}震{/shake}")
    assert result == "粗斜震"
