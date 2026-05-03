"""
Script Commands — 命令抽象基类 + 11 种具体命令
================================================
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Generator

if TYPE_CHECKING:
    from core.game import Game

class Command(ABC):
    """脚本命令抽象基类。

    Attributes:
        blocking: True = 等待玩家点击后继续；False = 自动连续执行。
    """

    blocking: bool = True

    @abstractmethod
    def execute(self, game: Game) -> Generator[None, None, None]:
        """执行命令，可 yield 暂停等待下一帧。"""
        yield  # pragma: no cover


class SceneCommand(Command):
    """切换场景。"""

    blocking = False

    def __init__(self, scene_id: str) -> None:
        self.scene_id = scene_id

    def execute(self, game: Game) -> Generator[None, None, None]:
        game.events.emit("scene_start", scene_id=self.scene_id)
        yield

    def __repr__(self) -> str:
        return f"SceneCommand({self.scene_id!r})"


class BGMCommand(Command):
    """播放 / 切换 BGM。"""

    blocking = False

    def __init__(self, track: str) -> None:
        self.track = track

    def execute(self, game: Game) -> Generator[None, None, None]:
        game.events.emit("audio:bgm", track=self.track)
        yield

    def __repr__(self) -> str:
        return f"BGMCommand({self.track!r})"


class ShowCommand(Command):
    """显示角色立绘。"""

    blocking = False

    def __init__(self, char: str, pose: str, position: str) -> None:
        self.char = char
        self.pose = pose
        self.position = position

    def execute(self, game: Game) -> Generator[None, None, None]:
        game.events.emit(
            "show", char=self.char, pose=self.pose, position=self.position,
        )
        yield

    def __repr__(self) -> str:
        return f"ShowCommand({self.char!r}, {self.pose!r}, {self.position!r})"


class HideCommand(Command):
    """隐藏角色立绘。"""

    blocking = False

    def __init__(self, char: str) -> None:
        self.char = char

    def execute(self, game: Game) -> Generator[None, None, None]:
        game.events.emit("hide", char=self.char)
        yield

    def __repr__(self) -> str:
        return f"HideCommand({self.char!r})"


class DialogueCommand(Command):
    """显示对话文本，等待玩家点击后继续。"""

    blocking = True

    def __init__(self, speaker: str, text: str, voice: str | None = None) -> None:
        self.speaker = speaker
        self.text = text
        self.voice = voice

    def execute(self, game: Game) -> Generator[None, None, None]:
        game.events.emit(
            "dialogue", speaker=self.speaker, text=self.text, voice=self.voice,
        )
        game.script_executor._waiting_dialogue = True
        yield  # 第一帧：让 DialogBox 初始化打字机
        # 等待玩家点击推进（由 ScriptExecutor._on_dialogue_next 清除标志）
        while game.script_executor._waiting_dialogue:
            yield

    def __repr__(self) -> str:
        return f"DialogueCommand({self.speaker!r}, {self.text[:20]!r})"


class ChoiceCommand(Command):
    """显示选项，等待玩家选择后跳转。

    Fields:
        choices: 选项列表，每项为 (文本, 动作, 标签)。
            - 文本: 选项显示文字
            - 动作: 目前仅支持 "jump"
            - 标签: 跳转目标标签名
    """

    blocking = True

    def __init__(self, choices: list[tuple[str, str, str]]) -> None:
        if not choices:
            raise ValueError("ChoiceCommand 至少需要一个选项")
        self.choices = choices

    def execute(self, game: Game) -> Generator[None, None, None]:
        choice_data = [
            {"text": text, "action": action, "label": label}
            for text, action, label in self.choices
        ]
        game.events.emit("choice", options=choice_data)
        
        game.script_executor._waiting_choice = True

        yield  # 等待玩家选择，UI 回传后由 executor 处理跳转

        while game.script_executor._waiting_choice:
            yield

    def __repr__(self) -> str:
        return f"ChoiceCommand(choices={len(self.choices)})"


class LabelCommand(Command):
    """跳转标签（标记位置，无执行逻辑）。"""

    blocking = False

    def __init__(self, label: str) -> None:
        self.label = label

    def execute(self, game: Game) -> Generator[None, None, None]:
        yield

    def __repr__(self) -> str:
        return f"LabelCommand({self.label!r})"


class JumpCommand(Command):
    """无条件跳转到标签。"""

    blocking = False

    def __init__(self, label: str) -> None:
        self.label = label

    def execute(self, game: Game) -> Generator[None, None, None]:
        game.events.emit("jump", label=self.label)
        yield

    def __repr__(self) -> str:
        return f"JumpCommand({self.label!r})"


class FlagCommand(Command):
    """设置布尔变量。"""

    blocking = False

    def __init__(self, name: str, value: bool) -> None:
        self.name = name
        self.value = value

    def execute(self, game: Game) -> Generator[None, None, None]:
        if game.variable_bank is not None:
            game.variable_bank[self.name] = self.value
        yield

    def __repr__(self) -> str:
        return f"FlagCommand({self.name!r} = {self.value})"


class IfCommand(Command):
    """条件判断：真 → 执行下一条命令；假 → 跳过下一条。"""

    blocking = False

    def __init__(self, name: str) -> None:
        self.name = name

    def execute(self, game: Game) -> Generator[None, None, None]:
        yield

    def __repr__(self) -> str:
        return f"IfCommand({self.name!r})"


class EndCommand(Command):
    """场景结束标记。"""

    blocking = True

    def execute(self, game: Game) -> Generator[None, None, None]:
        game.events.emit("scene_end")
        yield

    def __repr__(self) -> str:
        return "EndCommand()"
