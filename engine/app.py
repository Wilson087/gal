"""
主应用模块
==========
AVGApplication：pyglet 窗口子类，游戏循环主驱动。
集成配置管理、背景适配、UI 导航、存档、历史等全部子系统。
"""

import os
from typing import Optional

import pyglet
from pyglet.window import key, mouse
from pyglet.graphics import Batch, Group
from pyglet.text import Label

from .constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, FONT_FAMILIES,
    COLOR_BG_DARK,
)
from .config import GameConfig
from .variable import VariableBank
from .audio import AudioEngine
from .dialogue import DialogueSystem
from .choice import ChoiceSystem
from .character import CharacterManager
from .effects import EffectSystem
from .scene_manager import SceneManager
from .background_manager import BackgroundManager
from .save_manager import SaveManager
from .history_manager import HistoryManager
from .ui_manager import UIManager, ORDER_TOOLTIP
from .settings_panel import SettingsPanel
from .save_load_panel import SaveLoadPanel
from .history_panel import HistoryPanel
from .main_menu import MainMenu
from .logger import Logger

log = Logger("App")


class AVGApplication(pyglet.window.Window):
    """视觉小说主应用窗口，继承 pyglet.window.Window。

    管理所有子系统、游戏循环、事件分发。
    """

    def __init__(self, width: int = WINDOW_WIDTH, height: int = WINDOW_HEIGHT,
                 title: str = "Visual Novel") -> None:
        # 配置先加载
        self.game_config = GameConfig().load()
        cfg = self.game_config.display

        super().__init__(width, height, caption=title, resizable=True)
        self.set_minimum_size(640, 360)

        # 鼠标 / 时间跟踪
        self._mouse_x: int = 0
        self._mouse_y: int = 0
        self._total_time: float = 0.0

        # FPS
        self._show_fps = cfg.show_fps
        self._fps_display = pyglet.window.FPSDisplay(self)
        self._fps_count = 0
        self._fps_timer = 0.0
        self._fps_label: Optional[Label] = None

        # 自动模式
        self._auto_mode: bool = False
        self._auto_timer: float = 0.0

        # 渲染批次
        self.main_batch = Batch()
        self.ui_batch = Batch()

        # 核心子系统
        self.variable_bank = VariableBank()
        self.audio_engine = AudioEngine()
        self.character_manager = CharacterManager(self)
        self.dialogue_system = DialogueSystem(self)
        self.choice_system = ChoiceSystem(self)
        self.effect_system = EffectSystem(self)
        self.scene_manager = SceneManager(self)

        # 背景管理器（独立模块，支持4种适配模式）
        self.background_manager = BackgroundManager(self)
        self.background_manager.set_window(self)

        if hasattr(self, 'game_config'):
            self.background_manager.set_fit_mode(cfg.bg_fit_mode)

        # 新增子系统
        self.save_manager = SaveManager(self)
        self.history_manager = HistoryManager()
        self.history_manager.set_on_jump(self._on_history_jump)
        self.ui_manager = UIManager(self)

        # 设置面板
        self._settings_panel = SettingsPanel(self)
        self.ui_manager.set_settings_panel(self._settings_panel)
        # 存档/读档面板
        self._save_load_panel = SaveLoadPanel(self)
        self.ui_manager.set_save_load_panel(self._save_load_panel)
        # 历史记录面板
        self._history_panel = HistoryPanel(self)
        self.ui_manager.set_history_panel(self._history_panel)

        # 主菜单
        self._main_menu = MainMenu(self)
        self._is_in_main_menu = False

        # 帧率控制
        pyglet.clock.schedule_interval(self.update, 1 / 60.0)

        # 窗口位置恢复
        if cfg.window_x is not None and cfg.window_y is not None:
            try:
                self.set_location(cfg.window_x, cfg.window_y)
            except Exception:
                pass

    # ──── 剧本加载 ─────────────────────────────────────────

    def load_script(self, json_path: str) -> None:
        """加载 JSON 剧本。"""
        self.scene_manager.load_script(json_path)
        self.set_caption(self.scene_manager.title)

    def start_game(self) -> None:
        """启动游戏：跳转到第一个场景（从主菜单调用）。"""
        self._is_in_main_menu = False
        self.scene_manager.start_first_scene()

    def show_main_menu(self) -> None:
        """显示主菜单。"""
        self._is_in_main_menu = True
        self._main_menu.show()

    def _is_main_menu_visible(self) -> bool:
        return self._is_in_main_menu

    # ──── 自动模式 ─────────────────────────────────────────

    def _toggle_auto_mode(self) -> None:
        self._auto_mode = not self._auto_mode
        self._auto_timer = 0.0
        if self._auto_mode and self.dialogue_system:
            self.ui_manager.notification.show(
                "自动模式 " + ("ON" if self._auto_mode else "OFF"), 1.0)

    # ──── 历史回溯 ─────────────────────────────────────────

    def _on_history_jump(self, entry) -> None:
        """点击历史回溯到指定条目。"""
        sm = self.scene_manager
        sm.jump_to_scene(entry.scene_id)
        sm.dialogue_index = entry.dialogue_index
        sm._show_current_dialogue()

    # ──── 工具栏功能 ─────────────────────────────────────

    def _go_back(self) -> None:
        """后退到上一句对话。"""
        self.scene_manager.go_back()

    def _previous_choice(self) -> None:
        """跳转到上一个选项分支点。"""
        self.scene_manager.go_to_previous_choice()

    def _next_dialogue(self) -> None:
        """推进到下一句（工具栏"下句"按钮用）。"""
        if not self.scene_manager.is_choosing and not self.scene_manager.is_ended:
            self.dialogue_system.advance()

    def _toggle_mute(self) -> None:
        """切换全局静音。"""
        cfg = self.game_config.audio
        cfg.master_mute = not cfg.master_mute
        vol = 0.0 if cfg.master_mute else 1.0
        self.audio_engine.bgm_volume = vol * cfg.bgm_volume
        self.audio_engine.sfx_volume = vol * cfg.sfx_volume
        self.audio_engine.voice_volume = vol * cfg.voice_volume
        self.ui_manager.notification.show(
            "已静音" if cfg.master_mute else "已取消静音", 1.0)

    def _replay_voice(self) -> None:
        """重播当前对话的语音。"""
        sm = self.scene_manager
        scene = sm.scenes_dict.get(sm.current_scene_id)
        if scene:
            dialogues = scene.get("dialogue", [])
            if sm.dialogue_index < len(dialogues):
                voice_path = dialogues[sm.dialogue_index].get("voice", "")
                if voice_path:
                    self.audio_engine.play_voice(voice_path)
                    return
            # 场景级 voice
            scene_voice = scene.get("voice")
            if scene_voice:
                self.audio_engine.play_voice(scene_voice)

    def _take_screenshot(self) -> None:
        """保存截图到 saves/screenshots/ 目录。"""
        import os
        import time
        from pyglet.image import get_buffer_manager
        os.makedirs("saves/screenshots", exist_ok=True)
        try:
            buf = get_buffer_manager().get_color_buffer()
            img = buf.get_image_data()
            path = f"saves/screenshots/shot_{int(time.time())}.png"
            img.save(path)
            self.ui_manager.notification.show("截图已保存", 1.5)
        except Exception as e:
            log.error("截图失败: %s", e)

    def _return_to_menu(self) -> None:
        """返回主菜单（重新开始游戏）。"""
        self.ui_manager.hide_all_panels()
        self.scene_manager.start_first_scene()

    # ──── pyglet 事件处理 ─────────────────────────────────

    def on_draw(self) -> None:
        """每帧绘制。"""
        self.clear()
        pyglet.gl.glClearColor(
            COLOR_BG_DARK[0] / 255.0,
            COLOR_BG_DARK[1] / 255.0,
            COLOR_BG_DARK[2] / 255.0,
            1.0,
        )
        self.main_batch.draw()
        self.ui_batch.draw()

        # FPS 显示
        if self._show_fps and self._fps_label:
            self._fps_label.draw()

    def update(self, dt: float) -> None:
        """游戏逻辑更新（60 FPS）。"""
        self._total_time += dt

        # 子系统更新
        self.dialogue_system.update(dt)
        self.choice_system.update(dt)
        self.character_manager.update(dt)
        self.effect_system.update(dt)
        self.audio_engine.update_ducking()
        self.ui_manager.update(dt)

        # FPS 计数
        self._fps_count += 1
        self._fps_timer += dt
        if self._fps_timer >= 1.0 and self._show_fps:
            if not self._fps_label:
                self._fps_label = Label(
                    f"FPS: {self._fps_count}",
                    font_name=FONT_FAMILIES, font_size=12,
                    color=(0, 255, 0, 255),
                    x=10, y=self.height - 20,
                    anchor_x="left", anchor_y="top",
                )
            else:
                self._fps_label.text = f"FPS: {self._fps_count}"
                self._fps_label.y = self.height - 20
            self._fps_count = 0
            self._fps_timer = 0.0

        # 全屏鼠标自动隐藏
        if self.fullscreen:
            try:
                mx, my = self._mouse_x, self._mouse_y
                # 3 秒无操作隐藏
                pass  # 简化：pyglet 未直接提供无操作检测
            except Exception:
                pass

        # 自动模式
        if self._auto_mode and not self.scene_manager.is_choosing:
            if not self.dialogue_system.is_busy():
                self._auto_timer += dt
                auto_speed = self.game_config.text.auto_speed
                if self._auto_timer >= auto_speed:
                    self._auto_timer = 0.0
                    if self.scene_manager.is_ended:
                        self._auto_mode = False
                    else:
                        self.dialogue_system.advance()

    def on_resize(self, width: int, height: int) -> None:
        """窗口缩放事件。"""
        super().on_resize(width, height)
        self.background_manager.on_resize(width, height)
        self.ui_manager.on_resize(width, height)

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> None:
        """鼠标点击处理。"""
        self._mouse_x = x
        self._mouse_y = y

        if button != mouse.LEFT:
            return

        # 主菜单优先
        if self._is_in_main_menu:
            self._main_menu.on_mouse_press(x, y)
            return

        # UI 优先处理
        if self.ui_manager.on_mouse_press(x, y, button, modifiers):
            return

        # 游戏内
        if self.scene_manager.is_choosing:
            self.choice_system.on_click(x, y)
        elif self.scene_manager.is_ended:
            self.scene_manager.start_first_scene()
        else:
            self.dialogue_system.advance()
            # 自动模式：点击时重置计时器
            if self._auto_mode:
                self._auto_timer = 0.0

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        """鼠标移动跟踪。"""
        self._mouse_x = x
        self._mouse_y = y
        if self._is_in_main_menu:
            self._main_menu.on_mouse_motion(x, y)

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int,
                      buttons: int, modifiers: int) -> None:
        """鼠标拖拽（用于滑块）。"""
        self._mouse_x = x
        self._mouse_y = y
        self.ui_manager.on_mouse_drag(x, y, dx, dy)

    def on_mouse_release(self, x: int, y: int, button: int,
                         modifiers: int) -> None:
        """鼠标释放。"""
        self.ui_manager.on_mouse_release(x, y)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: float,
                        scroll_y: float) -> None:
        """鼠标滚轮。"""
        self._mouse_x = x
        self._mouse_y = y
        self.ui_manager.on_mouse_scroll(x, y, scroll_x, scroll_y)

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        """键盘事件。

        快捷键：
        - 空格/回车: 推进对话
        - ESC: 打开/关闭设置
        - F5: 快速保存 | F9: 快速读取
        - H: 历史 | A: 自动播放
        - Ctrl+S: 存档 | Ctrl+L: 读档
        - Ctrl: 快进
        - F11: 全屏切换
        """
        # 面板打开时的快捷键
        if self.ui_manager.is_any_panel_open():
            if symbol == key.ESCAPE:
                self.ui_manager.hide_all_panels()
                return
            elif symbol == key.H and self.ui_manager.is_panel_open("history"):
                self.ui_manager.hide_all_panels()
                return
            return

        # 游戏内快捷键
        if symbol in (key.SPACE, key.ENTER):
            if not self.scene_manager.is_choosing:
                self.dialogue_system.advance()
                if self._auto_mode:
                    self._auto_timer = 0.0

        elif symbol == key.ESCAPE:
            self.ui_manager.show_panel("settings")

        elif symbol == key.F5:
            if self.save_manager.quick_save():
                self.ui_manager.notification.show("已快速保存", 1.5)

        elif symbol == key.F9:
            self.save_manager.quick_load()

        elif symbol == key.H:
            self.ui_manager.show_panel("history")

        elif symbol == key.A:
            self._toggle_auto_mode()

        elif symbol == key.F11:
            self.set_fullscreen(not self.fullscreen)

        elif modifiers & key.MOD_CTRL:
            if symbol == key.S:
                self.ui_manager.show_panel("save")
            elif symbol == key.L:
                self.ui_manager.show_panel("load")
            else:
                # Ctrl 按住 = 快进
                self.dialogue_system._skip_type = True

    def on_close(self) -> None:
        """窗口关闭——保存配置。"""
        # 保存窗口位置
        try:
            wx, wy = self.get_location()
            self.game_config.display.window_x = wx
            self.game_config.display.window_y = wy
        except Exception:
            pass

        self.game_config.save()
        self.audio_engine.shutdown()
        super().on_close()

    # ──── 窗口模式切换 ─────────────────────────────────────

    def set_window_mode(self, mode: str) -> None:
        """切换窗口模式。

        Args:
            mode: "windowed" | "borderless" | "fullscreen"
        """
        if mode == "fullscreen":
            self.set_fullscreen(True)
        elif mode == "borderless":
            self.set_fullscreen(False)
            self._set_style(self.WINDOW_STYLE_BORDERLESS)
            screen = self.display.get_screens()[0]
            self.set_size(screen.width, screen.height)
            self.set_location(0, 0)
        else:
            self.set_fullscreen(False)
            self._set_style(self.WINDOW_STYLE_DEFAULT)
            cfg = self.game_config.display
            self.set_size(cfg.width, cfg.height)
        self.game_config.display.window_mode = mode
        self.game_config.save()

    def _set_style(self, style) -> None:
        """安全设置窗口样式。"""
        try:
            self.style = style
        except Exception:
            pass
