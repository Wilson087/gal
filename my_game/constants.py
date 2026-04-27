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
