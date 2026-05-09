"""
Save Data — 存档数据容器
=========================
纯数据 dataclass，不包含任何 pyglet 对象，只存储资源标识符。
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field


@dataclass
class CharEntry:
    """单个角色立绘状态。"""

    char_id: str = ""
    pose: str = ""
    position: str = "center"
    opacity: int = 255

    def to_dict(self) -> dict[str, object]:
        return {
            "char_id": self.char_id,
            "pose": self.pose,
            "position": self.position,
            "opacity": self.opacity,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> CharEntry:
        return cls(
            char_id=str(d.get("char_id", "")),
            pose=str(d.get("pose", "")),
            position=str(d.get("position", "center")),
            opacity=int(d.get("opacity", 255)),  # type: ignore[call-overload]
        )


@dataclass
class SaveData:
    """引擎存档数据。

    纯数据容器——序列化到 JSON，不含 pyglet 对象。
    未来新增字段通过 ``version`` 迁移兼容。
    """

    # 元信息
    version: int = 2
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now().isoformat()
    )

    # 脚本进度
    script_file: str = ""
    label_name: str = ""
    line_index: int = 0

    # 运行时状态
    flags: dict[str, bool] = field(default_factory=dict)
    vars: dict[str, int] = field(default_factory=dict)

    # 画面
    background_id: str = ""
    characters_on_screen: list[CharEntry] = field(default_factory=list)

    # 音频
    bgm_file: str = ""

    # 对话历史
    dialogue_history: list[dict[str, str]] = field(default_factory=list)

    # 好感度（v2 新增）
    char_affection: dict[str, int] = field(default_factory=dict)

    # 扩展
    extra_data: dict[str, object] = field(default_factory=dict)

    # ── 序列化 ──────────────────────────────────────────

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "script_file": self.script_file,
            "label_name": self.label_name,
            "line_index": self.line_index,
            "flags": self.flags,
            "vars": self.vars,
            "background_id": self.background_id,
            "characters_on_screen": [c.to_dict() for c in self.characters_on_screen],
            "bgm_file": self.bgm_file,
            "dialogue_history": self.dialogue_history,
            "char_affection": self.char_affection,
            "extra_data": self.extra_data,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> SaveData:
        chars_raw = d.get("characters_on_screen", [])
        if isinstance(chars_raw, list):
            chars = [CharEntry.from_dict(c) for c in chars_raw]
        else:
            chars = []

        return cls(
            version=int(d.get("version", 1)),  # type: ignore[call-overload]
            timestamp=str(d.get("timestamp", "")),
            script_file=str(d.get("script_file", "")),
            label_name=str(d.get("label_name", "")),
            line_index=int(d.get("line_index", 0)),  # type: ignore[call-overload]
            flags=dict(d.get("flags", {})),  # type: ignore[call-overload]
            vars=dict(d.get("vars", {})),  # type: ignore[call-overload]
            background_id=str(d.get("background_id", "")),
            characters_on_screen=chars,
            bgm_file=str(d.get("bgm_file", "")),
            dialogue_history=list(d.get("dialogue_history", [])),  # type: ignore[call-overload]
            char_affection=dict(d.get("char_affection", {})),  # type: ignore[call-overload]
            extra_data=dict(d.get("extra_data", {})),  # type: ignore[call-overload]
        )
