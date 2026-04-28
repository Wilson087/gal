"""
日志系统模块
============
统一日志输出，支持终端彩色显示和文件写入。
"""

import os
import sys
from datetime import datetime

# 日志级别
DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40

_LEVEL_NAMES = {DEBUG: "DEBUG", INFO: "INFO", WARNING: "WARN", ERROR: "ERROR"}

# ── ANSI 颜色（Windows 终端兼容） ─────────────────────────
_RESET = "\033[0m"
_GRAY = "\033[90m"
_WHITE = "\033[97m"
_YELLOW = "\033[93m"
_RED = "\033[91m"

_LEVEL_COLORS = {DEBUG: _GRAY, INFO: _WHITE, WARNING: _YELLOW, ERROR: _RED}

_LOG_DIR = "logs"
_LOG_FILE = None  # 按天延迟创建


def _get_log_file() -> str:
    """获取今天的日志文件路径。"""
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(_LOG_DIR, f"gal_{today}.log")
    return path


def _clean_old_logs(days: int = 30) -> None:
    """清理超过 days 天的旧日志。"""
    if not os.path.isdir(_LOG_DIR):
        return
    now = datetime.now().timestamp()
    for f in os.listdir(_LOG_DIR):
        if not f.startswith("gal_") or not f.endswith(".log"):
            continue
        path = os.path.join(_LOG_DIR, f)
        try:
            if os.path.getmtime(path) < now - days * 86400:
                os.remove(path)
        except OSError:
            pass


class Logger:
    """日志器，每个模块持一个实例。

    用法:
        log = Logger("Scene")
        log.info("剧本加载完成, %d 个场景", 5)
    """

    def __init__(self, name: str, level: int = INFO):
        self._name = name
        self._level = level

    def _log(self, level: int, msg: str, *args) -> None:
        if level < self._level:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_name = _LEVEL_NAMES.get(level, "?")
        text = msg % args if args else msg

        # 格式: [时间] [级别] [模块名] 消息
        line = f"[{timestamp}] [{level_name}] [{self._name}] {text}"

        # 终端输出（带颜色）
        color = _LEVEL_COLORS.get(level, _WHITE)
        print(f"{color}{line}{_RESET}")

        # 文件输出（纯文本）
        os.makedirs(_LOG_DIR, exist_ok=True)
        try:
            with open(_get_log_file(), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def debug(self, msg: str, *args) -> None:
        self._log(DEBUG, msg, *args)

    def info(self, msg: str, *args) -> None:
        self._log(INFO, msg, *args)

    def warning(self, msg: str, *args) -> None:
        self._log(WARNING, msg, *args)

    def warn(self, msg: str, *args) -> None:
        self._log(WARNING, msg, *args)

    def error(self, msg: str, *args) -> None:
        self._log(ERROR, msg, *args)


# ── 初始化 ────────────────────────────────────────────────

def init(level: int = INFO) -> None:
    """初始化日志系统（启动时调用一次）。"""
    os.makedirs(_LOG_DIR, exist_ok=True)
    _clean_old_logs(30)
    root = Logger("Init")
    root.info("日志系统初始化, 级别=%s", _LEVEL_NAMES.get(level, "?"))
