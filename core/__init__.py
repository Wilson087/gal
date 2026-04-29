"""Visual Novel Engine V2.5 — Core package."""

from .events import EventBus, Event
from .game import Game

__all__ = ["EventBus", "Event", "Game"]
