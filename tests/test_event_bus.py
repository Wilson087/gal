"""
EventBus 冒烟测试
=================
验证弱引用自动清理 + 错误隔离。
"""

from __future__ import annotations

import gc
import logging

from core.events import EventBus, Event


class _Listener:
    """测试用监听器类 —— 持有 bound method 回调。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def handle(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def test_weakref_cleanup() -> None:
    """注册回调 → 删对象 → gc → emit → 断言死引用已清理。"""
    bus = EventBus()

    obj = _Listener()
    bus.on(Event.UPDATE, obj.handle)
    bus.emit(Event.UPDATE, dt=0.016)
    assert len(obj.calls) == 1
    assert obj.calls[0]["dt"] == 0.016

    # 删除监听器对象，弱引用应失效
    del obj
    gc.collect()

    # emit 应触发惰性清理
    bus.emit(Event.UPDATE, dt=0.032)
    assert str(Event.UPDATE) not in bus._listeners


def test_error_isolation() -> None:
    """一个回调崩了，其他回调仍被调用。"""
    bus = EventBus()
    results: list[str] = []

    def bad_handler(**kwargs: object) -> None:
        raise RuntimeError("坏回调故意抛出的异常")

    def good_handler(**kwargs: object) -> None:
        results.append(str(kwargs.get("msg", "")))

    bus.on(Event.CLICK, bad_handler)
    bus.on(Event.CLICK, good_handler)
    bus.emit(Event.CLICK, x=100, y=200, msg="hello")

    assert results == ["hello"]


def test_off_unsubscribe() -> None:
    """退订后不再收到事件。"""
    bus = EventBus()
    results: list[str] = []

    def handler(**kwargs: object) -> None:
        results.append("fired")

    bus.on(Event.SAVE, handler)
    bus.emit(Event.SAVE, slot=1)
    assert len(results) == 1

    bus.off(Event.SAVE, handler)
    bus.emit(Event.SAVE, slot=2)
    assert len(results) == 1  # 不应再增长


def test_emit_empty() -> None:
    """对无监听器的事件 emit 不崩溃。"""
    bus = EventBus()
    bus.emit("nonexistent", data=42)  # 不应抛异常


def test_multiple_listeners() -> None:
    """同一事件多个监听器全部收到通知。"""
    bus = EventBus()
    a = _Listener()
    b = _Listener()
    bus.on(Event.DRAW, a.handle)
    bus.on(Event.DRAW, b.handle)
    bus.emit(Event.DRAW)
    assert len(a.calls) == 1
    assert len(b.calls) == 1


def test_event_enum_str() -> None:
    """Event 枚举转为小写蛇形字符串。"""
    assert str(Event.CLICK) == "click"
    assert str(Event.UPDATE) == "update"
    assert str(Event.DRAW) == "draw"
    assert str(Event.SCENE_START) == "scene_start"
    assert str(Event.DIALOGUE_COMPLETE) == "dialogue_complete"


def test_on_returns_callback() -> None:
    """on() 返回原回调供 off() 使用。"""
    bus = EventBus()

    def handler(**kwargs: object) -> None:
        pass

    cb = bus.on(Event.EXIT, handler)
    assert cb is handler
