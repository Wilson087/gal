#!/usr/bin/env python3
"""
Visual Novel Engine V2.5 — 入口
================================
GameWindow（pyglet.window.Window）启动游戏主循环，驱动 Game 中枢。
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

import pyglet
from pyglet.window import key

from config import AppConfig
from core.game import Game

logger = logging.getLogger("v2.5")


def _setup_logging(config: AppConfig) -> None:
    """按 AppConfig 配置标准 logging。

    Args:
        config: 应用配置，其 log_level / log_file 决定输出。
    """
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if config.log_file:
        handlers.append(logging.FileHandler(config.log_file, encoding="utf-8"))
    logging.basicConfig(
        level=config.log_level,
        format="[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )


class GameWindow(pyglet.window.Window):  # type: ignore[misc]
    """V2.5 主窗口，继承 pyglet.window.Window。

    持有 Game 引擎实例，通过 pyglet.clock 以 60fps 驱动游戏循环。
    处理键盘 / 鼠标 / 焦点 / 全屏等 OS 窗口事件。
    """

    def __init__(self, config: AppConfig) -> None:
        super().__init__(
            width=config.width,
            height=config.height,
            caption=config.title,
            resizable=True,
            vsync=True,
        )
        self.set_minimum_size(640, 360)

        self._config: AppConfig = config
        self._game: Game = Game(config)

        # 60fps 游戏循环
        pyglet.clock.schedule_interval(self._game.update, 1.0 / 60.0)

        logger.info(
            "GameWindow 已创建: %dx%d, vsync=on, fps=60",
            config.width, config.height,
        )

    # ── 渲染 ──────────────────────────────────────────────

    def on_draw(self) -> None:
        """帧渲染。同时作为焦点恢复的检测点。

        焦点恢复检测原理：
            窗口失去焦点时，OS 停止向 pyglet 发送 draw 事件（窗口被隐藏
            或不再需要重绘）。焦点恢复后，OS 重新开始发送 draw 事件，
            因此 on_draw 的第一帧即为窗口重新激活的可靠信号。
        """
        if self._game.paused:
            self._game.paused = False
            logger.debug("Window reactivated — game resumed")

        self.clear()
        self._game.draw()

    # ── 输入 ──────────────────────────────────────────────

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        """键盘事件。

        - F11: 切换全屏。
        - ESC: 关闭窗口 / 退出。
        """
        if symbol == key.F11:
            self.set_fullscreen(not self.fullscreen)
            logger.info(
                "Fullscreen toggled: %s",
                "ON" if self.fullscreen else "OFF",
            )
        elif symbol == key.ESCAPE:
            logger.info("ESC pressed — exiting")
            self.on_close()

    def on_mouse_press(
        self, x: int, y: int, button: int, modifiers: int
    ) -> None:
        """鼠标点击 — 左键转发到 Game.on_click。"""
        if button == pyglet.window.mouse.LEFT:
            self._game.on_click(x, y)

    # ── 焦点 ──────────────────────────────────────────────

    def on_deactivate(self) -> None:
        """窗口失去焦点 — 暂停游戏逻辑。"""
        self._game.paused = True
        logger.debug("Window deactivated — game paused")

    # ── 窗口事件 ──────────────────────────────────────────

    def on_resize(self, width: int, height: int) -> None:
        """窗口缩放 — 通知子系统。"""
        super().on_resize(width, height)
        self._game.events.emit("resize", width=width, height=height)

    def on_close(self) -> None:
        """窗口关闭 — 释放资源并安全退出。"""
        logger.info("Window closing — releasing resources")
        pyglet.clock.unschedule(self._game.update)
        self._game.events.clear()
        pyglet.app.exit()
        super().on_close()


# ── 入口 ──────────────────────────────────────────────────

def main() -> None:
    """V2.5 引擎主入口。"""
    config = AppConfig()

    _setup_logging(config)

    logger.info("Starting Visual Novel Engine V2.5")
    window = GameWindow(config)
    pyglet.app.run()
    logger.info("Engine shut down normally")


if __name__ == "__main__":
    main()
