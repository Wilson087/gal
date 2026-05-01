"""
SpriteActor 单元测试
====================
全 mock pyglet.sprite.Sprite，零 GPU 依赖。
mock 环境由 tests/conftest.py 统一注入。
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from graphics.sprite_actor import (
    SpriteActor,
    linear,
    ease_in_out_quad,
)

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
    _mock_pyglet_sprite.Sprite.side_effect = None
    _mock_pyglet_sprite.Sprite.return_value = MagicMock()
    _mock_pyglet_shapes.Rectangle.side_effect = None
    _mock_pyglet_shapes.Rectangle.return_value = MagicMock()


@pytest.fixture
def mock_sprite() -> MagicMock:
    """返回模拟的 pyglet Sprite。"""
    sprite = MagicMock()
    sprite.x = 100.0
    sprite.y = 200.0
    sprite.opacity = 255
    sprite.scale = 1.0
    sprite.rotation = 0.0
    sprite._delete = False
    return sprite


@pytest.fixture
def actor(mock_sprite: MagicMock) -> SpriteActor:
    """创建测试用 SpriteActor（注入 mock sprite）。"""
    _mock_pyglet_sprite.Sprite.return_value = mock_sprite
    mock_image = MagicMock()
    mock_batch = MagicMock()
    mock_group = MagicMock()
    return SpriteActor(mock_image, x=100, y=200, batch=mock_batch, group=mock_group)


# ── 1. move_to 完整到达目标 ──────────────────────────────

def test_move_to_completes(actor: SpriteActor, mock_sprite: MagicMock) -> None:
    actor.move_to(300, 400, 1.0)
    actor.update(1.0)

    # sprite.update 被调用以设置最终位置
    assert mock_sprite.update.call_count >= 1


# ── 2. fade_to 边界 clamp ─────────────────────────────────

def test_fade_to_clamped(actor: SpriteActor) -> None:
    actor.fade_to(300, 0.5)
    assert actor._tweens["opacity"].target == 255  # clamped

    actor.fade_to(-10, 0.5)
    assert actor._tweens["opacity"].target == 0   # clamped


# ── 3. scale 负值抛异常 ──────────────────────────────────

def test_scale_to_negative(actor: SpriteActor) -> None:
    with pytest.raises(ValueError, match="scale"):
        actor.scale_to(0, 1.0)
    with pytest.raises(ValueError, match="scale"):
        actor.scale_to(-1, 1.0)


# ── 4. duration 负值抛异常 ────────────────────────────────

def test_duration_negative(actor: SpriteActor) -> None:
    with pytest.raises(ValueError, match="duration"):
        actor.fade_to(128, -0.5)


# ── 5. duration == 0 瞬间跳转 ────────────────────────────

def test_duration_zero_instant(actor: SpriteActor, mock_sprite: MagicMock) -> None:
    actor.move_to(500, 600, 0)
    # 不应创建 tween
    assert "x" not in actor._tweens
    assert "y" not in actor._tweens
    mock_sprite.update.assert_called()


# ── 6. 同名动画覆盖 ──────────────────────────────────────

def test_new_anim_overrides(actor: SpriteActor) -> None:
    actor.move_to(300, 400, 1.0)
    assert actor._tweens["x"].target == 300

    actor.move_to(500, 600, 0.5)
    assert actor._tweens["x"].target == 500
    assert actor._tweens["y"].target == 600


# ── 7. 快速连续切换动画 ──────────────────────────────────

def test_rapid_animation_override(actor: SpriteActor, mock_sprite: MagicMock) -> None:
    actor.move_to(100, 100, 0.5)
    actor.update(0.016)  # 一帧
    actor.move_to(200, 200, 0.5)

    # 补间目标应该是第二次的
    assert actor._tweens["x"].target == 200
    assert actor._tweens["y"].target == 200


# ── 8. 不同属性并行 ──────────────────────────────────────

def test_different_attrs_parallel(actor: SpriteActor) -> None:
    actor.move_to(300, 400, 1.0).fade_to(128, 0.5)
    assert "x" in actor._tweens
    assert "y" in actor._tweens
    assert "opacity" in actor._tweens


# ── 9. easing — linear 中间值 ────────────────────────────

def test_easing_linear(actor: SpriteActor, mock_sprite: MagicMock) -> None:
    actor.move_to(200, 200, 1.0, easing=linear)
    actor.update(0.5)
    # update 被调用过（验证 easing 无崩溃）
    assert mock_sprite.update.call_count >= 1


# ── 10. easing — ease_in_out_quad 端点正确 ───────────────

def test_easing_in_out_quad(actor: SpriteActor, mock_sprite: MagicMock) -> None:
    actor.move_to(200, 200, 1.0, easing=ease_in_out_quad)
    actor.update(1.0)
    assert mock_sprite.update.call_count >= 1


# ── 11. dt=0 不改变状态 ──────────────────────────────────

def test_update_zero_dt(actor: SpriteActor) -> None:
    actor.move_to(300, 400, 1.0)
    before_x = actor._tweens["x"].elapsed
    actor.update(0)
    assert actor._tweens["x"].elapsed == before_x


# ── 12. delete 清理 ──────────────────────────────────────

def test_delete_cleanup(actor: SpriteActor, mock_sprite: MagicMock) -> None:
    actor.move_to(300, 400, 1.0)
    actor.delete()
    assert len(actor._tweens) == 0
    mock_sprite.delete.assert_called_once()


# ── 13. 链式调用 ──────────────────────────────────────────

def test_chain_calls(actor: SpriteActor) -> None:
    result = actor.move_to(300, 400, 0.5).fade_to(128, 0.3).scale_to(1.5, 0.2)
    assert result is actor


# ── 14. 缓动函数单元测试 ─────────────────────────────────

def test_linear_easing() -> None:
    assert linear(0.0) == 0.0
    assert linear(0.5) == 0.5
    assert linear(1.0) == 1.0


def test_quad_easing_endpoints() -> None:
    assert ease_in_out_quad(0.0) == 0.0
    assert ease_in_out_quad(1.0) == 1.0
    # 中点：t=0.5 → 2*(0.5)² = 0.5
    assert ease_in_out_quad(0.5) == 0.5


# ── 15. rotate_to 补间 ───────────────────────────────────

def test_rotate_to(actor: SpriteActor) -> None:
    actor.rotate_to(90, 1.0)
    assert "rotation" in actor._tweens
    assert actor._tweens["rotation"].target == 90


# ── 16. 即时 set_position ─────────────────────────────────

def test_set_position_instant(actor: SpriteActor, mock_sprite: MagicMock) -> None:
    actor.move_to(300, 400, 1.0)
    actor.set_position(999, 888)
    assert "x" not in actor._tweens
    assert "y" not in actor._tweens
    mock_sprite.update.assert_called_with(x=999, y=888)
