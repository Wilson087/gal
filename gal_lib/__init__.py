"""
╔══════════════════════════════════════════════════════════════════╗
║  gal_lib — 视觉小说游戏引擎（现代化版）                          ║
║  基于 Python tkinter 标准库，无第三方依赖                        ║
╚══════════════════════════════════════════════════════════════════╝

本包提供完整的视觉小说游戏引擎，包含剧本驱动对话系统、
立绘/背景渲染、选项分支、存档读档等核心功能，以及
富文本标记、角色说话动画、转场特效、屏幕滤镜、
粒子天气、多通道音频、增强存档等现代化特性。

使用示例:
    import tkinter as tk
    from gal_lib import VNGame, DEMO_SCRIPT

    root = tk.Tk()
    app = VNGame(root)
    app.load_script(DEMO_SCRIPT)
    app.start_game()
    root.mainloop()
"""

from .engine import VNGame
from .script import DEMO_SCRIPT
from .scriptbuilder import NovelScript, Scene, ScriptBase, ScriptScene
from .rich_text import parse_rich_text, strip_rich_tags, RichSegment

# 注册内置矢量图占位符
from . import vectorgraphics
vectorgraphics.register_defaults()

from .vectorgraphics import (
    load_all_vectors_from_package,
    load_all_images_from_package,
    register_png,
    register_from_resource,
    register_from_base64,
)

__all__ = ["VNGame", "DEMO_SCRIPT", "NovelScript", "Scene",
           "ScriptBase", "ScriptScene", "vectorgraphics",
           "load_all_vectors_from_package", "load_all_images_from_package",
           "register_png", "register_from_resource", "register_from_base64",
           "parse_rich_text", "strip_rich_tags", "RichSegment"]
__version__ = "2.0.0"
