#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║              视觉小说游戏框架 (Visual Novel Game Framework)     ║
║                      Version 1.0.0                         ║
╚══════════════════════════════════════════════════════════════╝

【依赖说明】
  - 仅使用 Python 标准库，无需安装任何第三方包
  - Python 3.10+
  - 模块: tkinter, json, pickle, os, random, pathlib

【运行方式】
  python visual_novel.py

【功能列表】
  1. 剧本驱动 — 从 JSON 格式读取剧情数据
  2. 对话系统 — 窗口底部显示角色名+对白，逐字打字机效果
  3. 立绘系统 — 左右两侧立绘，切换带淡入淡出
  4. 背景切换 — Canvas 背景切换，带白色淡入淡出过渡
  5. 选项分支 — 剧情选项按钮，点击跳转指定场景
  6. 存档/读档 — S 键保存 / L 键读取 (pickle)
  7. 文本历史 — H 键查看最近 10 条对白
  8. 设置面板 — Esc 键打开设置，调节文字速度
  9. 纯 tkinter 实现 — Canvas / Frame / Button / Toplevel

【操作方式】
  Space / 鼠标左键  — 推进对话 / 跳过打字效果
  S                 — 存档
  L                 — 读档
  H                 — 查看文本历史
  Esc               — 打开设置面板

【剧本 JSON 格式】
  {
    "title": "游戏标题",
    "scenes": [
      {
        "id": "scene1",
        "background": "背景图片路径或占位ID",
        "characters": {
          "left": "左立绘路径或占位ID",
          "right": "右立绘路径或占位ID"
        },
        "dialogue": [
          { "speaker": "角色名", "text": "对白内容" }
        ],
        "choices": [
          { "text": "选项文字", "next_scene": "场景ID" }
        ]
      }
    ]
  }
"""

import atexit
import tkinter as tk
from tkinter import font as tkfont
import json
import pickle
import os
import random
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Any, Union


# ============================================================================
# 常量定义
# ============================================================================

# 窗口默认尺寸
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 450

# 对话区域高度
DIALOGUE_FRAME_HEIGHT = 170

# 默认文字速度（毫秒/字符）
DEFAULT_TEXT_SPEED = 40

# 过渡动画步进间隔（毫秒）
BG_FADE_INTERVAL = 60
CHAR_FADE_INTERVAL = 50

# 字体设置
FONT_SPEAKER = ("微软雅黑", 16, "bold")
FONT_DIALOGUE = ("微软雅黑", 13)
FONT_BUTTON = ("微软雅黑", 14)
FONT_UI = ("微软雅黑", 12)
FONT_TITLE = ("微软雅黑", 36, "bold")
FONT_SUBTITLE = ("微软雅黑", 18)

# 立绘默认尺寸
CHAR_WIDTH = 170
CHAR_HEIGHT = 400

# 占位立绘颜色映射
PLACEHOLDER_COLORS = {
    "__demo_char_mystery__": ("#8E44AD", "???"),
    "__demo_char_girl__":    ("#E91E63", "星野"),
    "__demo_char_hero__":    ("#3498DB", "主角"),
}

# 占位背景颜色映射
PLACEHOLDER_BG_COLORS = {
    "__demo_bg_room__":  ("#2C3E50", "昏暗的房间"),
    "__demo_bg_valley__": ("#1E8449", "星落之谷"),
}

# 存档目录
SAVE_DIR = Path("saves")
SAVE_FILE_TEMPLATE = "save_{}.dat"

# 音频
AUDIO_DIR = Path("audio")
DEFAULT_VOLUME = 100

# 颜色主题
COLOR_BG_DARK = "#0a0a1a"
COLOR_DIALOGUE_BG = "#12122a"
COLOR_TEXT_PRIMARY = "#ecf0f1"
COLOR_TEXT_SPEAKER = "#e74c3c"
COLOR_TEXT_ACCENT = "#f1c40f"
COLOR_OVERLAY = "#ffffff"
COLOR_CHOICE_BG = "#1e1e3f"
COLOR_CHOICE_HOVER = "#2d2d5e"
COLOR_CHOICE_TEXT = "#ecf0f1"
COLOR_CHOICE_BORDER = "#e74c3c"
COLOR_BUTTON_SAVE = "#27ae60"
COLOR_BUTTON_LOAD = "#2980b9"


# ============================================================================
# 内置演示剧本数据
# ============================================================================

DEMO_SCRIPT = {
    "title": "星之回响",
    "version": "1.0",
    "scenes": [
        {
            "id": "start",
            "background": "__demo_bg_room__",
            "characters": {
                "left": "__demo_char_mystery__",
                "right": None
            },
            "dialogue": [
                {"speaker": "???", "text": "你终于醒了。"},
                {"speaker": "主角", "text": "这里是……？我什么都想不起来了。"},
                {"speaker": "???", "text": "这里是星落之谷。你已经昏迷三天了。"}
            ],
            "choices": [
                {"text": "询问对方身份", "next_scene": "ask_name"},
                {"text": "观察周围环境", "next_scene": "observe"},
                {"text": "保持沉默", "next_scene": "silent"}
            ]
        },
        {
            "id": "ask_name",
            "background": "__demo_bg_room__",
            "characters": {
                "left": "__demo_char_girl__",
                "right": None
            },
            "dialogue": [
                {"speaker": "主角", "text": "请问你是……？"},
                {"speaker": "少女", "text": "我叫星野，是这座山谷的守护者。"},
                {"speaker": "星野", "text": "你误入了山谷的结界，所以才会昏迷。"},
                {"speaker": "主角", "text": "结界？我完全不知道这些……"},
                {"speaker": "星野", "text": "看来你确实什么都不记得了。慢慢来吧。"}
            ],
            "choices": [
                {"text": "询问更多关于结界的事", "next_scene": "ask_barrier"},
                {"text": "道谢并准备离开", "next_scene": "leave"}
            ]
        },
        {
            "id": "observe",
            "background": "__demo_bg_valley__",
            "characters": {
                "left": "__demo_char_mystery__",
                "right": None
            },
            "dialogue": [
                {"speaker": "主角", "text": "（环顾四周）这是一个被群山环绕的山谷……"},
                {"speaker": "主角", "text": "空气中飘浮着奇怪的光点。"},
                {"speaker": "???", "text": "那些是星尘，是结界的一部分。"},
                {"speaker": "???", "text": "你能看到它们，说明你身上也有灵力。"},
                {"speaker": "主角", "text": "灵力？我只是一个普通人……"}
            ],
            "choices": [
                {"text": "让她继续说下去", "next_scene": "ask_barrier"},
                {"text": "表示想离开这里", "next_scene": "leave"}
            ]
        },
        {
            "id": "silent",
            "background": "__demo_bg_room__",
            "characters": {
                "left": "__demo_char_mystery__",
                "right": None
            },
            "dialogue": [
                {"speaker": "???", "text": "……你不打算说点什么吗？"},
                {"speaker": "主角", "text": "（沉默不语）"},
                {"speaker": "???", "text": "好吧，看来你还需要时间适应。"},
                {"speaker": "???", "text": "我叫星野，是这座山谷的守护者。"},
                {"speaker": "主角", "text": "……星野？"},
                {"speaker": "星野", "text": "对。你已经昏迷三天了，能活下来算是奇迹。"}
            ],
            "choices": [
                {"text": "询问结界的事", "next_scene": "ask_barrier"},
                {"text": "请求她送自己离开", "next_scene": "leave"}
            ]
        },
        {
            "id": "ask_barrier",
            "background": "__demo_bg_valley__",
            "characters": {
                "left": "__demo_char_girl__",
                "right": None
            },
            "dialogue": [
                {"speaker": "星野", "text": "这座山谷的结界是为了封印远古的灾厄而设的。"},
                {"speaker": "星野", "text": "你能够穿过结界进来，说明你与这封印有某种联系。"},
                {"speaker": "主角", "text": "我？与封印有联系？这太荒谬了……"},
                {"speaker": "星野", "text": "我知道这很难接受，但星尘在你周围的反应不会说谎。"},
                {"speaker": "星野", "text": "或许你正是预言中提到的那个「觉醒者」。"}
            ],
            "choices": [
                {"text": "接受命运，留下来帮忙", "next_scene": "ending_a"},
                {"text": "拒绝相信，坚持离开", "next_scene": "ending_b"}
            ]
        },
        {
            "id": "leave",
            "background": "__demo_bg_room__",
            "characters": {
                "left": "__demo_char_girl__",
                "right": None
            },
            "dialogue": [
                {"speaker": "星野", "text": "你想离开？"},
                {"speaker": "星野", "text": "但是结界已经认你为主了，没有你解开，任何人都出不去。"},
                {"speaker": "主角", "text": "什么？！"},
                {"speaker": "星野", "text": "所以，你暂时只能留在这里了。"},
                {"speaker": "星野", "text": "等你准备好之后，我带你去看结界核心。"}
            ],
            "choices": [
                {"text": "了解结界详情", "next_scene": "ask_barrier"},
                {"text": "无奈接受", "next_scene": "ending_a"}
            ]
        },
        {
            "id": "ending_a",
            "background": "__demo_bg_valley__",
            "characters": {
                "left": "__demo_char_girl__",
                "right": "__demo_char_hero__"
            },
            "dialogue": [
                {"speaker": "星野", "text": "太好了！有你帮忙，封印一定能稳定下来。"},
                {"speaker": "主角", "text": "虽然我还是不太明白……但我会尽力。"},
                {"speaker": "星野", "text": "来吧，我带你去看结界核心。你的故事，才刚刚开始。"}
            ]
        },
        {
            "id": "ending_b",
            "background": "__demo_bg_room__",
            "characters": {
                "left": "__demo_char_girl__",
                "right": None
            },
            "dialogue": [
                {"speaker": "星野", "text": "……我明白了。"},
                {"speaker": "星野", "text": "我不会强迫你。但结界不会轻易放你走。"},
                {"speaker": "星野", "text": "等你改变主意了，随时告诉我。"}
            ]
        }
    ]
}


# ============================================================================
#  音频引擎
# ============================================================================

class AudioEngine:
    """音频引擎：管理 BGM 与 SFX 播放。

    自动选择最佳后端 (ffplay > winsound > none):
      - ffplay     — 支持 mp3/ogg/flac/wav 等几乎所有格式
      - winsound   — Windows 内置，仅 .wav，零依赖
    """

    def __init__(self) -> None:
        self.volume: int = DEFAULT_VOLUME
        self.bgm_enabled: bool = True
        self.sfx_enabled: bool = True
        self._bgm_path: Optional[str] = None
        self._bgm_playing: bool = False
        self._bgm_process: Optional[subprocess.Popen] = None
        self._bgm_thread: Optional[threading.Thread] = None
        self._bgm_stop: threading.Event = threading.Event()
        atexit.register(self.shutdown)

    @property
    def available(self) -> bool:
        return self.backend_name != "none"

    @property
    def backend_name(self) -> str:
        if shutil.which("ffplay"):
            return "ffplay"
        try:
            import winsound  # noqa: F401
            return "winsound"
        except ImportError:
            return "none"

    def set_volume(self, vol: int) -> None:
        new_vol = 100 if vol > 0 else 0
        if new_vol == self.volume:
            return
        self.volume = new_vol
        if self.volume == 0:
            self.stop_bgm()
        elif self._bgm_path:
            self.stop_bgm()
            self.play_bgm(self._bgm_path)

    def get_volume(self) -> int:
        return self.volume

    def _resolve_path(self, path: str) -> str:
        p = Path(path)
        if p.is_absolute():
            return str(p)
        candidate = AUDIO_DIR / p
        if candidate.exists():
            return str(candidate)
        # ffplay 后端：搜索常见扩展名
        if self.backend_name == "ffplay":
            for ext in [".mp3", ".ogg", ".wav", ".flac", ".m4a", ".opus", ".wma"]:
                c2 = AUDIO_DIR / f"{p}{ext}"
                if c2.exists():
                    return str(c2)
        if not p.suffix:
            c2 = AUDIO_DIR / f"{p}.wav"
            if c2.exists():
                return str(c2)
        return str(p)

    def play_bgm(self, path: str) -> None:
        if not self.bgm_enabled or self.volume == 0:
            return
        resolved = self._resolve_path(path)
        if self._bgm_playing and self._bgm_path == resolved:
            return
        self.stop_bgm()
        self._bgm_path = resolved
        self._bgm_stop.clear()
        if not os.path.exists(resolved):
            return
        backend = self.backend_name
        if backend == "ffplay":
            self._bgm_playing = True
            self._bgm_thread = threading.Thread(
                target=self._bgm_loop_ffplay, daemon=True)
            self._bgm_thread.start()
        elif backend == "winsound":
            self._bgm_playing = True
            self._bgm_thread = threading.Thread(
                target=self._bgm_loop_winsound, daemon=True)
            self._bgm_thread.start()

    def _bgm_loop_ffplay(self) -> None:
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        try:
            self._bgm_process = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loop", "0",
                 "-volume", str(self.volume), self._bgm_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
            )
            self._bgm_process.wait()
        except Exception:
            pass
        finally:
            self._bgm_process = None
            if not self._bgm_stop.is_set():
                self._bgm_playing = False

    def _bgm_loop_winsound(self) -> None:
        import winsound
        try:
            winsound.PlaySound(
                self._bgm_path,
                winsound.SND_FILENAME | winsound.SND_LOOP | winsound.SND_ASYNC,
            )
        except Exception:
            pass
        self._bgm_stop.wait()

    def stop_bgm(self) -> None:
        self._bgm_playing = False
        self._bgm_stop.set()
        backend = self.backend_name
        if backend == "ffplay" and self._bgm_process:
            try:
                self._bgm_process.terminate()
                self._bgm_process.wait(timeout=2)
            except Exception:
                try:
                    self._bgm_process.kill()
                except Exception:
                    pass
            self._bgm_process = None
        elif backend == "winsound":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

    def play_sfx(self, path: str) -> None:
        if not self.sfx_enabled or self.volume == 0:
            return
        resolved = self._resolve_path(path)
        if not os.path.exists(resolved):
            return
        thread = threading.Thread(
            target=self._sfx_play_and_restore_bgm,
            args=(resolved,), daemon=True)
        thread.start()

    def _sfx_play_and_restore_bgm(self, sfx_path: str) -> None:
        was_playing = self._bgm_playing
        prev_bgm = self._bgm_path
        if was_playing:
            self.stop_bgm()
            time.sleep(0.05)
        backend = self.backend_name
        if backend == "ffplay":
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            try:
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit",
                     "-volume", str(self.volume), sfx_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    startupinfo=startupinfo, timeout=60,
                )
            except Exception:
                pass
        elif backend == "winsound":
            import winsound
            try:
                winsound.PlaySound(sfx_path, winsound.SND_FILENAME)
            except Exception:
                pass
        if was_playing and prev_bgm:
            self.play_bgm(prev_bgm)

    def shutdown(self) -> None:
        self.stop_bgm()


# ============================================================================
# 视觉小说游戏主引擎
# ============================================================================

class VNGame:
    """视觉小说游戏主引擎类。

    负责：剧本加载、场景切换、对话显示、立绘管理、
    选项分支、存档读档、文本历史和设置面板。
    """

    def __init__(self, root: tk.Tk) -> None:
        """初始化游戏引擎，构建 UI 并绑定事件。

        Args:
            root: tkinter 根窗口对象。
        """
        self.root = root
        self.root.title("视觉小说框架 — 星之回响")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.configure(bg=COLOR_BG_DARK)

        # ── 游戏数据 ──────────────────────────────────────────
        self.script: Optional[dict] = None          # 原始剧本数据
        self.scenes_dict: dict[str, dict] = {}      # 场景字典 id → scene_data
        self.current_scene_id: Optional[str] = None # 当前场景 ID
        self.dialogue_index: int = 0                # 当前对话索引
        self.history: list[tuple[str, str]] = []    # 文本历史 [(speaker, text), ...]

        # ── 运行状态 ──────────────────────────────────────────
        self._typing: bool = False          # 打字机动画进行中
        self._skip_type: bool = False       # 请求跳过打字效果
        self._choosing: bool = False        # 选项显示中
        self._typewriter_timer: Optional[str] = None  # after() 任务 ID
        self._current_full_text: str = ""   # 当前正在显示的完整文本
        self._game_ended: bool = False      # 游戏是否已结束
        self._title_showing: bool = False   # 是否在标题画面

        # ── 设置 ──────────────────────────────────────────────
        self.text_speed: int = DEFAULT_TEXT_SPEED

        # ── 音频引擎 ──────────────────────────────────────────
        self.audio = AudioEngine()

        # ── UI 组件引用（在 _build_ui 中初始化） ───────────────
        self.canvas: Optional[tk.Canvas] = None
        self.bg_overlay: Optional[int] = None          # 背景过渡遮罩 Canvas ID
        self.bg_rect_id: Optional[int] = None           # 背景矩形 Canvas ID
        self.bg_label_id: Optional[int] = None          # 背景文字 Canvas ID
        self.char_left_items: list[int] = []            # 左侧立绘 Canvas ID 列表
        self.char_right_items: list[int] = []           # 右侧立绘 Canvas ID 列表
        self.dialogue_frame: Optional[tk.Frame] = None
        self.speaker_label: Optional[tk.Label] = None
        self.text_label: Optional[tk.Label] = None
        self.next_indicator: Optional[tk.Label] = None
        self.choice_frame: Optional[tk.Frame] = None
        self.choice_buttons: list[tk.Button] = []

        # ── 构建 ──────────────────────────────────────────────
        self._build_ui()
        self._bind_events()

    # ========================================================================
    #  UI 构建
    # ========================================================================

    def _build_ui(self) -> None:
        """构建游戏主界面：顶部工具栏 + Canvas 显示区 + 底部对话 Frame。"""
        # ── 主布局 ──
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

        # ── Canvas 主显示区 ────────────────────────────────
        canvas_container = tk.Frame(self.root, bg=COLOR_BG_DARK)
        canvas_container.grid(row=1, column=0, sticky="nsew")
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            canvas_container,
            bg=COLOR_BG_DARK,
            highlightthickness=0,
            cursor="hand2"
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # ── 底部对话 Frame ─────────────────────────────────
        self.dialogue_frame = tk.Frame(
            self.root,
            bg=COLOR_DIALOGUE_BG,
            relief="raised",
            bd=2,
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
            self.dialogue_frame,
            text="",
            font=FONT_SPEAKER,
            fg=COLOR_TEXT_SPEAKER,
            bg=COLOR_DIALOGUE_BG,
            anchor="w",
            padx=24,
        )
        self.speaker_label.grid(row=0, column=0, sticky="ew", pady=(12, 0))

        # 对话文本标签
        self.text_label = tk.Label(
            self.dialogue_frame,
            text="",
            font=FONT_DIALOGUE,
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_DIALOGUE_BG,
            anchor="nw",
            justify="left",
            wraplength=WINDOW_WIDTH - 80,
            padx=24,
        )
        self.text_label.grid(row=1, column=0, sticky="nw", pady=(6, 12))

        # 下一句指示器（▼）
        self.next_indicator = tk.Label(
            self.dialogue_frame,
            text="",
            font=("微软雅黑", 18),
            fg=COLOR_TEXT_SPEAKER,
            bg=COLOR_DIALOGUE_BG,
        )
        self.next_indicator.grid(row=1, column=1, sticky="se", padx=(0, 28), pady=(0, 18))

        # 键盘快捷键提示
        self.hint_label = tk.Label(
            self.dialogue_frame,
            text="空格/点击推进 · S存档 · L读档 · H历史 · Esc设置",
            font=("微软雅黑", 9), fg="#7f8c8d",
            bg=COLOR_DIALOGUE_BG, anchor="e", padx=24,
        )
        self.hint_label.grid(row=2, column=0, columnspan=2,
                             sticky="ew", pady=(0, 4))

    # ========================================================================
    #  事件绑定
    # ========================================================================

    def _bind_events(self) -> None:
        """绑定键盘和鼠标事件到对应的处理方法。"""
        # 窗口关闭时停止音频
        self.root.protocol("WM_DELETE_WINDOW", self._on_game_close)

        # 键盘推进
        self.root.bind("<space>", self._on_advance)
        self.root.bind("<Return>", self._on_advance)
        # 存档/读档
        self.root.bind("<s>", lambda e: self.save_game())
        self.root.bind("<S>", lambda e: self.save_game())
        self.root.bind("<l>", lambda e: self.load_game())
        self.root.bind("<L>", lambda e: self.load_game())
        # 文本历史
        self.root.bind("<h>", lambda e: self.show_history())
        self.root.bind("<H>", lambda e: self.show_history())
        # 设置面板
        self.root.bind("<Escape>", lambda e: self._open_settings())
        # 鼠标点击 Canvas 推进对话
        self.canvas.bind("<Button-1>", self._on_advance)
        # 窗口尺寸变化
        self.root.bind("<Configure>", self._on_resize)

    def _on_resize(self, event: tk.Event) -> None:
        """窗口尺寸变化时更新对话文本换行宽度。

        Args:
            event: <Configure> 事件对象。
        """
        if self.text_label and event.widget == self.root:
            new_wrap = max(event.width - 80, 200)
            self.text_label.config(wraplength=new_wrap)

    # ========================================================================
    #  剧本加载
    # ========================================================================

    def load_script(self, source: Union[str, dict]) -> None:
        """加载并解析剧本数据。

        Args:
            source: JSON 文件路径（str）或直接传入的剧本字典。

        Raises:
            SystemExit: 剧本格式错误或文件无法读取时退出程序。
        """
        try:
            if isinstance(source, str):
                with open(source, "r", encoding="utf-8") as f:
                    self.script = json.load(f)
            elif isinstance(source, dict):
                self.script = source
            else:
                raise TypeError("source 必须是文件路径(str)或剧本字典(dict)")

            # 验证必须字段
            if "scenes" not in self.script or not isinstance(self.script["scenes"], list):
                raise ValueError("剧本缺少 'scenes' 字段或格式错误")

            # 构建场景索引
            self.scenes_dict = {}
            for scene in self.script["scenes"]:
                if "id" not in scene:
                    raise ValueError("场景缺少 'id' 字段")
                if "dialogue" not in scene or not isinstance(scene["dialogue"], list):
                    raise ValueError(f"场景 '{scene['id']}' 缺少 'dialogue' 字段")
                self.scenes_dict[scene["id"]] = scene

            if not self.scenes_dict:
                raise ValueError("剧本中没有任何有效场景")

            self.root.title(self.script.get("title", "视觉小说框架"))
        except json.JSONDecodeError as e:
            print(f"剧本 JSON 解析错误: {e}")
            self._show_error_and_exit("剧本 JSON 格式错误，请检查文件。")
        except FileNotFoundError as e:
            print(f"剧本文件未找到: {e}")
            self._show_error_and_exit(f"找不到剧本文件: {source}")
        except (ValueError, TypeError) as e:
            print(f"剧本数据错误: {e}")
            self._show_error_and_exit(f"剧本数据错误: {e}")

    def _show_error_and_exit(self, message: str) -> None:
        """显示错误对话框并退出程序。

        Args:
            message: 错误信息文本。
        """
        error_win = tk.Toplevel(self.root)
        error_win.title("错误")
        error_win.geometry("400x150")
        error_win.transient(self.root)
        error_win.grab_set()

        tk.Label(
            error_win,
            text=message,
            font=FONT_UI,
            wraplength=360,
            padx=20,
            pady=20,
        ).pack(expand=True)

        tk.Button(
            error_win,
            text="确定",
            command=lambda: (error_win.destroy(), self.root.destroy()),
            font=FONT_UI,
        ).pack(pady=10)

    # ========================================================================
    #  游戏启动
    # ========================================================================

    def start_game(self) -> None:
        """显示标题画面，点击后开始游戏。"""
        self._title_showing = True
        self._clear_all()
        self.speaker_label.config(text="")
        self.text_label.config(text="")
        self.next_indicator.config(text="")

        # 标题背景（渐变色效果 — 用多个矩形近似）
        self.root.update()
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT
        self.canvas.delete("all")

        # 深色渐变背景
        for i in range(20):
            frac = i / 20
            r = int(10 + frac * 15)
            g = int(10 + frac * 10)
            b = int(26 + frac * 20)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.canvas.create_rectangle(
                0, int(h * frac), w, int(h * (frac + 0.05)),
                fill=color, outline=""
            )

        # 标题文字（从加载的剧本读取）
        title = (self.script.get("title", "") if self.script else "") or "视觉小说框架"
        spaced_title = "  ".join(title)
        self.canvas.create_text(
            w // 2, h * 0.35,
            text=spaced_title,
            font=FONT_TITLE,
            fill=COLOR_TEXT_ACCENT,
            anchor="center",
        )

        # 副标题
        self.canvas.create_text(
            w // 2, h * 0.48,
            text=f"— {title} —",
            font=("微软雅黑", 16),
            fill=COLOR_TEXT_PRIMARY,
            anchor="center",
        )

        # 闪烁的"点击开始"
        self._start_label = self.canvas.create_text(
            w // 2, h * 0.65,
            text="— 点击任意处开始 —",
            font=("微软雅黑", 16),
            fill=COLOR_TEXT_SPEAKER,
            anchor="center",
        )

        # 闪烁动画
        self._blink_title()

    def _blink_title(self) -> None:
        """让标题画面的'点击开始'文字闪烁。"""
        if not self._title_showing:
            return
        if hasattr(self, '_start_label') and self._start_label:
            current = self.canvas.itemcget(self._start_label, "fill")
            new_color = COLOR_TEXT_ACCENT if current == COLOR_TEXT_SPEAKER else COLOR_TEXT_SPEAKER
            self.canvas.itemconfig(self._start_label, fill=new_color)
            self.root.after(600, self._blink_title)

    def _on_title_click(self, event: tk.Event = None) -> None:
        """标题画面点击后开始游戏。

        Args:
            event: 事件对象（可省略）。
        """
        if self._title_showing:
            self._title_showing = False
            # 重新绑定 Canvas 点击到正常的推进逻辑
            self.canvas.bind("<Button-1>", self._on_advance)
            self._enter_scene("start")

    # ========================================================================
    #  场景管理
    # ========================================================================

    def _enter_scene(self, scene_id: str) -> None:
        """进入指定场景：设置背景、立绘并显示第一句对白。

        Args:
            scene_id: 目标场景 ID。
        """
        # 取消正在进行的打字效果
        self._cancel_typewriter()
        self._cleanup_choice_frame()
        self.dialogue_index = 0
        self.current_scene_id = scene_id
        self._choosing = False
        self._game_ended = False

        scene = self.scenes_dict.get(scene_id)
        if scene is None:
            print(f"错误：场景 '{scene_id}' 不存在")
            self._show_error_and_exit(f"场景 '{scene_id}' 不存在，剧本可能损坏。")
            return

        # 切换 BGM
        if "bgm" in scene:
            bgm_path = scene.get("bgm")
            if bgm_path:
                self.audio.play_bgm(bgm_path)
            else:
                self.audio.stop_bgm()

        # 切换背景
        bg_id = scene.get("background", "")
        self._transition_background(bg_id, on_complete=lambda: (
            self._update_characters(scene.get("characters", {})),
            self._show_current_dialogue()
        ))

    def _show_current_dialogue(self) -> None:
        """根据当前对话索引显示对白或选项。"""
        scene = self.scenes_dict.get(self.current_scene_id)
        if scene is None:
            return

        dialogues = scene.get("dialogue", [])
        choices = scene.get("choices", None)

        if self.dialogue_index < len(dialogues):
            # 正常显示对白
            entry = dialogues[self.dialogue_index]
            speaker = entry.get("speaker", "")
            text = entry.get("text", "")

            # 检查本句是否有立绘变化
            if "character_left" in entry or "character_right" in entry:
                char_data = {}
                if "character_left" in entry:
                    char_data["left"] = entry["character_left"]
                if "character_right" in entry:
                    char_data["right"] = entry["character_right"]
                self._update_characters(char_data)

            # 播放本句音效
            sfx_path = entry.get("sfx")
            if sfx_path:
                self.audio.play_sfx(sfx_path)

            self.show_dialogue(text, speaker)
        elif choices:
            # 所有对白显示完毕，展示选项
            self.show_choices(choices)
        else:
            # 没有更多内容也没有选项 → 结束
            self._end_of_scene()

    def _end_of_scene(self) -> None:
        """场景结束时的处理。"""
        self._game_ended = True
        self.speaker_label.config(text="")
        self.text_label.config(text="—— END ——")
        self.next_indicator.config(text="")
        self.canvas.bind("<Button-1>", self._on_restart)

    def _on_restart(self, event: tk.Event = None) -> None:
        """点击重新开始游戏。

        Args:
            event: 事件对象（可省略）。
        """
        self.canvas.bind("<Button-1>", self._on_advance)
        self.start_game()
        # 再点击进入第一个场景
        self.canvas.bind("<Button-1>", self._on_title_click)

    # ========================================================================
    #  背景系统
    # ========================================================================

    def _get_placeholder_bg(self, bg_id: str) -> tuple:
        """获取占位背景的颜色和显示名称。

        Args:
            bg_id: 背景标识符。

        Returns:
            (颜色十六进制, 显示名称) 的元组。
        """
        return PLACEHOLDER_BG_COLORS.get(bg_id, ("#34495e", "未知场景"))

    def _render_placeholder_background(self, bg_id: str) -> None:
        """在 Canvas 上绘制占位背景（纯色矩形 + 文字标签）。

        Args:
            bg_id: 背景标识符。
        """
        self.canvas.delete("bg")  # 删除带 "bg" tag 的所有项
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT

        bg_color, bg_name = self._get_placeholder_bg(bg_id)

        # 主背景色
        self.bg_rect_id = self.canvas.create_rectangle(
            0, 0, w, h, fill=bg_color, outline="", tags="bg"
        )

        # 装饰：几个半透明圆点营造氛围
        random.seed(bg_id)
        for _ in range(30):
            x = random.randint(0, w)
            y = random.randint(0, h)
            r = random.randint(2, 6)
            alpha = random.choice(["gray12", "gray25", "gray50"])
            self.canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill=COLOR_TEXT_ACCENT, stipple=alpha, outline="", tags="bg"
            )

        # 场景名称标签
        self.bg_label_id = self.canvas.create_text(
            60, 30,
            text=bg_name,
            font=("微软雅黑", 14),
            fill=COLOR_TEXT_PRIMARY,
            anchor="w",
            tags="bg",
        )

        # 装饰线条
        self.canvas.create_line(
            60, 42, 220, 42,
            fill=COLOR_TEXT_ACCENT, width=2, tags="bg"
        )

    def _transition_background(self, new_bg_id: str, on_complete=None) -> None:
        """执行背景切换（白色淡入淡出过渡）。

        Args:
            new_bg_id: 新背景标识符。
            on_complete: 过渡完成后的回调函数。
        """
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT

        # 动画步进序列
        fade_in_steps = [
            ("gray12", 0),
            ("gray25", 0),
            ("gray50", 0),
            ("gray75", 0),
            ("", 255),  # 完全白
        ]

        # 步骤1: 旧背景上叠加白色遮罩（由浅到深）
        self.bg_overlay = self.canvas.create_rectangle(
            0, 0, w, h,
            fill=COLOR_OVERLAY,
            stipple="gray12",   # 初始几乎透明
            outline="",
            tags="overlay"
        )

        def _step_fade_in(idx=0):
            """逐步加深白色遮罩。"""
            if idx < len(fade_in_steps):
                stipple, _ = fade_in_steps[idx]
                if idx == 0:
                    pass  # 已经是 gray12
                else:
                    self.canvas.itemconfig(self.bg_overlay, stipple=stipple)
                self.root.after(BG_FADE_INTERVAL, _step_fade_in, idx + 1)
            else:
                # 白色完全覆盖 → 切换背景
                self._render_placeholder_background(new_bg_id)

                # 步骤2: 白色遮罩渐褪（由深到浅）
                fade_out_steps = ["gray75", "gray50", "gray25", "gray12"]

                def _step_fade_out(idx2=0):
                    if idx2 < len(fade_out_steps):
                        self.canvas.itemconfig(self.bg_overlay, stipple=fade_out_steps[idx2])
                        self.canvas.tag_raise("overlay")
                        self.root.after(BG_FADE_INTERVAL, _step_fade_out, idx2 + 1)
                    else:
                        # 移除遮罩
                        self.canvas.delete(self.bg_overlay)
                        self.bg_overlay = None
                        if on_complete:
                            on_complete()

                _step_fade_out(0)

        _step_fade_in(0)

    # ========================================================================
    #  立绘系统
    # ========================================================================

    def _get_placeholder_char(self, char_id: str) -> tuple:
        """获取占位立绘的颜色和名称。

        Args:
            char_id: 角色标识符。

        Returns:
            (颜色十六进制, 角色名) 的元组；若未找到返回默认值。
        """
        return PLACEHOLDER_COLORS.get(char_id, ("#7f8c8d", "未知"))

    def _draw_character_sprite(self, char_id: str, x_center: int,
                               y_bottom: int) -> list[int]:
        """在 Canvas 上绘制一个占位角色立绘（由基本几何图形组成的人形）。

        Args:
            char_id: 角色标识符。
            x_center: 角色中心 x 坐标。
            y_bottom: 角色底部 y 坐标。

        Returns:
            绘制的 Canvas 对象 ID 列表。
        """
        color, char_name = self._get_placeholder_char(char_id)
        items = []

        # 参数
        head_r = 35
        body_w = 100
        body_top = y_bottom - CHAR_HEIGHT + head_r * 2 + 30
        head_center_y = body_top - 10

        # --- 身体（多边形 -- 梯形轮廓）---
        shoulder_w = body_w * 0.9
        hip_w = body_w * 0.65
        body_shape = [
            x_center - shoulder_w / 2, body_top,
            x_center + shoulder_w / 2, body_top,
            x_center + hip_w / 2, y_bottom - 30,
            x_center - hip_w / 2, y_bottom - 30,
        ]
        body_id = self.canvas.create_polygon(
            body_shape, fill=color, outline="", stipple="",
            tags=f"char_{x_center}"
        )
        items.append(body_id)

        # --- 头部（椭圆）---
        head_id = self.canvas.create_oval(
            x_center - head_r, head_center_y - head_r,
            x_center + head_r, head_center_y + head_r,
            fill=color, outline="", tags=f"char_{x_center}"
        )
        items.append(head_id)

        # --- 高光装饰（头部的亮斑）---
        highlight = self.canvas.create_oval(
            x_center - head_r * 0.4, head_center_y - head_r * 0.6,
            x_center + head_r * 0.1, head_center_y - head_r * 0.1,
            fill=COLOR_TEXT_PRIMARY, stipple="gray12", outline="",
            tags=f"char_{x_center}"
        )
        items.append(highlight)

        # --- 名字标签 ---
        name_id = self.canvas.create_text(
            x_center, y_bottom - 8,
            text=char_name,
            font=("微软雅黑", 13, "bold"),
            fill=COLOR_TEXT_PRIMARY,
            anchor="s",
            tags=f"char_{x_center}"
        )
        items.append(name_id)

        return items

    def _clear_characters(self) -> None:
        """清除 Canvas 上所有立绘。"""
        self.canvas.delete("left_char")
        self.canvas.delete("right_char")
        self.char_left_items = []
        self.char_right_items = []

    def _update_characters(self, char_data: dict) -> None:
        """更新左右两侧的立绘，带淡入淡出过渡。

        Args:
            char_data: 格式 {"left": char_id, "right": char_id}。
                       值为 None 或省略表示清除该侧。
        """
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT
        y_bottom = h - 20

        left_id = char_data.get("left", None)
        right_id = char_data.get("right", None)

        # 更新左侧立绘
        self._fade_out_and_replace(
            "left", left_id,
            int(w * 0.22), y_bottom
        )

        # 更新右侧立绘
        self._fade_out_and_replace(
            "right", right_id,
            int(w * 0.78), y_bottom
        )

    def _fade_out_and_replace(self, side: str, new_char_id: Optional[str],
                               x_center: int, y_bottom: int) -> None:
        """执行一侧立绘的淡出→替换→淡入动画。

        Args:
            side: "left" 或 "right"。
            new_char_id: 新角色标识符，None 表示清除。
            x_center: 角色中心 x 坐标。
            y_bottom: 角色底部 y 坐标。
        """
        tag = "left_char" if side == "left" else "right_char"
        old_items = self.char_left_items if side == "left" else self.char_right_items

        fade_steps = ["", "gray75", "gray50", "gray25", "gray12"]

        def _fade_out(idx=0):
            """逐步淡出旧立绘。"""
            if idx < len(fade_steps) and old_items:
                stipple = fade_steps[idx]
                for item_id in old_items:
                    try:
                        self.canvas.itemconfig(item_id, stipple=stipple)
                    except tk.TclError:
                        pass
                self.root.after(CHAR_FADE_INTERVAL, _fade_out, idx + 1)
            else:
                # 删除旧立绘
                self.canvas.delete(tag)
                old_items.clear()

                # 如果有新角色，绘制并淡入
                if new_char_id:
                    new_items = self._draw_character_sprite(new_char_id, x_center, y_bottom)
                    for item_id in new_items:
                        self.canvas.itemconfig(item_id, stipple="gray12")
                        self.canvas.addtag(tag, "withtag", item_id)

                    if side == "left":
                        self.char_left_items = new_items
                    else:
                        self.char_right_items = new_items

                    _fade_in(0, new_items)
                else:
                    if side == "left":
                        self.char_left_items = []
                    else:
                        self.char_right_items = []

        def _fade_in(idx=0, items=None):
            """逐步淡入新立绘。"""
            if items is None:
                return
            fade_in_steps = ["gray12", "gray25", "gray50", "gray75", ""]
            if idx < len(fade_in_steps):
                stipple = fade_in_steps[idx]
                for item_id in items:
                    try:
                        self.canvas.itemconfig(item_id, stipple=stipple)
                    except tk.TclError:
                        pass
                self.root.after(CHAR_FADE_INTERVAL, _fade_in, idx + 1, items)

        _fade_out(0)

    # ========================================================================
    #  对话系统（打字机效果）
    # ========================================================================

    def show_dialogue(self, text: str, speaker: str = "") -> None:
        """显示对白并启动打字机效果。

        Args:
            text: 对白文本。
            speaker: 说话角色名。
        """
        self._cancel_typewriter()
        self.next_indicator.config(text="")
        self._current_full_text = text
        self._typing = True
        self._skip_type = False

        # 更新说话人
        self.speaker_label.config(text=speaker if speaker else "")

        # 开始打字机效果
        self.text_label.config(text="")
        self._typewriter_step(0)

    def _typewriter_step(self, index: int) -> None:
        """打字机动画的每一步：追加一个字符。

        Args:
            index: 当前已显示的字符数（下一个要显示的字符索引）。
        """
        if not self._typing:
            return

        if self._skip_type:
            # 跳过打字 → 直接显示完整文本
            self._finish_typewriter()
            return

        full_text = self._current_full_text
        if index < len(full_text):
            displayed = full_text[:index + 1]
            self.text_label.config(text=displayed)
            self._typewriter_timer = self.root.after(
                self.text_speed, self._typewriter_step, index + 1
            )
        else:
            # 打字完成
            self._finish_typewriter()

    def _finish_typewriter(self) -> None:
        """完成打字机效果：显示完整文本、显示下一条指示器。"""
        self._typing = False
        self._skip_type = False
        self.text_label.config(text=self._current_full_text)

        # 记录到历史
        speaker = self.speaker_label.cget("text")
        self.history.append((speaker, self._current_full_text))
        if len(self.history) > 100:
            self.history = self.history[-100:]

        # 显示 ▼ 指示器
        self.next_indicator.config(text="▼")

    def _cancel_typewriter(self) -> None:
        """取消正在进行的打字机动画。"""
        if self._typewriter_timer:
            try:
                self.root.after_cancel(self._typewriter_timer)
            except ValueError:
                pass
            self._typewriter_timer = None
        self._typing = False
        self._skip_type = False

    def _next_dialogue(self) -> None:
        """推进到下一句对话，如果当前场景结束则显示选项或结束。"""
        if self._choosing or self._title_showing or self._game_ended:
            return

        scene = self.scenes_dict.get(self.current_scene_id)
        if scene is None:
            return

        self.dialogue_index += 1
        self._show_current_dialogue()

    # ========================================================================
    #  推进对话的事件处理
    # ========================================================================

    def _on_game_close(self) -> None:
        """窗口关闭：停止音频后销毁窗口。"""
        self.audio.shutdown()
        self.root.destroy()

    def _on_advance(self, event: tk.Event = None) -> None:
        """处理推进对话的输入（Space / 鼠标点击）。

        在打字中 → 跳过打字；
        打字完成 → 下一条对话；
        标题画面 → 开始游戏。

        Args:
            event: 事件对象（可省略）。
        """
        if self._title_showing:
            self._on_title_click(event)
            return

        if self._game_ended:
            return

        if self._choosing:
            return

        if self._typing:
            self._skip_type = True
        else:
            self._next_dialogue()

    # ========================================================================
    #  选项分支
    # ========================================================================

    def show_choices(self, choices: list[dict]) -> None:
        """在 Canvas 中央显示选项按钮。

        Args:
            choices: 选项列表，格式 [{"text": "...", "next_scene": "..."}, ...]。
        """
        self._choosing = True
        self._cleanup_choice_frame()
        self.next_indicator.config(text="")

        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT

        # 选项背景遮罩（半透明效果）
        self.choice_overlay = self.canvas.create_rectangle(
            0, 0, w, h,
            fill="#000000",
            stipple="gray50",
            outline="",
            tags="choice_ui"
        )

        # 选项容器 Frame
        self.choice_frame = tk.Frame(
            self.canvas,
            bg=COLOR_CHOICE_BG,
            relief="solid",
            bd=2,
            highlightbackground=COLOR_CHOICE_BORDER,
            highlightthickness=2,
        )

        # 标题
        title_label = tk.Label(
            self.choice_frame,
            text="— 做出你的选择 —",
            font=("微软雅黑", 14, "bold"),
            fg=COLOR_TEXT_ACCENT,
            bg=COLOR_CHOICE_BG,
            pady=12,
        )
        title_label.pack(fill="x")

        # 选项按钮
        self.choice_buttons = []
        for choice in choices:
            text = choice.get("text", "继续")
            next_scene = choice.get("next_scene", "")

            btn = tk.Button(
                self.choice_frame,
                text=text,
                font=FONT_BUTTON,
                fg=COLOR_CHOICE_TEXT,
                bg=COLOR_CHOICE_BG,
                activeforeground=COLOR_TEXT_ACCENT,
                activebackground=COLOR_CHOICE_HOVER,
                relief="solid",
                bd=1,
                highlightbackground=COLOR_CHOICE_BORDER,
                highlightthickness=1,
                padx=40,
                pady=10,
                cursor="hand2",
                command=lambda ns=next_scene: self._on_choice_selected(ns),
            )
            btn.pack(fill="x", padx=20, pady=6)
            self.choice_buttons.append(btn)

        # 将 Frame 放到 Canvas 中央
        self.canvas.update_idletasks()
        self.choice_frame.update_idletasks()
        fw = self.choice_frame.winfo_reqwidth()
        fh = self.choice_frame.winfo_reqheight()

        self.canvas_window_id = self.canvas.create_window(
            w // 2, int(h * 0.45),
            window=self.choice_frame,
            anchor="center",
            width=min(fw + 40, 500),
            tags="choice_ui",
        )

    def _on_choice_selected(self, next_scene: str) -> None:
        """处理玩家选择选项后的跳转。

        Args:
            next_scene: 要跳转到的目标场景 ID。
        """
        self._cleanup_choice_frame()
        self._choosing = False
        self._enter_scene(next_scene)

    def _cleanup_choice_frame(self) -> None:
        """清理选项相关的 UI 组件。"""
        self.canvas.delete("choice_ui")
        if self.choice_frame:
            self.choice_frame.destroy()
            self.choice_frame = None
        self.choice_buttons = []

    # ========================================================================
    #  存档 / 读档
    # ========================================================================

    def save_game(self, slot: int = 0) -> None:
        """保存当前游戏进度到存档文件。

        Args:
            slot: 存档槽编号（默认 0）。
        """
        if self._title_showing:
            self._show_notification("标题画面无法存档")
            return
        if self.current_scene_id is None:
            return

        # 确保存档目录存在
        SAVE_DIR.mkdir(exist_ok=True)

        save_data = {
            "scene_id": self.current_scene_id,
            "dialogue_index": self.dialogue_index,
            "text_speed": self.text_speed,
            "volume": self.audio.get_volume(),
            "history": self.history[-50:],  # 保存最近 50 条
        }

        save_path = SAVE_DIR / SAVE_FILE_TEMPLATE.format(slot)
        try:
            with open(save_path, "wb") as f:
                pickle.dump(save_data, f)
            self._show_notification("存档成功 ✓", color=COLOR_BUTTON_SAVE)
        except (OSError, pickle.PicklingError) as e:
            self._show_notification(f"存档失败: {e}", color="#e74c3c")

    def load_game(self, slot: int = 0) -> None:
        """从存档文件读取并恢复游戏进度。

        Args:
            slot: 存档槽编号（默认 0）。
        """
        save_path = SAVE_DIR / SAVE_FILE_TEMPLATE.format(slot)

        if not save_path.exists():
            self._show_notification("未找到存档文件", color="#e74c3c")
            return

        try:
            with open(save_path, "rb") as f:
                save_data = pickle.load(f)

            # 恢复状态
            scene_id = save_data.get("scene_id", "")
            if scene_id not in self.scenes_dict:
                self._show_notification("存档数据无效：场景不存在", color="#e74c3c")
                return

            # 清理当前状态
            self._cancel_typewriter()
            self._cleanup_choice_frame()
            self._title_showing = False

            # 恢复数据
            self.current_scene_id = scene_id
            self.dialogue_index = save_data.get("dialogue_index", 0)
            self.text_speed = save_data.get("text_speed", DEFAULT_TEXT_SPEED)
            saved_volume = save_data.get("volume", DEFAULT_VOLUME)
            self.audio.set_volume(saved_volume)
            saved_history = save_data.get("history", [])
            self.history = list(saved_history)

            self._choosing = False
            self._game_ended = False

            # 刷新场景
            scene = self.scenes_dict[scene_id]

            def _after_bg():
                self._update_characters(scene.get("characters", {}))
                # 检查对话索引是否有效
                dialogues = scene.get("dialogue", [])
                if self.dialogue_index < len(dialogues):
                    entry = dialogues[self.dialogue_index]
                    self.show_dialogue(entry.get("text", ""), entry.get("speaker", ""))
                else:
                    choices = scene.get("choices", None)
                    if choices:
                        self.show_choices(choices)
                    else:
                        self._end_of_scene()

            self._transition_background(scene.get("background", ""), on_complete=_after_bg)
            self._show_notification("读档成功 ✓", color=COLOR_BUTTON_LOAD)

        except (OSError, pickle.UnpicklingError, KeyError) as e:
            self._show_notification(f"读档失败: {e}", color="#e74c3c")

    def _show_notification(self, message: str, color: str = "#f1c40f",
                           duration: int = 1500) -> None:
        """在 Canvas 上显示短暂的通知消息。

        Args:
            message: 通知文本。
            color: 文字颜色。
            duration: 显示持续时间（毫秒）。
        """
        w = self.canvas.winfo_width() or WINDOW_WIDTH
        h = self.canvas.winfo_height() or WINDOW_HEIGHT

        notif_id = self.canvas.create_text(
            w // 2, h // 2,
            text=message,
            font=("微软雅黑", 28, "bold"),
            fill=color,
            anchor="center",
            tags="notification",
        )

        self.root.after(duration, lambda: self.canvas.delete("notification"))

    # ========================================================================
    #  文本历史
    # ========================================================================

    def show_history(self) -> None:
        """在弹窗中显示最近 10 条对白历史。"""
        history_win = tk.Toplevel(self.root)
        history_win.title("文本历史")
        history_win.geometry("600x400")
        history_win.transient(self.root)
        history_win.configure(bg=COLOR_BG_DARK)

        # 标题
        tk.Label(
            history_win,
            text="— 对白历史 —",
            font=("微软雅黑", 16, "bold"),
            fg=COLOR_TEXT_ACCENT,
            bg=COLOR_BG_DARK,
            pady=12,
        ).pack(fill="x")

        # 历史内容列表
        frame = tk.Frame(history_win, bg=COLOR_BG_DARK)
        frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        canvas = tk.Canvas(frame, bg=COLOR_BG_DARK, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLOR_BG_DARK)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 显示最近的历史（取最近 10 条，反转以显示最新的在底部）
        recent = self.history[-10:] if len(self.history) >= 10 else self.history
        if not recent:
            tk.Label(
                scrollable_frame,
                text="暂无对白记录",
                font=FONT_UI,
                fg=COLOR_TEXT_PRIMARY,
                bg=COLOR_BG_DARK,
                pady=20,
            ).pack()
        else:
            for speaker, text in recent:
                entry_frame = tk.Frame(
                    scrollable_frame,
                    bg=COLOR_DIALOGUE_BG,
                    relief="solid",
                    bd=1,
                )
                entry_frame.pack(fill="x", pady=4, padx=4)

                spk = speaker if speaker else "（旁白）"
                tk.Label(
                    entry_frame,
                    text=spk,
                    font=("微软雅黑", 12, "bold"),
                    fg=COLOR_TEXT_SPEAKER,
                    bg=COLOR_DIALOGUE_BG,
                    anchor="w",
                    padx=12,
                ).pack(fill="x", pady=(8, 2))

                tk.Label(
                    entry_frame,
                    text=text,
                    font=("微软雅黑", 11),
                    fg=COLOR_TEXT_PRIMARY,
                    bg=COLOR_DIALOGUE_BG,
                    anchor="w",
                    wraplength=500,
                    justify="left",
                    padx=12,
                ).pack(fill="x", pady=(0, 8))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 关闭按钮
        tk.Button(
            history_win,
            text="关闭",
            font=FONT_UI,
            command=history_win.destroy,
            bg=COLOR_DIALOGUE_BG,
            fg=COLOR_TEXT_PRIMARY,
            relief="solid",
            bd=1,
            padx=20,
        ).pack(pady=(0, 12))

    # ========================================================================
    #  设置面板
    # ========================================================================

    def _open_settings(self) -> None:
        """打开设置面板（Esc 键触发）。"""
        settings_win = tk.Toplevel(self.root)
        settings_win.title("设置")
        settings_win.geometry("500x400")
        settings_win.transient(self.root)
        settings_win.grab_set()
        settings_win.configure(bg=COLOR_BG_DARK)

        # 标题
        tk.Label(
            settings_win,
            text="— 设 置 —",
            font=("微软雅黑", 18, "bold"),
            fg=COLOR_TEXT_ACCENT,
            bg=COLOR_BG_DARK,
            pady=20,
        ).pack(fill="x")

        # ── 文字速度调节 ──
        speed_frame = tk.Frame(settings_win, bg=COLOR_BG_DARK)
        speed_frame.pack(fill="x", padx=40, pady=20)

        tk.Label(
            speed_frame,
            text="文字速度",
            font=("微软雅黑", 14),
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG_DARK,
            anchor="w",
        ).pack(fill="x")

        speed_value_label = tk.Label(
            speed_frame,
            text=f"{self.text_speed} ms/字",
            font=("微软雅黑", 12),
            fg=COLOR_TEXT_SPEAKER,
            bg=COLOR_BG_DARK,
            anchor="w",
        )
        speed_value_label.pack(fill="x", pady=(4, 0))

        speed_scale = tk.Scale(
            speed_frame,
            from_=10, to=200,
            orient="horizontal",
            length=400,
            resolution=5,
            showvalue=False,
            bg=COLOR_DIALOGUE_BG,
            fg=COLOR_TEXT_PRIMARY,
            highlightbackground=COLOR_BG_DARK,
            troughcolor="#2c3e50",
            cursor="hand2",
        )
        speed_scale.set(self.text_speed)
        speed_scale.pack(pady=(8, 0))

        def _update_speed(val):
            """更新文字速度并显示当前值。"""
            speed = int(val)
            self.text_speed = speed
            speed_value_label.config(text=f"{speed} ms/字")

        speed_scale.config(command=_update_speed)

        # 速度预设按钮
        preset_frame = tk.Frame(settings_win, bg=COLOR_BG_DARK)
        preset_frame.pack(pady=(0, 10))

        for label, val in [("快速", 20), ("普通", 40), ("慢速", 80), ("很慢", 150)]:
            btn = tk.Button(
                preset_frame,
                text=label,
                font=("微软雅黑", 11),
                bg=COLOR_CHOICE_BG,
                fg=COLOR_TEXT_PRIMARY,
                activebackground=COLOR_CHOICE_HOVER,
                activeforeground=COLOR_TEXT_ACCENT,
                relief="solid",
                bd=1,
                padx=16,
                cursor="hand2",
                command=lambda v=val: (speed_scale.set(v), _update_speed(v)),
            )
            btn.pack(side="left", padx=6)

        # ── 音频静音开关 ──
        audio_frame = tk.Frame(settings_win, bg=COLOR_BG_DARK)
        audio_frame.pack(fill="x", padx=40, pady=10)
        tk.Label(audio_frame, text="音频",
                 font=("微软雅黑", 14), fg=COLOR_TEXT_PRIMARY,
                 bg=COLOR_BG_DARK, anchor="w").pack(fill="x")

        mute_state = tk.BooleanVar(value=self.audio.get_volume() == 0)
        mute_cb = tk.Checkbutton(
            audio_frame, text="静音", variable=mute_state,
            font=("微软雅黑", 12), fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG_DARK, selectcolor=COLOR_BG_DARK,
            activebackground=COLOR_BG_DARK,
            activeforeground=COLOR_TEXT_PRIMARY,
            cursor="hand2",
            command=lambda: self.audio.set_volume(0 if mute_state.get() else 100),
        )
        mute_cb.pack(anchor="w", pady=(4, 0))

        # ── 关闭按钮 ──
        tk.Button(
            settings_win,
            text="关闭",
            font=FONT_UI,
            command=settings_win.destroy,
            bg=COLOR_CHOICE_BORDER,
            fg=COLOR_TEXT_PRIMARY,
            relief="solid",
            bd=1,
            padx=30,
            pady=6,
            cursor="hand2",
        ).pack(pady=20)

    # ========================================================================
    #  全屏重置
    # ========================================================================

    def _clear_all(self) -> None:
        """清除 Canvas 上所有内容、取消打字机、清理选项、停止音乐。"""
        self.canvas.delete("all")
        self._cancel_typewriter()
        self._cleanup_choice_frame()
        self.char_left_items = []
        self.char_right_items = []
        self.bg_overlay = None
        self.bg_rect_id = None
        self.bg_label_id = None
        self.audio.stop_bgm()


# ============================================================================
#  程序入口
# ============================================================================

def main() -> None:
    """主函数：创建窗口、初始化引擎、加载演示剧本、启动游戏循环。"""
    root = tk.Tk()
    app = VNGame(root)

    # 加载内置演示剧本
    app.load_script(DEMO_SCRIPT)

    # 显示标题画面
    app.start_game()

    # 使标题点击生效（当 Canvas 尺寸已确定后绑定）
    app.canvas.after(100, lambda: app.canvas.bind("<Button-1>", app._on_title_click))

    # 进入主循环
    root.mainloop()


if __name__ == "__main__":
    main()
