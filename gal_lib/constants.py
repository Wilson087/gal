"""
常量配置模块
=============
定义窗口尺寸、颜色主题、字体、动画参数、立绘/背景占位映射等。
"""

from pathlib import Path

# ── 窗口 ──────────────────────────────────────────────────────
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080
WINDOW_MIN_WIDTH = 960
WINDOW_MIN_HEIGHT = 540

# ── 对话区域 ──────────────────────────────────────────────────
DIALOGUE_FRAME_HEIGHT = 170
DIALOG_POSITION_BOTTOM = "bottom"
DIALOG_POSITION_TOP = "top"
DIALOG_POSITION_FULL = "fullscreen"
DEFAULT_DIALOG_POSITION = DIALOG_POSITION_BOTTOM

# ── 文字速度（毫秒 / 字符） ──────────────────────────────────
DEFAULT_TEXT_SPEED = 40
TEXT_SPEED_MIN = 10
TEXT_SPEED_MAX = 200

# ── 角色名标签 ───────────────────────────────────────────────
CHARACTER_NAME_COLORS = {
    # key=角色名, value=颜色十六进制
}
DEFAULT_SPEAKER_COLOR = "#e74c3c"  # 默认角色名颜色（红）
DEFAULT_NARRATOR_COLOR = "#7f8c8d"  # 旁白颜色（灰）

# ── 动画间隔 ──────────────────────────────────────────────────
BG_FADE_INTERVAL = 60       # 背景过渡每步间隔（ms）
CHAR_FADE_INTERVAL = 50     # 立绘过渡每步间隔（ms）

# ── 字体 ──────────────────────────────────────────────────────
FONT_SPEAKER_LIST = ["微软雅黑", "SimHei", "Microsoft YaHei UI", "Segoe UI", "sans-serif"]
FONT_DIALOGUE_LIST = ["微软雅黑", "SimHei", "Microsoft YaHei UI", "Segoe UI", "sans-serif"]
FONT_SPEAKER  = ("微软雅黑", 16, "bold")
FONT_DIALOGUE = ("微软雅黑", 13)
FONT_BUTTON   = ("微软雅黑", 14)
FONT_UI       = ("微软雅黑", 12)
FONT_TITLE    = ("微软雅黑", 36, "bold")
FONT_SUBTITLE = ("微软雅黑", 18)

# ── 立绘尺寸 ──────────────────────────────────────────────────
CHAR_WIDTH  = 170
CHAR_HEIGHT = 400

# ── 角色说话动画 ─────────────────────────────────────────────
CHAR_SPEAK_FLOAT_AMOUNT = 6       # 说话时上下浮动像素
CHAR_SPEAK_PULSE_SCALE = 1.03     # 说话时缩放脉冲倍率
CHAR_ANIMATION_INTERVAL = 100     # 立绘动画刷新间隔（ms）
CHAR_SPEAK_BOUNCE_STEPS = 4       # 浮动动画的关键帧数

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
COLOR_BUTTON_DANGER  = "#c0392b"

# ── 屏幕滤镜颜色 ─────────────────────────────────────────────
FILTER_NONE = "none"
FILTER_SEPIA = "sepia"
FILTER_NIGHT = "night"
FILTER_MEMORY = "memory"

FILTER_COLORS = {
    FILTER_NONE:   None,
    FILTER_SEPIA:  "#704214",   # 褐色调
    FILTER_NIGHT:  "#1a2a5e",   # 夜蓝色
    FILTER_MEMORY: "#4a2a4a",   # 紫色回忆
}

# ── 转场效果类型 ─────────────────────────────────────────────
TRANSITION_CROSSFADE  = "crossfade"
TRANSITION_SLIDE_LEFT = "slide_left"
TRANSITION_SLIDE_RIGHT = "slide_right"
TRANSITION_BLINDS     = "blinds"
TRANSITION_RIPPLE     = "ripple"
TRANSITION_NONE       = "none"

DEFAULT_TRANSITION = TRANSITION_CROSSFADE
TRANSITION_DURATION = 600  # ms

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
SAVE_DIR           = Path("saves")
SAVE_FILE_TEMPLATE = "save_{}.dat"
SAVE_THUMB_DIR     = Path("saves") / "thumbs"
MAX_SAVE_SLOTS     = 100
SAVE_SLOTS_PER_PAGE = 12
AUTO_SAVE_SLOT     = "auto"    # 自动存档占用此 ID
QUICK_SAVE_SLOT    = "quick"   # 快速存档占用此 ID
AUTO_SAVE_INTERVAL = 60000     # 自动存档间隔（ms）
SAVE_THUMB_WIDTH   = 200
SAVE_THUMB_HEIGHT  = 112

# ── 音频 ──────────────────────────────────────────────────────
AUDIO_DIR         = Path("audio")
VOICE_DIR         = Path("voice")
DEFAULT_VOLUME    = 100
DEFAULT_VOLUME_BGM   = 80
DEFAULT_VOLUME_SFX   = 100
DEFAULT_VOLUME_VOICE = 100
BGM_ENABLED       = True
SFX_ENABLED       = True
VOICE_ENABLED     = True
CROSSFADE_DURATION = 1500    # BGM 交叉淡入淡出时长（ms）
CROSSFADE_STEPS    = 15      # 淡入淡出步数

# ── 自动模式 ─────────────────────────────────────────────────
AUTO_DEFAULT_DELAY = 1500    # 自动模式默认等待时间（ms）
AUTO_CHAR_DELAY    = 50      # 每字符额外增加等待（ms）
AUTO_VOICE_WAIT    = 300     # 语音结束后额外等待（ms）

# ── 立绘淡入淡出 stipple 序列 ─────────────────────────────────
FADE_OUT_STEPPLES = ["", "gray75", "gray50", "gray25", "gray12"]
FADE_IN_STEPPLES  = ["gray12", "gray25", "gray50", "gray75", ""]

# ── 背景过渡 stipple 序列 ────────────────────────────────────
BG_FADE_IN_STEPPLES  = ["gray12", "gray25", "gray50", "gray75", ""]
BG_FADE_OUT_STEPPLES = ["gray75", "gray50", "gray25", "gray12"]
