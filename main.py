#!/usr/bin/env python3
"""gal-lib-pyglet 视觉小说引擎启动入口。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.logger import init as log_init
from engine.app import AVGApplication


def main():
    log_init()
    app = AVGApplication()

    # 预先加载默认剧本（用于主菜单显示标题和版本）
    default_json = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "scripts", "harukanaru_sora.json")
    if os.path.exists(default_json):
        try:
            app.load_script(default_json)
        except Exception as e:
            print(f"加载默认剧本失败: {e}")

    app.show_main_menu()
    import pyglet
    pyglet.app.run()


if __name__ == "__main__":
    main()
