"""
共享 mock 环境
==============
所有测试文件共用同一套 pyglet / PIL mock，
注入 sys.modules，避免跨文件 mock 冲突。

在需要 mock 的测试文件中通过 ``import tests._mocks`` 引入。
"""

import sys
from unittest.mock import MagicMock

# ── pyglet ─────────────────────────────────────────────────
_mock_pyglet = MagicMock()
_mock_pyglet.__path__ = []
_mock_pyglet.__spec__ = MagicMock()
_mock_pyglet_image = MagicMock()
_mock_pyglet_sprite = MagicMock()
_mock_pyglet_graphics = MagicMock()
_mock_pyglet_shapes = MagicMock()
_mock_pyglet_media = MagicMock()
_mock_pyglet_text = MagicMock()
_mock_pyglet_window = MagicMock()

sys.modules["pyglet"] = _mock_pyglet
sys.modules["pyglet.image"] = _mock_pyglet_image
sys.modules["pyglet.sprite"] = _mock_pyglet_sprite
sys.modules["pyglet.graphics"] = _mock_pyglet_graphics
sys.modules["pyglet.shapes"] = _mock_pyglet_shapes
sys.modules["pyglet.media"] = _mock_pyglet_media
sys.modules["pyglet.text"] = _mock_pyglet_text
sys.modules["pyglet.window"] = _mock_pyglet_window

_mock_pyglet.image = _mock_pyglet_image
_mock_pyglet.sprite = _mock_pyglet_sprite
_mock_pyglet.graphics = _mock_pyglet_graphics
_mock_pyglet.shapes = _mock_pyglet_shapes
_mock_pyglet.media = _mock_pyglet_media
_mock_pyglet.text = _mock_pyglet_text
_mock_pyglet.window = _mock_pyglet_window

# ── PIL ────────────────────────────────────────────────────
_mock_pil = MagicMock()
_mock_pil_image = MagicMock()
sys.modules["PIL"] = _mock_pil
sys.modules["PIL.Image"] = _mock_pil_image
