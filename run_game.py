#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉小说游戏 — 启动入口
========================

运行方式:
    cd gal
    python run_game.py

依赖: 仅 Python 标准库 (tkinter, json, pickle)
"""

import sys
import os

# 确保项目根目录在 sys.path 中（使 gal_lib 可导入）
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

import tkinter as tk
from gal_lib import VNGame, DEMO_SCRIPT


def main() -> None:
    """创建窗口、初始化引擎、加载演示剧本、启动游戏循环。"""
    root = tk.Tk()
    app = VNGame(root)
    app.load_script(DEMO_SCRIPT)
    app.start_game()

    # 标题画面点击绑定（等 Canvas 尺寸就绪）
    app.canvas.after(100,
                     lambda: app.canvas.bind("<Button-1>", app._on_title_click))

    root.mainloop()


if __name__ == "__main__":
    main()
