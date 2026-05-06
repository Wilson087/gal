"""
LayerManager 单元测试
=====================
全 mock pyglet，零 GPU 依赖。
mock 环境由 tests/_mocks.py 注入。
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock

import tests._mocks  # noqa: F401 — pyglet mock setup

from graphics.layer import LayerManager, Layer

# 引用 _mocks.py 注入的 mock
_mock_pyglet = sys.modules["pyglet"]
_mock_pyglet_sprite = sys.modules["pyglet.sprite"]
_mock_pyglet_shapes = sys.modules["pyglet.shapes"]


def _make_mock_sprite() -> MagicMock:
    s = MagicMock()
    s.x = 0.0
    s.y = 0.0
    s.opacity = 255
    s.scale = 1.0
    s.rotation = 0.0
    s._delete = False
    return s


class TestLayerManager(unittest.TestCase):
    """LayerManager 6 层渲染测试。"""

    def setUp(self) -> None:
        """每个测试前重置 mock 并创建 LayerManager。"""
        for key in ("pyglet", "pyglet.image", "pyglet.sprite",
                    "pyglet.graphics", "pyglet.shapes"):
            sys.modules[key].reset_mock()
        _mock_pyglet.image = sys.modules["pyglet.image"]
        _mock_pyglet.sprite = _mock_pyglet_sprite
        _mock_pyglet.graphics = sys.modules["pyglet.graphics"]
        _mock_pyglet.shapes = _mock_pyglet_shapes
        s = MagicMock()
        s._delete = False
        _mock_pyglet_sprite.Sprite.side_effect = None
        _mock_pyglet_sprite.Sprite.return_value = s
        _mock_pyglet_shapes.Rectangle.side_effect = None
        _mock_pyglet_shapes.Rectangle.return_value = MagicMock()

        self.lm = LayerManager(width=1280, height=720)

    # ── 1. 添加/移除精灵 ────────────────────────────────────

    def test_show_remove_sprite(self) -> None:
        mock_img = MagicMock()
        mock_img.width = 64
        mock_img.height = 64
        actor = self.lm.show_sprite(Layer.MID, mock_img, (640, 360))
        self.assertEqual(len(self.lm._sprites[Layer.MID]), 1)

        self.lm.remove_sprite(actor)
        self.assertEqual(len(self.lm._sprites[Layer.MID]), 0)

    # ── 2. 设置背景替换旧背景 ─────────────────────────────────

    def test_set_background_replaces(self) -> None:
        mock_img = MagicMock()
        mock_img.width = 1280
        mock_img.height = 720
        self.lm.set_background(mock_img)
        self.assertIsNotNone(self.lm._bg_actor)

        mock_img2 = MagicMock()
        mock_img2.width = 1280
        mock_img2.height = 720
        self.lm.set_background(mock_img2)
        # 旧背景应已被替换
        self.assertIsNotNone(self.lm._bg_actor)

    # ── 3. clear_all ──────────────────────────────────────────

    def test_clear_all(self) -> None:
        mock_img = MagicMock()
        mock_img.width = 64
        mock_img.height = 64
        self.lm.set_background(mock_img)
        self.lm.show_sprite(Layer.MID, mock_img, (100, 100))
        self.lm.show_sprite(Layer.UI, mock_img, (200, 200))
        self.lm.clear_all()

        self.assertIsNone(self.lm._bg_actor)
        for layer in Layer:
            self.assertEqual(len(self.lm._sprites[layer]), 0)

    # ── 4. 重复移除不崩溃 ────────────────────────────────────

    def test_duplicate_remove(self) -> None:
        mock_img = MagicMock()
        mock_img.width = 64
        mock_img.height = 64
        actor = self.lm.show_sprite(Layer.MID, mock_img, (100, 100))
        self.lm.remove_sprite(actor)
        self.lm.remove_sprite(actor)  # 不应崩溃

    # ── 5. fade_out 创建 overlay ─────────────────────────────

    def test_fade_out_creates_overlay(self) -> None:
        mock_rect = MagicMock()
        _mock_pyglet_shapes.Rectangle.return_value = mock_rect

        self.lm.fade_out(1.0)
        self.assertIsNotNone(self.lm._overlay)
        self.assertIsNotNone(self.lm._fade_tween)
        self.assertEqual(self.lm._fade_tween.target, 255)

    # ── 6. fade_in 创建 overlay ──────────────────────────────

    def test_fade_in_creates_overlay(self) -> None:
        mock_rect = MagicMock()
        _mock_pyglet_shapes.Rectangle.return_value = mock_rect

        self.lm.fade_in(1.0)
        self.assertIsNotNone(self.lm._overlay)
        self.assertIsNotNone(self.lm._fade_tween)
        self.assertEqual(self.lm._fade_tween.target, 0)

    # ── 7. fade_out 自定义颜色 ────────────────────────────────

    def test_fade_custom_color(self) -> None:
        self.lm.fade_out(1.0, color=(255, 255, 255))
        # overlay 被创建
        self.assertIsNotNone(self.lm._overlay)
        self.assertIsNotNone(self.lm._fade_tween)
        self.assertEqual(self.lm._fade_tween.target, 255)

    # ── 8. update 驱动 actor ──────────────────────────────────

    def test_update_drives_actors(self) -> None:
        mock_img = MagicMock()
        mock_img.width = 64
        mock_img.height = 64
        actor = self.lm.show_sprite(Layer.MID, mock_img, (100, 100))
        # 设置动画
        actor.move_to(200, 200, 0.5)
        self.lm.update(0.3)
        # 动画已推进
        self.assertGreater(actor._tweens["x"].elapsed, 0)

    # ── 9. 图层排序 ──────────────────────────────────────────

    def test_layer_ordering(self) -> None:
        """OrderedGroup 的 order 值与 Layer 枚举一致。"""
        self.assertEqual(Layer.BG.value, 0)
        self.assertEqual(Layer.BEHIND.value, 1)
        self.assertEqual(Layer.MID.value, 2)
        self.assertEqual(Layer.FRONT.value, 3)
        self.assertEqual(Layer.EFFECTS.value, 4)
        self.assertEqual(Layer.UI.value, 5)

    # ── 10. Layer 枚举值 ──────────────────────────────────────

    def test_layer_enum_values(self) -> None:
        layers = list(Layer)
        self.assertEqual(len(layers), 6)
        values = [l.value for l in layers]
        self.assertEqual(values, [0, 1, 2, 3, 4, 5])

    # ── 11. fade_out 重复调用释放旧 overlay ─────────────────

    def test_fade_out_replaces_overlay(self) -> None:
        """连续两次 fade_out：第二次覆盖第一次，tween 重置。"""
        self.lm.fade_out(1.0)
        self.assertIsNotNone(self.lm._overlay)
        self.assertIsNotNone(self.lm._fade_tween)
        self.assertEqual(self.lm._fade_tween.duration, 1.0)

        self.lm.fade_out(2.0)
        self.assertIsNotNone(self.lm._fade_tween)
        self.assertEqual(self.lm._fade_tween.duration, 2.0)

    # ── 12. update 自动清除已删除 actor ──────────────────────

    def test_update_prunes_deleted_actors(self) -> None:
        mock_img = MagicMock()
        mock_img.width = 64
        mock_img.height = 64
        actor = self.lm.show_sprite(Layer.MID, mock_img, (100, 100))
        # 模拟外部直接 delete 不调 remove_sprite
        actor._deleted = True
        self.lm.update(0.016)
        # 已删除 actor 应被自动移除
        self.assertNotIn(actor, self.lm._sprites[Layer.MID])

    # ── 13. 特效占位方法不崩溃 ───────────────────────────────

    def test_effect_stubs_noop(self) -> None:
        self.lm.fog(0.5)
        self.lm.screen_shake(10, 0.3)
        # 不抛异常
