"""
gal-lib-pyglet: 基于 pyglet 的现代视觉小说引擎。
"""

from .app import AVGApplication
from .core.variable import VariableBank
from .core.script_loader import load_from_file, validate_script
from .core.rich_text import parse_rich_text, strip_rich_tags, RichSegment
from .audio.audio import AudioEngine
from .scene.scene_manager import SceneManager
from .ui.dialogue import DialogueSystem
from .ui.choice import ChoiceSystem
from .render.character import CharacterManager
from .render.effects import EffectSystem
from .core.logger import Logger, init as log_init

__version__ = "0.1.0"
