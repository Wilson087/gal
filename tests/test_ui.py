"""
UI 模块单元测试
===============
测试 UIElement ABC + DialogBox / ChoiceMenu / BacklogViewer / SettingsPanel。
纯状态逻辑测试，不测试渲染。pyglet 对象通过 conftest.py mock。
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from core.events import Event
from graphics.ui import (
    UIElement,
    DialogBox,
    ChoiceMenu,
    BacklogViewer,
    SettingsPanel,
    UIManager,
)


# ── Fixtures ──────────────────────────────────────────────────


def _make_mock_shape(*args: object, **kwargs: object) -> MagicMock:
    """创建带真实坐标属性的 mock 图形对象（用于 hit-test 运算）。"""
    m = MagicMock()
    for attr in ("x", "y", "width", "height"):
        if attr in kwargs:
            setattr(m, attr, kwargs[attr])
        else:
            setattr(m, attr, 0)
    return m


@pytest.fixture(autouse=True)
def _reset_ui_mocks() -> None:
    """每个测试前重置 pyglet.text / shapes / window 的 mock 状态。"""
    for mod_name in ("pyglet.text", "pyglet.shapes", "pyglet.window"):
        mock_mod = sys.modules.get(mod_name)
        if mock_mod is not None:
            mock_mod.reset_mock()
    # Rectangle / Label 返回有正确属性的 mock
    shapes_mod = sys.modules["pyglet.shapes"]
    shapes_mod.Rectangle.side_effect = _make_mock_shape
    text_mod = sys.modules["pyglet.text"]
    text_mod.Label.return_value = MagicMock()
    # 重新绑定子模块到 pyglet
    pyg = sys.modules["pyglet"]
    pyg.text = sys.modules["pyglet.text"]  # type: ignore[attr-defined]
    pyg.shapes = sys.modules["pyglet.shapes"]  # type: ignore[attr-defined]
    pyg.window = sys.modules["pyglet.window"]  # type: ignore[attr-defined]


@pytest.fixture
def mock_batch() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_group() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_event_bus() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_window() -> MagicMock:
    w = MagicMock()
    w.fullscreen = False
    return w


@pytest.fixture
def mock_audio() -> MagicMock:
    a = MagicMock()
    a._volumes = {"bgm": 0.8, "voice": 1.0, "se": 0.6}
    return a


# ── 1. UIElement ABC ──────────────────────────────────────────


def test_uielement_cannot_instantiate() -> None:
    """ABC 不能直接实例化。"""
    with pytest.raises(TypeError):
        UIElement()  # type: ignore[abstract]


def test_uielement_visible_default() -> None:
    """子类默认 visible=False。"""

    class _Concrete(UIElement):
        def show(self) -> None: self._visible = True
        def hide(self) -> None: self._visible = False
        def update(self, dt: float) -> None: pass
        def draw(self) -> None: pass

    obj = _Concrete()
    assert obj.visible is False
    obj.show()
    assert obj.visible is True
    obj.hide()
    assert obj.visible is False


# ── 2. DialogBox ──────────────────────────────────────────────


def test_dialog_show_text_state(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    box = DialogBox(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    box.show_text("Rei", "前辈，早上好～")
    assert box._full_text == "前辈，早上好～"
    assert box._current_speaker == "Rei"
    assert box._visible_chars == 0
    assert box._finished is False
    assert box.visible is True


def test_dialog_typewriter_advance(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    box = DialogBox(
        mock_batch, mock_group, 1280, 720,
        chars_per_second=10.0, event_bus=mock_event_bus,
    )
    box.show_text("", "0123456789")  # 10 chars
    box.update(0.5)  # 5 chars
    assert box._visible_chars == 5
    assert box._finished is False


def test_dialog_typewriter_completes(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    box = DialogBox(
        mock_batch, mock_group, 1280, 720,
        chars_per_second=10.0, event_bus=mock_event_bus,
    )
    box.show_text("", "01234")  # 5 chars
    box.update(1.0)  # 10 chars — exceeds
    assert box._finished is True
    mock_event_bus.emit.assert_called_with(Event.DIALOGUE_COMPLETE)


def test_dialog_finish(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    box = DialogBox(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    box.show_text("Rei", "你好世界")
    box.finish()
    assert box._visible_chars == 4
    assert box._finished is True
    assert box.is_finished() is True


def test_dialog_is_finished(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    box = DialogBox(
        mock_batch, mock_group, 1280, 720,
        chars_per_second=1.0, event_bus=mock_event_bus,
    )
    box.show_text("", "很长的文本")
    assert box.is_finished() is False
    box.finish()
    assert box.is_finished() is True


def test_dialog_click_finished_emits_next(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    box = DialogBox(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    box.show_text("Rei", "你好")
    box.finish()  # 先完成打字
    mock_event_bus.emit.reset_mock()
    box.handle_click(640, 100)
    mock_event_bus.emit.assert_called_with(Event.DIALOGUE_NEXT)


def test_dialog_click_unfinished_finishes(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    box = DialogBox(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    box.show_text("Rei", "你好")
    assert box._finished is False
    box.handle_click(640, 100)
    # 应变为已完成
    assert box._finished is True
    # 不应 emit DIALOGUE_NEXT（只是 finish，不推进）
    calls = [c[0][0] for c in mock_event_bus.emit.call_args_list if c[0]]
    assert Event.DIALOGUE_NEXT not in calls


def test_dialog_history_accumulates(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    box = DialogBox(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    box.show_text("A", "第一句")
    box.show_text("B", "第二句")
    box.show_text("C", "第三句")
    hist = box.get_history()
    assert len(hist) == 2  # 前两句已保存，第三句还在显示中
    assert hist[0] == {"speaker": "A", "text": "第一句"}
    assert hist[1] == {"speaker": "B", "text": "第二句"}


def test_dialog_indicator_blink(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    box = DialogBox(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    box.show_text("", "test")
    box.finish()
    before = box._indicator_visible
    box.update(0.5)  # 0.5s 后应切换
    assert box._indicator_visible is not before
    box.update(0.5)  # 再 0.5s 后应切回
    assert box._indicator_visible is before


# ── 3. ChoiceMenu ────────────────────────────────────────────


def test_choice_show_hide(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    menu = ChoiceMenu(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    menu.show([("选项A", "tag_a"), ("选项B", "tag_b")])
    assert menu.visible is True
    assert menu._selected_index == 0
    assert len(menu._buttons) == 2
    menu.hide()
    assert menu.visible is False
    assert len(menu._buttons) == 0


def test_choice_keyboard_nav(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    menu = ChoiceMenu(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    menu.show([("A", 1), ("B", 2), ("C", 3)])
    menu.handle_key(1)  # 下
    assert menu._selected_index == 1
    menu.handle_key(1)  # 下
    assert menu._selected_index == 2


def test_choice_keyboard_clamp(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    menu = ChoiceMenu(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    menu.show([("A", 1)])
    menu.handle_key(-1)  # 上（应 clamp 到 0）
    assert menu._selected_index == 0
    menu.handle_key(1)  # 下（应 clamp 到 0）
    assert menu._selected_index == 0


def test_choice_click_hit(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    menu = ChoiceMenu(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    menu.show([("A", "tag_a"), ("B", "tag_b")])

    # 点击第一个按钮的中心
    rect, _ = menu._buttons[0]
    cx = rect.x + rect.width / 2
    cy = rect.y + rect.height / 2
    menu.handle_click(cx, cy)

    # 应发出选择事件
    mock_event_bus.emit.assert_called_with("choice_selected", index=0, tag="tag_a")
    assert menu.visible is False  # 选中后自动隐藏


def test_choice_click_miss(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    menu = ChoiceMenu(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    menu.show([("A", 1)])
    # 点击远离按钮的位置
    menu.handle_click(9999, 9999)
    # 不应 emit choice_selected
    for call in mock_event_bus.emit.call_args_list:
        args = call[0]
        if args and args[0] == "choice_selected":
            pytest.fail("不应发出 choice_selected")
    assert menu.visible is True  # 未命中不应隐藏


def test_choice_mouse_hover(
    mock_batch: MagicMock, mock_group: MagicMock, mock_event_bus: MagicMock,
) -> None:
    menu = ChoiceMenu(mock_batch, mock_group, 1280, 720, event_bus=mock_event_bus)
    menu.show([("A", 1), ("B", 2)])
    # 悬停在第一个按钮上
    rect, _ = menu._buttons[0]
    cx = rect.x + rect.width / 2
    cy = rect.y + rect.height / 2
    menu.handle_mouse_motion(cx, cy)
    assert menu._hover_index == 0

    # 移开
    menu.handle_mouse_motion(9999, 9999)
    assert menu._hover_index == -1


# ── 4. BacklogViewer ─────────────────────────────────────────


def test_backlog_show_hide(
    mock_batch: MagicMock, mock_group: MagicMock,
) -> None:
    viewer = BacklogViewer(mock_batch, mock_group, 1280, 720)
    viewer.show([{"speaker": "Rei", "text": "你好"}])
    assert viewer.visible is True
    viewer.hide()
    assert viewer.visible is False


def test_backlog_scroll_clamp(
    mock_batch: MagicMock, mock_group: MagicMock,
) -> None:
    viewer = BacklogViewer(mock_batch, mock_group, 1280, 720)
    viewer.show([{"speaker": "A", "text": "短"}])
    # 只有一条记录，max_scroll 应为 0
    viewer.handle_scroll(-5)  # 向下滚
    assert viewer._scroll_offset == 0.0
    viewer.handle_scroll(5)  # 向上滚
    assert viewer._scroll_offset == 0.0


def test_backlog_click_outside(
    mock_batch: MagicMock, mock_group: MagicMock,
) -> None:
    viewer = BacklogViewer(mock_batch, mock_group, 1280, 720)
    viewer.show([{"speaker": "A", "text": "test"}])
    # 点击左上角（内容区域外）
    result = viewer.handle_click(5, 5)
    assert result is True
    assert viewer.visible is False


def test_backlog_click_inside(
    mock_batch: MagicMock, mock_group: MagicMock,
) -> None:
    viewer = BacklogViewer(mock_batch, mock_group, 1280, 720)
    viewer.show([{"speaker": "A", "text": "test"}])
    # 点击内容区域中心
    cx = (viewer._content_left + viewer._content_right) // 2
    cy = (viewer._content_top + viewer._content_bottom) // 2
    result = viewer.handle_click(cx, cy)
    assert result is False
    assert viewer.visible is True  # 不关闭


# ── 5. SettingsPanel ─────────────────────────────────────────


def test_settings_click_outside(
    mock_batch: MagicMock, mock_group: MagicMock,
    mock_audio: MagicMock, mock_window: MagicMock,
) -> None:
    panel = SettingsPanel(
        mock_batch, mock_group, 1280, 720,
        audio_manager=mock_audio, window=mock_window,
    )
    panel.show()
    # 点击左上角（面板外）
    result = panel.handle_click(0, 0)
    assert result is True
    assert panel.visible is False


def test_settings_slider_drag(
    mock_batch: MagicMock, mock_group: MagicMock,
    mock_audio: MagicMock, mock_window: MagicMock,
) -> None:
    panel = SettingsPanel(
        mock_batch, mock_group, 1280, 720,
        audio_manager=mock_audio, window=mock_window,
    )
    panel.show()

    # 先模拟点击滑块手柄开始拖动
    bgm_slider = panel._sliders["bgm"]
    hx = bgm_slider.handle.x + bgm_slider.handle.width / 2
    hy = bgm_slider.handle.y + bgm_slider.handle.height / 2
    panel.handle_click(hx, hy)
    assert panel._dragging_slider == "bgm"

    # 拖动到滑轨最右端
    bar_right = bgm_slider.bar.x + bgm_slider.bar.width
    panel.handle_mouse_drag(bar_right, hy)
    # 值应接近 1.0
    assert bgm_slider.current == pytest.approx(1.0, abs=0.05)

    # 释放
    panel.handle_mouse_release(0, 0)
    assert panel._dragging_slider is None


def test_settings_click_fullscreen_toggle(
    mock_batch: MagicMock, mock_group: MagicMock,
    mock_audio: MagicMock, mock_window: MagicMock,
) -> None:
    panel = SettingsPanel(
        mock_batch, mock_group, 1280, 720,
        audio_manager=mock_audio, window=mock_window,
    )
    panel.show()

    # 点击全屏按钮
    r = panel._fullscreen_btn_rect
    assert r is not None
    cx = r.x + r.width / 2
    cy = r.y + r.height / 2
    panel.handle_click(cx, cy)

    mock_window.set_fullscreen.assert_called_once_with(True)


# ── 6. UIManager ─────────────────────────────────────────────


def test_uimanager_constructs_components(
    mock_batch: MagicMock, mock_group: MagicMock,
    mock_event_bus: MagicMock, mock_audio: MagicMock, mock_window: MagicMock,
) -> None:
    ui = UIManager(
        mock_batch, mock_group, 1280, 720,
        event_bus=mock_event_bus,
        audio_manager=mock_audio,
        window=mock_window,
    )
    assert ui.dialog is not None
    assert ui.choice is not None
    assert ui.backlog is not None
    assert ui.settings is not None


def test_uimanager_routes_click_to_settings(
    mock_batch: MagicMock, mock_group: MagicMock,
    mock_event_bus: MagicMock, mock_audio: MagicMock, mock_window: MagicMock,
) -> None:
    ui = UIManager(
        mock_batch, mock_group, 1280, 720,
        event_bus=mock_event_bus,
        audio_manager=mock_audio,
        window=mock_window,
    )
    ui.settings.show()

    # 点击面板外部（左上角）→ 应关闭 settings
    ui._on_click(x=5, y=5)
    assert ui.settings.visible is False


def test_uimanager_routes_scroll_to_backlog(
    mock_batch: MagicMock, mock_group: MagicMock,
    mock_event_bus: MagicMock, mock_audio: MagicMock, mock_window: MagicMock,
) -> None:
    ui = UIManager(
        mock_batch, mock_group, 1280, 720,
        event_bus=mock_event_bus,
        audio_manager=mock_audio,
        window=mock_window,
    )
    ui.backlog._visible = True
    ui.backlog._max_scroll = 100.0
    ui._on_scroll(scroll_y=2.0)
    assert ui.backlog._scroll_offset > 0
