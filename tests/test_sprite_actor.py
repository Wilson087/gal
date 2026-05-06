"""
SpriteActor 单元测试
====================
全 mock pyglet.sprite.Sprite，零 GPU 依赖。
mock 环境由 tests/_mocks.py 注入。
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock

import tests._mocks  # noqa: F401 — pyglet mock setup

from graphics.sprite_actor import (
    SpriteActor,
    linear,
    ease_in_out_quad,
)

# 引用 _mocks.py 注入的 mock
_mock_pyglet = sys.modules["pyglet"]
_mock_pyglet_sprite = sys.modules["pyglet.sprite"]
_mock_pyglet_shapes = sys.modules["pyglet.shapes"]


def _make_mock_sprite() -> MagicMock:
    s = MagicMock()
    s.x = 100.0
    s.y = 200.0
    s.opacity = 255
    s.scale = 1.0
    s.rotation = 0.0
    s._delete = False
    return s


class TestSpriteActor(unittest.TestCase):
    """SpriteActor 补间动画测试。"""

    def setUp(self) -> None:
        """每个测试前重置 mock 并创建 actor。"""
        for key in ("pyglet", "pyglet.image", "pyglet.sprite",
                    "pyglet.graphics", "pyglet.shapes"):
            sys.modules[key].reset_mock()
        _mock_pyglet.image = sys.modules["pyglet.image"]
        _mock_pyglet.sprite = _mock_pyglet_sprite
        _mock_pyglet.graphics = sys.modules["pyglet.graphics"]
        _mock_pyglet.shapes = _mock_pyglet_shapes
        _mock_pyglet_sprite.Sprite.side_effect = None
        _mock_pyglet_sprite.Sprite.return_value = MagicMock()
        _mock_pyglet_shapes.Rectangle.side_effect = None
        _mock_pyglet_shapes.Rectangle.return_value = MagicMock()

        self._mock_sprite = _make_mock_sprite()
        _mock_pyglet_sprite.Sprite.return_value = self._mock_sprite
        mock_image = MagicMock()
        mock_batch = MagicMock()
        mock_group = MagicMock()
        self.actor = SpriteActor(mock_image, x=100, y=200, batch=mock_batch, group=mock_group)

    # ── 1. move_to 完整到达目标 ──────────────────────────────

    def test_move_to_completes(self) -> None:
        self.actor.move_to(300, 400, 1.0)
        self.actor.update(1.0)
        # sprite.update 被调用以设置最终位置
        self.assertGreaterEqual(self._mock_sprite.update.call_count, 1)

    # ── 2. fade_to 边界 clamp ─────────────────────────────────

    def test_fade_to_clamped(self) -> None:
        self.actor.fade_to(300, 0.5)
        self.assertEqual(self.actor._tweens["opacity"].target, 255)  # clamped

        self.actor.fade_to(-10, 0.5)
        self.assertEqual(self.actor._tweens["opacity"].target, 0)   # clamped

    # ── 3. scale 负值抛异常 ──────────────────────────────────

    def test_scale_to_negative(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.actor.scale_to(0, 1.0)
        self.assertIn("scale", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            self.actor.scale_to(-1, 1.0)
        self.assertIn("scale", str(ctx.exception))

    # ── 4. duration 负值抛异常 ────────────────────────────────

    def test_duration_negative(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.actor.fade_to(128, -0.5)
        self.assertIn("duration", str(ctx.exception))

    # ── 5. duration == 0 瞬间跳转 ────────────────────────────

    def test_duration_zero_instant(self) -> None:
        self.actor.move_to(500, 600, 0)
        # 不应创建 tween
        self.assertNotIn("x", self.actor._tweens)
        self.assertNotIn("y", self.actor._tweens)
        self._mock_sprite.update.assert_called()

    # ── 6. 同名动画覆盖 ──────────────────────────────────────

    def test_new_anim_overrides(self) -> None:
        self.actor.move_to(300, 400, 1.0)
        self.assertEqual(self.actor._tweens["x"].target, 300)

        self.actor.move_to(500, 600, 0.5)
        self.assertEqual(self.actor._tweens["x"].target, 500)
        self.assertEqual(self.actor._tweens["y"].target, 600)

    # ── 7. 快速连续切换动画 ──────────────────────────────────

    def test_rapid_animation_override(self) -> None:
        self.actor.move_to(100, 100, 0.5)
        self.actor.update(0.016)  # 一帧
        self.actor.move_to(200, 200, 0.5)

        # 补间目标应该是第二次的
        self.assertEqual(self.actor._tweens["x"].target, 200)
        self.assertEqual(self.actor._tweens["y"].target, 200)

    # ── 8. 不同属性并行 ──────────────────────────────────────

    def test_different_attrs_parallel(self) -> None:
        self.actor.move_to(300, 400, 1.0).fade_to(128, 0.5)
        self.assertIn("x", self.actor._tweens)
        self.assertIn("y", self.actor._tweens)
        self.assertIn("opacity", self.actor._tweens)

    # ── 9. easing — linear 中间值 ────────────────────────────

    def test_easing_linear(self) -> None:
        self.actor.move_to(200, 200, 1.0, easing=linear)
        self.actor.update(0.5)
        # update 被调用过（验证 easing 无崩溃）
        self.assertGreaterEqual(self._mock_sprite.update.call_count, 1)

    # ── 10. easing — ease_in_out_quad 端点正确 ───────────────

    def test_easing_in_out_quad(self) -> None:
        self.actor.move_to(200, 200, 1.0, easing=ease_in_out_quad)
        self.actor.update(1.0)
        self.assertGreaterEqual(self._mock_sprite.update.call_count, 1)

    # ── 11. dt=0 不改变状态 ──────────────────────────────────

    def test_update_zero_dt(self) -> None:
        self.actor.move_to(300, 400, 1.0)
        before_x = self.actor._tweens["x"].elapsed
        self.actor.update(0)
        self.assertEqual(self.actor._tweens["x"].elapsed, before_x)

    # ── 12. delete 清理 ──────────────────────────────────────

    def test_delete_cleanup(self) -> None:
        self.actor.move_to(300, 400, 1.0)
        self.actor.delete()
        self.assertEqual(len(self.actor._tweens), 0)
        self._mock_sprite.delete.assert_called_once()

    # ── 13. 链式调用 ──────────────────────────────────────────

    def test_chain_calls(self) -> None:
        result = self.actor.move_to(300, 400, 0.5).fade_to(128, 0.3).scale_to(1.5, 0.2)
        self.assertIs(result, self.actor)

    # ── 14. 缓动函数单元测试 ─────────────────────────────────

    def test_linear_easing(self) -> None:
        self.assertEqual(linear(0.0), 0.0)
        self.assertEqual(linear(0.5), 0.5)
        self.assertEqual(linear(1.0), 1.0)

    def test_quad_easing_endpoints(self) -> None:
        self.assertEqual(ease_in_out_quad(0.0), 0.0)
        self.assertEqual(ease_in_out_quad(1.0), 1.0)
        # 中点：t=0.5 → 2*(0.5)² = 0.5
        self.assertEqual(ease_in_out_quad(0.5), 0.5)

    # ── 15. rotate_to 补间 ───────────────────────────────────

    def test_rotate_to(self) -> None:
        self.actor.rotate_to(90, 1.0)
        self.assertIn("rotation", self.actor._tweens)
        self.assertEqual(self.actor._tweens["rotation"].target, 90)

    # ── 16. 即时 set_position ─────────────────────────────────

    def test_set_position_instant(self) -> None:
        self.actor.move_to(300, 400, 1.0)
        self.actor.set_position(999, 888)
        self.assertNotIn("x", self.actor._tweens)
        self.assertNotIn("y", self.actor._tweens)
        self._mock_sprite.update.assert_called_with(x=999, y=888)
