"""时空回廊 — 视觉小说游戏包

基于 gal_lib 引擎、ScriptBuilder 继承方式编写的独立剧本。
"""

import tkinter as tk
from gal_lib import VNGame

from . import constants  # noqa: F401
from .script import CorridorOfTime


def run() -> None:
    """启动游戏。"""
    root = tk.Tk()
    app = VNGame(root)
    app.load_script(CorridorOfTime().build())
    app.start_game()  # 显示主菜单
    root.mainloop()


if __name__ == "__main__":
    run()
