"""
MainMenu 单元测试
=================
纯状态逻辑测试，pyglet 对象通过 conftest.py mock。
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from modes.main_menu import MainMenu


@pytest.fixture(autouse=True)
def _reset_menu_mocks() -> None:
    """每个测试前重置 mock 状态。"""
    for mod_name in ("pyglet.text", "pyglet.shapes", "pyglet.window"):
        mock_mod = sys.modules.get(mod_name)
        if mock_mod is not None:
            mock_mod.reset_mock()

    def _make_mock_shape(*args: object, **kwargs: object) -> MagicMock:
        m = MagicMock()
        for attr in ("x", "y", "width", "height"):
            setattr(m, attr, kwargs.get(attr, 0))
        m.visible = True
        return m

    shapes_mod = sys.modules["pyglet.shapes"]
    shapes_mod.Rectangle.side_effect = _make_mock_shape
    text_mod = sys.modules["pyglet.text"]
    text_mod.Label.return_value = MagicMock()


@pytest.fixture
def mock_batch() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_group() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_event_bus() -> MagicMock:
    return MagicMock()


# ── 1. 基本显示/隐藏 ──────────────────────────────────────


def test_menu_show_hide(
    mock_batch: MagicMock, mock_group: MagicMock,
) -> None:
    menu = MainMenu(mock_batch, mock_group, 1280, 720)
    menu.show()
    assert menu._visible is True
    assert menu._selected_index == 0
    assert menu._hover_index == -1
    assert len(menu._buttons) == 6
    menu.hide()
    assert menu._visible is False
    assert len(menu._buttons) == 0


def test_menu_button_count(
    mock_batch: MagicMock, mock_group: MagicMock,
) -> None:
    menu = MainMenu(mock_batch, mock_group, 1280, 720)
    menu.show()
    assert len(menu._buttons) == 6


# ── 2. 点击 ─────────────────────────────────────────────


def test_menu_click_emits_tag(
    mock_batch: MagicMock, mock_group: MagicMock,
    mock_event_bus: MagicMock,
) -> None:
    menu = MainMenu(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    menu.show()

    rect = menu._buttons[0]["rect"]
    cx = rect.x + rect.width / 2
    cy = rect.y + rect.height / 2
    menu.handle_click(cx, cy)

    mock_event_bus.emit.assert_called_with("menu_select", tag="new_game", index=0)


def test_menu_click_miss_no_emit(
    mock_batch: MagicMock, mock_group: MagicMock,
    mock_event_bus: MagicMock,
) -> None:
    menu = MainMenu(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    menu.show()
    menu.handle_click(9999, 9999)
    # 不应 emit menu_select
    for call in mock_event_bus.emit.call_args_list:
        if call[0] and call[0][0] == "menu_select":
            pytest.fail("不应发出 menu_select")


# ── 3. 悬停 ─────────────────────────────────────────────


def test_menu_hover_updates_index(
    mock_batch: MagicMock, mock_group: MagicMock,
) -> None:
    menu = MainMenu(mock_batch, mock_group, 1280, 720)
    menu.show()

    rect = menu._buttons[2]["rect"]
    cx = rect.x + rect.width / 2
    cy = rect.y + rect.height / 2
    menu.handle_mouse_motion(cx, cy)
    assert menu._hover_index == 2

    menu.handle_mouse_motion(9999, 9999)
    assert menu._hover_index == -1


# ── 4. 键盘导航 ─────────────────────────────────────────


def test_menu_keyboard_nav(
    mock_batch: MagicMock, mock_group: MagicMock,
) -> None:
    menu = MainMenu(mock_batch, mock_group, 1280, 720)
    menu.show()

    import pyglet.window
    k = pyglet.window.key

    menu.handle_key(k.DOWN)
    assert menu._selected_index == 1
    menu.handle_key(k.DOWN)
    assert menu._selected_index == 2


def test_menu_keyboard_clamp(
    mock_batch: MagicMock, mock_group: MagicMock,
) -> None:
    menu = MainMenu(mock_batch, mock_group, 1280, 720)
    menu.show()

    import pyglet.window
    k = pyglet.window.key

    menu.handle_key(k.UP)
    assert menu._selected_index == 0  # clamp
    for _ in range(10):
        menu.handle_key(k.DOWN)
    assert menu._selected_index == 5  # last item


def test_menu_enter_emits_event(
    mock_batch: MagicMock, mock_group: MagicMock,
    mock_event_bus: MagicMock,
) -> None:
    menu = MainMenu(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    menu.show()

    import pyglet.window
    k = pyglet.window.key

    # 下移两个到 "CG 画廊"
    menu.handle_key(k.DOWN)
    menu.handle_key(k.DOWN)
    menu.handle_key(k.ENTER)

    mock_event_bus.emit.assert_called_with("menu_select", tag="cg_gallery", index=2)


# ── 5. 颜色更新 ─────────────────────────────────────────


def test_menu_update_colors(
    mock_batch: MagicMock, mock_group: MagicMock,
) -> None:
    menu = MainMenu(mock_batch, mock_group, 1280, 720)
    menu.show()
    menu.update(0.016)

    # 第一个按钮高亮（selected_index=0）
    rect0 = menu._buttons[0]["rect"]
    assert rect0.opacity == 230  # highlight alpha

    # 其他按钮普通
    rect3 = menu._buttons[3]["rect"]
    assert rect3.opacity == 200  # normal alpha
