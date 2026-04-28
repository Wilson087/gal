"""
gal-lib-pyglet: 基于 pyglet 的现代视觉小说引擎。
"""

from .app import AVGApplication
from .variable import VariableBank
from .script_loader import load_from_file, validate_script
from .rich_text import parse_rich_text, strip_rich_tags, RichSegment
from .audio import AudioEngine
from .scene_manager import SceneManager
from .dialogue import DialogueSystem
from .choice import ChoiceSystem
from .character import CharacterManager
from .effects import EffectSystem
from .logger import Logger, init as log_init

__version__ = "0.1.0"
