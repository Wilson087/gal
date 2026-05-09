"""
Visual Novel Engine V2.5 — 全局配置
=====================================
所有魔术字符串和可调参数的单一来源。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

# ── 引擎常量 ──────────────────────────────────────────────

WINDOW_WIDTH: int = 1280
WINDOW_HEIGHT: int = 720
RESOURCE_ROOT: str = "resources"
DATA_ROOT: str = RESOURCE_ROOT
SAVE_PATH: str = "saves"
LOG_PATH: str = "logs"
DEFAULT_TITLE: str = "Visual Novel Engine V2.5"
TARGET_FPS: int = 60
MAX_SCRIPT_ADVANCE: int = 1000
MAX_SAVE_SLOTS: int = 100

# 鉴赏模式
GALLERY_DATA: str = "resources/data/gallery.json"
MUSIC_DATA: str = "resources/data/music.json"
CHARACTER_DATA: str = "resources/data/characters.json"

# 脚本
SCRIPT_ROOT: str = "resources/scripts"


# ── 应用配置 ──────────────────────────────────────────────

@dataclass
class AppConfig:
    """V2.5 引擎运行时配置。

    所有字段均有默认值，用户可在构造时覆盖。
    """

    width: int = WINDOW_WIDTH
    height: int = WINDOW_HEIGHT
    title: str = DEFAULT_TITLE
    debug: bool = False
    log_level: int = logging.INFO
    log_file: str | None = None
    resource_root: str = RESOURCE_ROOT
    save_path: str = SAVE_PATH
    gallery_data: str = GALLERY_DATA
    music_data: str = MUSIC_DATA
    character_data: str = CHARACTER_DATA
    script_root: str = SCRIPT_ROOT
