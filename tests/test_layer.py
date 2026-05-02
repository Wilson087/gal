"""
LayerManager 单元测试
=====================
全 mock pyglet，零 GPU 依赖。
mock 环境由 tests/conftest.py 统一注入。
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from graphics.layer import LayerManager, Layer

# 引用 conftest 注入的 mock（模块级）
_mock_pyglet = sys.modules["pyglet"]
_mock_pyglet_sprite = sys.modules["pyglet.sprite"]
_mock_pyglet_shapes = sys.modules["pyglet.shapes"]


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_mocks() -> None:
    """每个测试前重置 mock 状态。"""
    for key in ("pyglet", "pyglet.image", "pyglet.sprite",
                "pyglet.graphics", "pyglet.shapes"):
        sys.modules[key].reset_mock()
    _mock_pyglet.image = sys.modules["pyglet.image"]  # type: ignore[attr-defined]
    _mock_pyglet.sprite = _mock_pyglet_sprite  # type: ignore[attr-defined]
    _mock_pyglet.graphics = sys.modules["pyglet.graphics"]  # type: ignore[attr-defined]
    _mock_pyglet.shapes = _mock_pyglet_shapes  # type: ignore[attr-defined]
    s = MagicMock()
    s._delete = False
    _mock_pyglet_sprite.Sprite.side_effect = None
    _mock_pyglet_sprite.Sprite.return_value = s
    _mock_pyglet_shapes.Rectangle.side_effect = None
    _mock_pyglet_shapes.Rectangle.return_value = MagicMock()


@pytest.fixture
def mock_sprite_cls() -> MagicMock:
    """Mock pyglet.sprite.Sprite 构造器。"""
    sprite = MagicMock()
    sprite.x = 0.0
    sprite.y = 0.0
    sprite.opacity = 255
    sprite.scale = 1.0
    sprite.rotation = 0.0
    sprite._delete = False
    _mock_pyglet_sprite.Sprite.return_value = sprite
    return sprite


@pytest.fixture
def lm() -> LayerManager:
    return LayerManager(width=1280, height=720)


# ── 1. 添加/移除精灵 ────────────────────────────────────

def test_show_remove_sprite(lm: LayerManager) -> None:
    mock_img = MagicMock()
    mock_img.width = 64
    mock_img.height = 64
    actor = lm.show_sprite(Layer.MID, mock_img, (640, 360))
    assert len(lm._sprites[Layer.MID]) == 1

    lm.remove_sprite(actor)
    assert len(lm._sprites[Layer.MID]) == 0


# ── 2. 设置背景替换旧背景 ─────────────────────────────────

def test_set_background_replaces(lm: LayerManager) -> None:
    mock_img = MagicMock()
    mock_img.width = 1280
    mock_img.height = 720
    lm.set_background(mock_img)
    assert lm._bg_actor is not None

    mock_img2 = MagicMock()
    mock_img2.width = 1280
    mock_img2.height = 720
    lm.set_background(mock_img2)
    # 旧背景应已被替换
    assert lm._bg_actor is not None


# ── 3. clear_all ──────────────────────────────────────────

def test_clear_all(lm: LayerManager) -> None:
    mock_img = MagicMock()
    mock_img.width = 64
    mock_img.height = 64
    lm.set_background(mock_img)
    lm.show_sprite(Layer.MID, mock_img, (100, 100))
    lm.show_sprite(Layer.UI, mock_img, (200, 200))
    lm.clear_all()

    assert lm._bg_actor is None
    for layer in Layer:
        assert len(lm._sprites[layer]) == 0


# ── 4. 重复移除不崩溃 ────────────────────────────────────

def test_duplicate_remove(lm: LayerManager) -> None:
    mock_img = MagicMock()
    mock_img.width = 64
    mock_img.height = 64
    actor = lm.show_sprite(Layer.MID, mock_img, (100, 100))
    lm.remove_sprite(actor)
    lm.remove_sprite(actor)  # 不应崩溃


# ── 5. fade_out 创建 overlay ─────────────────────────────

def test_fade_out_creates_overlay(lm: LayerManager) -> None:
    mock_rect = MagicMock()
    _mock_pyglet_shapes.Rectangle.return_value = mock_rect

    lm.fade_out(1.0)
    assert lm._overlay is not None
    assert lm._fade_tween is not None
    assert lm._fade_tween.target == 255


# ── 6. fade_in 创建 overlay ──────────────────────────────

def test_fade_in_creates_overlay(lm: LayerManager) -> None:
    mock_rect = MagicMock()
    _mock_pyglet_shapes.Rectangle.return_value = mock_rect

    lm.fade_in(1.0)
    assert lm._overlay is not None
    assert lm._fade_tween is not None
    assert lm._fade_tween.target == 0


# ── 7. fade_out 自定义颜色 ────────────────────────────────

def test_fade_custom_color(lm: LayerManager) -> None:
    lm.fade_out(1.0, color=(255, 255, 255))
    # overlay 被创建
    assert lm._overlay is not None
    assert lm._fade_tween is not None
    assert lm._fade_tween.target == 255


# ── 8. update 驱动 actor ──────────────────────────────────

def test_update_drives_actors(lm: LayerManager) -> None:
    mock_img = MagicMock()
    mock_img.width = 64
    mock_img.height = 64
    actor = lm.show_sprite(Layer.MID, mock_img, (100, 100))
    # 设置动画
    actor.move_to(200, 200, 0.5)
    lm.update(0.3)
    # 动画已推进
    assert actor._tweens["x"].elapsed > 0


# ── 9. 图层排序 ──────────────────────────────────────────

def test_layer_ordering() -> None:
    """OrderedGroup 的 order 值与 Layer 枚举一致。"""
    assert Layer.BG.value == 0
    assert Layer.BEHIND.value == 1
    assert Layer.MID.value == 2
    assert Layer.FRONT.value == 3
    assert Layer.EFFECTS.value == 4
    assert Layer.UI.value == 5


# ── 10. Layer 枚举值 ──────────────────────────────────────

def test_layer_enum_values() -> None:
    layers = list(Layer)
    assert len(layers) == 6
    values = [l.value for l in layers]
    assert values == [0, 1, 2, 3, 4, 5]


# ── 11. fade_out 重复调用释放旧 overlay ─────────────────

def test_fade_out_replaces_overlay(lm: LayerManager) -> None:
    """连续两次 fade_out：第二次覆盖第一次，tween 重置。"""
    lm.fade_out(1.0)
    assert lm._overlay is not None
    assert lm._fade_tween is not None
    assert lm._fade_tween.duration == 1.0

    lm.fade_out(2.0)
    assert lm._fade_tween is not None
    assert lm._fade_tween.duration == 2.0


# ── 12. update 自动清除已删除 actor ──────────────────────

def test_update_prunes_deleted_actors(lm: LayerManager) -> None:
    mock_img = MagicMock()
    mock_img.width = 64
    mock_img.height = 64
    actor = lm.show_sprite(Layer.MID, mock_img, (100, 100))
    # 模拟外部直接 delete 不调 remove_sprite
    actor._deleted = True
    lm.update(0.016)
    # 已删除 actor 应被自动移除
    assert actor not in lm._sprites[Layer.MID]


# ── 13. 特效占位方法不崩溃 ───────────────────────────────

def test_effect_stubs_noop(lm: LayerManager) -> None:
    lm.fog(0.5)
    lm.screen_shake(10, 0.3)
    # 不抛异常
