"""
Script Parser — `.ws` 文件解析器
=================================
读取 .ws 文件，返回 List[Command]。
"""

from __future__ import annotations

import logging
from typing import Any

from .commands import (
    BGMCommand,
    ChoiceCommand,
    Command,
    DialogueCommand,
    FlagCommand,
    HideCommand,
    IfCommand,
    JumpCommand,
    LabelCommand,
    SceneCommand,
    ShowCommand,
)

logger = logging.getLogger(__name__)


def parse(filepath: str) -> list[Command]:
    """解析 .ws 脚本文件，返回命令列表。

    Args:
        filepath: .ws 文件路径。

    Returns:
        解析后的命令列表。

    Raises:
        FileNotFoundError: 文件不存在。
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        logger.error("脚本文件不存在: %s", filepath)
        raise

    commands: list[Command] = []
    labels_seen: set[str] = set()

    i = 0
    while i < len(lines):
        raw = lines[i].strip()

        # 空行 / 注释
        if not raw or raw.startswith("#"):
            i += 1
            continue

        if raw.startswith("@"):
            i = _parse_directive(raw, i, lines, commands, labels_seen)
        elif raw.startswith('"'):
            i = _parse_dialogue(raw, i, commands)
        else:
            logger.warning("无法识别的行 (L%d): %s", i + 1, raw)
            i += 1

    return commands


# ── 指令解析 ──────────────────────────────────────────────

def _parse_directive(
    raw: str, i: int, lines: list[str],
    commands: list[Command], labels_seen: set[str],
) -> int:
    """解析 @ 开头的指令行。返回下一行索引。"""
    parts = raw[1:].split(maxsplit=1)
    keyword = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if keyword == "scene":
        commands.append(SceneCommand(scene_id=args.strip()))

    elif keyword == "bgm":
        commands.append(BGMCommand(track=args.strip()))

    elif keyword == "show":
        # @show char pose at position
        # 支持多词位置 (如 "far left")：找到 "at" 的位置
        tokens = args.split()
        if len(tokens) >= 3 and "at" in (t.lower() for t in tokens):
            at_idx = next(i for i, t in enumerate(tokens) if t.lower() == "at")
            char = tokens[0]
            pose = tokens[1]
            position = " ".join(tokens[at_idx + 1:])
            commands.append(ShowCommand(char=char, pose=pose, position=position))
        else:
            logger.warning("格式错误 (L%d): @show char pose at position", i + 1)

    elif keyword == "hide":
        commands.append(HideCommand(char=args.strip()))

    elif keyword == "choice":
        i += 1
        choices: list[tuple[str, str, str]] = []
        while i < len(lines):
            cline = lines[i].strip()
            # 选项行格式: "文本": action label
            if cline.startswith('"') and ':' in cline:
                # 找到最后一个 " 后面的 : action label
                last_quote = cline.rfind('"')
                colon_pos = cline.find(':', last_quote)
                if colon_pos == -1:
                    logger.warning("选项格式错误 (L%d): %s", i + 1, cline)
                    i += 1
                    continue
                text = cline[1:last_quote].strip()
                action_part = cline[colon_pos + 1:].strip()
                act_tokens = action_part.split()
                if len(act_tokens) >= 2:
                    action = act_tokens[0]
                    label = act_tokens[1]
                    choices.append((text, action, label))
                else:
                    logger.warning("选项动作格式错误 (L%d): %s", i + 1, cline)
                i += 1
            else:
                break

        if choices:
            commands.append(ChoiceCommand(choices=choices))
        else:
            logger.warning("@choice 无有效选项 (L%d)", i)
        return i  # choice 已经推进 i

    elif keyword == "label":
        label = args.strip()
        if label in labels_seen:
            logger.warning("重复标签: %s (L%d)", label, i + 1)
        labels_seen.add(label)
        commands.append(LabelCommand(label=label))

    elif keyword == "jump":
        commands.append(JumpCommand(label=args.strip()))

    elif keyword == "flag":
        tokens = args.split()
        if len(tokens) >= 2:
            name = tokens[0]
            raw = tokens[1].lower()
            if raw in ("true", "1", "yes"):
                value = True
            elif raw in ("false", "0", "no"):
                value = False
            else:
                logger.warning("未知的 flag 值 (L%d): '%s'，视为 False", i + 1, tokens[1])
                value = False
            commands.append(FlagCommand(name=name, value=value))
        else:
            logger.warning("@flag 格式错误 (L%d): @flag name true/false", i + 1)

    elif keyword == "if":
        commands.append(IfCommand(name=args.strip()))

    else:
        logger.warning("未知指令 (L%d): @%s", i + 1, keyword)

    return i + 1


# ── 对话解析 ──────────────────────────────────────────────

def _parse_dialogue(raw: str, i: int, commands: list[Command]) -> int:
    """解析 " 开头的对话行。"""
    voice: str | None = None
    content = raw

    # 提取 [voice:...] 标记
    if " [voice:" in content:
        content_part, _, voice_part = content.rpartition(" [voice:")
        content = content_part.strip()
        voice = voice_part.rstrip("]").strip()

    # 去掉首尾引号
    if content.startswith('"'):
        content = content[1:]
    if content.endswith('"'):
        content = content[:-1]

    # 分离说话人和内容：优先英文逗号，其次中文逗号
    # 仅当逗号前为单个词（无空格）时才作为说话人解析，
    # 避免自然语言中的逗号（如 "Hello, world"）被误解析
    speaker = ""
    text = content

    def _is_single_word(s: str) -> bool:
        return bool(s) and " " not in s

    # 1) 英文逗号 + 空格 "Rei, text"
    if ", " in content:
        sp, _, tx = content.partition(", ")
        if _is_single_word(sp):
            speaker = sp.strip()
            text = tx.strip()
    # 2) 英文逗号无空格 "Rei,text"
    elif "," in content:
        sp, _, tx = content.partition(",")
        if _is_single_word(sp):
            speaker = sp.strip()
            text = tx.strip()
    # 3) 中文逗号 fallback
    elif "，" in content:
        sp, _, tx = content.partition("，")
        speaker = sp.strip()
        text = tx.strip()

    commands.append(DialogueCommand(speaker=speaker, text=text, voice=voice))
    return i + 1
