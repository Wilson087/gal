"""
Game — 引擎中枢
================
持有所有子系统引用和事件总线，按 GameState 分发 update / draw / 输入。

子系统依赖关系（构造顺序 / Layer）
-----------------------------------
::

    Layer 0: flags / variable_bank  — 全局变量存储
    Layer 1: resource_manager       — 资源加载 / LRU 缓存
    Layer 2: audio                  — 依赖 resource_manager
    Layer 3: save_system            — 依赖 variable_bank
    Layer 4: script_executor        — 依赖 variable_bank
    Layer 10: layers + ui_manager   — 组合渲染 + UI
    附加:    cg_gallery             — CG 画廊
    附加:    music_room             — 音乐欣赏
    附加:    character_viewer       — 立绘鉴赏
"""

from __future__ import annotations

import logging
from typing import Any

import pyglet

from config import AppConfig
from .events import EventBus, Event, GameState

logger = logging.getLogger(__name__)


class Game:
    """引擎中枢 —— 持有事件总线和所有子系统引用。

    Game 类是纯 Python，不依赖 pyglet 渲染上下文。
    所有渲染 / 输入由 main.py 的 GameWindow 转发。
    按 GameState 状态机分发 update / draw / 输入。
    """

    def __init__(self, config: AppConfig) -> None:
        self.config: AppConfig = config
        self.events: EventBus = EventBus()
        self._state: GameState = GameState.TITLE
        self._prev_state: GameState | None = None
        self._paused: bool = False
        self._window: Any = None

        # ── Layer 0 — 变量 / 旗标（独立 dict） ────────────
        self.flags: dict[str, bool] = {}
        self.variable_bank: dict[str, object] = {}

        # ── 子系统占位（Layer 顺序） ──────────────────────
        self.resource_manager: Any = None        # Layer 1
        self.audio: Any = None                   # Layer 2
        self.save_system: Any = None             # Layer 3
        self.script_executor: Any = None         # Layer 4
        self.scene_manager: Any = None           # Layer 5
        self.character_manager: Any = None       # Layer 6
        self.dialogue_system: Any = None         # Layer 7
        self.choice_system: Any = None           # Layer 8
        self.effect_system: Any = None           # Layer 9
        self.ui_manager: Any = None              # Layer 10
        self.layers: Any = None                  # Layer 10

        # ── 鉴赏模式 ────────────────────────────────────
        self.cg_gallery: Any = None
        self.music_room: Any = None
        self.character_viewer: Any = None
        self.main_menu: Any = None

        # ── 角色立绘追踪 ──────────────────────────────
        self._char_sprites: dict[str, Any] = {}

        logger.info(
            "Game 实例已创建: %dx%d, debug=%s",
            config.width, config.height, config.debug,
        )

    # ── 状态机 ──────────────────────────────────────────────

    @property
    def state(self) -> GameState:
        return self._state

    @state.setter
    def state(self, value: GameState) -> None:
        if value != self._state:
            logger.info("State: %s → %s", self._state.name, value.name)
            self._prev_state = self._state
            self._state = value

    @property
    def paused(self) -> bool:
        return self._paused

    @paused.setter
    def paused(self, value: bool) -> None:
        if value != self._paused:
            self._paused = value
            logger.debug("Game %s", "paused" if value else "resumed")

    # ── 初始化 ──────────────────────────────────────────────

    def init_subsystems(self, window: Any = None) -> None:
        """按依赖顺序创建并注册所有子系统。

        调用时机：GameWindow 构造完成后、pyglet.app.run() 之前。

        Args:
            window: pyglet.window.Window 实例（供 SettingsPanel 全屏切换）。
        """
        self._window = window
        # 延迟导入避免循环依赖
        from systems.resource import ResourceManager
        from audio.audio_manager import AudioManager
        from systems.save_system import SaveSystem
        from script.executor import ScriptExecutor
        from graphics.layer import LayerManager, Layer
        from graphics.ui import UIManager
        from modes.gallery import CGGallery, MusicRoom, CharacterViewer
        from modes.main_menu import MainMenu

        # ── Layer 1: 资源管理器 ──────────────────────────
        self.resource_manager = ResourceManager(self.config.resource_root)
        self.register("resource_manager", self.resource_manager)
        logger.info("Layer 1: ResourceManager 已初始化")

        # ── Layer 2: 音频 ────────────────────────────────
        self.audio = AudioManager(event_bus=self.events)
        self.register("audio", self.audio)
        logger.info("Layer 2: AudioManager 已初始化")

        # ── Layer 3: 存档 ────────────────────────────────
        self.save_system = SaveSystem(save_root=self.config.save_path)
        self.register("save_system", self.save_system)
        logger.info("Layer 3: SaveSystem 已初始化")

        # ── Layer 4: 脚本执行器 ──────────────────────────
        self.script_executor = ScriptExecutor(self)
        self.register("script_executor", self.script_executor)
        logger.info("Layer 4: ScriptExecutor 已初始化")

        # ── Layer 10: 图层管理器 + UI ────────────────────
        self.layers = LayerManager(self.config.width, self.config.height)
        self.register("layers", self.layers)

        self.ui_manager = UIManager(
            batch=self.layers.batch,
            ui_group=self.layers.get_group(Layer.UI),
            width=self.config.width,
            height=self.config.height,
            event_bus=self.events,
            audio_manager=self.audio,
            window=window,
        )
        self.register("ui_manager", self.ui_manager)
        logger.info("Layer 10: LayerManager + UIManager 已初始化")

        # ── 鉴赏模式 ─────────────────────────────────────
        self.cg_gallery = CGGallery(
            batch=self.layers.batch,
            ui_group=self.layers.get_group(Layer.UI),
            width=self.config.width,
            height=self.config.height,
            resource_manager=self.resource_manager,
            flags=self.flags,
            config_path=self.config.gallery_data,
            event_bus=self.events,
        )
        self.cg_gallery.load_config()
        self.register("cg_gallery", self.cg_gallery)

        self.music_room = MusicRoom(
            batch=self.layers.batch,
            ui_group=self.layers.get_group(Layer.UI),
            width=self.config.width,
            height=self.config.height,
            resource_manager=self.resource_manager,
            audio_manager=self.audio,
            flags=self.flags,
            config_path=self.config.music_data,
        )
        self.music_room.load_config()
        self.register("music_room", self.music_room)

        self.character_viewer = CharacterViewer(
            batch=self.layers.batch,
            ui_group=self.layers.get_group(Layer.UI),
            width=self.config.width,
            height=self.config.height,
            resource_manager=self.resource_manager,
            config_path=self.config.character_data,
        )
        self.character_viewer.load_config()
        self.register("character_viewer", self.character_viewer)

        # ── 主菜单 ───────────────────────────────────────
        self.main_menu = MainMenu(
            batch=self.layers.batch,
            ui_group=self.layers.get_group(Layer.UI),
            width=self.config.width,
            height=self.config.height,
            resource_manager=self.resource_manager,
            event_bus=self.events,
        )
        self.register("main_menu", self.main_menu)
        logger.info("MainMenu 已初始化")

        # ── 事件订阅 ─────────────────────────────────────
        self.events.on(Event.KEY_PRESS, self._on_key)
        self.events.on("scroll", self._on_scroll)
        self.events.on("choice", self._on_choice)
        self.events.on("choice_selected", self._on_choice_selected)
        self.events.on(Event.SCENE_END, self._on_scene_end)
        self.events.on("menu_select", self._on_menu_select)
        # 剧本驱动的事件
        self.events.on("scene_start", self._on_scene_start)
        self.events.on("dialogue", self._on_dialogue)
        self.events.on("audio:bgm", self._on_bgm)
        self.events.on("show", self._on_show)
        self.events.on("hide", self._on_hide)
        self.events.on(Event.DIALOGUE_NEXT, self.script_executor.on_dialogue_next)

        # 追踪角色精灵
        self._char_sprites: dict[str, Any] = {}

        logger.info("所有子系统初始化完成")
        self._show_main_menu()

    # ── 游戏循环 — 状态分发 ────────────────────────────────

    def update(self, dt: float) -> None:
        """推进游戏逻辑（60fps）。按当前 GameState 分发。

        Args:
            dt: delta 时间（秒）。
        """
        if self._paused:
            return

        if self._state == GameState.NOVEL:
            self.script_executor.update()
            self.layers.update(dt)
            self.ui_manager.update(dt)
        elif self._state == GameState.TITLE:
            self.layers.update(dt)
            self.main_menu.update(dt)
        elif self._state == GameState.CG_GALLERY:
            self.cg_gallery.update(dt)
        elif self._state == GameState.MUSIC_ROOM:
            self.music_room.update(dt)
        elif self._state == GameState.CHARACTER_VIEWER:
            self.character_viewer.update(dt)

        self.events.emit(Event.UPDATE, dt=dt)

    def draw(self) -> None:
        """渲染一帧。按当前 GameState 分发绘制顺序。"""
        if self._state in (GameState.NOVEL, GameState.TITLE):
            self.layers.draw()
        else:
            # 鉴赏模式：绘制 Batch 中的 UI 元素
            self.layers.batch.draw()
            if self._state == GameState.CG_GALLERY:
                self.cg_gallery.draw()
            # MusicRoom / CharacterViewer 的 overlay 如有需要在此

        self.events.emit(Event.DRAW)

    # ── 输入分发 ────────────────────────────────────────────

    def handle_escape(self) -> bool:
        """处理 ESC 键。

        Returns:
            True 表示 ESC 已被消费（鉴赏模式返回），
            False 表示应由 GameWindow 处理（关闭窗口）。
        """
        if self._state in (GameState.CG_GALLERY, GameState.MUSIC_ROOM,
                            GameState.CHARACTER_VIEWER):
            self._return_to_previous()
            return True
        return False

    def on_click(self, x: int, y: int) -> None:
        """鼠标点击 — 按状态分发。"""
        if self._state == GameState.NOVEL:
            self.events.emit(Event.CLICK, x=x, y=y)
        elif self._state == GameState.TITLE:
            if self.main_menu is not None:
                self.main_menu.handle_click(x, y)
        elif self._state == GameState.CG_GALLERY:
            self.cg_gallery.handle_click(x, y)
        elif self._state == GameState.MUSIC_ROOM:
            self.music_room.handle_click(x, y)
        elif self._state == GameState.CHARACTER_VIEWER:
            self.character_viewer.handle_click(x, y)

    def handle_mouse_motion(self, x: int, y: int) -> None:
        """鼠标移动 — 按状态分发（由 GameWindow 直接调用，不走 EventBus）。"""
        if self._state == GameState.NOVEL:
            if self.ui_manager is not None:
                self.ui_manager.handle_mouse_motion(x, y)
        elif self._state == GameState.TITLE:
            if self.main_menu is not None:
                self.main_menu.handle_mouse_motion(x, y)
        elif self._state == GameState.CG_GALLERY:
            self.cg_gallery.handle_mouse_motion(x, y)
        elif self._state == GameState.MUSIC_ROOM:
            self.music_room.handle_mouse_motion(x, y)
        elif self._state == GameState.CHARACTER_VIEWER:
            self.character_viewer.handle_mouse_motion(x, y)

    def handle_mouse_drag(self, x: int, y: int, buttons: int = 0, modifiers: int = 0) -> None:
        """鼠标拖动 — 按状态分发。"""
        if self._state == GameState.NOVEL:
            if self.ui_manager is not None:
                self.ui_manager.handle_mouse_drag(x, y)
        # 鉴赏模式不使用拖拽

    def handle_mouse_release(self, x: int, y: int) -> None:
        """鼠标释放 — 按状态分发。"""
        if self._state == GameState.NOVEL:
            if self.ui_manager is not None:
                self.ui_manager.handle_mouse_release(x, y)

    # ── 剧本事件处理 ────────────────────────────────────────

    def _on_scene_start(self, **kwargs: Any) -> None:
        """场景切换：清除旧立绘，加载并设置背景。"""
        scene_id = str(kwargs.get("scene_id", ""))
        if not scene_id or self.resource_manager is None or self.layers is None:
            return
        # 清除上一场景的立绘
        for actor in self._char_sprites.values():
            self.layers.remove_sprite(actor)
        self._char_sprites.clear()
        # 尝试多个常见路径
        for path in (
            f"images/{scene_id}.png",
            f"images/bg/{scene_id}.png",
        ):
            img = self.resource_manager.get_image(path)
            if img is not None:
                self.layers.set_background(img)
                logger.info("场景背景已设置: %s", path)
                return
        logger.warning("场景背景未找到: %s", scene_id)

    def _on_dialogue(self, **kwargs: Any) -> None:
        """对话事件：显示在 DialogBox。"""
        if self.ui_manager is None:
            return
        speaker = str(kwargs.get("speaker", ""))
        text = str(kwargs.get("text", ""))
        voice = kwargs.get("voice")
        self.ui_manager.dialog.show_text(speaker, text, voice)

    def _on_bgm(self, **kwargs: Any) -> None:
        """BGM 事件：加载并播放。"""
        track = str(kwargs.get("track", ""))
        if not track or self.audio is None or self.resource_manager is None:
            return
        for path in (f"bgm/{track}.ogg", f"bgm/{track}.mp3", f"audio/{track}.ogg"):
            source = self.resource_manager.get_audio(path)
            if source is not None:
                self.audio.play_bgm(source, volume=0.7)
                return
        logger.debug("BGM 未找到: %s", track)

    def _on_show(self, **kwargs: Any) -> None:
        """角色立绘显示事件（ShowCommand → "show"）。"""
        if self.resource_manager is None or self.layers is None:
            return
        char = str(kwargs.get("char", ""))
        pose = str(kwargs.get("pose", ""))
        position = str(kwargs.get("position", "center"))
        if not char or not pose:
            return

        image_path = f"images/{char}-{pose}.png"
        img = self.resource_manager.get_image(image_path)
        if img is None:
            logger.warning("立绘未找到: %s", image_path)
            return

        # 移除同角色旧立绘
        if char in self._char_sprites:
            self.layers.remove_sprite(self._char_sprites[char])

        from graphics.layer import Layer
        # 按 position 字符串计算 X 坐标（以精灵中心为基准）
        pos_lower = position.lower()
        if "left" in pos_lower:
            anchor_x = self.config.width * 0.25
        elif "right" in pos_lower:
            anchor_x = self.config.width * 0.75
        else:
            anchor_x = self.config.width * 0.5

        x = int(anchor_x - img.width / 2)
        actor = self.layers.show_sprite(Layer.MID, img, (x, 0))
        self._char_sprites[char] = actor
        logger.info("立绘已显示: %s (%s) at %s", char, pose, position)

    def _on_hide(self, **kwargs: Any) -> None:
        """角色立绘隐藏事件（HideCommand → "hide"）。"""
        if self.layers is None:
            return
        char = str(kwargs.get("char", ""))
        if not char:
            return
        if char in self._char_sprites:
            self.layers.remove_sprite(self._char_sprites.pop(char))
            logger.info("立绘已隐藏: %s", char)

    # ── 键盘 ────────────────────────────────────────────────

    def _on_key(self, **kwargs: Any) -> None:
        """键盘事件回调（订阅 KEY_PRESS）。ESC 由 GameWindow.handle_escape 处理。"""
        symbol = int(kwargs.get("symbol", 0))
        if self._state == GameState.TITLE and self.main_menu is not None:
            self.main_menu.handle_key(symbol)

    # ── 滚轮 ────────────────────────────────────────────────

    def _on_scroll(self, **kwargs: Any) -> None:
        """滚轮事件回调（订阅 "scroll"）。"""
        dy = float(kwargs.get("scroll_y", 0))
        if self._state == GameState.CG_GALLERY:
            self.cg_gallery.handle_scroll(dy)
        elif self._state == GameState.MUSIC_ROOM:
            self.music_room.handle_scroll(dy)

    # ── 选项处理 ────────────────────────────────────────────

    def _on_choice(self, **kwargs: Any) -> None:
        """选项出现回调（订阅 "choice" 事件）— 将脚本选项转发到 ChoiceMenu。"""
        options = kwargs.get("options", [])
        if not options or self.ui_manager is None:
            return

        # 游戏中：用索引作为 tag（脚本执行器按索引跳转）
        choices = [
            (opt.get("text", ""), i)
            for i, opt in enumerate(options)
        ]
        self.ui_manager.choice.show(choices)

    def _on_choice_selected(self, **kwargs: Any) -> None:
        """游戏内选项分支（订阅 "choice_selected"）—— 交给脚本执行器。"""
        index = kwargs.get("index", -1)
        if index >= 0:
            if self.script_executor is not None:
                self.script_executor.on_choice_selected(index)
            else:
                logger.error("无法处理选项: script_executor 未初始化")

    def _on_menu_select(self, **kwargs: Any) -> None:
        """主菜单选择回调（订阅 "menu_select"）—— 按 tag 执行状态转换。"""
        tag = kwargs.get("tag", "")

        if tag == "new_game":
            self._start_new_game()
        elif tag == "load_game":
            self._show_load_menu()
        elif tag == "cg_gallery":
            self._enter_gallery_mode(GameState.CG_GALLERY)
        elif tag == "music_room":
            self._enter_gallery_mode(GameState.MUSIC_ROOM)
        elif tag == "character_viewer":
            self._enter_gallery_mode(GameState.CHARACTER_VIEWER)
        elif tag == "quit":
            if self._window is not None:
                self._window.on_close()
            else:
                pyglet.app.exit()

    def _on_scene_end(self, **kwargs: Any) -> None:
        """场景结束回调 — 返回标题画面。"""
        logger.info("场景结束，返回标题画面")
        self._return_to_title()

    # ── 状态转换 ────────────────────────────────────────────

    def _start_new_game(self) -> None:
        """开始新游戏：加载序章脚本。"""
        if self.script_executor is None:
            logger.error("无法开始新游戏: script_executor 未初始化")
            return
        if self.main_menu is not None:
            self.main_menu.hide()
        self._char_sprites.clear()
        try:
            script_path = f"{self.config.script_root}/prologue.ws"
            self.script_executor.load(script_path)
            self.script_executor.start()
            self.state = GameState.NOVEL
            logger.info("新游戏已开始: %s", script_path)
        except FileNotFoundError:
            logger.error("脚本文件未找到，无法开始新游戏")
        except Exception:
            logger.error("新游戏启动失败", exc_info=True)

    def _enter_gallery_mode(self, target: GameState) -> None:
        """进入鉴赏模式。"""
        if self._state == target:
            return
        if self.main_menu is not None:
            self.main_menu.hide()
        self.state = target
        if target == GameState.CG_GALLERY and self.cg_gallery is not None:
            self.cg_gallery.show()
        elif target == GameState.MUSIC_ROOM and self.music_room is not None:
            self.music_room.show()
        elif target == GameState.CHARACTER_VIEWER and self.character_viewer is not None:
            self.character_viewer.show()

    def _return_to_previous(self) -> None:
        """从鉴赏模式 / 设置返回上一个状态。"""
        if self._state == GameState.CG_GALLERY and self.cg_gallery is not None:
            self.cg_gallery.hide()
        elif self._state == GameState.MUSIC_ROOM and self.music_room is not None:
            self.music_room.hide()
        elif self._state == GameState.CHARACTER_VIEWER and self.character_viewer is not None:
            self.character_viewer.hide()

        prev = self._prev_state if self._prev_state is not None else GameState.TITLE
        self.state = prev

    def _hide_all_galleries(self) -> None:
        """隐藏所有鉴赏模式。"""
        if self.cg_gallery is not None:
            self.cg_gallery.hide()
        if self.music_room is not None:
            self.music_room.hide()
        if self.character_viewer is not None:
            self.character_viewer.hide()

    def _return_to_title(self) -> None:
        """返回标题画面。"""
        if self.script_executor is not None and self.script_executor.running:
            self.script_executor.running = False
        if self.audio is not None:
            self.audio.stop_bgm(fade_out=1.0)
        self._hide_all_galleries()
        if self.layers is not None:
            self.layers.clear_all()
        self._char_sprites.clear()
        if self.ui_manager is not None and self.ui_manager.dialog is not None:
            if self.ui_manager.dialog.visible:
                self.ui_manager.dialog.hide()
        self.state = GameState.TITLE
        self._show_main_menu()

    def _show_main_menu(self) -> None:
        """显示主菜单：加载标题背景 + 显示按钮。"""
        if self.main_menu is None or self.resource_manager is None or self.layers is None:
            return
        # 加载标题背景
        for path in ("images/学校-校门.png", "images/bg/title.png"):
            img = self.resource_manager.get_image(path)
            if img is not None:
                self.layers.set_background(img)
                break
        self.main_menu.show()
        logger.info("主菜单已显示")

    def _start_title_screen(self) -> None:
        """启动标题画面脚本。"""
        if self.script_executor is None:
            logger.error("标题画面启动失败: script_executor 未初始化")
            return
        try:
            script_path = f"{self.config.script_root}/title.ws"
            self.script_executor.load(script_path)
            self.script_executor.start()
            logger.info("标题画面脚本已启动")
        except FileNotFoundError:
            logger.warning("标题画面脚本未找到: %s（引擎可正常运行）", script_path)
        except Exception:
            logger.error("标题画面启动失败", exc_info=True)

    def _show_load_menu(self) -> None:
        """显示读档菜单（TODO：可扩展为完整 UI）。"""
        if self.save_system is None:
            return
        slots = sorted(self.save_system.list_slots())
        if not slots:
            logger.info("没有可用的存档")
            return
        # 加载最近存档
        latest = slots[-1]
        data = self.save_system.load(latest)
        if data is not None:
            self._apply_save_data(data)
            logger.info("已加载存档: slot=%d", latest)

    def _apply_save_data(self, data: Any) -> None:
        """将存档数据应用到运行时状态。"""
        self.flags.clear()
        self.flags.update(data.flags)
        self.variable_bank.clear()
        self.variable_bank.update(data.vars)
        if self.script_executor is not None:
            self.script_executor.load(data.script_file)
            self.script_executor.start()
            if data.label_name:
                self.script_executor.jump(data.label_name)
        self.state = GameState.NOVEL

    # ── 子系统注册 ──────────────────────────────────────────

    def register(self, name: str, subsystem: Any) -> None:
        """按属性名注册子系统。

        Args:
            name: 子系统属性名（如 ``"audio"``）。
            subsystem: 子系统实例。

        Raises:
            AttributeError: 若 name 不是预设的子系统槽位。
        """
        if not hasattr(self, name):
            raise AttributeError(f"未知的子系统槽位: {name}")
        setattr(self, name, subsystem)
        logger.debug("子系统 '%s' 已注册", name)

    # ── 清理 ────────────────────────────────────────────────

    def shutdown(self) -> None:
        """释放所有子系统资源。"""
        logger.info("引擎关闭中...")
        if self.audio is not None:
            self.audio.stop_bgm(fade_out=0.0)
        if self.resource_manager is not None:
            self.resource_manager.shutdown()
        self.events.clear()
        logger.info("引擎已关闭")
