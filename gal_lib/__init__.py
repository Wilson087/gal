"""
╔══════════════════════════════════════════════════════════════════╗
║  gal_lib — 视觉小说游戏引擎                                     ║
║  基于 Python tkinter 标准库，无第三方依赖                        ║
╚══════════════════════════════════════════════════════════════════╝

本包提供完整的视觉小说游戏引擎，包含剧本驱动对话系统、
立绘/背景渲染、选项分支、存档读档等核心功能。

使用示例:
    import tkinter as tk
    from gal_lib import VNGame, DEMO_SCRIPT

    root = tk.Tk()
    app = VNGame(root)
    app.load_script(DEMO_SCRIPT)
    app.start_game()
    root.mainloop()

构建剧本（类/函数方式）:
    from gal_lib.scriptbuilder import NovelScript, Scene

    script = NovelScript("我的游戏")
    scene = Scene("start", bg="...", left="...")
    scene.dialogue("角色", "对白")
    script.add_scene(scene)
    app.load_script(script.build())

继承方式:
    from gal_lib.scriptbuilder import ScriptBase, ScriptScene

    class Opening(ScriptScene):
        id = "start"; bg = "..."; left = "..."
        def define(self):
            self.say("角色", "对白")
            self.ask(("继续", "next"),)

    class MyGame(ScriptBase):
        title = "我的游戏"
        scenes = [Opening]
    app.load_script(MyGame().build())
"""

from .engine import VNGame
from .script import DEMO_SCRIPT
from .scriptbuilder import NovelScript, Scene, ScriptBase, ScriptScene

# 注册内置矢量图占位符
from . import vectorgraphics
vectorgraphics.register_defaults()

# 重新导出资源加载函数
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
           "register_png", "register_from_resource", "register_from_base64"]
__version__ = "1.0.0"
