"""时空回廊 — 自定义角色与背景占位符（回退颜色）及资源加载。"""
from gal_lib.constants import PLACEHOLDER_COLORS, PLACEHOLDER_BG_COLORS

# ── 注册调色板（回退用） ────────────────────────────────────────
PLACEHOLDER_COLORS["__my_char_protagonist__"] = ("#3498DB", "林夕")
PLACEHOLDER_COLORS["__my_char_mystery__"]    = ("#8E44AD", "???")
PLACEHOLDER_COLORS["__my_char_companion__"]  = ("#E91E63", "艾达")

PLACEHOLDER_BG_COLORS["__my_bg_lab__"]       = ("#2C3E50", "时空实验室")
PLACEHOLDER_BG_COLORS["__my_bg_garden__"]    = ("#1E8449", "记忆庭院")
PLACEHOLDER_BG_COLORS["__my_bg_corridor__"]  = ("#5D4E37", "无限回廊")


# ── 从独立 JSON 文件加载矢量图定义 ──────────────────────────────
from gal_lib.vectorgraphics import load_all_vectors_from_package

_VECTOR_PACKAGE = "my_game.resources.vectors"
_loaded = load_all_vectors_from_package(_VECTOR_PACKAGE)
if _loaded:
    print(f"[my_game] 已注册 {len(_loaded)} 个矢量图: {', '.join(_loaded)}")

# ── 注册《夏空の轮廓》PNG 素材 ──────────────────────────────────
from gal_lib.vectorgraphics import register_png

register_png("家-卧室", "my_game.resources.images", "家-卧室.png", width=1920, height=1080)
register_png("家-客厅", "my_game.resources.images", "家-客厅.png", width=1920, height=1080)
register_png("家-门口", "my_game.resources.images", "家-门口.png", width=1920, height=1080)

# 穹·哥特装（S=全身远景, M=半身中景, L=特写近景）
register_png("春日野穹-哥特服装-S",    "my_game.resources.images", "春日野穹-哥特服装-S.png", width=403, height=522)
register_png("春日野穹-哥特服装-S-开心", "my_game.resources.images", "春日野穹-哥特服装-S-开心.png", width=403, height=522)
register_png("春日野穹-哥特服装-S-不悦", "my_game.resources.images", "春日野穹-哥特服装-S-不悦.png", width=403, height=522)
register_png("春日野穹-哥特服装-M",    "my_game.resources.images", "春日野穹-哥特服装-M.png", width=557, height=528)
register_png("春日野穹-哥特服装-L",    "my_game.resources.images", "春日野穹-哥特服装-L.png", width=956, height=608)

# ── 音频资源说明 ────────────────────────────────────────────────
# 将音频文件放入 audio/ 目录（项目根目录），
# 在剧本中用相对路径引用即可，例如:
#   场景设置: bgm="my_bgm.mp3"
#   对白设置: sfx="click.wav"
# 支持的格式取决于后端:
#   ffplay (推荐) — mp3, ogg, flac, wav, m4a, opus, wma ...
#   winsound      — 仅 .wav
# 安装 FFmpeg (ffplay) 即可解锁所有格式。
