"""
Game — 引擎中枢
================
持有所有子系统引用和事件总线，提供 update / draw / on_click 入口。

子系统依赖关系（构造顺序 / Layer）
-----------------------------------
::

    Layer 0: variable_bank      — 无依赖，全局变量存储
    Layer 1: resource_manager   — 无依赖，资源加载 / 缓存
    Layer 2: audio              — 依赖 resource_manager（加载音频文件）
    Layer 3: save_system        — 依赖 variable_bank（序列化变量）
    Layer 4: script_executor    — 依赖 variable_bank + scene_manager
    Layer 5: scene_manager      — 依赖 resource_manager（加载场景资源）
    Layer 6: character_manager  — 依赖 resource_manager（立绘）
    Layer 7: dialogue_system    — 依赖 scene_manager + character_manager
    Layer 8: choice_system      — 依赖 scene_manager
    Layer 9: effect_system      — 无依赖，纯渲染
    Layer10: ui_manager         — 依赖 dialogue + choice + save
    Layer10: layers             — 依赖以上全部（组合渲染）

- 构造顺序：Layer 0 → 10（先无依赖，后组合）。
- draw() 顺序：Layer 0 → 10 自底向上（背景 → 角色 → UI）。
- update() 顺序：Layer 0 → 10 自顶向下。
"""

from __future__ import annotations

import logging
from typing import Any

from config import AppConfig
from .events import EventBus, Event

logger = logging.getLogger(__name__)


class Game:
    """引擎中枢 —— 持有事件总线和所有子系统引用。

    Game 类是纯 Python，不依赖 pyglet。所有渲染 / 输入由
    main.py 的 GameWindow 转发到本类的 on_click / update / draw。
    """

    def __init__(self, config: AppConfig) -> None:
        self.config: AppConfig = config
        self.events: EventBus = EventBus()
        self._paused: bool = False

        # ── 子系统占位（Layer 顺序） ──────────────────────
        # Layer 0 — 无依赖
        self.variable_bank: Any = None
        self.resource_manager: Any = None

        # Layer 2 — 依赖 resource_manager
        self.audio: Any = None

        # Layer 3 — 依赖 variable_bank
        self.save_system: Any = None

        # Layer 4 — 依赖 variable_bank + scene_manager
        self.script_executor: Any = None

        # Layer 5 — 依赖 resource_manager
        self.scene_manager: Any = None

        # Layer 6 — 依赖 resource_manager
        self.character_manager: Any = None

        # Layer 7 — 依赖 scene_manager + character_manager
        self.dialogue_system: Any = None

        # Layer 8 — 依赖 scene_manager
        self.choice_system: Any = None

        # Layer 9 — 无依赖
        self.effect_system: Any = None

        # Layer 10 — 依赖多个上层模块
        self.ui_manager: Any = None
        self.layers: Any = None

        logger.info(
            "Game 实例已创建: %dx%d, debug=%s",
            config.width, config.height, config.debug,
        )

    # ── 游戏循环入口 ──────────────────────────────────────

    def on_click(self, x: int, y: int) -> None:
        """处理鼠标点击。

        Args:
            x: 窗口坐标 X。
            y: 窗口坐标 Y。
        """
        self.events.emit(Event.CLICK, x=x, y=y)

    def update(self, dt: float) -> None:
        """推进游戏逻辑 dt 秒（由 pyglet @ 60fps 驱动）。

        paused 时跳过所有逻辑，仅维持帧渲染。

        Args:
            dt: 上一帧到本帧的 delta 时间（秒）。
        """
        if self._paused:
            return
        self.events.emit(Event.UPDATE, dt=dt)

    def draw(self) -> None:
        """渲染一帧。子系统按 Layer 0 → 10 顺序绘制。"""
        self.events.emit(Event.DRAW)

    # ── 暂停 ──────────────────────────────────────────────

    @property
    def paused(self) -> bool:
        """游戏是否暂停（窗口失焦等）。"""
        return self._paused

    @paused.setter
    def paused(self, value: bool) -> None:
        if value != self._paused:
            self._paused = value
            logger.debug("Game %s", "paused" if value else "resumed")

    # ── 子系统注册 ────────────────────────────────────────

    def register(self, name: str, subsystem: Any) -> None:
        """按属性名注册子系统。

        Args:
            name: 子系统属性名（如 ``"audio"``）。
            subsystem: 子系统实例。

        Raises:
            AttributeError: 若 name 不是预设的子系统槽位。
        """
        if not hasattr(self, name):
            raise AttributeError(f"未知的子系统槽位: {name}")
        setattr(self, name, subsystem)
        logger.debug("子系统 '%s' 已注册", name)

    def init_subsystems(self) -> None:
        """按依赖顺序初始化所有子系统（V2.5 后续实现）。

        当前占位：所有子系统保持 None，由后续模块调用 register() 注入。
        """
        # TODO: Layer 0 — 无依赖
        # self.variable_bank = VariableBank()
        # self.resource_manager = ResourceManager(self.config.resource_root)

        # TODO: Layer 2 — 依赖 resource_manager
        # self.audio = AudioEngine(self.resource_manager)

        # TODO: Layer 3 — 依赖 variable_bank
        # self.save_system = SaveSystem(self.variable_bank, self.config.save_path)

        # TODO: Layer 4-10 — 逐层注入
        pass
