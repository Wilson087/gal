"""
Script Executor — 生成器驱动的脚本执行器
==========================================
推进命令队列，处理跳转、分支、阻塞等待。
"""

from __future__ import annotations

import logging
from typing import Any, Generator

from config import MAX_SCRIPT_ADVANCE
from .commands import (
    ChoiceCommand,
    Command,
    DialogueCommand,
    IfCommand,
    JumpCommand,
    LabelCommand,
)
from .parser import parse

logger = logging.getLogger(__name__)


class ScriptExecutor:
    """脚本执行器 —— 管理命令队列与当前协程。

    通过 `update()` 驱动，支持跳转、条件分支、选项等待。
    """

    def __init__(self, game: Any) -> None:
        self._game: Any = game
        self._commands: list[Command] = []
        self._pc: int = 0
        self._labels: dict[str, int] = {}
        self._current: Generator[None, None, None] | None = None
        self._running: bool = False
        self._max_advance: int = MAX_SCRIPT_ADVANCE

        # 运行时标志
        self._flags: dict[str, bool] = {}
        # 当前选中的选项索引（ChoiceCommand 回传）
        self._choice_result: int = -1
        # 对话等待标志（DialogueCommand 用，DIALOGUE_NEXT 时清除）
        self._waiting_dialogue: bool = False

    # ── 加载 ──────────────────────────────────────────────

    def load(self, filepath: str) -> None:
        """解析脚本文件并建立标签映射。

        Args:
            filepath: .ws 文件路径。

        Raises:
            FileNotFoundError: 文件不存在。
        """
        if self._running:
            logger.warning("加载新脚本时将中止正在执行的脚本: %s", filepath)
        self._commands = parse(filepath)
        self._labels.clear()
        self._pc = 0
        self._running = False
        self._current = None
        self._flags.clear()
        self._waiting_dialogue = False

        for idx, cmd in enumerate(self._commands):
            if isinstance(cmd, LabelCommand):
                self._labels[cmd.label] = idx

        logger.debug(
            "脚本已加载: %s (%d 命令, %d 标签)",
            filepath, len(self._commands), len(self._labels),
        )

    def start(self) -> None:
        """开始 / 重新开始执行脚本。"""
        self._pc = 0
        self._running = True
        self._current = None
        self._waiting_dialogue = False
        logger.debug("脚本开始执行")

    # ── 每帧驱动 ──────────────────────────────────────────

    def update(self) -> None:
        """每帧调用，推进非阻塞指令，驱动当前协程。

        最多连续执行 `_max_advance` 条非阻塞指令，
        遇到阻塞指令或协程时停止等待下一帧。
        """
        if not self._running:
            return

        # ── 驱动当前协程（如有） ───────────────────────────
        if self._current is not None:
            try:
                next(self._current)
            except StopIteration:
                self._current = None
                self._pc += 1
            except Exception:
                logger.error("协程执行异常", exc_info=True)
                self._running = False
            return  # 协程未完成 → 下一帧继续

        # ── 推进非阻塞指令 ────────────────────────────────
        advance_count = 0
        while self._running and self._pc < len(self._commands):
            advance_count += 1
            if advance_count > self._max_advance:
                logger.error(
                    "脚本执行超过 %d 条连续指令，强制停止（可能死循环）",
                    self._max_advance,
                )
                self._running = False
                return

            cmd = self._commands[self._pc]

            # IfCommand —— 特殊处理：条件跳转
            if isinstance(cmd, IfCommand):
                self._handle_if(cmd)
                continue

            # JumpCommand —— 无条件跳转
            if isinstance(cmd, JumpCommand):
                self._handle_jump(cmd)
                continue

            # LabelCommand —— 跳过（仅标记）
            if isinstance(cmd, LabelCommand):
                self._pc += 1
                continue

            if cmd.blocking:
                # 阻塞命令：启动协程，等待下一帧
                try:
                    self._current = cmd.execute(self._game)
                except Exception:
                    logger.error("阻塞命令执行异常: %s", type(cmd).__name__, exc_info=True)
                    self._running = False
                return
            else:
                # 非阻塞命令：驱动协程到底
                try:
                    gen = cmd.execute(self._game)
                    next(gen)
                except StopIteration:
                    pass
                except Exception:
                    logger.error("非阻塞命令执行异常: %s", type(cmd).__name__, exc_info=True)
                    self._running = False
                    return
                self._pc += 1

        # 脚本结束
        if self._pc >= len(self._commands):
            self._running = False
            self._game.events.emit("scene_end")
            logger.debug("脚本执行完毕")

    # ── 跳转 ──────────────────────────────────────────────

    def jump(self, label: str) -> None:
        """跳转到指定标签。

        Args:
            label: 目标标签名。若不存在则停止执行。
        """
        self._game.events.emit("jump", label=label)
        if label in self._labels:
            self._pc = self._labels[label]
            self._current = None
            logger.debug("跳转到: %s (pc=%d)", label, self._pc)
        else:
            logger.error("跳转标签不存在: %s", label)
            self._running = False

    # ── 对话回传 ──────────────────────────────────────────

    def on_dialogue_next(self, **kwargs: Any) -> None:
        """玩家点击推进对话时调用（由 DIALOGUE_NEXT 事件触发）。"""
        self._waiting_dialogue = False

    # ── 选项回传 ──────────────────────────────────────────

    def on_choice_selected(self, index: int) -> None:
        """玩家选择了某选项后调用（由 UI 触发）。

        Args:
            index: 选择的选项索引（0-based）。
        """
        if not (0 <= self._pc < len(self._commands)):
            logger.warning("on_choice_selected 在无效 PC=%d 调用（命令数=%d）", self._pc, len(self._commands))
            return
        cmd = self._commands[self._pc]
        if not isinstance(cmd, ChoiceCommand):
            logger.warning("on_choice_selected 但当前命令不是 ChoiceCommand")
            return
        if 0 <= index < len(cmd.choices):
            _, _, label = cmd.choices[index]
            self._current = None
            self.jump(label)
        else:
            logger.error("选项索引无效: %d (共 %d 个选项)", index, len(cmd.choices))

    # ── 状态查询 ──────────────────────────────────────────

    @property
    def running(self) -> bool:
        """脚本是否正在运行。"""
        return self._running

    @property
    def current_command(self) -> Command | None:
        """当前命令。"""
        if 0 <= self._pc < len(self._commands):
            return self._commands[self._pc]
        return None

    @property
    def flags(self) -> dict[str, bool]:
        """运行时标志字典。"""
        return self._flags

    # ── 内部 ──────────────────────────────────────────────

    def _handle_if(self, cmd: IfCommand) -> None:
        """处理 IfCommand：真 → 执行下一条；假 → 跳过下一条。"""
        flag_value = self._flags.get(cmd.name, False)
        if not flag_value:
            # 假 → 跳过下一条（通常是 @jump）
            self._pc += 2
        else:
            # 真 → 正常执行下一条
            self._pc += 1

    def _handle_jump(self, cmd: JumpCommand) -> None:
        """处理 JumpCommand：无条件跳转。"""
        self.jump(cmd.label)
