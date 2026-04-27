"""
常量配置模块
=============
定义窗口尺寸、颜色主题、字体、动画参数、立绘/背景占位映射等。
"""

from pathlib import Path

# ── 窗口 ──────────────────────────────────────────────────────
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 450

# ── 对话区域 ──────────────────────────────────────────────────
DIALOGUE_FRAME_HEIGHT = 170

# ── 文字速度（毫秒 / 字符） ──────────────────────────────────
DEFAULT_TEXT_SPEED = 40

# ── 动画间隔 ──────────────────────────────────────────────────
BG_FADE_INTERVAL = 60       # 背景过渡每步间隔（ms）
CHAR_FADE_INTERVAL = 50     # 立绘过渡每步间隔（ms）

# ── 字体 ──────────────────────────────────────────────────────
FONT_SPEAKER  = ("微软雅黑", 16, "bold")
FONT_DIALOGUE = ("微软雅黑", 13)
FONT_BUTTON   = ("微软雅黑", 14)
FONT_UI       = ("微软雅黑", 12)
FONT_TITLE    = ("微软雅黑", 36, "bold")
FONT_SUBTITLE = ("微软雅黑", 18)

# ── 立绘尺寸 ──────────────────────────────────────────────────
CHAR_WIDTH  = 170
CHAR_HEIGHT = 400

# ── 颜色主题 ──────────────────────────────────────────────────
COLOR_BG_DARK        = "#0a0a1a"
COLOR_DIALOGUE_BG    = "#12122a"
COLOR_TEXT_PRIMARY   = "#ecf0f1"
COLOR_TEXT_SPEAKER   = "#e74c3c"
COLOR_TEXT_ACCENT    = "#f1c40f"
COLOR_OVERLAY        = "#ffffff"
COLOR_CHOICE_BG      = "#1e1e3f"
COLOR_CHOICE_HOVER   = "#2d2d5e"
COLOR_CHOICE_TEXT    = "#ecf0f1"
COLOR_CHOICE_BORDER  = "#e74c3c"
COLOR_BUTTON_SAVE    = "#27ae60"
COLOR_BUTTON_LOAD    = "#2980b9"

# ── 占位立绘映射 ──────────────────────────────────────────────
PLACEHOLDER_COLORS = {
    "__demo_char_mystery__": ("#8E44AD", "???"),
    "__demo_char_girl__":    ("#E91E63", "星野"),
    "__demo_char_hero__":    ("#3498DB", "主角"),
}

# ── 占位背景映射 ──────────────────────────────────────────────
PLACEHOLDER_BG_COLORS = {
    "__demo_bg_room__":  ("#2C3E50", "昏暗的房间"),
    "__demo_bg_valley__": ("#1E8449", "星落之谷"),
}

# ── 存档 ──────────────────────────────────────────────────────
SAVE_DIR          = Path("saves")
SAVE_FILE_TEMPLATE = "save_{}.dat"

# ── 立绘淡入淡出 stipple 序列 ─────────────────────────────────
FADE_OUT_STEPPLES = ["", "gray75", "gray50", "gray25", "gray12"]
FADE_IN_STEPPLES  = ["gray12", "gray25", "gray50", "gray75", ""]

# ── 背景过渡 stipple 序列 ────────────────────────────────────
BG_FADE_IN_STEPPLES  = ["gray12", "gray25", "gray50", "gray75", ""]
BG_FADE_OUT_STEPPLES = ["gray75", "gray50", "gray25", "gray12"]
