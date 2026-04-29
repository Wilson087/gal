"""
常量配置模块
=============
定义窗口尺寸、颜色主题、字体、动画参数等。
"""

# ── 窗口 ──────────────────────────────────────────────────────
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

# ── 对话区域 ──────────────────────────────────────────────────
DIALOGUE_FRAME_HEIGHT = 180         # 170→180
DIALOGUE_PADDING = 30               # 20→30（内边距增大）
DIALOGUE_MARGIN_BOTTOM = 8          # 10→8
DIALOGUE_RADIUS = 24                # 新增：对话框圆角半径
DIALOGUE_MARGIN_H = 12              # 新增：对话框左右边距
SPEAKER_PILL_HEIGHT = 32            # 新增：名签高度
SPEAKER_PILL_OFFSET = 6             # 新增：名签突出对话框上方距离

# ── 文字速度（秒 / 字符） ──────────────────────────────────
DEFAULT_TEXT_SPEED = 0.04  # 40ms per char
TEXT_SPEED_MIN = 0.01
TEXT_SPEED_MAX = 0.2

# ── 角色名标签 ───────────────────────────────────────────────
CHARACTER_NAME_COLORS: dict[str, str] = {}
DEFAULT_SPEAKER_COLOR = (245, 245, 245, 255)      # 白色（名签内）
DEFAULT_NARRATOR_COLOR = (176, 190, 197, 255)     # B0BEC5（微提亮度）

# ── 字体 ──────────────────────────────────────────────────────
FONT_FAMILIES = ["Microsoft YaHei", "SimHei", "Microsoft YaHei UI", "sans-serif"]
FONT_SIZE_SPEAKER = 15             # 16→15
FONT_SIZE_DIALOGUE = 18            # 14→18（增大提升可读性）
FONT_SIZE_CHOICE = 18              # 14→18
FONT_SIZE_NEXT_INDICATOR = 14      # 12→14

# ── 颜色主题（RGBA 元组） ──────────────────────────────────
COLOR_BG_DARK       = (10, 10, 24, 255)     # 0A0A18
COLOR_DIALOGUE_BG   = (14, 14, 36, 224)     # 0E0E24E0（微减蓝色倾向）
COLOR_TEXT_PRIMARY  = (245, 245, 245, 255)   # F5F5F5
COLOR_TEXT_SPEAKER  = (255, 255, 255, 255)   # 白色（名签内文字）
COLOR_TEXT_SHADOW   = (0, 0, 0, 120)         # 新增：文字阴影色
COLOR_OVERLAY       = (255, 255, 255, 255)
COLOR_CHOICE_BG     = (255, 255, 255, 25)    # rgba white 10%
COLOR_CHOICE_HOVER  = (255, 255, 255, 46)    # rgba white 18%
COLOR_CHOICE_TEXT   = (245, 245, 245, 255)
COLOR_CHOICE_BORDER = (66, 165, 245, 255)    # #42A5F5（强调色）
COLOR_ACCENT        = (66, 165, 245, 255)    # #42A5F5（全局强调色）
COLOR_ACCENT_DIM    = (25, 118, 210, 255)    # #1976D2（深强调色）

# ── 转场效果类型 ─────────────────────────────────────────────
TRANSITION_CROSSFADE  = "crossfade"
TRANSITION_SLIDE_LEFT = "slide_left"
TRANSITION_SLIDE_RIGHT = "slide_right"
TRANSITION_BLINDS     = "blinds"
TRANSITION_RIPPLE     = "ripple"
TRANSITION_FLASH      = "flash"
TRANSITION_NONE       = "none"

DEFAULT_TRANSITION = TRANSITION_CROSSFADE
TRANSITION_DURATION = 0.6  # seconds

# ── 屏幕滤镜颜色 ─────────────────────────────────────────────
FILTER_NONE   = "none"
FILTER_SEPIA  = "sepia"
FILTER_NIGHT  = "night"
FILTER_MEMORY = "memory"

FILTER_COLORS = {
    FILTER_NONE:   None,
    FILTER_SEPIA:  (112, 66, 20),     # 褐色调
    FILTER_NIGHT:  (26, 42, 94),      # 夜蓝色
    FILTER_MEMORY: (74, 42, 74),      # 紫色回忆
}

# ── 立绘 ──────────────────────────────────────────────────────
CHAR_X_LEFT_RATIO = 0.22
CHAR_X_RIGHT_RATIO = 0.78
CHAR_Y_BOTTOM_MARGIN = 20
CHAR_FADE_DURATION = 0.3  # seconds

# ── 说话动画 ─────────────────────────────────────────────────
CHAR_SPEAK_FLOAT_AMOUNT = 6
CHAR_SPEAK_BOUNCE_STEPS = 4
CHAR_ANIMATION_INTERVAL = 0.1

# ── 占位立绘回退颜色 ──────────────────────────────────────────
PLACEHOLDER_COLORS = {
    "__demo_char_mystery__": (142, 68, 173),   # 8E44AD
    "__demo_char_girl__":    (233, 30, 99),    # E91E63
    "__demo_char_hero__":    (52, 152, 219),   # 3498DB
}

# ── 占位背景回退颜色 ──────────────────────────────────────────
PLACEHOLDER_BG_COLORS = {
    "__demo_bg_room__":  (44, 62, 80),    # 2C3E50
    "__demo_bg_valley__": (30, 132, 73),  # 1E8449
}

# ── 音频 ──────────────────────────────────────────────────────
BGM_VOLUME_DEFAULT = 0.8
SFX_VOLUME_DEFAULT = 1.0
VOICE_VOLUME_DEFAULT = 1.0

# ── scene.json 特殊 key（旧项目扩展字段） ─────────────────────
DIALOGUE_COLOR_KEY = "color"  # dialogue-entry 级文字颜色覆盖

# ── 资源路径 ──────────────────────────────────────────────────
RESOURCES_DIR = "resources"
IMAGES_DIR = f"{RESOURCES_DIR}/images"
AUDIO_DIR = "audio"
FONTS_DIR = f"{RESOURCES_DIR}/fonts"
