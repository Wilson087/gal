"""
游戏引擎主模块
==============
定义 VNGame 类，统筹管理场景切换、对话流程、立绘更新、
选项分支、存档读档、文本历史和设置面板等核心游戏逻辑。
"""

import tkinter as tk
import json
import pickle
from pathlib import Path
from typing import Optional

from .constants import *
from .script import load_from_file, validate_script
from .renderer import (
    render_background,
    draw_character,
    create_fade_overlay,
    remove_overlay,
    show_notification,
)
from .audio import AudioEngine


# ========================================================================
#  主引擎类
# ========================================================================

class VNGame:
    """视觉小说游戏主引擎。

    负责：
    - 剧本加载与场景切换
    - 对话逐字显示与推进
    - 立绘（左/右）显示与淡入淡出
    - 背景切换过渡
    - 选项分支按钮
    - pickle 存档/读档
    - 文本历史弹窗
    - 设置面板（文字速度调节等）

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
        self.root.title("视觉小说框架")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.configure(bg=COLOR_BG_DARK)

        # ── 游戏数据 ──────────────────────────────────────────
        self.script: Optional[dict] = None
        self.scenes_dict: dict[str, dict] = {}
        self.current_scene_id: Optional[str] = None
        self.dialogue_index: int = 0
        self.history: list[tuple[str, str]] = []

        # ── 运行时状态 ────────────────────────────────────────
        self._typing: bool = False
        self._skip_type: bool = False
        self._choosing: bool = False
        self._typewriter_timer: Optional[str] = None
        self._current_full_text: str = ""
        self._game_ended: bool = False
        self._title_showing: bool = False
        self._start_label: Optional[int] = None

        # ── 设置 ──────────────────────────────────────────────
        self.text_speed: int = DEFAULT_TEXT_SPEED

        # ── 音频引擎 ──────────────────────────────────────────
        self.audio = AudioEngine()

        # ── 立绘引用（供淡入淡出动效使用） ────────────────────
        self.char_left_items: list[int] = []
        self.char_right_items: list[int] = []

        # ── 过渡遮罩 ID ──────────────────────────────────────
        self.bg_overlay: Optional[int] = None

        # ── UI 组件（在 _build_ui 中赋值） ────────────────────
        self.canvas: Optional[tk.Canvas] = None
        self.dialogue_frame: Optional[tk.Frame] = None
        self.speaker_label: Optional[tk.Label] = None
        self.text_label: Optional[tk.Label] = None
        self.next_indicator: Optional[tk.Label] = None
        self.choice_frame: Optional[tk.Frame] = None
        self.choice_buttons: list[tk.Button] = []
        self.choice_overlay: Optional[int] = None

        # ── 构建并启动 ────────────────────────────────────────
        self._build_ui()
        self._bind_events()

    # ====================================================================
    #  UI 构建
    # ====================================================================

    def _build_ui(self) -> None:
        """构建主界面：顶部工具栏 + Canvas 显示区 + 底部对话 Frame。"""
        # 主布局
        self.root.grid_rowconfigure(0, weight=0)   # 工具栏 - 固定
        self.root.grid_rowconfigure(1, weight=1)   # Canvas - 可伸缩
        self.root.grid_rowconfigure(2, weight=0)   # 对话 - 固定
        self.root.grid_columnconfigure(0, weight=1)

        # ── 顶部工具栏 ──────────────────────────────────────
        self.toolbar = tk.Frame(
            self.root, bg=COLOR_DIALOGUE_BG, height=30,
            relief="raised", bd=1,
        )
        self.toolbar.grid(row=0, column=0, sticky="ew")
        self.toolbar.grid_propagate(False)

        _btn_style = dict(
            font=("微软雅黑", 10), bg=COLOR_DIALOGUE_BG,
            fg=COLOR_TEXT_PRIMARY, relief="flat", bd=0,
            activebackground=COLOR_CHOICE_HOVER,
            activeforeground=COLOR_TEXT_ACCENT,
            padx=8, pady=2, cursor="hand2",
        )

        tk.Button(self.toolbar, text="存档 S", **_btn_style,
                  command=self.save_game).pack(side="left", padx=(6, 0))
        tk.Button(self.toolbar, text="读档 L", **_btn_style,
                  command=self.load_game).pack(side="left", padx=0)
        tk.Button(self.toolbar, text="历史 H", **_btn_style,
                  command=self.show_history).pack(side="left", padx=0)
        tk.Button(self.toolbar, text="设置 Esc", **_btn_style,
                  command=self._open_settings).pack(side="left", padx=0)

        # ── Canvas 主区 ──────────────────────────────────────
        container = tk.Frame(self.root, bg=COLOR_BG_DARK)
        container.grid(row=1, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            container, bg=COLOR_BG_DARK,
            highlightthickness=0, cursor="hand2",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # ── 对话 Frame ───────────────────────────────────────
        self.dialogue_frame = tk.Frame(
            self.root, bg=COLOR_DIALOGUE_BG,
            relief="raised", bd=2,
            height=DIALOGUE_FRAME_HEIGHT,
        )
        self.dialogue_frame.grid(row=2, column=0, sticky="ew")
        self.dialogue_frame.grid_propagate(False)

        self.dialogue_frame.grid_columnconfigure(0, weight=1)
        self.dialogue_frame.grid_columnconfigure(1, weight=0)
        self.dialogue_frame.grid_rowconfigure(0, weight=0)
        self.dialogue_frame.grid_rowconfigure(1, weight=1)
        self.dialogue_frame.grid_rowconfigure(2, weight=0)

        # 说话人标签
        self.speaker_label = tk.Label(
            self.dialogue_frame, text="",
            font=FONT_SPEAKER, fg=COLOR_TEXT_SPEAKER,
            bg=COLOR_DIALOGUE_BG, anchor="w", padx=24,
        )
        self.speaker_label.grid(row=0, column=0, sticky="ew", pady=(12, 0))

        # 对白文本标签
        self.text_label = tk.Label(
            self.dialogue_frame, text="",
            font=FONT_DIALOGUE, fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_DIALOGUE_BG, anchor="nw",
            justify="left", wraplength=WINDOW_WIDTH - 80,
            padx=24,
        )
        self.text_label.grid(row=1, column=0, sticky="nw", pady=(6, 12))

        # 下一句指示器 "▼"
        self.next_indicator = tk.Label(
            self.dialogue_frame, text="",
            font=("微软雅黑", 18), fg=COLOR_TEXT_SPEAKER,
            bg=COLOR_DIALOGUE_BG,
        )
        self.next_indicator.grid(row=1, column=1, sticky="se",
                                 padx=(0, 28), pady=(0, 18))

        # 键盘快捷键提示
        self.hint_label = tk.Label(
            self.dialogue_frame,
            text="空格/点击推进 · S存档 · L读档 · H历史 · Esc设置",
            font=("微软雅黑", 9), fg="#7f8c8d",
            bg=COLOR_DIALOGUE_BG, anchor="e", padx=24,
        )
        self.hint_label.grid(row=2, column=0, columnspan=2,
                             sticky="ew", pady=(0, 4))

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

        if self.canvas:
            self.canvas.bind("<Button-1>", self._on_advance)

        self.root.bind("<Configure>", self._on_resize)

        # 窗口关闭时停止音频
        self.root.protocol("WM_DELETE_WINDOW", self._on_game_close)

    def _on_resize(self, event: tk.Event) -> None:
        """窗口缩放时更新文字换行宽度。"""
        if self.text_label and event.widget is self.root:
            new_wrap = max(event.width - 80, 200)
            self.text_label.config(wraplength=new_wrap)

    # ====================================================================
    #  剧本加载
    # ====================================================================

    def load_script(self, source: str | dict) -> None:
        """加载并解析剧本数据。

        支持传入 JSON 文件路径（str）或已解析的字典。

        Args:
            source: 剧本文件路径或字典对象。

        Raises:
            SystemExit: 格式错误或文件无法读取时退出。
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

        except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"剧本加载失败: {e}")
            self._show_error_and_exit(str(e))

    def _show_error_and_exit(self, message: str) -> None:
        """显示错误对话框并退出。"""
        win = tk.Toplevel(self.root)
        win.title("错误")
        win.geometry("440x160")
        win.transient(self.root)
        win.grab_set()
        tk.Label(win, text=message, font=FONT_UI,
                 wraplength=400, padx=20, pady=20).pack(expand=True)
        tk.Button(win, text="确定", font=FONT_UI,
                  command=lambda: (win.destroy(), self.root.destroy())
                  ).pack(pady=10)

    # ====================================================================
    #  游戏启动 / 标题
    # ====================================================================

    def start_game(self) -> None:
        """显示标题画面，点击后进入首个场景。"""
        self._title_showing = True
        self._clear_all()
        self.speaker_label.config(text="")
        self.text_label.config(text="")
        self.next_indicator.config(text="")

        # 确保窗口已完成布局，避免 winfo_width/height 返回 1
        self.root.update()
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT

        # 渐变背景（逐条矩形近似）
        for i in range(20):
            frac = i / 20
            r, g, b = int(10 + frac * 15), int(10 + frac * 10), int(26 + frac * 20)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.canvas.create_rectangle(
                0, int(h * frac), w, int(h * (frac + 0.05)),
                fill=color, outline="")

        # 从加载的剧本读取标题
        title = (self.script.get("title", "") if self.script else "") or "视觉小说框架"
        spaced_title = "  ".join(title)

        self.canvas.create_text(w // 2, int(h * 0.35),
                                text=spaced_title, font=FONT_TITLE,
                                fill=COLOR_TEXT_ACCENT, anchor="center")
        self.canvas.create_text(w // 2, int(h * 0.48),
                                text=f"— {title} —",
                                font=("微软雅黑", 16), fill=COLOR_TEXT_PRIMARY,
                                anchor="center")

        self._start_label = self.canvas.create_text(
            w // 2, int(h * 0.65),
            text="— 点击任意处开始 —",
            font=("微软雅黑", 16), fill=COLOR_TEXT_SPEAKER, anchor="center",
        )
        self._blink_title()

    def _blink_title(self) -> None:
        """标题 '点击开始' 闪烁动画。"""
        if not self._title_showing or self._start_label is None:
            return
        current = self.canvas.itemcget(self._start_label, "fill")
        new = COLOR_TEXT_ACCENT if current == COLOR_TEXT_SPEAKER else COLOR_TEXT_SPEAKER
        try:
            self.canvas.itemconfig(self._start_label, fill=new)
        except tk.TclError:
            return
        self.root.after(600, self._blink_title)

    def _on_title_click(self, event: tk.Event = None) -> None:
        """标题点击 -> 进入首个场景。"""
        if not self._title_showing:
            return
        self._title_showing = False
        if self.canvas:
            self.canvas.bind("<Button-1>", self._on_advance)
        self._enter_scene("start")

    # ====================================================================
    #  场景管理
    # ====================================================================

    def _enter_scene(self, scene_id: str) -> None:
        """切换到指定场景。

        依次执行：取消打字机 -> 清理选项 -> 背景过渡 -> 更新立绘 -> 显示对白。

        Args:
            scene_id: 目标场景 ID。
        """
        self._cancel_typewriter()
        self._cleanup_choice_frame()
        self.dialogue_index = 0
        self.current_scene_id = scene_id
        self._choosing = False
        self._game_ended = False

        scene = self.scenes_dict.get(scene_id)
        if scene is None:
            self._show_error_and_exit(f"场景 '{scene_id}' 不存在")
            return

        # 切换 BGM（场景指定 bgm → 播放；bgm 显式空字符串 → 停止）
        if "bgm" in scene:
            bgm_path = scene.get("bgm")
            if bgm_path:
                self.audio.play_bgm(bgm_path)
            else:
                self.audio.stop_bgm()
        # 场景没有 bgm 字段 → 保持现有 BGM 不中断

        def _after_bg():
            self._update_characters(scene.get("characters", {}))
            self._show_current_dialogue()

        self._transition_background(scene.get("background", ""), on_complete=_after_bg)

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

            # 支持单句内立绘变化
            if "character_left" in entry or "character_right" in entry:
                char_data = {}
                if "character_left" in entry:
                    char_data["left"] = entry["character_left"]
                if "character_right" in entry:
                    char_data["right"] = entry["character_right"]
                self._update_characters(char_data)

            # 播放本句音效（如果指定了 sfx 字段）
            sfx_path = entry.get("sfx")
            if sfx_path:
                self.audio.play_sfx(sfx_path)

            self.show_dialogue(text, speaker)
        elif choices:
            self.show_choices(choices)
        else:
            self._end_of_scene()

    def _end_of_scene(self) -> None:
        """场景结束处理（显示 END，允许点击重启）。"""
        self._game_ended = True
        self.speaker_label.config(text="")
        self.text_label.config(text="—— END ——")
        self.next_indicator.config(text="")
        if self.canvas:
            self.canvas.bind("<Button-1>", lambda e: self.start_game())

    def _next_dialogue(self) -> None:
        """推进到下一句对白。"""
        if self._choosing or self._title_showing or self._game_ended:
            return
        if self.current_scene_id is None:
            return
        self.dialogue_index += 1
        self._show_current_dialogue()

    # ====================================================================
    #  对话推进事件
    # ====================================================================

    def _on_game_close(self) -> None:
        """窗口关闭：停止音频后销毁窗口。"""
        self.audio.shutdown()
        self.root.destroy()

    def _on_advance(self, event: tk.Event = None) -> None:
        """处理推进操作：打字中 -> 跳过；已完成 -> 下一句；标题 -> 开始。"""
        if self._title_showing:
            self._on_title_click(event)
        elif self._game_ended or self._choosing:
            return
        elif self._typing:
            self._skip_type = True
        else:
            self._next_dialogue()

    # ====================================================================
    #  背景切换
    # ====================================================================

    def _transition_background(self, new_bg_id: str,
                               on_complete=None) -> None:
        """背景切换白色淡入淡出动画。

        Args:
            new_bg_id: 新背景标识符。
            on_complete: 动画完成后的回调。
        """
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT

        self.bg_overlay = create_fade_overlay(self.canvas, w, h)

        def _fade_in(idx=0):
            """白色遮罩渐深 -> 覆盖旧背景。"""
            if idx < len(BG_FADE_IN_STEPPLES):
                stipple = BG_FADE_IN_STEPPLES[idx]
                if idx > 0:
                    self.canvas.itemconfig(self.bg_overlay, stipple=stipple)
                self.root.after(BG_FADE_INTERVAL, _fade_in, idx + 1)
            else:
                # 切换背景
                render_background(self.canvas, new_bg_id, w, h)

                def _fade_out(idx2=0):
                    """白色遮罩渐浅 -> 露出新背景。"""
                    if idx2 < len(BG_FADE_OUT_STEPPLES):
                        self.canvas.itemconfig(
                            self.bg_overlay, stipple=BG_FADE_OUT_STEPPLES[idx2])
                        self.canvas.tag_raise("overlay")
                        self.root.after(BG_FADE_INTERVAL, _fade_out, idx2 + 1)
                    else:
                        remove_overlay(self.canvas, self.bg_overlay)
                        self.bg_overlay = None
                        if on_complete:
                            on_complete()

                _fade_out(0)

        _fade_in(0)

    # ====================================================================
    #  立绘系统
    # ====================================================================

    def _update_characters(self, char_data: dict) -> None:
        """更新左右立绘（带淡入淡出）。

        Args:
            char_data: {"left": char_id, "right": char_id}。
                       None 表示清除该侧。
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
        """单侧立绘淡出 -> 替换 -> 淡入。

        Args:
            side: "left" 或 "right"。
            new_char_id: 新角色 ID（None = 仅清除）。
            x_center: 角色中心 x。
            y_bottom: 角色底部 y。
        """
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
                # 删除旧立绘
                self.canvas.delete(tag)
                old_items.clear()

                # 如果无新角色，结束
                if not new_char_id:
                    if side == "left":
                        self.char_left_items = []
                    else:
                        self.char_right_items = []
                    return

                # 绘制新立绘
                new_items = draw_character(
                    self.canvas, new_char_id, x_center, y_bottom)
                for item_id in new_items:
                    self.canvas.itemconfig(item_id, stipple="gray12")
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
    #  对话（打字机效果）
    # ====================================================================

    def show_dialogue(self, text: str, speaker: str = "") -> None:
        """显示对白并启动打字机逐字效果。

        Args:
            text: 对白文本。
            speaker: 说话角色名（空字符串表示旁白）。
        """
        self._cancel_typewriter()
        self.next_indicator.config(text="")
        self._current_full_text = text
        self._typing = True
        self._skip_type = False

        self.speaker_label.config(text=speaker if speaker else "")
        self.text_label.config(text="")
        self._typewriter_step(0)

    def _typewriter_step(self, index: int) -> None:
        """打字机逐字步进。

        Args:
            index: 下一个要显示的字符索引。
        """
        if not self._typing:
            return

        if self._skip_type:
            self._finish_typewriter()
            return

        text = self._current_full_text
        if index < len(text):
            self.text_label.config(text=text[: index + 1])
            self._typewriter_timer = self.root.after(
                self.text_speed, self._typewriter_step, index + 1)
        else:
            self._finish_typewriter()

    def _finish_typewriter(self) -> None:
        """打字完成：显示全文、记录历史、显示 ▼ 指示器。"""
        self._typing = False
        self._skip_type = False
        self.text_label.config(text=self._current_full_text)

        speaker = self.speaker_label.cget("text")
        self.history.append((speaker, self._current_full_text))
        if len(self.history) > 100:
            self.history = self.history[-100:]

        self.next_indicator.config(text="▼")

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

    # ====================================================================
    #  选项分支
    # ====================================================================

    def show_choices(self, choices: list[dict]) -> None:
        """在画面中央显示选项按钮。

        Args:
            choices: [{"text": "...", "next_scene": "..."}, ...]。
        """
        self._choosing = True
        self._cleanup_choice_frame()
        self.next_indicator.config(text="")

        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT

        # 半透明黑色遮罩
        self.choice_overlay = self.canvas.create_rectangle(
            0, 0, w, h, fill="#000000", stipple="gray50",
            outline="", tags="choice_ui")

        # 选项容器
        self.choice_frame = tk.Frame(
            self.canvas, bg=COLOR_CHOICE_BG, relief="solid", bd=2,
            highlightbackground=COLOR_CHOICE_BORDER, highlightthickness=2)

        tk.Label(self.choice_frame, text="— 做出你的选择 —",
                 font=("微软雅黑", 14, "bold"),
                 fg=COLOR_TEXT_ACCENT, bg=COLOR_CHOICE_BG,
                 pady=12).pack(fill="x")

        self.choice_buttons = []
        for choice in choices:
            text = choice.get("text", "继续")
            next_scene = choice.get("next_scene", "")

            btn = tk.Button(
                self.choice_frame, text=text,
                font=FONT_BUTTON, fg=COLOR_CHOICE_TEXT, bg=COLOR_CHOICE_BG,
                activeforeground=COLOR_TEXT_ACCENT,
                activebackground=COLOR_CHOICE_HOVER,
                relief="solid", bd=1,
                highlightbackground=COLOR_CHOICE_BORDER, highlightthickness=1,
                padx=40, pady=10, cursor="hand2",
                command=lambda ns=next_scene: self._on_choice_selected(ns))
            btn.pack(fill="x", padx=20, pady=6)
            self.choice_buttons.append(btn)

        self.choice_frame.update_idletasks()
        fw = min(self.choice_frame.winfo_reqwidth() + 40, 500)
        self.canvas.create_window(
            w // 2, int(h * 0.45),
            window=self.choice_frame, anchor="center",
            width=fw, tags="choice_ui")

    def _on_choice_selected(self, next_scene: str) -> None:
        """选项被选中 -> 跳转场景。

        Args:
            next_scene: 目标场景 ID。
        """
        self._cleanup_choice_frame()
        self._choosing = False
        self._enter_scene(next_scene)

    def _cleanup_choice_frame(self) -> None:
        """清理选项 UI。"""
        self.canvas.delete("choice_ui")
        if self.choice_frame:
            self.choice_frame.destroy()
            self.choice_frame = None
        self.choice_buttons = []

    # ====================================================================
    #  存档 / 读档
    # ====================================================================

    def save_game(self, slot: int = 0) -> None:
        """保存当前进度到存档文件。

        Args:
            slot: 存档槽编号（默认 0）。
        """
        if self._title_showing:
            show_notification(self.canvas, "标题画面无法存档",
                              color="#e74c3c")
            return
        if self.current_scene_id is None:
            return

        SAVE_DIR.mkdir(exist_ok=True)
        data = {
            "scene_id": self.current_scene_id,
            "dialogue_index": self.dialogue_index,
            "text_speed": self.text_speed,
            "volume": self.audio.get_volume(),
            "history": self.history[-50:],
        }

        path = SAVE_DIR / SAVE_FILE_TEMPLATE.format(slot)
        try:
            with open(path, "wb") as f:
                pickle.dump(data, f)
            show_notification(self.canvas, "存档成功 ✓", color=COLOR_BUTTON_SAVE)
        except (OSError, pickle.PicklingError) as e:
            show_notification(self.canvas, f"存档失败: {e}", color="#e74c3c")

    def load_game(self, slot: int = 0) -> None:
        """从存档文件恢复进度。

        Args:
            slot: 存档槽编号（默认 0）。
        """
        path = SAVE_DIR / SAVE_FILE_TEMPLATE.format(slot)
        if not path.exists():
            show_notification(self.canvas, "未找到存档文件", color="#e74c3c")
            return

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)

            scene_id = data.get("scene_id", "")
            if scene_id not in self.scenes_dict:
                show_notification(self.canvas, "存档无效：场景不存在",
                                  color="#e74c3c")
                return

            self._cancel_typewriter()
            self._cleanup_choice_frame()
            self._title_showing = False

            self.current_scene_id = scene_id
            self.dialogue_index = data.get("dialogue_index", 0)
            self.text_speed = data.get("text_speed", DEFAULT_TEXT_SPEED)
            saved_volume = data.get("volume", DEFAULT_VOLUME)
            self.audio.set_volume(saved_volume)
            self.history = list(data.get("history", []))
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
                        self.show_choices(choices)
                    else:
                        self._end_of_scene()

            self._transition_background(
                scene.get("background", ""), on_complete=_after)
            show_notification(self.canvas, "读档成功 ✓", color=COLOR_BUTTON_LOAD)

        except (OSError, pickle.UnpicklingError, KeyError) as e:
            show_notification(self.canvas, f"读档失败: {e}", color="#e74c3c")

    # ====================================================================
    #  文本历史
    # ====================================================================

    def show_history(self) -> None:
        """弹窗显示最近对白历史。"""
        win = tk.Toplevel(self.root)
        win.title("文本历史")
        win.geometry("600x420")
        win.transient(self.root)
        win.configure(bg=COLOR_BG_DARK)

        tk.Label(win, text="— 对白历史 —",
                 font=("微软雅黑", 16, "bold"),
                 fg=COLOR_TEXT_ACCENT, bg=COLOR_BG_DARK,
                 pady=12).pack(fill="x")

        outer = tk.Frame(win, bg=COLOR_BG_DARK)
        outer.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        cv = tk.Canvas(outer, bg=COLOR_BG_DARK, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=COLOR_BG_DARK)

        inner.bind("<Configure>",
                   lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=inner, anchor="nw")
        cv.configure(yscrollcommand=sb.set)

        # ── 鼠标滚轮支持 ────────────────────────────────────────
        def _on_wheel(event):
            """Windows：event.delta 为 120 的倍数；Mac 类似。"""
            cv.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_wheel_up(event):
            cv.yview_scroll(-3, "units")

        def _on_wheel_down(event):
            cv.yview_scroll(3, "units")

        for w in (cv, inner):
            w.bind("<MouseWheel>", _on_wheel)
            w.bind("<Button-4>", _on_wheel_up)    # Linux
            w.bind("<Button-5>", _on_wheel_down)  # Linux

        recent = self.history[-10:] if self.history else []
        if not recent:
            tk.Label(inner, text="暂无对白记录", font=FONT_UI,
                     fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG_DARK,
                     pady=20).pack()
        else:
            for speaker, text in recent:
                row = tk.Frame(inner, bg=COLOR_DIALOGUE_BG,
                               relief="solid", bd=1)
                row.pack(fill="x", pady=4, padx=4)
                l1 = tk.Label(row, text=speaker or "（旁白）",
                              font=("微软雅黑", 12, "bold"),
                              fg=COLOR_TEXT_SPEAKER, bg=COLOR_DIALOGUE_BG,
                              anchor="w", padx=12,
                              )
                l1.pack(fill="x", pady=(8, 2))
                l2 = tk.Label(row, text=text,
                              font=("微软雅黑", 11),
                              fg=COLOR_TEXT_PRIMARY, bg=COLOR_DIALOGUE_BG,
                              anchor="w", wraplength=500,
                              justify="left", padx=12,
                              )
                l2.pack(fill="x", pady=(0, 8))
                # 让行内所有子控件也响应滚轮
                for child in (row, l1, l2):
                    child.bind("<MouseWheel>", _on_wheel)
                    child.bind("<Button-4>", _on_wheel_up)
                    child.bind("<Button-5>", _on_wheel_down)

        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        tk.Button(win, text="关闭", font=FONT_UI,
                  command=win.destroy,
                  bg=COLOR_DIALOGUE_BG, fg=COLOR_TEXT_PRIMARY,
                  relief="solid", bd=1, padx=20,
                  ).pack(pady=(0, 12))

    # ====================================================================
    #  设置面板
    # ====================================================================

    def _open_settings(self) -> None:
        """Esc 键弹出设置面板（Toplevel）。"""
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("500x540")
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=COLOR_BG_DARK)

        tk.Label(win, text="— 设 置 —",
                 font=("微软雅黑", 18, "bold"),
                 fg=COLOR_TEXT_ACCENT, bg=COLOR_BG_DARK,
                 pady=20).pack(fill="x")

        # ── 文字速度 ──
        sp_frame = tk.Frame(win, bg=COLOR_BG_DARK)
        sp_frame.pack(fill="x", padx=40, pady=10)

        tk.Label(sp_frame, text="文字速度",
                 font=("微软雅黑", 14), fg=COLOR_TEXT_PRIMARY,
                 bg=COLOR_BG_DARK, anchor="w").pack(fill="x")

        val_label = tk.Label(sp_frame,
                             text=f"{self.text_speed} ms/字",
                             font=("微软雅黑", 12),
                             fg=COLOR_TEXT_SPEAKER, bg=COLOR_BG_DARK,
                             anchor="w")
        val_label.pack(fill="x", pady=(4, 0))

        scale = tk.Scale(sp_frame, from_=10, to=200,
                         orient="horizontal", length=400,
                         resolution=5, showvalue=False,
                         bg=COLOR_DIALOGUE_BG, fg=COLOR_TEXT_PRIMARY,
                         highlightbackground=COLOR_BG_DARK,
                         troughcolor="#2c3e50", cursor="hand2")
        scale.set(self.text_speed)
        scale.pack(pady=(8, 0))

        def _set_speed(val):
            self.text_speed = int(val)
            val_label.config(text=f"{self.text_speed} ms/字")

        scale.config(command=_set_speed)

        # 预设按钮
        preset_frame = tk.Frame(win, bg=COLOR_BG_DARK)
        preset_frame.pack(pady=(0, 10))
        for label, val in [("快速", 20), ("普通", 40),
                           ("慢速", 80), ("很慢", 150)]:
            tk.Button(preset_frame, text=label,
                      font=("微软雅黑", 11),
                      bg=COLOR_CHOICE_BG, fg=COLOR_TEXT_PRIMARY,
                      activebackground=COLOR_CHOICE_HOVER,
                      activeforeground=COLOR_TEXT_ACCENT,
                      relief="solid", bd=1, padx=16, cursor="hand2",
                      command=lambda v=val: (scale.set(v), _set_speed(v)),
                      ).pack(side="left", padx=6)

        # ── 音量 ──
        vol_frame = tk.Frame(win, bg=COLOR_BG_DARK)
        vol_frame.pack(fill="x", padx=40, pady=10)
        tk.Label(vol_frame, text="音量",
                 font=("微软雅黑", 14), fg=COLOR_TEXT_PRIMARY,
                 bg=COLOR_BG_DARK, anchor="w").pack(fill="x")

        vol_val_label = tk.Label(vol_frame,
                                 text=f"{self.audio.get_volume()}%",
                                 font=("微软雅黑", 12),
                                 fg=COLOR_TEXT_SPEAKER, bg=COLOR_BG_DARK,
                                 anchor="w")
        vol_val_label.pack(fill="x", pady=(4, 0))

        vol_scale = tk.Scale(vol_frame, from_=0, to=100,
                             orient="horizontal", length=400,
                             resolution=5, showvalue=False,
                             bg=COLOR_DIALOGUE_BG, fg=COLOR_TEXT_PRIMARY,
                             highlightbackground=COLOR_BG_DARK,
                             troughcolor="#2c3e50", cursor="hand2")
        vol_scale.set(self.audio.get_volume())
        vol_scale.pack(pady=(8, 0))

        def _set_volume(val):
            vol = int(val)
            self.audio.set_volume(vol)
            vol_val_label.config(text=f"{vol}%")

        vol_scale.config(command=_set_volume)

        # 音量预设按钮
        vol_preset = tk.Frame(win, bg=COLOR_BG_DARK)
        vol_preset.pack(pady=(0, 10))
        for label, val in [("静音", 0), ("低", 25), ("中", 50), ("高", 80), ("最大", 100)]:
            tk.Button(vol_preset, text=label,
                      font=("微软雅黑", 11),
                      bg=COLOR_CHOICE_BG, fg=COLOR_TEXT_PRIMARY,
                      activebackground=COLOR_CHOICE_HOVER,
                      activeforeground=COLOR_TEXT_ACCENT,
                      relief="solid", bd=1, padx=12, cursor="hand2",
                      command=lambda v=val: (vol_scale.set(v), _set_volume(v)),
                      ).pack(side="left", padx=4)

        # 音频状态提示
        backend = self.audio.backend_name
        if backend == "ffplay":
            hint_text = "后端: ffplay · 支持 mp3/ogg/flac/wav 等格式 · 实时音量调节"
        elif backend == "winsound":
            hint_text = "后端: winsound · 仅支持 .wav 格式 · 安装 FFmpeg 可解锁更多格式"
        elif backend == "none":
            hint_text = "当前平台无可用音频后端"
        else:
            hint_text = f"后端: {backend}"
        tk.Label(vol_frame, text=hint_text,
                 font=("微软雅黑", 10), fg="#7f8c8d",
                 bg=COLOR_BG_DARK).pack()

        # ── 关闭 ──
        tk.Button(win, text="关闭", font=FONT_UI, command=win.destroy,
                  bg=COLOR_CHOICE_BORDER, fg=COLOR_TEXT_PRIMARY,
                  relief="solid", bd=1, padx=30, pady=6, cursor="hand2",
                  ).pack(pady=20)

    # ====================================================================
    #  工具方法
    # ====================================================================

    def _clear_all(self) -> None:
        """重置 Canvas、取消打字机、清理选项、停止音乐。"""
        self.canvas.delete("all")
        self._cancel_typewriter()
        self._cleanup_choice_frame()
        self.char_left_items = []
        self.char_right_items = []
        self.bg_overlay = None
        self.audio.stop_bgm()
