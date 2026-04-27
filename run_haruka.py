#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
夏空の轮廓 — 启动入口

运行方式:
    cd gal
    python run_haruka.py
"""

import sys
import os

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

import tkinter as tk
from gal_lib import VNGame
from my_game import constants  # 注册 PNG 素材到引擎


def main() -> None:
    root = tk.Tk()
    app = VNGame(root)
    app.first_scene = "room_afternoon"
    app.load_script("my_game/harukanaru_sora.json")
    app.start_game()
    root.mainloop()


if __name__ == "__main__":
    main()
