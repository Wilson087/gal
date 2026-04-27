#!/usr/bin/env python3
"""时空回廊 — 启动入口

用法:
    cd gal
    python run_my_game.py
"""

import sys
import os

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from my_game import run

if __name__ == "__main__":
    run()
