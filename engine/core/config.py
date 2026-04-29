"""
全局配置管理模块
================
用户可调配置的持久化（JSON），封装显示/音频/文本/游戏性等配置分类。
"""

import json
import os
import typing
from dataclasses import dataclass, field, asdict, fields
from typing import Optional

from .logger import Logger

log = Logger("Config")

_CONFIG_FILE = "config.json"


@dataclass
class DisplayConfig:
    """显示设置"""
    window_mode: str = "windowed"       # windowed, borderless, fullscreen
    width: int = 1280
    height: int = 720
    bg_fit_mode: str = "cover"          # cover, fit, stretch, original
    ui_scale: float = 1.0
    show_fps: bool = False
    window_x: Optional[int] = None      # 上次窗口位置
    window_y: Optional[int] = None


@dataclass
class AudioConfig:
    """音频设置"""
    master_volume: float = 1.0
    bgm_volume: float = 0.8
    sfx_volume: float = 1.0
    voice_volume: float = 1.0
    master_mute: bool = False
    bgm_mute: bool = False
    sfx_mute: bool = False
    voice_mute: bool = False


@dataclass
class TextConfig:
    """文本设置"""
    text_speed: float = 0.04        # seconds per char
    auto_speed: float = 3.0         # seconds between auto lines
    skip_mode: str = "read"         # read, all, off
    font_size: float = 14.0


@dataclass
class GameplayConfig:
    """游戏性设置"""
    text_backtrack: bool = True
    auto_hide_ui: bool = True
    click_sound: bool = False


@dataclass
class ShortcutConfig:
    """快捷键设置"""
    show: bool = True                # 设置面板中显示快捷键列表


class GameConfig:
    """全局配置，管理 JSON 持久化。"""

    def __init__(self) -> None:
        self.display = DisplayConfig()
        self.audio = AudioConfig()
        self.text = TextConfig()
        self.gameplay = GameplayConfig()
        self.shortcut = ShortcutConfig()
        self._loaded = False

    def load(self) -> "GameConfig":
        """从 config.json 加载配置，文件不存在则返回默认。"""
        if not os.path.exists(_CONFIG_FILE):
            log.debug("配置文件不存在，使用默认配置")
            self._loaded = True
            return self
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._merge(data)
            log.debug("配置加载完成")
        except (json.JSONDecodeError, KeyError, TypeError):
            log.debug("配置文件损坏，使用默认配置")
            pass
        self._loaded = True
        return self

    def save(self) -> None:
        """保存配置到 config.json。"""
        data = {
            "display": asdict(self.display),
            "audio": asdict(self.audio),
            "text": asdict(self.text),
            "gameplay": asdict(self.gameplay),
            "shortcut": asdict(self.shortcut),
        }
        tmp = _CONFIG_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, _CONFIG_FILE)
            log.debug("配置已保存")
        except OSError:
            pass

    def _merge(self, data: dict) -> None:
        """从字典递归合并到当前配置。"""
        for section_name, section_obj in [
            ("display", self.display),
            ("audio", self.audio),
            ("text", self.text),
            ("gameplay", self.gameplay),
            ("shortcut", self.shortcut),
        ]:
            raw = data.get(section_name, {})
            if not isinstance(raw, dict):
                continue

            # 获取 dataclass 字段的声明类型注释
            type_hints = typing.get_type_hints(section_obj.__class__)

            for key, value in raw.items():
                if not hasattr(section_obj, key):
                    continue
                if value is None:
                    setattr(section_obj, key, None)
                    continue

                declared = type_hints.get(key, type(None))
                # 解开 Optional[X] → X（取 Union 中非 None 的第一个类型）
                origin = getattr(declared, "__origin__", None)
                if origin is typing.Union:
                    args = declared.__args__
                    declared = next((a for a in args if a is not type(None)), declared)

                if declared is float and isinstance(value, (int, float)):
                    setattr(section_obj, key, float(value))
                elif declared is int and isinstance(value, (int, float)):
                    setattr(section_obj, key, int(value))
                elif declared is bool and isinstance(value, bool):
                    setattr(section_obj, key, value)
                elif declared is str and isinstance(value, str):
                    setattr(section_obj, key, value)

    @property
    def effective_bgm_volume(self) -> float:
        if self.audio.master_mute or self.audio.bgm_mute:
            return 0.0
        return self.audio.master_volume * self.audio.bgm_volume

    @property
    def effective_sfx_volume(self) -> float:
        if self.audio.master_mute or self.audio.sfx_mute:
            return 0.0
        return self.audio.master_volume * self.audio.sfx_volume

    @property
    def effective_voice_volume(self) -> float:
        if self.audio.master_mute or self.audio.voice_mute:
            return 0.0
        return self.audio.master_volume * self.audio.voice_volume
