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
from pyglet.window import mouse

from config import AppConfig
from core.events import Event
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

        self._app_config: AppConfig = config
        self._game: Game = Game(config)

        # 初始化所有子系统
        self._game.init_subsystems(window=self)

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
        - 其余按键: 转发到 EventBus，由 UI 等子系统消费。
        """
        if symbol == key.F11:
            self.set_fullscreen(not self.fullscreen)
            logger.info(
                "Fullscreen toggled: %s",
                "ON" if self.fullscreen else "OFF",
            )
        elif symbol == key.ESCAPE:
            # 鉴赏模式中 ESC 返回上一状态，否则退出
            if not self._game.handle_escape():
                logger.info("ESC pressed — exiting")
                self.on_close()
        else:
            self._game.events.emit(
                Event.KEY_PRESS, symbol=symbol, modifiers=modifiers
            )

    def on_mouse_press(
        self, x: int, y: int, button: int, modifiers: int
    ) -> None:
        """鼠标点击 — 左键转发到 Game.on_click。"""
        if button == mouse.LEFT:
            self._game.on_click(x, y)

    def on_mouse_scroll(
        self, x: int, y: int, scroll_x: float, scroll_y: float
    ) -> None:
        """鼠标滚轮 — 转发到 EventBus。"""
        self._game.events.emit(
            "scroll", x=x, y=y, scroll_x=scroll_x, scroll_y=scroll_y
        )

    def on_mouse_motion(
        self, x: int, y: int, dx: int, dy: int
    ) -> None:
        """鼠标移动 — 按状态分发，不走 EventBus 避免每帧广播。"""
        self._game.handle_mouse_motion(x, y)

    def on_mouse_drag(
        self, x: int, y: int, dx: int, dy: int,
        buttons: int, modifiers: int,
    ) -> None:
        """鼠标拖动 — 按状态分发（用于设置面板滑块）。"""
        self._game.handle_mouse_drag(x, y, buttons, modifiers)

    def on_mouse_release(
        self, x: int, y: int, button: int, modifiers: int
    ) -> None:
        """鼠标释放 — 按状态分发（结束滑块拖动）。"""
        self._game.handle_mouse_release(x, y)

    # ── 焦点 ──────────────────────────────────────────────

    def on_deactivate(self) -> None:
        """窗口失去焦点 — 暂停游戏逻辑。"""
        self._game.paused = True
        logger.debug("Window deactivated — game paused")

    # ── 窗口事件 ──────────────────────────────────────────

    def on_resize(self, width: int, height: int) -> None:
        """窗口缩放 — 通知子系统。"""
        super().on_resize(width, height)
        self._game.events.emit(Event.RESIZE, width=width, height=height)

    def on_close(self) -> None:
        """窗口关闭 — 释放资源并安全退出。"""
        logger.info("Window closing — releasing resources")
        pyglet.clock.unschedule(self._game.update)
        self._game.shutdown()
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
