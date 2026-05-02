"""
Script System 单元测试
======================
测试解析器 + 执行器（纯 Python，无需 mock pyglet）。
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from script.parser import parse
from script.commands import (
    BGMCommand,
    ChoiceCommand,
    DialogueCommand,
    FlagCommand,
    IfCommand,
    JumpCommand,
    LabelCommand,
    SceneCommand,
    ShowCommand,
)
from script.executor import ScriptExecutor


# ── 辅助：写入临时 .ws 文件 ──────────────────────────────

def _write_ws(content: str) -> str:
    """写入临时 .ws 文件，返回文件路径。"""
    fd, path = tempfile.mkstemp(suffix=".ws", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ── 辅助：创建 mock Game ──────────────────────────────────

def _mock_game() -> MagicMock:
    g = MagicMock()
    g.variable_bank = {}
    return g


# ══════════════════════════════════════════════════════════
# Parser 测试
# ══════════════════════════════════════════════════════════

def test_parse_scene_cmd() -> None:
    path = _write_ws("@scene classroom\n")
    cmds = parse(path)
    assert len(cmds) == 1
    assert isinstance(cmds[0], SceneCommand)
    assert cmds[0].scene_id == "classroom"


def test_parse_bgm() -> None:
    path = _write_ws("@bgm happy01\n")
    cmds = parse(path)
    assert isinstance(cmds[0], BGMCommand)
    assert cmds[0].track == "happy01"


def test_parse_show() -> None:
    path = _write_ws("@show rei uniform_smile at center\n")
    cmds = parse(path)
    assert isinstance(cmds[0], ShowCommand)
    assert cmds[0].char == "rei"
    assert cmds[0].pose == "uniform_smile"
    assert cmds[0].position == "center"


def test_parse_dialogue_english_comma() -> None:
    """英文逗号优先匹配。"""
    path = _write_ws('"Rei, 前辈，早上好～"\n')
    cmds = parse(path)
    assert isinstance(cmds[0], DialogueCommand)
    assert cmds[0].speaker == "Rei"
    assert cmds[0].text == "前辈，早上好～"


def test_parse_dialogue_chinese_comma() -> None:
    """中文逗号作为 fallback。"""
    path = _write_ws('"玲，早上好"\n')
    cmds = parse(path)
    assert isinstance(cmds[0], DialogueCommand)
    assert cmds[0].speaker == "玲"
    assert cmds[0].text == "早上好"


def test_parse_dialogue_no_speaker() -> None:
    """无逗号时整段为旁白。"""
    path = _write_ws('"窗外阳光明媚。"\n')
    cmds = parse(path)
    assert isinstance(cmds[0], DialogueCommand)
    assert cmds[0].speaker == ""
    assert cmds[0].text == "窗外阳光明媚。"


def test_parse_dialogue_voice_tag() -> None:
    path = _write_ws('"前辈，早上好～" [voice:rei_001]\n')
    cmds = parse(path)
    cmd = cmds[0]
    assert isinstance(cmd, DialogueCommand)
    assert cmd.voice == "rei_001"
    assert cmd.speaker == "前辈"


def test_parse_choice() -> None:
    path = _write_ws(
        '@choice\n'
        '"一起吃饭": jump lunch_event\n'
        '"去图书馆": jump library_event\n'
    )
    cmds = parse(path)
    assert isinstance(cmds[0], ChoiceCommand)
    assert len(cmds[0].choices) == 2
    assert cmds[0].choices[0] == ("一起吃饭", "jump", "lunch_event")
    assert cmds[0].choices[1] == ("去图书馆", "jump", "library_event")


def test_parse_label_and_jump() -> None:
    path = _write_ws("@label start\n@jump start\n")
    cmds = parse(path)
    assert isinstance(cmds[0], LabelCommand)
    assert isinstance(cmds[1], JumpCommand)
    assert cmds[1].label == "start"


def test_parse_flag() -> None:
    path = _write_ws("@flag met_rei true\n")
    cmds = parse(path)
    assert isinstance(cmds[0], FlagCommand)
    assert cmds[0].name == "met_rei"
    assert cmds[0].value is True


def test_parse_if() -> None:
    path = _write_ws("@if met_rei\n")
    cmds = parse(path)
    assert isinstance(cmds[0], IfCommand)
    assert cmds[0].name == "met_rei"


def test_parse_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        parse("/nonexistent/script.ws")


def test_parse_duplicate_label_warning(caplog: pytest.LogCaptureFixture) -> None:
    path = _write_ws("@label start\n@label start\n")
    parse(path)
    assert "重复标签" in caplog.text


def test_parse_unknown_directive(caplog: pytest.LogCaptureFixture) -> None:
    path = _write_ws("@unknown_cmd test\n")
    parse(path)
    assert "未知指令" in caplog.text


# ══════════════════════════════════════════════════════════
# Executor 测试
# ══════════════════════════════════════════════════════════

def test_executor_nonblocking_advance() -> None:
    """非阻塞命令自动连续执行直到阻塞或结束。"""
    game = _mock_game()
    exe = ScriptExecutor(game)
    path = _write_ws(
        '@scene classroom\n'
        '@bgm bgm01\n'
        '"开始"'
    )
    exe.load(path)
    exe.start()
    exe.update()

    assert isinstance(exe.current_command, DialogueCommand)


def test_executor_blocking_dialogue() -> None:
    """对话命令阻塞，等待下一帧。"""
    game = _mock_game()
    exe = ScriptExecutor(game)
    path = _write_ws('"你好"\n"世界"\n')
    exe.load(path)
    exe.start()

    exe.update()
    assert isinstance(exe.current_command, DialogueCommand)
    # 当前命令仍是第一个对话（阻塞）
    cmd = exe.current_command
    assert isinstance(cmd, DialogueCommand)
    assert cmd.text == "你好"


def test_executor_jump() -> None:
    """@jump 到标签。"""
    game = _mock_game()
    exe = ScriptExecutor(game)
    path = _write_ws(
        '@jump target\n'
        '"被跳过"\n'
        '@label target\n'
        '"到达目标"'
    )
    exe.load(path)
    exe.start()
    exe.update()

    cmd = exe.current_command
    assert isinstance(cmd, DialogueCommand)
    assert cmd.text == "到达目标"


def test_executor_flag_and_if_true() -> None:
    """@flag + @if 条件成立 → 执行 @jump。"""
    game = _mock_game()
    exe = ScriptExecutor(game)

    path = _write_ws(
        '@if seen\n'
        '@jump skip\n'
        '"不应到达"\n'
        '@label skip\n'
        '"跳转成功"'
    )
    exe.load(path)
    exe._flags["seen"] = True  # 必须在 load 之后设置（load 会 clear）
    exe.start()
    exe.update()

    cmd = exe.current_command
    assert isinstance(cmd, DialogueCommand)
    assert cmd.text == "跳转成功"


def test_executor_flag_and_if_false() -> None:
    """@if 条件不成立 → 跳过 @jump，继续下一条。"""
    game = _mock_game()
    exe = ScriptExecutor(game)
    # _flags 里没有 "seen" → False

    path = _write_ws(
        '@if seen\n'
        '@jump skip\n'
        '"不应被跳过"\n'
        '@label skip\n'
        '"被跳过的"'
    )
    exe.load(path)
    exe.start()
    exe.update()

    cmd = exe.current_command
    assert isinstance(cmd, DialogueCommand)
    assert cmd.text == "不应被跳过"


def test_executor_loop_protection() -> None:
    """无限循环 → 1000 条后停止。"""
    game = _mock_game()
    exe = ScriptExecutor(game)
    exe._max_advance = 5  # 降低阈值加速测试

    # 构造跳转到自身的死循环
    path = _write_ws(
        '@label loop\n'
        '@jump loop\n'
    )
    exe.load(path)
    exe.start()
    exe.update()

    assert not exe.running


def test_executor_nonexistent_label() -> None:
    """跳转到不存在的标签 → 停止执行。"""
    game = _mock_game()
    exe = ScriptExecutor(game)
    path = _write_ws(
        '@jump nowhere\n'
        '"不应到达"'
    )
    exe.load(path)
    exe.start()
    exe.update()

    assert not exe.running


def test_executor_scene_end_event() -> None:
    """脚本结束时发布 scene_end 事件。"""
    game = _mock_game()
    exe = ScriptExecutor(game)
    path = _write_ws('@bgm test\n')
    exe.load(path)
    exe.start()
    exe.update()
    # 全部非阻塞 → 应已结束
    game.events.emit.assert_called_with("scene_end")
