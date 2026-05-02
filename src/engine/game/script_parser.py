"""
脚本解析器
===

解析游戏脚本并驱动剧情执行。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Generator, Sequence, Mapping
from enum import Enum, auto
from itertools import count
from typing import Any, Optional, Self
from weakref import WeakSet, finalize

class BuildCommand(Enum):
    PUSH = auto()
    POP = auto()
    DICT = auto()
    SEQ = auto()
    BUILD = auto()

BC = BuildCommand

class Data:
    @abstractmethod
    def build(self, out: Generator[None, tuple[BuildCommand, Any], Any]) -> None: ...

    @staticmethod
    def _to_value() -> Generator[None, tuple[BuildCommand, Any], Any]:
        stack = deque()
        try:
            while True:
                c, v = yield
                match c:
                    case BC.PUSH:
                        stack.append(v)
                    case BC.POP:
                        stack.pop()
                    case BC.DICT | BC.SEQ:
                        stack.append(c)
                    case BC.BUILD:
                        vs = deque()
                        while True:
                            v = stack.pop()
                            if v == BC.DICT:
                                stack.append(dict(vs))
                                break
                            elif v == BC.SEQ:
                                stack.append((*vs,))
                                break
                            else:
                                vs.appendleft(v)
        finally:
            if stack:
                return stack[0]

    @classmethod
    def to_value(cls):
        g = cls._to_value()
        next(g)
        return g

class Persona(Data):
    name: Optional[str] = None
    color: str = "#000000"

    _obj_id: int
    _dialogue: Dialogue

    def say(self, text: str):
        self._dialogue._out.send((BC.PUSH, {
            "type": "say",
            "params": {
                "id": self._obj_id,
                "text": text
            }
        }))

    def build(self, out: Generator[None, tuple[BuildCommand, Any], Any]) -> None:
        out.send((BC.DICT, None))
        out.send((BC.PUSH, ("id", type(self).__name__)))
        out.send((BC.PUSH, ("name", self.name)))
        out.send((BC.PUSH, ("color", self.color)))
        out.send((BC.BUILD, None))

class Scene(Data):
    name: Optional[str] = None

    _obj_id: int
    _dialogue: Dialogue

    def build(self, out: Generator[None, tuple[BuildCommand, Any], Any]) -> None:
        out.send((BC.DICT, None))
        out.send((BC.PUSH, ("id", type(self).__name__)))
        out.send((BC.PUSH, ("name", self.name)))
        out.send((BC.BUILD, None))

class Dialogue(Data):
    _persona_count: count[int]
    _personas: WeakSet[Persona]

    def _del_persona(self, _id: int):
        self._out.send((BC.PUSH, {
            "type": "del_persona",
            "params": {
                "id": _id
            }
        }))

    def persona(self, persona: type[Persona]) -> Persona:
        if not self._personas:
            self._persona_count = count()

        _id = next(self._persona_count)

        p = persona()
        p._dialogue = self
        p._obj_id = _id

        self._out.send((BC.PUSH, {
            "type": "persona",
            "params": {
                "id": _id,
                "persona": persona.__name__,
            }
        }))

        self._personas.add(p)
        finalize(p, self._del_persona, _id)
        return p
    
    _scene_count: count[int]
    _scenes: WeakSet[Scene]

    def _del_scene(self, _id: int):
        self._out.send((BC.PUSH, {
            "type": "del_scene",
            "params": {
                "id": _id
            }
        }))

    def scene(self, scene: type[Scene]):
        if not self._scenes:
            self._scene_count = count()

        _id = next(self._scene_count)

        s = scene()
        s._dialogue = self
        s._obj_id = _id

        self._out.send((BC.PUSH, {
            "type": "scene",
            "params": {
                "id": _id,
                "scene": scene.__name__,
            }
        }))

        self._scenes.add(s)
        finalize(s, self._del_scene, _id)
        return s
    
    def narration(self, text: str):
        self._out.send((BC.PUSH, {
            "type": "narration",
            "params": {
                "text": text
            }
        }))

    def build(self, out: Generator[None, tuple[BuildCommand, Any], Any]) -> None:
        out.send((BC.DICT, None))
        out.send((BC.PUSH, ("id", type(self).__name__)))

        out.send((BC.SEQ, None))
        out.send((BC.PUSH, "dialogue"))
        out.send((BC.SEQ, None))
        self._persona_count = count()
        self._personas = WeakSet()
        self._scene_count = count()
        self._scenes = WeakSet()
        self._out = out
        self.flow()
        out.send((BC.BUILD, None))
        out.send((BC.BUILD, None))

        out.send((BC.BUILD, None))

    def flow(self):
        pass
