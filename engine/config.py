"""
全局配置管理模块
================
用户可调配置的持久化（JSON），封装显示/音频/文本/游戏性等配置分类。
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

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
            self._loaded = True
            return self
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._merge(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # 损坏则使用默认
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
            for key, value in raw.items():
                if hasattr(section_obj, key):
                    # 类型转换
                    expected_type = type(getattr(section_obj, key))
                    if expected_type == float and isinstance(value, (int, float)):
                        setattr(section_obj, key, float(value))
                    elif expected_type == int and isinstance(value, (int, float)):
                        setattr(section_obj, key, int(value))
                    elif expected_type == bool and isinstance(value, bool):
                        setattr(section_obj, key, value)
                    elif expected_type == str and isinstance(value, str):
                        setattr(section_obj, key, value)
                    elif value is None and expected_type in (type(None), Optional):
                        setattr(section_obj, key, None)

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
