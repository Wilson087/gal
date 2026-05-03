"""
Event Bus — 观察者模式 pub/sub（弱引用）
========================================
支持 emit / on / off，弱引用防内存泄漏，错误隔离。

用法::

    from core.events import EventBus, Event

    bus = EventBus()
    bus.on(Event.CLICK, my_handler)
    bus.emit(Event.CLICK, x=100, y=200)
    bus.off(Event.CLICK, my_handler)

事件名可以用 Event 枚举（推荐，IDE 自动补全）或裸字符串。
"""

from __future__ import annotations

import logging
import weakref
from enum import Enum, auto
from typing import Any, Callable

logger = logging.getLogger(__name__)

CallbackType = Callable[..., None]


class Event(Enum):
    """预定义引擎事件。

    自动转换为小写蛇形字符串名，如 ``Event.CLICK`` → ``"click"``。
    子系统也可用裸字符串注册自定义事件。
    """

    # 引擎生命周期
    INIT = auto()
    UPDATE = auto()
    DRAW = auto()
    EXIT = auto()

    # 输入
    CLICK = auto()
    KEY_PRESS = auto()

    # 窗口
    RESIZE = auto()
    FOCUS_LOST = auto()
    FOCUS_GAINED = auto()

    # 场景
    SCENE_START = auto()
    SCENE_END = auto()

    # 对话
    DIALOGUE_NEXT = auto()
    DIALOGUE_COMPLETE = auto()

    # 存档
    SAVE = auto()
    LOAD = auto()

    def __str__(self) -> str:
        return self.name.lower()


class GameState(Enum):
    """引擎全局状态 — 控制输入分发和更新焦点。"""

    TITLE = auto()
    NOVEL = auto()
    CG_GALLERY = auto()
    MUSIC_ROOM = auto()
    CHARACTER_VIEWER = auto()
    SETTINGS = auto()


class EventBus:
    """事件总线 — 观察者模式的弱引用实现。

    特性：
    - 弱引用：监听器对象被删除后，回调自动失效，不阻止 GC。
    - 惰性清理：死引用在 emit() 时自动回收，无后台线程。
    - 错误隔离：单个回调异常不影响其他监听器。

    警告：
        内联 lambda（如 ``bus.on("e", lambda **kw: ...)``）会在 emit 前被 GC。
        调用方必须持有 lambda 的强引用，或改用具名函数 / bound method。
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[weakref.ReferenceType]] = {}  # type: ignore[type-arg]

    # ── 订阅 ──────────────────────────────────────────────

    def on(self, event_name: str | Event, callback: CallbackType) -> CallbackType:
        """注册事件监听器。

        Args:
            event_name: 事件名（Event 枚举或字符串）。
            callback:  回调函数。若为 bound method 则用 WeakMethod 包装。

        Returns:
            原 callback，供 off() 退订时使用。
        """
        name = str(event_name)
        wr = self._make_weak(callback)
        if name not in self._listeners:
            self._listeners[name] = []
        self._listeners[name].append(wr)
        logger.debug("订阅: event=%r cb=%r", name, callback)
        return callback

    # ── 退订 ──────────────────────────────────────────────

    def off(self, event_name: str | Event, callback: CallbackType) -> None:
        """移除指定事件的某个监听器（按身份比对）。

        Args:
            event_name: 事件名。
            callback:   on() 时使用的同一回调对象。
        """
        name = str(event_name)
        if name not in self._listeners:
            return
        before = len(self._listeners[name])
        # 使用函数 / 实例身份比较，而非 bound-method 身份
        kept: list[weakref.ReferenceType] = []  # type: ignore[type-arg]
        for wr in self._listeners[name]:
            resolved = self._resolve(wr)
            if resolved is None:
                continue
            if resolved is callback:
                continue
            if hasattr(resolved, "__func__") and hasattr(callback, "__func__"):
                # 比较底层函数和实例以解决 bound-method 重创建问题
                rf: Any = resolved
                cf: Any = callback
                if rf.__func__ is cf.__func__ and rf.__self__ is cf.__self__:
                    continue
            kept.append(wr)
        self._listeners[name] = kept
        if not self._listeners[name]:
            del self._listeners[name]
        else:
            after = len(self._listeners[name])
            if after < before:
                logger.debug("退订: event=%r removed=%d remaining=%d", name, before - after, after)

    # ── 触发 ──────────────────────────────────────────────

    def emit(self, event_name: str | Event, **kwargs: Any) -> None:
        """触发事件，将 **kwargs 传递给所有监听器。

        自动清理已失效的弱引用。单个回调抛出异常时记录日志后继续。

        Args:
            event_name: 事件名。
            **kwargs:   传递给回调的关键字参数。
        """
        name = str(event_name)
        if name not in self._listeners:
            return

        stale: list[int] = []
        for i, wr in enumerate(self._listeners[name]):
            cb = self._resolve(wr)
            if cb is None:
                stale.append(i)
                continue
            try:
                cb(**kwargs)
            except Exception:
                logger.error("事件 %r 回调 %r 异常:", name, cb, exc_info=True)

        if stale:
            self._listeners[name] = [
                wr
                for i, wr in enumerate(self._listeners[name])
                if i not in stale
            ]
            if not self._listeners[name]:
                del self._listeners[name]

    # ── 清空 ──────────────────────────────────────────────

    def clear(self) -> None:
        """移除所有事件的所有监听器。关闭引擎时调用。"""
        count = sum(len(v) for v in self._listeners.values())
        self._listeners.clear()
        logger.debug("事件总线已清空: %d 个监听器", count)

    # ── 内部 ──────────────────────────────────────────────

    @staticmethod
    def _make_weak(cb: CallbackType) -> weakref.ReferenceType:  # type: ignore[type-arg]
        """为回调创建合适的弱引用包装。"""
        if hasattr(cb, "__self__") and cb.__self__ is not None:  # pyright: ignore[reportFunctionMemberAccess]
            return weakref.WeakMethod(cb)
        return weakref.ref(cb)

    @staticmethod
    def _resolve(wr: weakref.ReferenceType) -> CallbackType | None:  # type: ignore[type-arg]
        """解析弱引用，返回存活回调或 None。"""
        return wr()
