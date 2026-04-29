"""
对话历史记录模块
================
环形缓冲区记录所有对话，支持滚轮查阅和点击回溯。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .logger import Logger

log = Logger("History")


@dataclass
class HistoryEntry:
    """单条对话历史记录。"""
    speaker: str = ""
    text: str = ""
    scene_id: str = ""
    dialogue_index: int = 0


class HistoryManager:
    """对话历史管理器。

    环形缓冲区，最多保留 MAX_ENTRIES 条记录。
    支持点击任意条目回溯到该句。
    """

    MAX_ENTRIES = 1000

    def __init__(self) -> None:
        self._entries: list[HistoryEntry] = []
        self._start = 0  # 环形缓冲区起始位置

        # 回调：用户点击回溯时触发
        self._on_jump_callback: Optional[Callable[[HistoryEntry], None]] = None

    def set_on_jump(self, callback: Callable[[HistoryEntry], None]) -> None:
        """设置点击回溯的回调。"""
        self._on_jump_callback = callback

    def record(self, speaker: str, text: str,
               scene_id: str, dialogue_index: int) -> None:
        """记录一条对话历史。

        Args:
            speaker: 说话角色名。
            text: 对话文本。
            scene_id: 当前场景 ID。
            dialogue_index: 对话索引。
        """
        entry = HistoryEntry(
            speaker=speaker,
            text=text,
            scene_id=scene_id,
            dialogue_index=dialogue_index,
        )

        if len(self._entries) < self.MAX_ENTRIES:
            self._entries.append(entry)
        else:
            self._entries[self._start] = entry
            self._start = (self._start + 1) % self.MAX_ENTRIES
        log.debug("历史记录: [%d] %s: %s", len(self.get_entries()) - 1, speaker or "(旁白)", text[:30])

    def get_entries(self) -> list[HistoryEntry]:
        """获取所有历史记录（按时间顺序）。"""
        if len(self._entries) < self.MAX_ENTRIES:
            return list(self._entries)
        return (self._entries[self._start:] +
                self._entries[:self._start])

    def get_last_n(self, n: int) -> list[HistoryEntry]:
        """获取最近 N 条记录。"""
        entries = self.get_entries()
        return entries[-n:]

    def jump_to_entry(self, entry: HistoryEntry) -> None:
        """跳转到指定回溯点。

        Args:
            entry: 要回溯到的 HistoryEntry。
        """
        if self._on_jump_callback:
            self._on_jump_callback(entry)

    def clear(self) -> None:
        """清空所有历史记录。"""
        self._entries.clear()
        self._start = 0
