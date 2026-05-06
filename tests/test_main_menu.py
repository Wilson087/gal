"""
MainMenu 单元测试
=================
纯状态逻辑测试，pyglet 对象通过 _mocks.py mock。
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock

import tests._mocks  # noqa: F401 — pyglet mock setup

from graphics.main_menu import MainMenu


class TestMainMenu(unittest.TestCase):
    """MainMenu 显示/隐藏/点击/键盘导航测试。"""

    def setUp(self) -> None:
        """每个测试前重置 mock 状态。"""
        for mod_name in ("pyglet.text", "pyglet.shapes", "pyglet.window"):
            mock_mod = sys.modules.get(mod_name)
            if mock_mod is not None:
                mock_mod.reset_mock()
        # Rectangle 返回带数值属性的 mock（hit-test 需要 <= 比较）
        shapes_mod = sys.modules["pyglet.shapes"]

        def _make_mock_shape(*args: object, **kwargs: object) -> MagicMock:
            m = MagicMock()
            for attr in ("x", "y", "width", "height"):
                if attr in kwargs:
                    setattr(m, attr, kwargs[attr])
                else:
                    setattr(m, attr, 0)
            return m

        shapes_mod.Rectangle.side_effect = _make_mock_shape
        text_mod = sys.modules["pyglet.text"]
        text_mod.Label.return_value = MagicMock()
        pyg = sys.modules["pyglet"]
        pyg.text = sys.modules["pyglet.text"]
        pyg.shapes = sys.modules["pyglet.shapes"]
        pyg.window = sys.modules["pyglet.window"]

        # 设置键盘常量（MainMenu.handle_key 内部会 import pyglet.window）
        km = sys.modules["pyglet.window"].key
        km.UP = 0xFF52
        km.DOWN = 0xFF54
        km.ENTER = 0xFF0D
        km.SPACE = 0x20

    def _make_menu(self) -> MainMenu:
        batch = MagicMock()
        group = MagicMock()
        return MainMenu(batch, group, 1280, 720)

    def test_show_hide(self) -> None:
        menu = self._make_menu()
        menu.show()
        self.assertTrue(menu._visible)
        menu.hide()
        self.assertFalse(menu._visible)

    def test_click_selects(self) -> None:
        bus = MagicMock()
        batch = MagicMock()
        group = MagicMock()
        menu = MainMenu(batch, group, 1280, 720, event_bus=bus)
        menu.show()
        # 点击第一个按钮
        btn = menu._buttons[0]
        rect = btn["rect"]
        cx = rect.x + rect.width / 2
        cy = rect.y + rect.height / 2
        menu.handle_click(cx, cy)
        bus.emit.assert_called_once_with("menu_select", tag="new_game", index=0)

    def test_hover_highlight(self) -> None:
        menu = self._make_menu()
        menu.show()

        # 悬停在第一个按钮
        btn = menu._buttons[0]
        rect = btn["rect"]
        cx = rect.x + rect.width / 2
        cy = rect.y + rect.height / 2
        menu.handle_mouse_motion(cx, cy)
        self.assertEqual(menu._hover_index, 0)

        # 移开
        menu.handle_mouse_motion(9999, 9999)
        self.assertEqual(menu._hover_index, -1)

    def test_key_navigation(self) -> None:
        menu = self._make_menu()
        menu.show()

        # 按上（不应小于 0）
        menu.handle_key(0xFF52)  # UP
        self.assertEqual(menu._selected_index, 0)

        # 按下
        menu.handle_key(0xFF54)  # DOWN
        self.assertEqual(menu._selected_index, 1)

        # 再按下
        menu.handle_key(0xFF54)  # DOWN
        self.assertEqual(menu._selected_index, 2)

        # 按上
        menu.handle_key(0xFF52)  # UP
        self.assertEqual(menu._selected_index, 1)

    def test_key_select_last_item(self) -> None:
        menu = self._make_menu()
        menu.show()

        # 一直按到末尾
        for _ in range(10):
            menu.handle_key(0xFF54)  # DOWN
        self.assertEqual(menu._selected_index, 6)  # 共 7 项 (0-6)

    def test_overlay_opacity(self) -> None:
        menu = self._make_menu()
        menu.show()
        menu.set_overlay_opacity(0.5)
        # 不应崩溃
        if menu._overlay is not None:
            self.assertEqual(menu._overlay.opacity, 127)
