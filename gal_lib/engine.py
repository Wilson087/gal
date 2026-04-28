"""
游戏引擎主模块
==============
定义 VNGame 类，统筹管理场景切换、对话流程、立绘更新、
选项分支、存档读档、文本历史和设置面板等核心游戏逻辑。

现代化升级功能：
- 富文本标记（等待、震动、变色、变速）
- 角色说话动画（浮动、脉冲）
- 角色名标签颜色
- 圆角对话框 / 可配置对话框位置
- 四通道音频（BGM/SFX/Voice + 独立音量）
- BGM 交叉淡入淡出
- 转场效果（淡入淡出、滑动、百叶窗、涟漪）
- 屏幕滤镜、粒子天气、屏幕震动/闪烁
- 多槽位存档/读档（含缩略图占位、日期、摘要）
- 自动模式 / 跳过模式
- 增强回看历史（可重播语音）
- 变量系统 / 条件选项
- CG 画廊
- 历史导出
- 主菜单
"""

import datetime
import json
import os
import pickle
import threading
import tkinter as tk
from pathlib import Path
from typing import Any, Callable, Optional

from .constants import *
from .script import load_from_file, validate_script
from .renderer import (
    render_background,
    draw_character,
)
from .audio import AudioEngine
from .ui import UIManager
from .rich_text import parse_rich_text, strip_rich_tags, RichSegment
from .effects import (
    transition_crossfade,
    transition_slide,
    transition_blinds,
    transition_ripple,
    TRANSITION_FUNCTIONS,
    apply_filter,
    remove_filter,
    start_noise,
    stop_noise,
    start_snow,
    start_rain,
    stop_particles,
    start_shake,
    stop_shake,
    start_flash,
)
from collections import OrderedDict  # noqa: F401


# ========================================================================
#  主引擎类
# ========================================================================

class VNGame:
    """视觉小说游戏主引擎。

    负责：
    - 剧本加载与场景切换
    - 对话逐字显示与推进（支持富文本标记）
    - 立绘（左/右）显示与淡入淡出 + 说话动画
    - 背景切换过渡（多种转场效果）
    - 选项分支（支持变量条件）
    - 多槽位存档/读档（缩略图、日期、摘要）
    - 文本历史弹窗（语音重播）
    - 设置面板（多通道音量、文字速度、全屏等）
    - 自动模式 / 跳过模式
    - 变量系统 / CG 画廊
    - 主菜单

    用法:
        root = tk.Tk()
        game = VNGame(root)
        game.load_script("script.json")
        game.start_game()
        root.mainloop()
    """

    # ====================================================================
    #  初始化
    # ====================================================================

    def __init__(self, root: tk.Tk) -> None:
        """初始化引擎。

        Args:
            root: tkinter 根窗口对象。
        """
        self.root = root
        self.root.title("视觉小说引擎")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.configure(bg=COLOR_BG_DARK)

        # ── 游戏数据 ──────────────────────────────────────────
        self.script: Optional[dict] = None
        self.scenes_dict: dict[str, dict] = {}
        self.current_scene_id: Optional[str] = None
        self.dialogue_index: int = 0
        self.history: list[dict] = []  # [{speaker, text, voice}]

        # ── 运行时状态 ────────────────────────────────────────
        self._typing = False
        self._skip_type = False
        self._choosing = False
        self._typewriter_timer: Optional[str] = None
        self._current_full_text = ""
        self._current_rich_segments: list[RichSegment] = []
        self._game_ended = False
        self._title_showing = False
        self._start_label: Optional[int] = None
        self._in_main_menu = False

        # ── 设置 ──────────────────────────────────────────────
        self.text_speed = DEFAULT_TEXT_SPEED
        self._text_speed_base = DEFAULT_TEXT_SPEED
        self.dialog_position = DEFAULT_DIALOG_POSITION
        self.skip_mode = "read"  # "read" / "all" / "off"
        self._skip_active = False
        self._auto_mode = False
        self._auto_timer: Optional[str] = None

        # ── 富文本渲染状态 ────────────────────────────────────
        self._current_text_color: Optional[str] = None
        self._current_text_speed_mult = 1.0
        self._shake_text = False
        self._shake_text_timer: Optional[str] = None

        # ── 音频引擎 ──────────────────────────────────────────
        self.audio = AudioEngine()
        self.audio.on_voice_end = self._on_voice_end

        # ── 立绘引用 ──────────────────────────────────────────
        self.char_left_items: list[int] = []
        self.char_right_items: list[int] = []

        # ── 说话动画 ──────────────────────────────────────────
        self._speaking_side: Optional[str] = None  # "left" / "right"
        self._speaking_anim_timer: Optional[str] = None
        self._speaking_anim_step = 0
        self._char_orig_positions: dict[str, int] = {}  # tag -> original y

        # ── 过渡遮罩 ID ───────────────────────────────────────
        self.bg_overlay: Optional[int] = None

        # ── 屏幕滤镜 ──────────────────────────────────────────
        self._current_filter = FILTER_NONE

        # ── UI 管理 ──────────────────────────────────────────
        self.ui = UIManager(root)
        self.ui.configure_root("视觉小说引擎")

        # 设置 UI 回调
        self.ui.set_callbacks(
            on_advance=self._on_advance,
            on_choice=self._on_choice_from_ui,
            on_save=lambda: self._open_save_load("save"),
            on_load=lambda: self._open_save_load("load"),
            on_history=self.show_history,
            on_main_menu=self._show_main_menu,
            on_settings=self._open_settings,
        )

        # 构建主界面
        self.ui.build_main_ui()

        # UI 组件快捷引用（引擎内部大量使用，保持向后兼容）
        self.canvas: Optional[tk.Canvas] = self.ui.canvas
        self.dialogue_frame: Optional[tk.Frame] = self.ui.dialogue_frame
        self.speaker_label: Optional[tk.Label] = self.ui.speaker_label
        self.text_label: Optional[tk.Label] = self.ui.text_label
        self.next_indicator: Optional[tk.Label] = self.ui.next_indicator
        self.hint_label: Optional[tk.Label] = self.ui.hint_label
        self.choice_frame: Optional[tk.Frame] = None  # 由 UIManager 管理
        self.choice_buttons: list[tk.Button] = []
        self.choice_overlay: Optional[int] = None
        self.main_menu_frame: Optional[tk.Frame] = None

        # ── 变量系统 ──────────────────────────────────────────
        self.variables: dict[str, Any] = {}

        # ── 首个场景 ID（新游戏从这里开始，可在加载剧本后修改） ──
        self.first_scene: str = "start"
        self._seen_dialogues: set[str] = set()  # 已读对话追踪

        # ── CG 画廊 ──────────────────────────────────────────
        self._unlocked_cgs: set[str] = set()
        self._scene_screenshots: dict[str, str] = OrderedDict()  # scene_id -> thumbnail path

        # ── 事件绑定 ─────────────────────────────────────────
        self._bind_events()

    # ====================================================================
    #  UI 构建
    # ====================================================================

    def _build_ui(self) -> None:
        """构建游戏主界面。

        委托给 UIManager.build_main_ui()，已在 __init__ 中调用。
        """
        pass  # UI 构建已由 self.ui 在 __init__ 中完成

    # ====================================================================
    #  事件绑定
    # ====================================================================

    def _bind_events(self) -> None:
        """绑定键盘 / 鼠标事件。"""
        self.root.bind("<space>", self._on_advance)
        self.root.bind("<Return>", self._on_advance)
        self.root.bind("<s>", lambda e: self.save_game())
        self.root.bind("<S>", lambda e: self.save_game())
        self.root.bind("<l>", lambda e: self.load_game())
        self.root.bind("<L>", lambda e: self.load_game())
        self.root.bind("<h>", lambda e: self.show_history())
        self.root.bind("<H>", lambda e: self.show_history())
        self.root.bind("<Escape>", lambda e: self._open_settings())

        # 快进/快退
        self.root.bind("<F5>", lambda e: self.quick_save())
        self.root.bind("<F9>", lambda e: self.quick_load())

        # 自动模式
        self.root.bind("a", lambda e: self._toggle_auto_mode())
        self.root.bind("A", lambda e: self._toggle_auto_mode())

        # 全屏
        self.root.bind("<F11>", lambda e: self._toggle_fullscreen())

        if self.canvas:
            self.canvas.bind("<Button-1>", self._on_advance)

        self.root.bind("<Configure>", self._on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self._on_game_close)

    def _on_resize(self, event: tk.Event) -> None:
        if event.widget is self.root:
            self.ui.update_text_wraplength(event.width)

    def _on_game_close(self) -> None:
        self.audio.shutdown()
        self.root.destroy()

    # ====================================================================
    #  剧本加载
    # ====================================================================

    def load_script(self, source: str | dict) -> None:
        """加载并解析剧本数据。

        Args:
            source: 剧本文件路径或字典对象。
        """
        try:
            if isinstance(source, str):
                self.script = load_from_file(source)
            elif isinstance(source, dict):
                self.script = source
            else:
                raise TypeError("source 必须是文件路径 (str) 或剧本字典 (dict)")

            errors = validate_script(self.script)
            if errors:
                detail = "\n".join(errors[:5])
                raise ValueError(f"剧本格式错误 ({len(errors)} 项):\n{detail}")

            self.scenes_dict = {s["id"]: s for s in self.script["scenes"]}
            self.root.title(self.script.get("title", "视觉小说框架"))

            # 从剧本读取角色名颜色配置
            char_colors = self.script.get("character_colors", {})
            CHARACTER_NAME_COLORS.update(char_colors)

        except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"剧本加载失败: {e}")
            self._show_error_and_exit(str(e))

    def _show_error_and_exit(self, message: str) -> None:
        self.ui.show_error_dialog(message, on_close=self.root.destroy)

    # ====================================================================
    #  变量系统
    # ====================================================================

    def get_var(self, name: str, default: Any = 0) -> Any:
        """获取变量值。

        Args:
            name: 变量名。
            default: 默认值。

        Returns:
            变量值。
        """
        return self.variables.get(name, default)

    def set_var(self, name: str, value: Any) -> None:
        """设置变量值。

        支持自增/自减语法：值以 "+" 或 "-" 开头表示相对变更。

        Args:
            name: 变量名。
            value: 新值或相对变更表达式。
        """
        if isinstance(value, str) and len(value) > 1 and value[0] in ("+", "-"):
            try:
                delta = int(value)
                self.variables[name] = self.variables.get(name, 0) + delta
            except ValueError:
                self.variables[name] = value
        else:
            self.variables[name] = value

    def _evaluate_condition(self, condition: str) -> bool:
        """求值条件表达式。

        格式: "变量名 运算符 值"
        运算符支持: >, <, >=, <=, ==, !=

        Args:
            condition: 条件字符串，如 "affection > 2"。

        Returns:
            条件是否成立。无法解析时返回 True（视为无条件）。
        """
        if not condition:
            return True
        parts = condition.split()
        if len(parts) != 3:
            return True
        var_name, op, raw_val = parts
        var_val = self.variables.get(var_name, 0)
        try:
            cmp_val = int(raw_val)
        except ValueError:
            cmp_val = raw_val

        if op == ">":
            return var_val > cmp_val
        elif op == "<":
            return var_val < cmp_val
        elif op == ">=":
            return var_val >= cmp_val
        elif op == "<=":
            return var_val <= cmp_val
        elif op == "==":
            return var_val == cmp_val
        elif op == "!=":
            return var_val != cmp_val
        return True

    # ====================================================================
    #  游戏启动 / 主菜单
    # ====================================================================

    def start_game(self) -> None:
        """启动游戏：进入主菜单。"""
        self._show_main_menu()

    def _show_main_menu(self) -> None:
        """显示主菜单（新游戏、继续、画廊、设置、退出）。"""
        self._in_main_menu = True
        self._title_showing = True
        self._cleanup_main_menu()
        self._clear_all()
        self.ui.set_dialogue_frame_visible(False)

        title = (self.script.get("title", "") if self.script else "") or "视觉小说引擎"
        ver = self.script.get("version", "") if self.script else ""

        has_saves = self._has_any_save()
        buttons = [("新游戏", self._on_new_game)]
        if has_saves:
            buttons.append(("继续游戏", self._on_continue))
        buttons.extend([
            ("CG 画廊", self._open_gallery),
            ("设置", self._open_settings),
            ("退出", self._on_menu_quit),
        ])

        self.ui.show_main_menu(title, version=ver, buttons=buttons)

    def _on_new_game(self) -> None:
        """新游戏：重置变量、清除存档状态，从 start 场景开始。"""
        self._in_main_menu = False
        self._title_showing = False
        self._cleanup_main_menu()
        self.ui.set_dialogue_frame_visible(True)
        self.variables = {}
        self._seen_dialogues = set()
        self.history = []
        if self.canvas:
            self.canvas.bind("<Button-1>", self._on_advance)
        self._enter_scene(self.first_scene)

    def _on_continue(self) -> None:
        """继续游戏：打开读档界面。"""
        self._open_save_load("load")

    def _on_menu_quit(self) -> None:
        """退出游戏。"""
        self.audio.shutdown()
        self.root.destroy()

    def _cleanup_main_menu(self) -> None:
        """清理主菜单 UI。"""
        self.ui.cleanup_main_menu()

    def _has_any_save(self) -> bool:
        """检查是否存在存档文件。"""
        if not SAVE_DIR.exists():
            return False
        for f in SAVE_DIR.iterdir():
            if f.name.startswith("save_") and f.suffix == ".dat":
                return True
        return False

    def _blink_title(self) -> None:
        if not self._title_showing or self._start_label is None:
            return
        self.ui.blink_text_item(
            self._start_label, COLOR_TEXT_SPEAKER, COLOR_TEXT_ACCENT, 600)

    # ====================================================================
    #  场景管理
    # ====================================================================

    def _enter_scene(self, scene_id: str,
                     transition: str = DEFAULT_TRANSITION) -> None:
        """切换到指定场景。

        Args:
            scene_id: 目标场景 ID。
            transition: 转场效果类型。
        """
        self._cancel_typewriter()
        self._cleanup_choice_frame()
        self._stop_speaking_animation()
        self.dialogue_index = 0
        self.current_scene_id = scene_id
        self._choosing = False
        self._game_ended = False

        scene = self.scenes_dict.get(scene_id)
        if scene is None:
            self._show_error_and_exit(f"场景 '{scene_id}' 不存在")
            return

        # 处理场景音效指令
        if "sfx" in scene:
            self.audio.play_sfx(scene["sfx"])

        # 处理场景画面滤镜
        if "filter" in scene:
            w = self.canvas.winfo_width() or WINDOW_WIDTH
            h = self.canvas.winfo_height() or WINDOW_HEIGHT
            intensity = scene.get("filter_intensity", 0.3)
            apply_filter(self.canvas, scene["filter"], w, h, intensity)

        # 处理场景天气效果
        weather = scene.get("weather", "").lower()
        if weather in ("snow", "rain"):
            w = self.canvas.winfo_width() or WINDOW_WIDTH
            h = self.canvas.winfo_height() or WINDOW_HEIGHT
            count = scene.get("weather_count", 60)
            if weather == "snow":
                start_snow(self.canvas, w, h, count)
            else:
                start_rain(self.canvas, w, h, count)
        else:
            stop_particles(self.canvas)

        # BGM 切换（带交叉淡入淡出）
        if "bgm" in scene:
            bgm_path = scene.get("bgm")
            if bgm_path:
                self.audio.play_bgm(bgm_path,
                                    loop_point=scene.get("bgm_loop_point"))
            else:
                self.audio.stop_bgm()

        def _after_bg():
            self._update_characters(scene.get("characters", {}))
            # 处理场景入场脚本（voice 等）
            scene_voice = scene.get("voice")
            if scene_voice:
                self.audio.play_voice(scene_voice)
            self._show_current_dialogue()

        # 使用效果模块的转场
        bg_id = scene.get("background", "")
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT
        transition_func = TRANSITION_FUNCTIONS.get(transition, transition_crossfade)
        transition_func(self.canvas, "", bg_id, w, h,
                        on_complete=_after_bg,
                        duration=TRANSITION_DURATION)

    def _show_current_dialogue(self) -> None:
        """按当前对话索引显示对白或选项。"""
        scene = self.scenes_dict.get(self.current_scene_id)
        if scene is None:
            return

        dialogues = scene.get("dialogue", [])
        choices = scene.get("choices")

        if self.dialogue_index < len(dialogues):
            entry = dialogues[self.dialogue_index]
            speaker = entry.get("speaker", "")
            text = entry.get("text", "")

            # 记录已读对话（纯文本）
            self._seen_dialogues.add(strip_rich_tags(text))

            # 单句内立绘变化
            if "character_left" in entry or "character_right" in entry:
                char_data = {}
                if "character_left" in entry:
                    char_data["left"] = entry["character_left"]
                if "character_right" in entry:
                    char_data["right"] = entry["character_right"]
                self._update_characters(char_data)

            # 音效
            sfx_path = entry.get("sfx")
            if sfx_path:
                self.audio.play_sfx(sfx_path)

            # 语音
            voice_path = entry.get("voice")
            if voice_path:
                self.audio.play_voice(voice_path)

            # 变量操作
            if "set_var" in entry:
                for k, v in entry["set_var"].items():
                    self.set_var(k, v)

            # 启动说话动画
            if speaker:
                self._start_speaking_for(speaker)

            # 检查跳过模式
            if self.skip_mode == "all":
                self._skip_active = True
            elif self.skip_mode == "read":
                # 已读跳过，用对话文本做判断（简化处理）
                pass

            # 调试：打印当前对话内容
            print(f"[DEBUG] _show_current_dialogue idx={self.dialogue_index} "
                  f"speaker={speaker!r} text={text[:40]!r} "
                  f"char_right={entry.get('character_right', '')!r} "
                  f"typing={self._typing}")

            self.show_dialogue(text, speaker)

        elif choices:
            valid_choices = []
            for c in choices:
                condition = c.get("if", "")
                if self._evaluate_condition(condition):
                    valid_choices.append(c)
            if valid_choices:
                self.show_choices(valid_choices)
            else:
                # 没有可用选项，视为场景结束
                self._end_of_scene()
        else:
            self._end_of_scene()

    def _end_of_scene(self) -> None:
        """场景结束处理。"""
        self._game_ended = True
        self.speaker_label.config(text="")
        self.text_label.config(text="—— END ——")
        self.next_indicator.config(text="")
        if self.canvas:
            self.canvas.bind("<Button-1>", lambda e: self._show_main_menu())

    def _next_dialogue(self) -> None:
        """推进到下一句对白。"""
        if self._choosing or self._title_showing or self._game_ended:
            return
        if self.current_scene_id is None:
            return
        self._stop_speaking_animation()
        self.dialogue_index += 1
        self._show_current_dialogue()

    # ====================================================================
    #  对话推进事件
    # ====================================================================

    def _on_advance(self, event: tk.Event = None) -> None:
        """处理推进操作。"""
        if self._title_showing or self._in_main_menu:
            return

        if self._game_ended:
            self._show_main_menu()
            return

        if self._choosing:
            return

        if self._typing:
            self._skip_type = True
            return

        self._next_dialogue()

    # ====================================================================
    #  背景切换（兼容旧接口）
    # ====================================================================

    def _transition_background(self, new_bg_id: str,
                                on_complete=None) -> None:
        """背景切换（兼容旧接口，使用默认交叉淡入淡出）。

        Args:
            new_bg_id: 新背景标识符。
            on_complete: 完成回调。
        """
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT
        transition_crossfade(self.canvas, "", new_bg_id, w, h,
                              on_complete=on_complete)

    # ====================================================================
    #  立绘系统
    # ====================================================================

    def _update_characters(self, char_data: dict) -> None:
        """更新左右立绘（带淡入淡出）。

        Args:
            char_data: {"left": char_id, "right": char_id}。
        """
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT
        y_bottom = h - 20

        left_id = char_data.get("left")
        right_id = char_data.get("right")

        self._fade_out_and_replace("left", left_id, int(w * 0.22), y_bottom)
        self._fade_out_and_replace("right", right_id, int(w * 0.78), y_bottom)

    def _fade_out_and_replace(self, side: str, new_char_id: Optional[str],
                               x_center: int, y_bottom: int) -> None:
        """单侧立绘淡出 -> 替换 -> 淡入。"""
        tag = "left_char" if side == "left" else "right_char"
        old_items = self.char_left_items if side == "left" else self.char_right_items

        def _fade_out(idx=0):
            if idx < len(FADE_OUT_STEPPLES) and old_items:
                stipple = FADE_OUT_STEPPLES[idx]
                for item_id in list(old_items):
                    try:
                        self.canvas.itemconfig(item_id, stipple=stipple)
                    except tk.TclError:
                        pass
                self.root.after(CHAR_FADE_INTERVAL, _fade_out, idx + 1)
            else:
                self.canvas.delete(tag)
                old_items.clear()

                if not new_char_id:
                    if side == "left":
                        self.char_left_items = []
                    else:
                        self.char_right_items = []
                    return

                new_items = draw_character(
                    self.canvas, new_char_id, x_center, y_bottom)
                for item_id in new_items:
                    try:
                        self.canvas.itemconfig(item_id, stipple="gray12")
                    except tk.TclError:
                        pass
                    self.canvas.addtag(tag, "withtag", item_id)

                if side == "left":
                    self.char_left_items = new_items
                else:
                    self.char_right_items = new_items

                _fade_in(0, new_items)

        def _fade_in(idx=0, items=None):
            if items is None:
                return
            if idx < len(FADE_IN_STEPPLES):
                stipple = FADE_IN_STEPPLES[idx]
                for item_id in items:
                    try:
                        self.canvas.itemconfig(item_id, stipple=stipple)
                    except tk.TclError:
                        pass
                self.root.after(CHAR_FADE_INTERVAL, _fade_in, idx + 1, items)

        _fade_out(0)

    # ====================================================================
    #  说话动画
    # ====================================================================

    _character_speaker_tags: dict[str, str] = {}  # speaker_name -> char_tag

    def _start_speaking_for(self, speaker: str) -> None:
        """根据说话者启动对应立绘的说话动画。

        Args:
            speaker: 说话角色名。
        """
        scene = self.scenes_dict.get(self.current_scene_id)
        if not scene:
            return
        chars = scene.get("characters", {})
        current_entry = scene.get("dialogue", [])
        if self.dialogue_index < len(current_entry):
            entry = current_entry[self.dialogue_index]
            if "character_left" in entry:
                chars["left"] = entry["character_left"]
            if "character_right" in entry:
                chars["right"] = entry["character_right"]

        # 尝试匹配角色名和立绘
        target_side = None
        for side in ("left", "right"):
            char_id = chars.get(side)
            if char_id:
                _, name = (PLACEHOLDER_COLORS.get(char_id, ("#7f8c8d", ""))
                           if char_id else ("", ""))
                if name and (name == speaker or speaker in name or name in speaker):
                    target_side = side
                    break

        # 无匹配时看哪侧有立绘就动哪侧
        if target_side is None:
            if self.char_left_items and chars.get("left"):
                target_side = "left"
            elif self.char_right_items and chars.get("right"):
                target_side = "right"

        if target_side:
            self._start_speaking_animation(target_side)

    def _start_speaking_animation(self, side: str) -> None:
        """启动指定侧立绘说话浮动动画。

        Args:
            side: "left" 或 "right"。
        """
        self._stop_speaking_animation()
        self._speaking_side = side
        self._speaking_anim_step = 0
        items = self.char_left_items if side == "left" else self.char_right_items
        if not items:
            return

        # 记录原始 y 坐标
        tag = "left_char" if side == "left" else "right_char"
        # 存原始位置前先清空（首次）
        if not self._char_orig_positions:
            # 遍历找第一个位置项
            for item_id in items:
                try:
                    coords = self.canvas.coords(item_id)
                    if coords:
                        # 用第一个 y 作为基准
                        self._char_orig_positions[tag] = int(coords[1])
                        break
                except tk.TclError:
                    pass

        self._speaking_anim_tick()

    def _speaking_anim_tick(self) -> None:
        """说话动画帧更新。"""
        if self._speaking_side is None:
            return

        side = self._speaking_side
        items = self.char_left_items if side == "left" else self.char_right_items
        if not items:
            self._speaking_side = None
            return

        tag = "left_char" if side == "left" else "right_char"
        # 浮动曲线：sin 波
        step = self._speaking_anim_step
        float_amount = CHAR_SPEAK_FLOAT_AMOUNT

        # Bounce 关键帧：0, -max, -max/2, 0
        bounce_table = [0, -float_amount, -float_amount // 2, 0]
        offset = bounce_table[step % len(bounce_table)]

        for item_id in items:
            try:
                self.canvas.move(item_id, 0, offset - getattr(self, f"_last_offset_{side}", 0))
            except tk.TclError:
                pass

        setattr(self, f"_last_offset_{side}", offset)
        self._speaking_anim_step += 1

        # 同时检测语音是否还在播放
        if self.audio.voice_playing:
            self._speaking_anim_timer = self.root.after(
                CHAR_ANIMATION_INTERVAL, self._speaking_anim_tick)
        else:
            # 语音结束，继续动画一小段时间后停止
            if self._speaking_anim_step < 8:
                self._speaking_anim_timer = self.root.after(
                    CHAR_ANIMATION_INTERVAL, self._speaking_anim_tick)
            else:
                self._reset_character_position(side)

    def _stop_speaking_animation(self) -> None:
        """停止说话动画。"""
        if self._speaking_anim_timer:
            try:
                self.root.after_cancel(self._speaking_anim_timer)
            except ValueError:
                pass
            self._speaking_anim_timer = None
        if self._speaking_side:
            self._reset_character_position(self._speaking_side)
        self._speaking_side = None
        self._speaking_anim_step = 0

    def _reset_character_position(self, side: str) -> None:
        """复位角色立绘 y 位置。"""
        tag = "left_char" if side == "left" else "right_char"
        for item_id in (self.char_left_items if side == "left" else self.char_right_items):
            try:
                coords = self.canvas.coords(item_id)
                if coords and len(coords) >= 2:
                    self.canvas.move(item_id, 0, -getattr(self, f"_last_offset_{side}", 0))
            except tk.TclError:
                pass
        setattr(self, f"_last_offset_{side}", 0)

    def _on_voice_end(self) -> None:
        """语音播放结束回调。"""
        # 如果正在自动模式，触发下一步
        if self._auto_mode and not self._typing:
            self._schedule_auto_next()

    # ====================================================================
    #  对话（打字机效果 + 富文本）
    # ====================================================================

    def show_dialogue(self, text: str, speaker: str = "") -> None:
        """显示对白并启动打字机逐字效果（支持富文本标记）。

        Args:
            text: 对白文本（可含 {w=} {color=} {shake} 等标记）。
            speaker: 说话角色名。
        """
        self._cancel_typewriter()
        self.next_indicator.config(text="")
        self._current_full_text = text
        self._current_rich_segments = parse_rich_text(text)
        self._typing = True
        self._skip_type = False

        # 角色名标签颜色
        speaker_color = CHARACTER_NAME_COLORS.get(speaker, DEFAULT_SPEAKER_COLOR if speaker else DEFAULT_NARRATOR_COLOR)
        self.speaker_label.config(text=speaker if speaker else "",
                                   fg=speaker_color)

        self.text_label.config(text="")
        self._text_speed_base = self.text_speed
        self._current_text_color = None
        self._current_text_speed_mult = 1.0
        self._shake_text = False

        # 开始逐字显示
        self._char_index = 0
        self._seg_index = 0
        self._seg_char_pos = 0
        self._current_segments_text = ""

        # 启动行走指针（遍历分段）
        self._typewriter_process()

        print(f"[DEBUG] show_dialogue done, speaker={speaker!r} "
              f"segments={len(self._current_rich_segments)}, _typing={self._typing}")

    def _typewriter_process(self) -> None:
        """富文本打字机处理：遍历分段，逐字输出。"""
        if not self._typing:
            print(f"[DEBUG] _typewriter_process SKIP: _typing=False")
            return

        if self._skip_type:
            print(f"[DEBUG] _typewriter_process SKIP_TYPE")
            self._finish_typewriter()
            return

        segments = self._current_rich_segments

        # 找到当前应该处理的段
        while self._seg_index < len(segments):
            seg = segments[self._seg_index]

            if seg.type == "text":
                # 输出文本
                raw_text = seg.text
                if self._seg_char_pos < len(raw_text):
                    # 输出一个字
                    self._current_segments_text += raw_text[self._seg_char_pos]
                    self._seg_char_pos += 1
                    self._update_text_display()

                    # 调试：第一个字符
                    if self._seg_char_pos == 1:
                        import sys
                        print(f"[DEBUG] typewriter START: text={raw_text[:30]!r}", flush=True)

                    # 计算打字延迟
                    delay = int(self._text_speed_base * self._current_text_speed_mult)
                    self._typewriter_timer = self.root.after(
                        delay, self._typewriter_process)
                    return
                else:
                    # 本段结束
                    self._seg_index += 1
                    self._seg_char_pos = 0

            elif seg.type == "wait":
                # 等待
                wait_ms = int(seg.data * 1000) if seg.data else 500
                self._typewriter_timer = self.root.after(
                    wait_ms, self._typewriter_process)
                self._seg_index += 1
                return

            elif seg.type == "color":
                self._current_text_color = seg.data
                self._update_text_display()
                self._seg_index += 1

            elif seg.type == "endcolor":
                self._current_text_color = None
                self._seg_index += 1

            elif seg.type == "speed":
                self._current_text_speed_mult = seg.data if seg.data else 1.0
                self._seg_index += 1

            elif seg.type == "endspeed":
                self._current_text_speed_mult = 1.0
                self._seg_index += 1

            elif seg.type == "shake":
                self._shake_text = True
                self._start_text_shake()
                self._seg_index += 1

            elif seg.type == "endshake":
                self._shake_text = False
                self._stop_text_shake()
                self._seg_index += 1

            elif seg.type == "font":
                # 字体切换（复杂，暂跳过）
                self._seg_index += 1

            elif seg.type == "endfont":
                self._seg_index += 1

            else:
                self._seg_index += 1

        # 全部分段处理完毕
        if self._seg_index >= len(segments):
            self._finish_typewriter()

    def _update_text_display(self) -> None:
        """更新文字标签显示（应用颜色）。"""
        display_text = self._current_segments_text
        if self._current_text_color:
            # tkinter Label 不支持内联颜色，设置整体颜色
            self.text_label.config(fg=self._current_text_color)
        else:
            self.text_label.config(fg=COLOR_TEXT_PRIMARY)
        self.text_label.config(text=display_text)

    def _start_text_shake(self) -> None:
        """启动文字震动。"""
        if self._shake_text_timer:
            return

        def _tick():
            if not self._shake_text:
                self._shake_text_timer = None
                return
            # 通过修改标签的 padx/pady 微调位置
            curr_padx = self.text_label.cget("padx")
            import random
            offset = random.randint(-2, 2)
            try:
                self.text_label.config(padx=24 + offset)
            except tk.TclError:
                pass
            self._shake_text_timer = self.root.after(50, _tick)

        _tick()

    def _stop_text_shake(self) -> None:
        """停止文字震动。"""
        if self._shake_text_timer:
            try:
                self.root.after_cancel(self._shake_text_timer)
            except ValueError:
                pass
            self._shake_text_timer = None
        try:
            self.text_label.config(padx=24)
        except tk.TclError:
            pass

    def _finish_typewriter(self) -> None:
        """打字完成：显示全文、记录历史、显示 ▼ 指示器。"""
        self._typing = False
        self._skip_type = False
        self._stop_text_shake()

        # 显示完整纯文本
        clean_text = strip_rich_tags(self._current_full_text)
        self.text_label.config(text=clean_text, fg=COLOR_TEXT_PRIMARY)

        # 记录历史
        speaker = self.speaker_label.cget("text")
        voice_path = None
        scene = self.scenes_dict.get(self.current_scene_id)
        if scene:
            dialogues = scene.get("dialogue", [])
            if self.dialogue_index < len(dialogues):
                voice_path = dialogues[self.dialogue_index].get("voice")

        self.history.append({
            "speaker": speaker,
            "text": clean_text,
            "voice": voice_path,
            "scene": self.current_scene_id,
            "time": datetime.datetime.now().isoformat(),
        })
        if len(self.history) > 200:
            self.history = self.history[-200:]

        self.next_indicator.config(text="▼")

        # 自动模式
        if self._auto_mode:
            self._schedule_auto_next()

    def _cancel_typewriter(self) -> None:
        """取消正在进行的打字机计时器。"""
        if self._typewriter_timer:
            try:
                self.root.after_cancel(self._typewriter_timer)
            except ValueError:
                pass
            self._typewriter_timer = None
        self._typing = False
        self._skip_type = False
        self._stop_text_shake()

    # ====================================================================
    #  自动模式
    # ====================================================================

    def _toggle_auto_mode(self) -> None:
        """切换自动模式开关。"""
        if self._auto_mode:
            self._stop_auto_mode()
        else:
            self._start_auto_mode()

    def _start_auto_mode(self) -> None:
        """启动自动模式。"""
        self._auto_mode = True
        self.ui.show_notification("自动模式 ON", color="#2ecc71", duration=1000)
        if not self._typing and not self._choosing and not self._title_showing:
            self._schedule_auto_next()

    def _stop_auto_mode(self) -> None:
        """停止自动模式。"""
        self._auto_mode = False
        if self._auto_timer:
            try:
                self.root.after_cancel(self._auto_timer)
            except ValueError:
                pass
            self._auto_timer = None
        self.ui.show_notification("自动模式 OFF", color="#e74c3c", duration=1000)

    def _schedule_auto_next(self) -> None:
        """安排自动模式的下一次推进。"""
        if not self._auto_mode or self._choosing or self._title_showing or self._game_ended:
            return

        # 计算等待时间
        delay = AUTO_DEFAULT_DELAY
        clean_text = strip_rich_tags(self._current_full_text)
        delay += len(clean_text) * AUTO_CHAR_DELAY

        # 如果有语音，等语音结束
        if self.audio.voice_playing:
            delay = max(delay, 300)  # 短轮询
            self._auto_timer = self.root.after(200, self._schedule_auto_next)
            return

        self._auto_timer = self.root.after(min(delay, 5000), self._next_dialogue)

    # ====================================================================
    #  跳过模式
    # ====================================================================

    def _start_skip(self) -> None:
        """启动跳过模式。"""
        self._skip_active = True
        self._skip_type = True

    def _stop_skip(self) -> None:
        """停止跳过模式。"""
        self._skip_active = False

    # ====================================================================
    #  选项分支
    # ====================================================================

    def show_choices(self, choices: list[dict]) -> None:
        """在画面中央显示选项按钮。

        支持条件选项: choice 中可含 "if" 字段。
        委托给 UIManager 渲染 UI。

        Args:
            choices: [{"text": "...", "next_scene": "...", "if": "..."}, ...]。
        """
        self._choosing = True
        self.ui.show_next_indicator(False)
        self.ui.show_choices(choices)

    def _on_choice_selected(self, next_scene: str) -> None:
        """选项被选中 -> 跳转场景。"""
        self._cleanup_choice_frame()
        self._choosing = False
        self._enter_scene(next_scene)

    def _on_choice_from_ui(self, choice_dict: dict) -> None:
        """UIManager 选项回调：处理 set_var 后跳转。

        Args:
            choice_dict: 完整的选项字典。
        """
        # 处理变量效果
        effects = choice_dict.get("set_var")
        if effects:
            for k, v in effects.items():
                self.set_var(k, v)
        next_scene = choice_dict.get("next_scene", "")
        self._on_choice_selected(next_scene)

    def _cleanup_choice_frame(self) -> None:
        """清理选项 UI。"""
        self.ui.cleanup_choices()

    # ====================================================================
    #  存档 / 读档（增强版）
    # ====================================================================

    def save_game(self, slot: int = 0) -> None:
        """保存当前进度到指定存档槽。

        Args:
            slot: 存档槽编号（0-99）或 "auto"/"quick"。
        """
        if self._title_showing or self._in_main_menu:
            self.ui.show_notification("标题画面无法存档", color="#e74c3c")
            return
        if self.current_scene_id is None:
            return

        SAVE_DIR.mkdir(exist_ok=True)
        SAVE_THUMB_DIR.mkdir(exist_ok=True)

        scene = self.scenes_dict.get(self.current_scene_id, {})
        dialogues = scene.get("dialogue", [])
        summary = ""
        if self.dialogue_index > 0 and self.dialogue_index <= len(dialogues):
            entry = dialogues[self.dialogue_index - 1]
            summary = strip_rich_tags(entry.get("text", ""))[:60]
        elif self.dialogue_index < len(dialogues):
            entry = dialogues[self.dialogue_index]
            summary = strip_rich_tags(entry.get("text", ""))[:60]

        data = {
            "scene_id": self.current_scene_id,
            "dialogue_index": self.dialogue_index,
            "text_speed": self.text_speed,
            "volume": self.audio.get_volume(),
            "volume_bgm": self.audio.volume_bgm,
            "volume_sfx": self.audio.volume_sfx,
            "volume_voice": self.audio.volume_voice,
            "history": self.history[-50:],
            "variables": dict(self.variables),
            "unlocked_cgs": list(self._unlocked_cgs),
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "summary": summary,
            "scene_title": scene.get("id", ""),
        }

        path = SAVE_DIR / SAVE_FILE_TEMPLATE.format(slot)
        try:
            with open(path, "wb") as f:
                pickle.dump(data, f)
            self.ui.show_notification("存档成功 ✓", color=COLOR_BUTTON_SAVE, duration=1000)
        except (OSError, pickle.PicklingError) as e:
            self.ui.show_notification(f"存档失败: {e}", color="#e74c3c")

    def load_game(self, slot: int = 0) -> None:
        """从指定存档槽恢复进度。

        Args:
            slot: 存档槽编号（0-99）或 "auto"/"quick"。
        """
        path = SAVE_DIR / SAVE_FILE_TEMPLATE.format(slot)
        if not path.exists():
            self.ui.show_notification("未找到存档文件", color="#e74c3c")
            return

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)

            scene_id = data.get("scene_id", "")
            if scene_id not in self.scenes_dict:
                self.ui.show_notification("存档无效：场景不存在", color="#e74c3c")
                return

            self._cancel_typewriter()
            self._cleanup_choice_frame()
            self._cleanup_main_menu()
            self._title_showing = False
            self._in_main_menu = False
            self.ui.set_dialogue_frame_visible(True)

            self.current_scene_id = scene_id
            self.dialogue_index = data.get("dialogue_index", 0)
            self.text_speed = data.get("text_speed", DEFAULT_TEXT_SPEED)
            saved_volume = data.get("volume", DEFAULT_VOLUME)
            self.audio.set_volume(saved_volume)
            self.audio.volume_bgm = data.get("volume_bgm", DEFAULT_VOLUME_BGM)
            self.audio.volume_sfx = data.get("volume_sfx", DEFAULT_VOLUME_SFX)
            self.audio.volume_voice = data.get("volume_voice", DEFAULT_VOLUME_VOICE)
            self.history = list(data.get("history", []))
            self.variables = dict(data.get("variables", {}))
            self._unlocked_cgs = set(data.get("unlocked_cgs", []))
            self._choosing = False
            self._game_ended = False

            scene = self.scenes_dict[scene_id]

            def _after():
                self._update_characters(scene.get("characters", {}))
                dialogues = scene.get("dialogue", [])
                if self.dialogue_index < len(dialogues):
                    e = dialogues[self.dialogue_index]
                    self.show_dialogue(e.get("text", ""), e.get("speaker", ""))
                else:
                    choices = scene.get("choices")
                    if choices:
                        valid = [c for c in choices
                                 if self._evaluate_condition(c.get("if", ""))]
                        if valid:
                            self.show_choices(valid)
                        else:
                            self._end_of_scene()
                    else:
                        self._end_of_scene()

            self._transition_background(
                scene.get("background", ""), on_complete=_after)
            self.ui.show_notification("读档成功 ✓", color=COLOR_BUTTON_LOAD, duration=1000)

        except (OSError, pickle.UnpicklingError, KeyError) as e:
            self.ui.show_notification(f"读档失败: {e}", color="#e74c3c")

    def quick_save(self) -> None:
        """快速存档（F5）。"""
        self.save_game(QUICK_SAVE_SLOT)

    def quick_load(self) -> None:
        """快速读档（F9）。"""
        self.load_game(QUICK_SAVE_SLOT)

    def _open_save_load(self, mode: str) -> None:
        """打开存档/读档界面（委托给 UIManager）。

        Args:
            mode: "save" 或 "load"。
        """
        if self._title_showing and mode == "save":
            self.ui.show_notification("标题画面无法存档", color="#e74c3c")
            return

        def _get_slot_info(slot):
            """读取指定槽位的存档信息。"""
            path = SAVE_DIR / SAVE_FILE_TEMPLATE.format(slot)
            if not path.exists():
                return None
            try:
                with open(path, "rb") as f:
                    return pickle.load(f)
            except Exception:
                return None

        self.ui.open_save_load(
            mode,
            on_save=self.save_game,
            on_load=self.load_game,
            get_slot_info=_get_slot_info,
        )

    # ====================================================================
    #  文本历史（增强版）
    # ====================================================================

    def show_history(self) -> None:
        """弹窗显示完整对白历史（委托给 UIManager）。"""
        self.ui.show_history(
            entries=self.history,
            on_replay_voice=self.audio.play_voice,
            on_export=self._export_history,
        )

    def _export_history(self, parent=None) -> None:
        """将历史对白导出为 txt 文件。"""
        if not self.history:
            self.ui.show_notification("无历史可导出", color="#e74c3c")
            return

        try:
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                parent=parent or self.root,
                title="导出历史",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                initialfile="对话历史.txt",
            )
            if not path:
                return

            title = self.script.get("title", "视觉小说") if self.script else "视觉小说"
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"= {title} - 对话历史 =\n")
                f.write(f"导出时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                f.write("=" * 50 + "\n\n")
                for entry in self.history:
                    speaker = entry.get("speaker", "")
                    text = entry.get("text", "")
                    if speaker:
                        f.write(f"【{speaker}】\n")
                    f.write(f"{text}\n\n")
                f.write("=" * 50 + "\n")
                f.write("— 完 —\n")

            self.ui.show_notification(f"导出成功: {Path(path).name}",
                              color="#2ecc71")
        except Exception as e:
            self.ui.show_notification(f"导出失败: {e}", color="#e74c3c")

    # ====================================================================
    #  CG 画廊
    # ====================================================================

    def _open_gallery(self) -> None:
        """打开 CG 画廊窗口（委托给 UIManager）。"""
        all_bgs = []
        if self.script:
            seen = set()
            for scene in self.script.get("scenes", []):
                bg_id = scene.get("background", "")
                if bg_id and bg_id not in seen:
                    seen.add(bg_id)
                    label = bg_id.replace("__", "").replace("_", " ")
                    all_bgs.append((bg_id, label))
        self.ui.open_gallery(all_bgs, self._unlocked_cgs)

    # ====================================================================
    #  设置面板（增强版）
    # ====================================================================

    def _open_settings(self) -> None:
        """打开设置面板（委托给 UIManager）。"""
        self.ui.open_settings(
            current_speed=self.text_speed,
            volume_bgm=self.audio.volume_bgm,
            volume_sfx=self.audio.volume_sfx,
            volume_voice=self.audio.volume_voice,
            global_muted=self.audio.muted,
            bgm_ducking=self.audio.bgm_ducking_enabled,
            skip_mode=self.skip_mode,
            dialog_position=self.dialog_position,
            on_speed_change=lambda v: setattr(self, 'text_speed', v),
            on_bgm_volume=self.audio.set_volume_bgm,
            on_sfx_volume=self.audio.set_volume_sfx,
            on_voice_volume=self.audio.set_volume_voice,
            on_global_mute=self.audio.set_mute,
            on_bgm_ducking=lambda v: setattr(self.audio, 'bgm_ducking_enabled', v),
            on_skip_mode=lambda v: setattr(self, 'skip_mode', v),
            on_dialog_position=self._set_dialog_position,
            on_fullscreen=lambda _: self.ui.toggle_fullscreen(),
        )

    def _set_dialog_position(self, pos: str) -> None:
        """设置对话框位置。"""
        self.dialog_position = pos
        self.ui.set_dialog_position(pos)

    def _toggle_fullscreen(self, var=None) -> None:
        """切换全屏模式。"""
        state = self.ui.toggle_fullscreen()
        if var:
            var.set(state)

    # ====================================================================
    #  工具方法
    # ====================================================================

    def _clear_all(self) -> None:
        """重置 Canvas、取消打字机、清理选项、停止音乐。"""
        self.ui.clear_all()
        self._cancel_typewriter()
        self._stop_speaking_animation()
        self.char_left_items = []
        self.char_right_items = []
        self.bg_overlay = None
        stop_particles(self.canvas)
        remove_filter(self.canvas)
        stop_noise(self.canvas)
        self.audio.stop_bgm()
