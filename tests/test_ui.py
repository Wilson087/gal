"""
UI 模块单元测试
===============
测试 UIElement ABC + DialogBox / ChoiceMenu / BacklogViewer / SettingsPanel。
纯状态逻辑测试，不测试渲染。pyglet 对象通过 _mocks.py mock。
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock

import tests._mocks  # noqa: F401 — pyglet mock setup

from src.core.events import Event
from src.graphics.ui import (
    UIElement,
    DialogBox,
    ChoiceMenu,
    BacklogViewer,
    SettingsPanel,
    UIManager,
)


def _make_mock_shape(*args: object, **kwargs: object) -> MagicMock:
    """创建带真实坐标属性的 mock 图形对象（用于 hit-test 运算）。"""
    m = MagicMock()
    for attr in ("x", "y", "width", "height"):
        if attr in kwargs:
            setattr(m, attr, kwargs[attr])
        else:
            setattr(m, attr, 0)
    return m


class TestUIElement(unittest.TestCase):
    """UIElement ABC 测试。"""

    def test_uielement_cannot_instantiate(self) -> None:
        """ABC 不能直接实例化。"""
        with self.assertRaises(TypeError):
            UIElement()  # type: ignore[abstract]

    def test_uielement_visible_default(self) -> None:
        """子类默认 visible=False。"""

        class _Concrete(UIElement):
            def show(self) -> None: self._visible = True
            def hide(self) -> None: self._visible = False
            def update(self, dt: float) -> None: pass
            def draw(self) -> None: pass

        obj = _Concrete()
        self.assertFalse(obj.visible)
        obj.show()
        self.assertTrue(obj.visible)
        obj.hide()
        self.assertFalse(obj.visible)


class _UIBase(unittest.TestCase):
    """UI 测试基类 —— 提供 mock 对象创建和 mock 重置。"""

    def setUp(self) -> None:
        for mod_name in ("pyglet.text", "pyglet.shapes", "pyglet.window"):
            mock_mod = sys.modules.get(mod_name)
            if mock_mod is not None:
                mock_mod.reset_mock()
        shapes_mod = sys.modules["pyglet.shapes"]
        shapes_mod.Rectangle.side_effect = _make_mock_shape
        text_mod = sys.modules["pyglet.text"]
        text_mod.Label.return_value = MagicMock()
        pyg = sys.modules["pyglet"]
        pyg.text = sys.modules["pyglet.text"]
        pyg.shapes = sys.modules["pyglet.shapes"]
        pyg.window = sys.modules["pyglet.window"]

    @property
    def _mock_batch(self) -> MagicMock:
        return MagicMock()

    @property
    def _mock_group(self) -> MagicMock:
        return MagicMock()

    @property
    def _mock_event_bus(self) -> MagicMock:
        return MagicMock()

    @property
    def _mock_window(self) -> MagicMock:
        w = MagicMock()
        w.fullscreen = False
        return w

    @property
    def _mock_audio(self) -> MagicMock:
        a = MagicMock()
        a._volumes = {"bgm": 0.8, "voice": 1.0, "se": 0.6}
        return a


# ── 2. DialogBox ──────────────────────────────────────────────

class TestDialogBox(_UIBase):
    """DialogBox 打字机效果、点击推进、历史记录测试。"""

    def test_dialog_show_text_state(self) -> None:
        box = DialogBox(self._mock_batch, self._mock_group, 1280, 720, event_bus=self._mock_event_bus)
        box.show_text("Rei", "前辈，早上好～")
        self.assertEqual(box._full_text, "前辈，早上好～")
        self.assertEqual(box._current_speaker, "Rei")
        self.assertEqual(box._visible_chars, 0)
        self.assertFalse(box._finished)
        self.assertTrue(box.visible)

    def test_dialog_typewriter_advance(self) -> None:
        box = DialogBox(
            self._mock_batch, self._mock_group, 1280, 720,
            chars_per_second=10.0, event_bus=self._mock_event_bus,
        )
        box.show_text("", "0123456789")  # 10 chars
        box.update(0.5)  # 5 chars
        self.assertEqual(box._visible_chars, 5)
        self.assertFalse(box._finished)

    def test_dialog_typewriter_completes(self) -> None:
        bus = self._mock_event_bus
        box = DialogBox(
            self._mock_batch, self._mock_group, 1280, 720,
            chars_per_second=10.0, event_bus=bus,
        )
        box.show_text("", "01234")  # 5 chars
        box.update(1.0)  # 10 chars — exceeds
        self.assertTrue(box._finished)
        bus.emit.assert_called_with(Event.DIALOGUE_COMPLETE)

    def test_dialog_finish(self) -> None:
        box = DialogBox(self._mock_batch, self._mock_group, 1280, 720, event_bus=self._mock_event_bus)
        box.show_text("Rei", "你好世界")
        box.finish()
        self.assertEqual(box._visible_chars, 4)
        self.assertTrue(box._finished)
        self.assertTrue(box.is_finished())

    def test_dialog_is_finished(self) -> None:
        box = DialogBox(
            self._mock_batch, self._mock_group, 1280, 720,
            chars_per_second=1.0, event_bus=self._mock_event_bus,
        )
        box.show_text("", "很长的文本")
        self.assertFalse(box.is_finished())
        box.finish()
        self.assertTrue(box.is_finished())

    def test_dialog_click_finished_emits_next(self) -> None:
        bus = self._mock_event_bus
        box = DialogBox(self._mock_batch, self._mock_group, 1280, 720, event_bus=bus)
        box.show_text("Rei", "你好")
        box.finish()  # 先完成打字
        bus.emit.reset_mock()
        box.handle_click(640, 100)
        bus.emit.assert_called_with(Event.DIALOGUE_NEXT)

    def test_dialog_click_unfinished_finishes(self) -> None:
        bus = self._mock_event_bus
        box = DialogBox(self._mock_batch, self._mock_group, 1280, 720, event_bus=bus)
        box.show_text("Rei", "你好")
        self.assertFalse(box._finished)
        box.handle_click(640, 100)
        # 应变为已完成
        self.assertTrue(box._finished)
        # 不应 emit DIALOGUE_NEXT（只是 finish，不推进）
        calls = [c[0][0] for c in bus.emit.call_args_list if c[0]]
        self.assertNotIn(Event.DIALOGUE_NEXT, calls)

    def test_dialog_history_accumulates(self) -> None:
        box = DialogBox(self._mock_batch, self._mock_group, 1280, 720, event_bus=self._mock_event_bus)
        box.show_text("A", "第一句")
        box.show_text("B", "第二句")
        box.show_text("C", "第三句")
        hist = box.get_history()
        self.assertEqual(len(hist), 2)  # 前两句已保存，第三句还在显示中
        self.assertEqual(hist[0], {"speaker": "A", "text": "第一句"})
        self.assertEqual(hist[1], {"speaker": "B", "text": "第二句"})

    def test_dialog_indicator_blink(self) -> None:
        box = DialogBox(self._mock_batch, self._mock_group, 1280, 720, event_bus=self._mock_event_bus)
        box.show_text("", "test")
        box.finish()
        before = box._indicator_visible
        box.update(0.5)  # 0.5s 后应切换
        self.assertIsNot(box._indicator_visible, before)
        box.update(0.5)  # 再 0.5s 后应切回
        self.assertIs(box._indicator_visible, before)


# ── 3. ChoiceMenu ────────────────────────────────────────────

class TestChoiceMenu(_UIBase):
    """ChoiceMenu 选项列表、键盘导航、点击测试。"""

    def test_choice_show_hide(self) -> None:
        menu = ChoiceMenu(self._mock_batch, self._mock_group, 1280, 720, event_bus=self._mock_event_bus)
        menu.show([("选项A", "tag_a"), ("选项B", "tag_b")])
        self.assertTrue(menu.visible)
        self.assertEqual(menu._selected_index, -1)
        self.assertEqual(len(menu._buttons), 2)
        menu.hide()
        self.assertFalse(menu.visible)
        self.assertEqual(len(menu._buttons), 0)

    def test_choice_keyboard_nav(self) -> None:
        menu = ChoiceMenu(self._mock_batch, self._mock_group, 1280, 720, event_bus=self._mock_event_bus)
        menu.show([("A", 1), ("B", 2), ("C", 3)])
        menu.handle_key(1)  # 下
        self.assertEqual(menu._selected_index, 0)
        menu.handle_key(1)  # 下
        self.assertEqual(menu._selected_index, 1)

    def test_choice_keyboard_clamp(self) -> None:
        menu = ChoiceMenu(self._mock_batch, self._mock_group, 1280, 720, event_bus=self._mock_event_bus)
        menu.show([("A", 1)])
        menu.handle_key(-1)  # 上（应 clamp 到 0）
        self.assertEqual(menu._selected_index, 0)
        menu.handle_key(1)  # 下（应 clamp 到 0）
        self.assertEqual(menu._selected_index, 0)

    def test_choice_click_hit(self) -> None:
        bus = self._mock_event_bus
        menu = ChoiceMenu(self._mock_batch, self._mock_group, 1280, 720, event_bus=bus)
        menu.show([("A", "tag_a"), ("B", "tag_b")])

        # 点击第一个按钮的中心
        rect, _ = menu._buttons[0]
        cx = rect.x + rect.width / 2
        cy = rect.y + rect.height / 2
        menu.handle_click(cx, cy)

        # 应发出选择事件
        bus.emit.assert_called_with("choice_selected", index=0, tag="tag_a")
        self.assertFalse(menu.visible)  # 选中后自动隐藏

    def test_choice_click_miss(self) -> None:
        bus = self._mock_event_bus
        menu = ChoiceMenu(self._mock_batch, self._mock_group, 1280, 720, event_bus=bus)
        menu.show([("A", 1)])
        # 点击远离按钮的位置
        menu.handle_click(9999, 9999)
        # 不应 emit choice_selected
        for call in bus.emit.call_args_list:
            args = call[0]
            if args and args[0] == "choice_selected":
                self.fail("不应发出 choice_selected")
        self.assertTrue(menu.visible)  # 未命中不应隐藏

    def test_choice_mouse_hover(self) -> None:
        menu = ChoiceMenu(self._mock_batch, self._mock_group, 1280, 720, event_bus=self._mock_event_bus)
        menu.show([("A", 1), ("B", 2)])
        # 悬停在第一个按钮上
        rect, _ = menu._buttons[0]
        cx = rect.x + rect.width / 2
        cy = rect.y + rect.height / 2
        menu.handle_mouse_motion(cx, cy)
        self.assertEqual(menu._hover_index, 0)

        # 移开
        menu.handle_mouse_motion(9999, 9999)
        self.assertEqual(menu._hover_index, -1)


# ── 4. BacklogViewer ─────────────────────────────────────────

class TestBacklogViewer(_UIBase):
    """BacklogViewer 显示/隐藏/滚动/点击测试。"""

    def test_backlog_show_hide(self) -> None:
        viewer = BacklogViewer(self._mock_batch, self._mock_group, 1280, 720)
        viewer.show([{"speaker": "Rei", "text": "你好"}])
        self.assertTrue(viewer.visible)
        viewer.hide()
        self.assertFalse(viewer.visible)

    def test_backlog_scroll_clamp(self) -> None:
        viewer = BacklogViewer(self._mock_batch, self._mock_group, 1280, 720)
        viewer.show([{"speaker": "A", "text": "短"}])
        # 只有一条记录，max_scroll 应为 0
        viewer.handle_scroll(-5)  # 向下滚
        self.assertEqual(viewer._scroll_offset, 0.0)
        viewer.handle_scroll(5)  # 向上滚
        self.assertEqual(viewer._scroll_offset, 0.0)

    def test_backlog_click_outside(self) -> None:
        viewer = BacklogViewer(self._mock_batch, self._mock_group, 1280, 720)
        viewer.show([{"speaker": "A", "text": "test"}])
        # 点击左上角（内容区域外）
        result = viewer.handle_click(5, 5)
        self.assertTrue(result)
        self.assertFalse(viewer.visible)

    def test_backlog_click_inside(self) -> None:
        viewer = BacklogViewer(self._mock_batch, self._mock_group, 1280, 720)
        viewer.show([{"speaker": "A", "text": "test"}])
        # 点击内容区域中心
        cx = (viewer._content_left + viewer._content_right) // 2
        cy = (viewer._content_top + viewer._content_bottom) // 2
        result = viewer.handle_click(cx, cy)
        self.assertFalse(result)
        self.assertTrue(viewer.visible)  # 不关闭


# ── 5. SettingsPanel ─────────────────────────────────────────

class TestSettingsPanel(_UIBase):
    """SettingsPanel 滑块、全屏按钮测试。"""

    def test_settings_click_outside(self) -> None:
        panel = SettingsPanel(
            self._mock_batch, self._mock_group, 1280, 720,
            audio_manager=self._mock_audio, window=self._mock_window,
        )
        panel.show()
        # 点击左上角（面板外）
        result = panel.handle_click(0, 0)
        self.assertTrue(result)
        self.assertFalse(panel.visible)

    def test_settings_slider_drag(self) -> None:
        panel = SettingsPanel(
            self._mock_batch, self._mock_group, 1280, 720,
            audio_manager=self._mock_audio, window=self._mock_window,
        )
        panel.show()

        # 先模拟点击滑块手柄开始拖动
        bgm_slider = panel._sliders["bgm"]
        hx = bgm_slider.handle.x + bgm_slider.handle.width / 2
        hy = bgm_slider.handle.y + bgm_slider.handle.height / 2
        panel.handle_click(hx, hy)
        self.assertEqual(panel._dragging_slider, "bgm")

        # 拖动到滑轨最右端
        bar_right = bgm_slider.bar.x + bgm_slider.bar.width
        panel.handle_mouse_drag(bar_right, hy)
        # 值应接近 1.0
        self.assertAlmostEqual(bgm_slider.current, 1.0, delta=0.05)

        # 释放
        panel.handle_mouse_release(0, 0)
        self.assertIsNone(panel._dragging_slider)

    def test_settings_click_fullscreen_toggle(self) -> None:
        w = self._mock_window
        panel = SettingsPanel(
            self._mock_batch, self._mock_group, 1280, 720,
            audio_manager=self._mock_audio, window=w,
        )
        panel.show()

        # 点击全屏按钮
        r = panel._fullscreen_btn_rect
        self.assertIsNotNone(r)
        cx = r.x + r.width / 2
        cy = r.y + r.height / 2
        panel.handle_click(cx, cy)

        w.set_fullscreen.assert_called_once_with(True)


# ── 6. UIManager ─────────────────────────────────────────────

class TestUIManager(_UIBase):
    """UIManager 组件装配、事件路由测试。"""

    def test_uimanager_constructs_components(self) -> None:
        ui = UIManager(
            self._mock_batch, self._mock_group, 1280, 720,
            event_bus=self._mock_event_bus,
            audio_manager=self._mock_audio,
            window=self._mock_window,
        )
        self.assertIsNotNone(ui.dialog)
        self.assertIsNotNone(ui.choice)
        self.assertIsNotNone(ui.backlog)
        self.assertIsNotNone(ui.settings)

    def test_uimanager_routes_click_to_settings(self) -> None:
        ui = UIManager(
            self._mock_batch, self._mock_group, 1280, 720,
            event_bus=self._mock_event_bus,
            audio_manager=self._mock_audio,
            window=self._mock_window,
        )
        ui.settings.show()

        # 点击面板外部（左上角）→ 应关闭 settings
        ui._on_click(x=5, y=5)
        self.assertFalse(ui.settings.visible)

    def test_uimanager_routes_scroll_to_backlog(self) -> None:
        ui = UIManager(
            self._mock_batch, self._mock_group, 1280, 720,
            event_bus=self._mock_event_bus,
            audio_manager=self._mock_audio,
            window=self._mock_window,
        )
        ui.backlog._visible = True
        ui.backlog._max_scroll = 100.0
        ui._on_scroll(scroll_y=2.0)
        self.assertGreater(ui.backlog._scroll_offset, 0)
