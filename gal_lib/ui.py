"""
UI 管理模块
===========
定义 UIManager 类，专职负责所有 tkinter UI 组件的创建、布局与销毁。

职责范围:
    - 主窗口（root）的初始配置
    - 顶部工具栏（存档、读档、历史、主菜单、设置按钮）
    - Canvas 主显示区（背景、立绘、选项的承载容器）
    - 底部对话 Frame（说话人标签、文本标签、推进指示器、快捷键提示）
    - 选项分支 UI（半透明遮罩 + 按钮容器）
    - 主菜单 UI（标题 + 按钮列表）
    - 设置弹窗、文本历史弹窗、存档/读档弹窗
    - 错误对话框、通知文字

设计原则:
    - UIManager 不持有任何游戏状态（场景、对话索引等仅由 VNGame 管理）
    - 所有用户交互通过回调（callback）通知调用方
    - 使用 from .constants import * 获取颜色/字体等配置
"""

import datetime
import pickle
import tkinter as tk
from pathlib import Path
from typing import Any, Callable, Optional

from .constants import *
from .renderer import show_notification as _render_notification


# ========================================================================
#  UI 管理器
# ========================================================================

class UIManager:
    """专职管理所有 UI 组件的创建与生命周期。

    用法:
        ui = UIManager(root)
        ui.set_callbacks(
            on_save=lambda: ...,
            on_load=lambda: ...,
            on_history=lambda: ...,
            on_settings=lambda: ...,
            on_main_menu=lambda: ...,
            on_advance=lambda: ...,
        )
        ui.build_main_ui()
    """

    def __init__(self, root: tk.Tk) -> None:
        """初始化 UI 管理器（仅保存 root，不创建任何组件）。

        Args:
            root: tkinter 根窗口对象。
        """
        self.root = root

        # ── 回调（由 set_callbacks 或 VNGame 设置） ──────────────
        self.on_save: Optional[Callable] = None
        self.on_load: Optional[Callable] = None
        self.on_quick_save: Optional[Callable] = None
        self.on_quick_load: Optional[Callable] = None
        self.on_history: Optional[Callable] = None
        self.on_settings: Optional[Callable] = None
        self.on_main_menu: Optional[Callable] = None
        self.on_advance: Optional[Callable] = None
        self.on_choice: Optional[Callable] = None  # Callable[[dict], None] — 接收完整 choice dict

        # ── UI 组件引用 ──────────────────────────────────────────
        self.canvas: Optional[tk.Canvas] = None
        self.toolbar: Optional[tk.Frame] = None

        # 对话区域
        self.dialogue_frame: Optional[tk.Frame] = None
        self.speaker_label: Optional[tk.Label] = None
        self.text_label: Optional[tk.Label] = None
        self.next_indicator: Optional[tk.Label] = None
        self.hint_label: Optional[tk.Label] = None

        # 选项
        self.choice_frame: Optional[tk.Frame] = None
        self.choice_buttons: list[tk.Button] = []
        self.choice_overlay: Optional[int] = None

        # 主菜单
        self.main_menu_frame: Optional[tk.Frame] = None

        # 背景遮罩 ID（由转场使用）
        self.bg_overlay: Optional[int] = None

    # ====================================================================
    #  回调注册
    # ====================================================================

    def set_callbacks(
        self,
        on_save: Optional[Callable] = None,
        on_load: Optional[Callable] = None,
        on_quick_save: Optional[Callable] = None,
        on_quick_load: Optional[Callable] = None,
        on_history: Optional[Callable] = None,
        on_settings: Optional[Callable] = None,
        on_main_menu: Optional[Callable] = None,
        on_advance: Optional[Callable] = None,
        on_choice: Optional[Callable] = None,  # Callable[[dict], None]
    ) -> None:
        """注册用户交互回调。

        Args:
            on_save: 点击"存档"按钮。
            on_load: 点击"读档"按钮。
            on_quick_save: 快速存档（F5）。
            on_quick_load: 快速读档（F9）。
            on_history: 点击"历史"按钮。
            on_settings: 点击"设置"按钮。
            on_main_menu: 点击"主菜单"按钮。
            on_advance: 推进对话（Space / 鼠标点击 Canvas）。
            on_choice: 选择选项，接收完整 choice dict。
        """
        if on_save is not None:
            self.on_save = on_save
        if on_load is not None:
            self.on_load = on_load
        if on_quick_save is not None:
            self.on_quick_save = on_quick_save
        if on_quick_load is not None:
            self.on_quick_load = on_quick_load
        if on_history is not None:
            self.on_history = on_history
        if on_settings is not None:
            self.on_settings = on_settings
        if on_main_menu is not None:
            self.on_main_menu = on_main_menu
        if on_advance is not None:
            self.on_advance = on_advance
        if on_choice is not None:
            self.on_choice = on_choice

    # ====================================================================
    #  主 UI 构建
    # ====================================================================

    def build_main_ui(self) -> None:
        """构建游戏主界面：顶部工具栏 + Canvas 显示区 + 底部对话 Frame。"""
        self.root.grid_rowconfigure(0, weight=0)   # 工具栏 - 固定
        self.root.grid_rowconfigure(1, weight=1)   # Canvas - 可伸缩
        self.root.grid_rowconfigure(2, weight=0)   # 对话 - 固定
        self.root.grid_columnconfigure(0, weight=1)

        self._build_toolbar()
        self._build_canvas()
        self._build_dialogue_frame()

    def configure_root(
        self, title: str = "视觉小说引擎",
        width: int = WINDOW_WIDTH, height: int = WINDOW_HEIGHT,
    ) -> None:
        """配置根窗口属性。

        Args:
            title: 窗口标题。
            width: 窗口宽度。
            height: 窗口高度。
        """
        self.root.title(title)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.configure(bg=COLOR_BG_DARK)

    # ── 工具栏 ──────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        """构建顶部工具栏。"""
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

        tk.Button(
            self.toolbar, text="存档", **_btn_style,
            command=lambda: self.on_save and self.on_save(),
        ).pack(side="left", padx=(6, 0))

        tk.Button(
            self.toolbar, text="读档", **_btn_style,
            command=lambda: self.on_load and self.on_load(),
        ).pack(side="left", padx=0)

        tk.Button(
            self.toolbar, text="历史", **_btn_style,
            command=lambda: self.on_history and self.on_history(),
        ).pack(side="left", padx=0)

        tk.Button(
            self.toolbar, text="主菜单", **_btn_style,
            command=lambda: self.on_main_menu and self.on_main_menu(),
        ).pack(side="left", padx=0)

        tk.Button(
            self.toolbar, text="设置", **_btn_style,
            command=lambda: self.on_settings and self.on_settings(),
        ).pack(side="left", padx=0)

    def set_toolbar_visible(self, visible: bool) -> None:
        """显示或隐藏工具栏。

        Args:
            visible: True 显示，False 隐藏。
        """
        if self.toolbar:
            if visible:
                self.toolbar.grid()
            else:
                self.toolbar.grid_remove()

    # ── Canvas ──────────────────────────────────────────────────────

    def _build_canvas(self) -> None:
        """构建 Canvas 主显示区。"""
        container = tk.Frame(self.root, bg=COLOR_BG_DARK)
        container.grid(row=1, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            container, bg=COLOR_BG_DARK,
            highlightthickness=0, cursor="hand2",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.canvas.bind("<Button-1>", self._on_canvas_click)

    def _on_canvas_click(self, event: tk.Event) -> None:
        """Canvas 鼠标点击回调。"""
        if self.on_advance:
            self.on_advance()

    # ── 对话 Frame ──────────────────────────────────────────────────

    def _build_dialogue_frame(self) -> None:
        """构建底部对话 Frame（说话人标签、文本标签、推进指示器、提示）。"""
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

        # 说话人
        self.speaker_label = tk.Label(
            self.dialogue_frame, text="",
            font=FONT_SPEAKER, fg=COLOR_TEXT_SPEAKER,
            bg=COLOR_DIALOGUE_BG, anchor="w", padx=24,
        )
        self.speaker_label.grid(row=0, column=0, sticky="ew", pady=(12, 0))

        # 对话文本
        self.text_label = tk.Label(
            self.dialogue_frame, text="",
            font=FONT_DIALOGUE, fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_DIALOGUE_BG, anchor="nw",
            justify="left", wraplength=WINDOW_WIDTH - 80,
            padx=24,
        )
        self.text_label.grid(row=1, column=0, sticky="nw", pady=(6, 12))

        # 推进指示器（▼）
        self.next_indicator = tk.Label(
            self.dialogue_frame, text="",
            font=("微软雅黑", 18), fg=COLOR_TEXT_SPEAKER,
            bg=COLOR_DIALOGUE_BG,
        )
        self.next_indicator.grid(row=1, column=1, sticky="se",
                                 padx=(0, 28), pady=(0, 18))

        # 快捷键提示
        self.hint_label = tk.Label(
            self.dialogue_frame,
            text="点击推进 · A自动 · Ctrl快进 · S存档 · L读档 · Esc设置",
            font=("微软雅黑", 9), fg="#7f8c8d",
            bg=COLOR_DIALOGUE_BG, anchor="e", padx=24,
        )
        self.hint_label.grid(row=2, column=0, columnspan=2,
                             sticky="ew", pady=(0, 4))

    def set_dialogue_frame_visible(self, visible: bool) -> None:
        """显示或隐藏对话 Frame。

        Args:
            visible: True 显示，False 隐藏。
        """
        if self.dialogue_frame:
            if visible:
                self.dialogue_frame.grid()
            else:
                self.dialogue_frame.grid_remove()

    def set_dialog_position(self, pos: str) -> None:
        """设置对话框位置。

        Args:
            pos: "bottom" / "top" / "fullscreen"。
        """
        if not self.dialogue_frame:
            return
        if pos == "bottom":
            self.dialogue_frame.grid(row=2, column=0, sticky="ew")
        elif pos == "top":
            self.dialogue_frame.grid(row=0, column=0, sticky="ew")
        elif pos == "fullscreen":
            self.dialogue_frame.grid(row=1, column=0, sticky="sew")
            self.dialogue_frame.config(height=WINDOW_HEIGHT // 2)

    # ====================================================================
    #  对话更新
    # ====================================================================

    def set_speaker(self, text: str, color: str = COLOR_TEXT_SPEAKER) -> None:
        """更新说话人标签。

        Args:
            text: 说话人名称。
            color: 文字颜色。
        """
        if self.speaker_label:
            self.speaker_label.config(text=text, fg=color)

    def set_text(self, text: str, color: str = COLOR_TEXT_PRIMARY) -> None:
        """更新对话文本标签。

        Args:
            text: 显示的文本内容。
            color: 文字颜色。
        """
        if self.text_label:
            self.text_label.config(text=text, fg=color)

    def show_next_indicator(self, visible: bool = True) -> None:
        """显示或隐藏推进指示器（▼）。

        Args:
            visible: True 显示，False 隐藏。
        """
        if self.next_indicator:
            self.next_indicator.config(text="▼" if visible else "")

    def update_text_wraplength(self, width: int) -> None:
        """根据窗口宽度更新文本换行宽度。

        Args:
            width: 窗口当前宽度。
        """
        if self.text_label:
            new_wrap = max(width - 80, 200)
            self.text_label.config(wraplength=new_wrap)

    # ====================================================================
    #  选项分支 UI
    # ====================================================================

    def show_choices(self, choices: list[dict]) -> None:
        """在 Canvas 中央显示选项按钮。

        Args:
            choices: [{"text": "...", "next_scene": "...", "if": "..."}, ...]。
                     当用户选择时，on_choice(next_scene) 被调用。
        """
        self.cleanup_choices()

        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT

        # 半透明遮罩
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

            def make_handler(c: dict) -> Callable:
                def handler() -> None:
                    if self.on_choice:
                        self.on_choice(c)
                return handler

            btn = tk.Button(
                self.choice_frame, text=text,
                font=FONT_BUTTON, fg=COLOR_CHOICE_TEXT, bg=COLOR_CHOICE_BG,
                activeforeground=COLOR_TEXT_ACCENT,
                activebackground=COLOR_CHOICE_HOVER,
                relief="solid", bd=1,
                highlightbackground=COLOR_CHOICE_BORDER, highlightthickness=1,
                padx=40, pady=10, cursor="hand2",
                command=make_handler(choice))
            btn.pack(fill="x", padx=20, pady=6)
            self.choice_buttons.append(btn)

        self.choice_frame.update_idletasks()
        fw = min(self.choice_frame.winfo_reqwidth() + 40, 500)
        self.canvas.create_window(
            w // 2, int(h * 0.45),
            window=self.choice_frame, anchor="center",
            width=fw, tags="choice_ui")

    def cleanup_choices(self) -> None:
        """清理选项相关 UI。"""
        self.canvas.delete("choice_ui")
        if self.choice_frame:
            self.choice_frame.destroy()
            self.choice_frame = None
        self.choice_buttons = []

    # ====================================================================
    #  主菜单 UI
    # ====================================================================

    def show_main_menu(
        self,
        title: str,
        version: str = "",
        buttons: Optional[list[tuple[str, Callable]]] = None,
    ) -> None:
        """在 Canvas 上显示主菜单。

        Args:
            title: 游戏标题。
            version: 版本号（可选）。
            buttons: (按钮文字, 回调) 列表。
        """
        self.cleanup_main_menu()

        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT

        # 渐变背景
        for i in range(20):
            frac = i / 20
            r, g, b = int(10 + frac * 15), int(10 + frac * 10), int(26 + frac * 20)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.canvas.create_rectangle(
                0, int(h * frac), w, int(h * (frac + 0.05)),
                fill=color, outline="", tags="main_menu_bg")

        spaced_title = "  ".join(title)
        self.canvas.create_text(w // 2, int(h * 0.22),
                                text=spaced_title, font=FONT_TITLE,
                                fill=COLOR_TEXT_ACCENT, anchor="center",
                                tags="main_menu_bg")
        self.canvas.create_text(w // 2, int(h * 0.32),
                                text=f"— {title} —",
                                font=("微软雅黑", 16), fill=COLOR_TEXT_PRIMARY,
                                anchor="center", tags="main_menu_bg")

        # 按钮容器
        self.main_menu_frame = tk.Frame(self.canvas, bg="", bd=0)
        btn_style = dict(
            font=("微软雅黑", 14),
            fg=COLOR_TEXT_PRIMARY, bg="#1e1e3f",
            activeforeground=COLOR_TEXT_ACCENT,
            activebackground="#2d2d5e",
            relief="solid", bd=1,
            padx=60, pady=10, cursor="hand2",
            highlightbackground=COLOR_CHOICE_BORDER,
            highlightthickness=1,
        )

        if buttons:
            for text, cmd in buttons:
                tk.Button(self.main_menu_frame, text=text,
                          command=cmd, **btn_style).pack(fill="x", pady=6)

        self.canvas.create_window(w // 2, int(h * 0.58),
                                  window=self.main_menu_frame,
                                  anchor="center",
                                  tags="main_menu_frame")

        # 版本信息
        if version:
            self.canvas.create_text(w // 2, h - 30,
                                    text=f"v{version}",
                                    font=("微软雅黑", 10),
                                    fill="#5a5a7a",
                                    anchor="center",
                                    tags="main_menu_bg")

    def cleanup_main_menu(self) -> None:
        """清理主菜单 UI。"""
        self.canvas.delete("main_menu_bg")
        if self.main_menu_frame:
            self.main_menu_frame.destroy()
            self.main_menu_frame = None
        self.canvas.delete("main_menu_frame")

    # ====================================================================
    #  通知
    # ====================================================================

    def show_notification(
        self, text: str,
        color: str = "#f1c40f", duration: int = 1500,
    ) -> None:
        """在 Canvas 中央显示短暂通知。

        Args:
            text: 通知文本。
            color: 文字颜色。
            duration: 显示时长（毫秒）。
        """
        _render_notification(self.canvas, text, color, duration)

    # ====================================================================
    #  错误对话框
    # ====================================================================

    def show_error_dialog(
        self, message: str,
        on_close: Optional[Callable] = None,
    ) -> None:
        """显示错误弹窗。

        Args:
            message: 错误信息。
            on_close: 关闭时的回调。
        """
        win = tk.Toplevel(self.root)
        win.title("错误")
        win.geometry("440x160")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text=message, font=FONT_UI,
                 wraplength=400, padx=20, pady=20).pack(expand=True)

        def _close() -> None:
            win.destroy()
            if on_close:
                on_close()

        tk.Button(win, text="确定", font=FONT_UI,
                  command=_close).pack(pady=10)

    # ====================================================================
    #  设置面板
    # ====================================================================

    def open_settings(
        self,
        current_speed: int = DEFAULT_TEXT_SPEED,
        volume_bgm: int = DEFAULT_VOLUME_BGM,
        volume_sfx: int = DEFAULT_VOLUME_SFX,
        volume_voice: int = DEFAULT_VOLUME_VOICE,
        global_muted: bool = False,
        skip_mode: str = "read",
        dialog_position: str = DEFAULT_DIALOG_POSITION,
        on_speed_change: Optional[Callable[[int], None]] = None,
        on_bgm_volume: Optional[Callable[[int], None]] = None,
        on_sfx_volume: Optional[Callable[[int], None]] = None,
        on_voice_volume: Optional[Callable[[int], None]] = None,
        on_global_mute: Optional[Callable[[bool], None]] = None,
        on_skip_mode: Optional[Callable[[str], None]] = None,
        on_dialog_position: Optional[Callable[[str], None]] = None,
        on_fullscreen: Optional[Callable[[bool], None]] = None,
    ) -> None:
        """打开设置窗口。

        Args:
            current_speed: 当前文字速度。
            volume_bgm: 当前 BGM 音量。
            volume_sfx: 当前 SFX 音量。
            volume_voice: 当前语音音量。
            global_muted: 是否全局静音。
            skip_mode: 当前跳过模式。
            dialog_position: 对话框位置。
            on_speed_change: 文字速度变更回调。
            on_bgm_volume: BGM 音量变更回调。
            on_sfx_volume: SFX 音量变更回调。
            on_voice_volume: 语音音量变更回调。
            on_global_mute: 全局静音回调。
            on_skip_mode: 跳过模式变更回调。
            on_dialog_position: 对话框位置变更回调。
            on_fullscreen: 全屏切换回调。
        """
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("560x660")
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=COLOR_BG_DARK)

        # 滚动支持
        outer = tk.Frame(win, bg=COLOR_BG_DARK)
        outer.pack(fill="both", expand=True)

        cv = tk.Canvas(outer, bg=COLOR_BG_DARK, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=COLOR_BG_DARK)

        inner.bind("<Configure>",
                   lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=inner, anchor="nw")
        cv.configure(yscrollcommand=sb.set)

        def _mw(event: tk.Event) -> None:
            cv.yview_scroll(int(-1 * (event.delta / 120)), "units")

        cv.bind("<MouseWheel>", _mw)
        inner.bind("<MouseWheel>", _mw)

        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        tk.Label(inner, text="— 设 置 —",
                 font=("微软雅黑", 18, "bold"),
                 fg=COLOR_TEXT_ACCENT, bg=COLOR_BG_DARK,
                 pady=15).pack(fill="x")

        # ── 文字速度 ──
        self._settings_slider_with_presets(
            inner, "文字速度",
            current_speed, 10, 200, 5,
            [("快速", 20), ("普通", 40), ("慢速", 80), ("很慢", 150)],
            lambda v: on_speed_change(int(v)) if on_speed_change else None,
        )

        # ── BGM 音量 ──
        self._settings_slider(inner, "BGM 音量",
                              volume_bgm, 0, 100, 5,
                              lambda v: on_bgm_volume(int(v)) if on_bgm_volume else None)

        # ── SFX 音量 ──
        self._settings_slider(inner, "SFX 音量",
                              volume_sfx, 0, 100, 5,
                              lambda v: on_sfx_volume(int(v)) if on_sfx_volume else None)

        # ── 语音音量 ──
        self._settings_slider(inner, "语音音量",
                              volume_voice, 0, 100, 5,
                              lambda v: on_voice_volume(int(v)) if on_voice_volume else None)

        # ── 全局静音 ──
        mute_frame = tk.Frame(inner, bg=COLOR_BG_DARK)
        mute_frame.pack(fill="x", padx=40, pady=10)
        mute_state = tk.BooleanVar(value=global_muted)
        tk.Checkbutton(
            mute_frame, text="全局静音", variable=mute_state,
            font=("微软雅黑", 12), fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG_DARK, selectcolor=COLOR_BG_DARK,
            activebackground=COLOR_BG_DARK,
            cursor="hand2",
            command=lambda: on_global_mute(mute_state.get()) if on_global_mute else None,
        ).pack(anchor="w")

        # ── 跳过模式 ──
        skip_frame = tk.Frame(inner, bg=COLOR_BG_DARK)
        skip_frame.pack(fill="x", padx=40, pady=10)
        tk.Label(skip_frame, text="跳过模式",
                 font=("微软雅黑", 12), fg=COLOR_TEXT_PRIMARY,
                 bg=COLOR_BG_DARK, anchor="w").pack(fill="x")

        skip_var = tk.StringVar(value=skip_mode)
        skip_opts = tk.Frame(skip_frame, bg=COLOR_BG_DARK)
        skip_opts.pack(anchor="w", pady=(4, 0))
        for label, val in [("关闭", "off"), ("已读跳过", "read"), ("全部跳过", "all")]:
            tk.Radiobutton(
                skip_opts, text=label, variable=skip_var,
                value=val, font=("微软雅黑", 11),
                fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG_DARK,
                selectcolor=COLOR_BG_DARK,
                activebackground=COLOR_BG_DARK,
                cursor="hand2",
                command=lambda v=val: on_skip_mode(v) if on_skip_mode else None,
            ).pack(side="left", padx=(0, 15))

        # ── 全屏切换 ──
        fs_frame = tk.Frame(inner, bg=COLOR_BG_DARK)
        fs_frame.pack(fill="x", padx=40, pady=10)
        fs_state = tk.BooleanVar(value=False)
        tk.Checkbutton(
            fs_frame, text="全屏模式 (F11)", variable=fs_state,
            font=("微软雅黑", 12), fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG_DARK, selectcolor=COLOR_BG_DARK,
            activebackground=COLOR_BG_DARK,
            cursor="hand2",
            command=lambda: on_fullscreen(fs_state.get()) if on_fullscreen else None,
        ).pack(anchor="w")

        # ── 对话框位置 ──
        pos_frame = tk.Frame(inner, bg=COLOR_BG_DARK)
        pos_frame.pack(fill="x", padx=40, pady=10)
        tk.Label(pos_frame, text="对话框位置",
                 font=("微软雅黑", 12), fg=COLOR_TEXT_PRIMARY,
                 bg=COLOR_BG_DARK, anchor="w").pack(fill="x")
        pos_var = tk.StringVar(value=dialog_position)
        pos_opts = tk.Frame(pos_frame, bg=COLOR_BG_DARK)
        pos_opts.pack(anchor="w", pady=(4, 0))
        for label, val in [("底部", "bottom"), ("顶部", "top"), ("全屏", "fullscreen")]:
            tk.Radiobutton(
                pos_opts, text=label, variable=pos_var,
                value=val, font=("微软雅黑", 11),
                fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG_DARK,
                selectcolor=COLOR_BG_DARK,
                activebackground=COLOR_BG_DARK,
                cursor="hand2",
                command=lambda v=val: on_dialog_position(v) if on_dialog_position else None,
            ).pack(side="left", padx=(0, 15))

        # ── 关闭 ──
        tk.Button(inner, text="关闭", font=FONT_UI, command=win.destroy,
                  bg=COLOR_CHOICE_BORDER, fg=COLOR_TEXT_PRIMARY,
                  relief="solid", bd=1, padx=30, pady=6, cursor="hand2",
                  ).pack(pady=20)

    def _settings_slider(
        self, parent: tk.Frame, title: str,
        value: int, from_: int, to: int, resolution: int,
        on_change: Optional[Callable],
    ) -> None:
        """构建设置页中的一个滑块区域。"""
        frame = tk.Frame(parent, bg=COLOR_BG_DARK)
        frame.pack(fill="x", padx=40, pady=8)

        tk.Label(frame, text=title,
                 font=("微软雅黑", 14), fg=COLOR_TEXT_PRIMARY,
                 bg=COLOR_BG_DARK, anchor="w").pack(fill="x")

        scale = tk.Scale(frame, from_=from_, to=to,
                         orient="horizontal", length=380,
                         resolution=resolution, showvalue=True,
                         bg=COLOR_DIALOGUE_BG, fg=COLOR_TEXT_PRIMARY,
                         highlightbackground=COLOR_BG_DARK,
                         troughcolor="#2c3e50", cursor="hand2")
        scale.set(value)
        if on_change:
            scale.config(command=on_change)
        scale.pack(pady=(4, 0))

    def _settings_slider_with_presets(
        self, parent: tk.Frame, title: str,
        value: int, from_: int, to: int, resolution: int,
        presets: list[tuple[str, int]],
        on_change: Optional[Callable],
    ) -> None:
        """构建设置页中带预设按钮的滑块区域。"""
        frame = tk.Frame(parent, bg=COLOR_BG_DARK)
        frame.pack(fill="x", padx=40, pady=8)

        tk.Label(frame, text=title,
                 font=("微软雅黑", 14), fg=COLOR_TEXT_PRIMARY,
                 bg=COLOR_BG_DARK, anchor="w").pack(fill="x")

        scale = tk.Scale(frame, from_=from_, to=to,
                         orient="horizontal", length=380,
                         resolution=resolution, showvalue=True,
                         bg=COLOR_DIALOGUE_BG, fg=COLOR_TEXT_PRIMARY,
                         highlightbackground=COLOR_BG_DARK,
                         troughcolor="#2c3e50", cursor="hand2")
        scale.set(value)
        if on_change:
            scale.config(command=on_change)
        scale.pack(pady=(4, 0))

        pf = tk.Frame(frame, bg=COLOR_BG_DARK)
        pf.pack(pady=(0, 4))
        for label, val in presets:
            tk.Button(pf, text=label,
                      font=("微软雅黑", 11),
                      bg=COLOR_CHOICE_BG, fg=COLOR_TEXT_PRIMARY,
                      activebackground=COLOR_CHOICE_HOVER,
                      activeforeground=COLOR_TEXT_ACCENT,
                      relief="solid", bd=1, padx=16, cursor="hand2",
                      command=lambda v=val: (scale.set(v), on_change(v) if on_change else None),
                      ).pack(side="left", padx=6)

    # ====================================================================
    #  文本历史弹窗
    # ====================================================================

    def show_history(
        self,
        entries: list[dict],
        on_replay_voice: Optional[Callable[[str], None]] = None,
        on_export: Optional[Callable] = None,
    ) -> None:
        """打开文本历史弹窗。

        Args:
            entries: 历史条目列表，每项 {"speaker": str, "text": str, "voice": str}。
            on_replay_voice: 重播语音回调，参数为语音路径。
            on_export: 导出历史回调。
        """
        win = tk.Toplevel(self.root)
        win.title("文本历史")
        win.geometry("640x500")
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

        def _on_wheel(event: tk.Event) -> None:
            cv.yview_scroll(int(-1 * (event.delta / 120)), "units")

        for w in (cv, inner):
            w.bind("<MouseWheel>", _on_wheel)

        if not entries:
            tk.Label(inner, text="暂无对白记录", font=FONT_UI,
                     fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG_DARK,
                     pady=20).pack()
        else:
            for entry in entries:
                speaker = entry.get("speaker", "")
                text = entry.get("text", "")
                voice_path = entry.get("voice")

                row = tk.Frame(inner, bg=COLOR_DIALOGUE_BG,
                               relief="solid", bd=1)
                row.pack(fill="x", pady=4, padx=4)

                header = tk.Frame(row, bg=COLOR_DIALOGUE_BG)
                header.pack(fill="x", padx=12, pady=(8, 2))

                tk.Label(header, text=speaker or "（旁白）",
                         font=("微软雅黑", 12, "bold"),
                         fg=COLOR_TEXT_SPEAKER if speaker else DEFAULT_NARRATOR_COLOR,
                         bg=COLOR_DIALOGUE_BG, anchor="w").pack(side="left")

                if voice_path and on_replay_voice:
                    tk.Button(
                        header, text="🔊 重播", font=("微软雅黑", 9),
                        bg=COLOR_CHOICE_BG, fg=COLOR_TEXT_PRIMARY,
                        relief="flat", bd=0, cursor="hand2",
                        activebackground=COLOR_CHOICE_HOVER,
                        command=lambda v=voice_path: on_replay_voice(v),
                    ).pack(side="right", padx=(10, 0))

                tk.Label(row, text=text,
                         font=("微软雅黑", 11),
                         fg=COLOR_TEXT_PRIMARY, bg=COLOR_DIALOGUE_BG,
                         anchor="w", wraplength=540,
                         justify="left", padx=12).pack(fill="x", pady=(0, 8))

        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # 底部按钮
        btn_frame = tk.Frame(win, bg=COLOR_BG_DARK)
        btn_frame.pack(fill="x", padx=20, pady=(0, 12))

        if on_export:
            tk.Button(btn_frame, text="导出历史", font=FONT_UI,
                      bg=COLOR_CHOICE_BG, fg=COLOR_TEXT_PRIMARY,
                      relief="solid", bd=1, padx=15, cursor="hand2",
                      command=on_export).pack(side="left")

        tk.Button(btn_frame, text="关闭", font=FONT_UI,
                  command=win.destroy,
                  bg=COLOR_DIALOGUE_BG, fg=COLOR_TEXT_PRIMARY,
                  relief="solid", bd=1, padx=20).pack(side="right")

    # ====================================================================
    #  存档 / 读档弹窗
    # ====================================================================

    def open_save_load(
        self,
        mode: str,  # "save" | "load"
        on_save: Optional[Callable[[int], None]] = None,
        on_load: Optional[Callable[[int], None]] = None,
        get_slot_info: Optional[Callable[[int], dict]] = None,
    ) -> None:
        """打开存档/读档弹窗。

        Args:
            mode: "save" 或 "load"。
            on_save: 存档回调，参数为槽位号。
            on_load: 读档回调，参数为槽位号。
            get_slot_info: 获取槽位信息的回调，返回 dict 含 date/summary。
        """
        win = tk.Toplevel(self.root)
        win.title("存档" if mode == "save" else "读档")
        win.geometry("700x520")
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=COLOR_BG_DARK)

        tk.Label(win, text=f"— {'存档' if mode == 'save' else '读档'} —",
                 font=("微软雅黑", 18, "bold"),
                 fg=COLOR_TEXT_ACCENT, bg=COLOR_BG_DARK,
                 pady=15).pack(fill="x")

        # 当前页
        page_var = tk.IntVar(value=0)
        slots_frame = tk.Frame(win, bg=COLOR_BG_DARK)
        slots_frame.pack(fill="both", expand=True, padx=20)

        def _refresh_page() -> None:
            """刷新当前页的槽位显示。"""
            for w in slots_frame.winfo_children():
                w.destroy()
            page = page_var.get()
            start = page * SAVE_SLOTS_PER_PAGE
            end = min(start + SAVE_SLOTS_PER_PAGE, MAX_SAVE_SLOTS)

            cols = 3
            row_frame = None
            for i, slot in enumerate(range(start, end)):
                if i % cols == 0:
                    row_frame = tk.Frame(slots_frame, bg=COLOR_BG_DARK)
                    row_frame.pack(fill="x", pady=3)
                self._make_slot_widget(row_frame, slot, mode,
                                       on_save, on_load,
                                       get_slot_info).pack(
                    side="left", padx=5, expand=True, fill="x")

        # 翻页
        nav_frame = tk.Frame(win, bg=COLOR_BG_DARK)
        nav_frame.pack(fill="x", padx=20, pady=10)

        max_page = (MAX_SAVE_SLOTS + SAVE_SLOTS_PER_PAGE - 1) // SAVE_SLOTS_PER_PAGE

        def prev_page() -> None:
            if page_var.get() > 0:
                page_var.set(page_var.get() - 1)
                _refresh_page()

        def next_page() -> None:
            if page_var.get() < max_page - 1:
                page_var.set(page_var.get() + 1)
                _refresh_page()

        tk.Button(nav_frame, text="◀ 上一页", font=FONT_UI,
                  bg=COLOR_CHOICE_BG, fg=COLOR_TEXT_PRIMARY,
                  activebackground=COLOR_CHOICE_HOVER,
                  relief="solid", bd=1, padx=10, cursor="hand2",
                  command=prev_page).pack(side="left", padx=5)
        tk.Label(nav_frame,
                 textvariable=page_var,
                 font=FONT_UI, fg=COLOR_TEXT_PRIMARY,
                 bg=COLOR_BG_DARK, padx=20).pack(side="left")
        tk.Button(nav_frame, text="下一页 ▶", font=FONT_UI,
                  bg=COLOR_CHOICE_BG, fg=COLOR_TEXT_PRIMARY,
                  activebackground=COLOR_CHOICE_HOVER,
                  relief="solid", bd=1, padx=10, cursor="hand2",
                  command=next_page).pack(side="left", padx=5)

        _refresh_page()

        tk.Button(win, text="关闭", font=FONT_UI,
                  command=win.destroy,
                  bg=COLOR_DIALOGUE_BG, fg=COLOR_TEXT_PRIMARY,
                  relief="solid", bd=1, padx=20, pady=4,
                  ).pack(pady=(0, 10))

    def _make_slot_widget(
        self,
        parent: tk.Frame,
        slot: int,
        mode: str,
        on_save: Optional[Callable[[int], None]],
        on_load: Optional[Callable[[int], None]],
        get_slot_info: Optional[Callable[[int], dict]],
    ) -> tk.Frame:
        """创建一个存档槽位按钮组件。

        Args:
            parent: 父容器。
            slot: 槽位编号。
            mode: "save" 或 "load"。
            on_save: 存档回调。
            on_load: 读档回调。
            get_slot_info: 获取槽位信息。

        Returns:
            槽位 Frame。
        """
        frame = tk.Frame(parent, bg=COLOR_CHOICE_BG, relief="solid",
                         bd=1, padx=8, pady=6, cursor="hand2")
        frame.configure(width=190, height=100)
        frame.pack_propagate(False)

        slot_label = str(slot).zfill(2) if isinstance(slot, int) else slot
        title = f"[{slot_label}]"
        summary_text = ""
        status_text = "空"

        if get_slot_info:
            info = get_slot_info(slot)
            if info:
                date_str = info.get("date", "")
                summary = info.get("summary", "") or info.get("scene_title", "")
                title = f"[{slot_label}] {date_str}" if date_str else title
                summary_text = summary[:40] if summary else ""
                status_text = "✓ 有存档"

        tk.Label(frame, text=title,
                 font=("微软雅黑", 9, "bold"),
                 fg=COLOR_TEXT_ACCENT, bg=COLOR_CHOICE_BG,
                 anchor="w").pack(fill="x")
        tk.Label(frame, text=summary_text,
                 font=("微软雅黑", 8),
                 fg=COLOR_TEXT_PRIMARY, bg=COLOR_CHOICE_BG,
                 anchor="w", wraplength=170, justify="left").pack(fill="x", pady=(2, 0))
        tk.Label(frame, text=status_text,
                 font=("微软雅黑", 8),
                 fg="#7f8c8d",
                 bg=COLOR_CHOICE_BG, anchor="w").pack(fill="x")

        def _on_click() -> None:
            if mode == "save" and on_save:
                on_save(slot)
            elif mode == "load" and on_load:
                # 关闭弹窗的上级窗口
                p = frame.master
                while p and not isinstance(p, tk.Toplevel):
                    p = p.master
                if p:
                    p.destroy()
                on_load(slot)

        for child in frame.winfo_children():
            child.bind("<Button-1>", lambda e: _on_click())
        frame.bind("<Button-1>", lambda e: _on_click())

        return frame

    # ====================================================================
    #  CG 画廊
    # ====================================================================

    def open_gallery(
        self,
        scenes: list[tuple[str, str]],  # [(bg_id, label), ...]
        unlocked: set[str],
    ) -> None:
        """打开 CG 画廊窗口。

        Args:
            scenes: (背景ID, 显示名称) 列表。
            unlocked: 已解锁的背景 ID 集合。
        """
        win = tk.Toplevel(self.root)
        win.title("CG 画廊")
        win.geometry("700x520")
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=COLOR_BG_DARK)

        tk.Label(win, text="— CG 画廊 —",
                 font=("微软雅黑", 18, "bold"),
                 fg=COLOR_TEXT_ACCENT, bg=COLOR_BG_DARK,
                 pady=15).pack(fill="x")

        if not scenes:
            tk.Label(win, text="暂无可用 CG", font=FONT_UI,
                     fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG_DARK,
                     pady=40).pack()
        else:
            cg_frame = tk.Frame(win, bg=COLOR_BG_DARK)
            cg_frame.pack(fill="both", expand=True, padx=20, pady=10)

            cols = 3
            for i, (bg_id, label) in enumerate(scenes):
                is_unlocked = bg_id in unlocked
                row = i // cols
                col = i % cols

                cell = tk.Frame(cg_frame, bg=COLOR_CHOICE_BG,
                                relief="solid", bd=1, padx=5, pady=5,
                                width=200, height=140)
                cell.grid(row=row, column=col, padx=5, pady=5)
                cell.grid_propagate(False)

                if is_unlocked:
                    color, _ = PLACEHOLDER_BG_COLORS.get(bg_id, ("#34495e", ""))
                    tk.Label(cell, text=label,
                             font=("微软雅黑", 10),
                             fg=COLOR_TEXT_PRIMARY, bg=color,
                             anchor="center").place(relx=0.5, rely=0.5,
                                                    anchor="center")
                else:
                    tk.Label(cell, text="🔒 未解锁",
                             font=("微软雅黑", 10),
                             fg="#5a5a7a", bg=COLOR_CHOICE_BG,
                             anchor="center").place(relx=0.5, rely=0.5,
                                                    anchor="center")

        tk.Button(win, text="关闭", font=FONT_UI,
                  command=win.destroy,
                  bg=COLOR_DIALOGUE_BG, fg=COLOR_TEXT_PRIMARY,
                  relief="solid", bd=1, padx=20, pady=4,
                  ).pack(pady=(0, 10))

    # ====================================================================
    #  标题画面
    # ====================================================================

    def show_title_screen(
        self,
        title: str,
        on_click: Optional[Callable] = None,
    ) -> tuple[int, int, list[int]]:
        """在 Canvas 上显示标题画面。

        Args:
            title: 游戏标题。
            on_click: 点击开始的回调。

        Returns:
            (canvas宽度, 画布高度, 闪烁文字项ID列表)
        """
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT

        # 渐变背景
        for i in range(20):
            frac = i / 20
            r, g, b = int(10 + frac * 15), int(10 + frac * 10), int(26 + frac * 20)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.canvas.create_rectangle(
                0, int(h * frac), w, int(h * (frac + 0.05)),
                fill=color, outline="")

        # 标题
        spaced_title = "  ".join(title)
        self.canvas.create_text(
            w // 2, h * 0.35,
            text=spaced_title, font=FONT_TITLE,
            fill=COLOR_TEXT_ACCENT, anchor="center")

        self.canvas.create_text(
            w // 2, h * 0.48,
            text=f"— {title} —",
            font=("微软雅黑", 16),
            fill=COLOR_TEXT_PRIMARY, anchor="center")

        # 闪烁的"点击开始"
        blink_id = self.canvas.create_text(
            w // 2, h * 0.65,
            text="— 点击任意处开始 —",
            font=("微软雅黑", 16),
            fill=COLOR_TEXT_SPEAKER, anchor="center")

        # 绑定点击
        if on_click:
            self.canvas.bind("<Button-1>", lambda e: on_click())

        return w, h, [blink_id]

    def blink_text_item(self, item_id: int, color_a: str, color_b: str,
                        interval: int = 600) -> None:
        """让指定 Canvas 文字项在两个颜色之间闪烁。

        Args:
            item_id: Canvas 文字项 ID。
            color_a: 颜色 A。
            color_b: 颜色 B。
            interval: 切换间隔（毫秒）。
        """
        current = self.canvas.itemcget(item_id, "fill")
        new_color = color_b if current == color_a else color_a
        try:
            self.canvas.itemconfig(item_id, fill=new_color)
        except tk.TclError:
            return
        self.root.after(interval, lambda: self.blink_text_item(
            item_id, color_a, color_b, interval))

    # ====================================================================
    #  全屏工具
    # ====================================================================

    def toggle_fullscreen(self) -> bool:
        """切换全屏模式。

        Returns:
            切换后的全屏状态。
        """
        is_full = self.root.attributes("-fullscreen")
        self.root.attributes("-fullscreen", not is_full)
        return not is_full

    # ====================================================================
    #  完全重置
    # ====================================================================

    def clear_all(self) -> None:
        """清除 Canvas 上所有内容，销毁选项帧。"""
        self.canvas.delete("all")
        self.cleanup_choices()
        self.cleanup_main_menu()
        self.choice_overlay = None
        self.bg_overlay = None
