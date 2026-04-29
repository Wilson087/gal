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
SAVE_PATH: str = "saves"
LOG_PATH: str = "logs"
DEFAULT_TITLE: str = "Visual Novel Engine V2.5"
TARGET_FPS: int = 60


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
