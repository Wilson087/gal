"""
日志系统模块
============
统一日志输出，支持终端彩色显示和文件写入。
"""

import os
import sys
import traceback
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


# 全局终端/文件日志级别（由 init() 设置，Logger 实例共享）
_terminal_level: int = INFO
_file_level: int = DEBUG


class Logger:
    """日志器，每个模块持一个实例。

    debug 日志仅写入文件，终端只输出 info 及以上级别。
    可通过 init() 的 terminal_level / file_level 参数调整。
    """

    def __init__(self, name: str):
        self._name = name

    def _log(self, level: int, msg: str, *args) -> None:
        text = msg % args if args else msg

        if level >= _terminal_level:
            self._output_terminal(level, text)
        if level >= _file_level:
            self._output_file(level, text)

    def _output_terminal(self, level: int, text: str) -> None:
        """终端输出（带颜色）。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_name = _LEVEL_NAMES.get(level, "?")
        line = f"[{timestamp}] [{level_name}] [{self._name}] {text}"
        color = _LEVEL_COLORS.get(level, _WHITE)
        print(f"{color}{line}{_RESET}")

    def _output_file(self, level: int, text: str) -> None:
        """文件输出（完整时间戳，纯文本）。"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_name = _LEVEL_NAMES.get(level, "?")
        line = f"[{timestamp}] [{level_name}] [{self._name}] {text}"
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

    def exception(self, msg: str, *args) -> None:
        """记录异常信息（含调用栈，始终写入终端和文件）。"""
        text = msg % args if args else msg
        tb = traceback.format_exc()
        full = f"{text}\n{tb}" if tb else text
        # exception 始终输出，不受级别过滤
        self._output_terminal(ERROR, full)
        self._output_file(ERROR, full)


# ── 全局未捕获异常钩子 ─────────────────────────────────


def _global_exception_hook(exc_type, exc_value, exc_tb) -> None:
    """将未捕获的异常写入日志文件后再调用原始钩子。"""
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [FATAL] [System] 未捕获的异常:\n{tb_text}"
    os.makedirs(_LOG_DIR, exist_ok=True)
    try:
        with open(_get_log_file(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    # 终端输出错误摘要
    print(f"\033[91m[{timestamp}] [FATAL] [System] {exc_type.__name__}: {exc_value}\033[0m")
    # 调用原始钩子
    sys.__excepthook__(exc_type, exc_value, exc_tb)


# ── 初始化 ────────────────────────────────────────────────

def init(terminal_level: int = INFO, file_level: int = DEBUG) -> None:
    """初始化日志系统（启动时调用一次）。

    Args:
        terminal_level: 终端输出级别（默认 INFO，不显示 debug）。
        file_level: 文件输出级别（默认 DEBUG，记录全部日志）。
    """
    global _terminal_level, _file_level
    _terminal_level = terminal_level
    _file_level = file_level
    os.makedirs(_LOG_DIR, exist_ok=True)
    _clean_old_logs(30)
    # 注册全局未捕获异常钩子
    sys.excepthook = _global_exception_hook
    root = Logger("Init")
    root.info("日志系统初始化: 终端=%s 文件=%s",
              _LEVEL_NAMES.get(terminal_level, "?"),
              _LEVEL_NAMES.get(file_level, "?"))
