"""
音频引擎模块
============
四通道音频引擎（BGM/SFX/Voice + Master），
支持多后端自动降级、BGM交叉淡入淡出、语音闪避。

后端优先级: ffplay > afplay (macOS) > aplay (Linux) > winsound (Windows) > none

用法:
    from gal_lib.audio import AudioEngine

    audio = AudioEngine()
    audio.play_bgm("path/to/bgm.mp3")
    audio.play_sfx("path/to/sfx.ogg")
    audio.play_voice("path/to/voice.wav")
    audio.volume_bgm = 80
"""

import atexit
import collections
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from .constants import (
    AUDIO_DIR,
    VOICE_DIR,
    DEFAULT_VOLUME,
    DEFAULT_VOLUME_BGM,
    DEFAULT_VOLUME_SFX,
    DEFAULT_VOLUME_VOICE,
    BGM_DUCK_RATIO,
)

# ========================================================================
#  后端检测
# ========================================================================

def _check_ffplay() -> bool:
    return shutil.which("ffplay") is not None


def _check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def _check_afplay() -> bool:
    return shutil.which("afplay") is not None


def _check_aplay() -> bool:
    return shutil.which("aplay") is not None


def _detect_backend() -> tuple[str, str]:
    """检测可用音频后端。

    Returns:
        (后端标识, 后端显示名称)
    """
    if _check_ffplay():
        return ("ffplay", "ffplay (FFmpeg)")
    if sys.platform == "darwin" and _check_afplay():
        return ("afplay", "afplay (macOS)")
    if sys.platform == "linux" and _check_aplay():
        return ("aplay", "aplay (Linux)")
    if sys.platform == "win32":
        try:
            import winsound  # noqa: F401
            return ("winsound", "winsound (Windows)")
        except ImportError:
            pass
    return ("none", "无可用音频后端")


_BACKEND, _BACKEND_NAME = _detect_backend()
_HAS_FFMPEG = _check_ffmpeg()

# 首次使用非 ffplay 后端时打印提示
_FALLBACK_HINT_SHOWN = False


def _print_fallback_hint() -> None:
    global _FALLBACK_HINT_SHOWN
    if not _FALLBACK_HINT_SHOWN:
        print(f"[音频] 使用后端: {_BACKEND_NAME}")
        if _BACKEND not in ("ffplay",):
            print("[音频] 提示: 安装 FFmpeg 可获得更好的音频兼容性")
            print("[音频]       https://ffmpeg.org/download.html")
        if _BACKEND in ("winsound", "aplay"):
            print("[音频] 提示: 当前后端不支持运行时调音量")
        _FALLBACK_HINT_SHOWN = True


_print_fallback_hint()


def _resolve_audio_path(path: str, search_dir: Optional[Path] = None) -> str:
    """解析音频文件路径，支持自动扩展名补全。

    Args:
        path: 文件路径或名称。
        search_dir: 搜索根目录，None 时使用 AUDIO_DIR。

    Returns:
        解析后的绝对路径字符串（文件不存在时仍返回原路径）。
    """
    search_dir = search_dir or AUDIO_DIR
    p = Path(path)
    if p.is_absolute():
        return str(p)
    # 检查 search_dir 下
    candidate = search_dir / p
    if candidate.exists():
        return str(candidate)
    # 尝试常见扩展名
    for ext in [".mp3", ".ogg", ".wav", ".flac", ".m4a", ".opus", ".wma"]:
        c2 = search_dir / f"{p}{ext}"
        if c2.exists():
            return str(c2)
    if not p.suffix:
        c2 = search_dir / f"{p}.wav"
        if c2.exists():
            return str(c2)
    return str(p)


def _get_startupinfo():
    """获取 Windows 子进程启动信息（隐藏窗口）。"""
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return si
    return None


# ========================================================================
#  跨平台音频播放
# ========================================================================

def _play_with_backend(path: str, volume: int = 100, loop: bool = False,
                       ss: Optional[float] = None) -> Optional[subprocess.Popen]:
    """使用当前后端播放音频文件。

    Args:
        path: 音频文件路径。
        volume: 音量 0-100。
        loop: 是否循环播放。
        ss: 起始时间（秒）。

    Returns:
        Popen 对象，或 None（同步播放/失败）。
    """
    if not os.path.exists(path):
        print(f"[音频] 文件不存在: {path}")
        return None

    si = _get_startupinfo()
    vol = max(0, min(100, volume))

    if _BACKEND == "ffplay":
        cmd = ["ffplay", "-nodisp", "-autoexit",
               "-volume", str(vol)]
        if loop:
            cmd.extend(["-loop", "0"])
        if ss is not None:
            cmd.extend(["-ss", str(ss)])
        cmd.append(path)
        try:
            return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, startupinfo=si)
        except Exception as e:
            print(f"[音频] ffplay 启动失败: {e}")
            return None

    elif _BACKEND == "afplay":
        # macOS afplay: -v volume (0.0-1.0), no loop support
        vol_float = max(0.0, min(1.0, vol / 100.0))
        cmd = ["afplay", "-v", str(vol_float)]
        if ss is not None:
            cmd.extend(["--time", str(ss)])
        cmd.append(path)
        try:
            return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, startupinfo=si)
        except Exception as e:
            print(f"[音频] afplay 启动失败: {e}")
            return None

    elif _BACKEND == "aplay":
        # Linux aplay: 不支持音量调节和循环
        cmd = ["aplay", "-q"]
        if ss is not None:
            # aplay 不支持 -ss，跳过
            pass
        cmd.append(path)
        try:
            return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, startupinfo=si)
        except Exception as e:
            print(f"[音频] aplay 启动失败: {e}")
            return None

    elif _BACKEND == "winsound":
        import winsound
        try:
            if loop:
                flags = winsound.SND_FILENAME | winsound.SND_LOOP | winsound.SND_ASYNC
            else:
                flags = winsound.SND_FILENAME | winsound.SND_ASYNC
            winsound.PlaySound(path, flags)
        except Exception as e:
            print(f"[音频] winsound 播放失败: {e}")
        # winsound 异步播放不返回进程对象
        return None

    return None


def _play_crossfade_pipe(old_path: str, new_path: str, volume: int,
                         fade_d: float = 2.0) -> Optional[subprocess.Popen]:
    """使用 ffmpeg acrossfade 生成交叉淡化音频并播放（无爆音）。

    仅当 ffmpeg + ffplay 均可用时生效。

    Args:
        old_path: 旧 BGM 路径。
        new_path: 新 BGM 路径。
        volume: 目标音量 0-100。
        fade_d: 淡入淡出时长（秒）。

    Returns:
        播放 crossfade 的 Popen 对象，失败返回 None。
    """
    if not _HAS_FFMPEG or _BACKEND != "ffplay":
        return None

    si = _get_startupinfo()
    vol = max(1, min(100, volume))

    cmd = [
        "ffmpeg", "-y",
        "-i", old_path,
        "-i", new_path,
        "-filter_complex",
        f"[0:a][1:a]acrossfade=d={fade_d}:c1=tri:c2=tri",
        "-f", "wav", "-",
    ]
    try:
        ffmpeg_proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            startupinfo=si,
        )
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"[音频] ffmpeg crossfade 失败: {e}")
        return None

    player_cmd = [
        "ffplay", "-nodisp", "-autoexit",
        "-volume", str(vol), "-",
    ]
    try:
        player = subprocess.Popen(
            player_cmd, stdin=ffmpeg_proc.stdout,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            startupinfo=si,
        )
    except Exception as e:
        ffmpeg_proc.kill()
        print(f"[音频] crossfade 播放失败: {e}")
        return None

    ffmpeg_proc.stdout.close()
    return player


# ========================================================================
#  音频引擎
# ========================================================================

class AudioEngine:
    """四通道音频引擎：Master / BGM / SFX / Voice。

    音量架构:
        - volume (Master): 0-100，全局总音量，缩放各通道
        - volume_bgm: 0-100，BGM 通道音量
        - volume_sfx: 0-100，SFX 通道音量
        - volume_voice: 0-100，语音通道音量
        - 有效音量 = master * channel_vol / 100

    静音:
        - 勾选全局静音时保存当前所有音量值
        - 取消静音时恢复到之前的音量设置（不重置）

    BGM 闪避（Ducking）:
        - 播放语音时自动降低 BGM 音量
        - 语音结束后平滑恢复
    """

    def __init__(self) -> None:
        # ── 音量 ──────────────────────────────────────────────
        self._volume: int = DEFAULT_VOLUME           # Master 0-100
        self._volume_bgm: int = DEFAULT_VOLUME_BGM   # BGM 0-100
        self._volume_sfx: int = DEFAULT_VOLUME_SFX   # SFX 0-100
        self._volume_voice: int = DEFAULT_VOLUME_VOICE  # Voice 0-100

        # ── 静音状态 ──────────────────────────────────────────
        self._muted: bool = False
        self._volumes_before_mute: dict[str, int] = {}

        # ── 进程管理池 ────────────────────────────────────────
        self._processes: list[subprocess.Popen] = []

        # ── BGM 状态 ──────────────────────────────────────────
        self._bgm_path: Optional[str] = None
        self._bgm_playing: bool = False
        self._bgm_process: Optional[subprocess.Popen] = None
        self._bgm_loop_point: Optional[float] = None
        self._bgm_stop_event: threading.Event = threading.Event()
        self._bgm_thread: Optional[threading.Thread] = None

        # ── BGM 闪避（Ducking） ──────────────────────────────
        self._bgm_ducking_enabled: bool = True
        self._bgm_ducked: bool = False
        self._bgm_original_vol: int = 0
        self._bgm_duck_vol: int = 0

        # ── SFX 状态 ──────────────────────────────────────────
        self._sfx_enabled: bool = True
        self._sfx_queue: collections.deque = collections.deque()
        self._sfx_thread: Optional[threading.Thread] = None
        self._sfx_running: bool = False
        self._sfx_stop_event: threading.Event = threading.Event()

        # ── Voice 状态 ────────────────────────────────────────
        self._voice_enabled: bool = True
        self._voice_process: Optional[subprocess.Popen] = None
        self._voice_path: Optional[str] = None
        self._voice_playing: bool = False
        self._voice_stop_event: threading.Event = threading.Event()
        self._voice_thread: Optional[threading.Thread] = None

        # ── 事件回调 ──────────────────────────────────────────
        self.on_voice_end: Optional[callable] = None
        self.on_bgm_end: Optional[callable] = None

        atexit.register(self.shutdown)

    # ── 属性 ─────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return _BACKEND != "none"

    @property
    def backend_name(self) -> str:
        return _BACKEND_NAME

    @property
    def bgm_ducking_enabled(self) -> bool:
        return self._bgm_ducking_enabled

    @bgm_ducking_enabled.setter
    def bgm_ducking_enabled(self, val: bool) -> None:
        self._bgm_ducking_enabled = val
        if not val and self._bgm_ducked:
            self._restore_bgm_from_duck()

    # ====================================================================
    #  进程池管理
    # ====================================================================

    def _register_process(self, proc: Optional[subprocess.Popen]) -> None:
        if proc is not None:
            self._processes.append(proc)

    def _unregister_process(self, proc: Optional[subprocess.Popen]) -> None:
        if proc is not None and proc in self._processes:
            try:
                self._processes.remove(proc)
            except ValueError:
                pass

    def _cleanup_process(self, proc: Optional[subprocess.Popen]) -> None:
        """安全终止单个进程并从池中移除。"""
        if proc is None:
            return
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=1)
                except Exception:
                    pass
        self._unregister_process(proc)

    def _cleanup_all_processes(self) -> None:
        """终止所有已注册的后台进程。"""
        for proc in list(self._processes):
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=1)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        self._processes.clear()

    # ====================================================================
    #  音量（Master + 四通道）
    # ====================================================================

    def _effective_volume(self, channel_vol: int) -> int:
        """计算有效音量 = Master * 通道音量 / 100。"""
        if self._muted:
            return 0
        return int(self._volume * channel_vol / 100)

    # ── Master 音量 ───────────────────────────────────────────

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, val: int) -> None:
        self._volume = max(0, min(100, val))

    def set_volume(self, val: int) -> None:
        self.volume = val

    def get_volume(self) -> int:
        return self._volume

    # ── 静音 ──────────────────────────────────────────────────

    @property
    def muted(self) -> bool:
        return self._muted or self._volume == 0

    def set_mute(self, muted: bool) -> None:
        """设置全局静音。

        静音时保存所有通道音量，取消静音时恢复。
        """
        if muted == self._muted and muted != (self._volume == 0):
            # 音量已为 0 但 _muted 为 False，视为静音
            if muted:
                self._muted = True
                self._stop_all_playback()
                return

        if muted:
            if not self._muted:
                # 保存当前音量
                self._volumes_before_mute = {
                    "volume": self._volume,
                    "volume_bgm": self._volume_bgm,
                    "volume_sfx": self._volume_sfx,
                    "volume_voice": self._volume_voice,
                }
                self._muted = True
                self._volume = 0
                self._stop_all_playback()
        else:
            self._muted = False
            # 恢复到静音前的音量
            saved = self._volumes_before_mute
            if saved:
                self._volume = saved.get("volume", DEFAULT_VOLUME)
                self._volume_bgm = saved.get("volume_bgm", DEFAULT_VOLUME_BGM)
                self._volume_sfx = saved.get("volume_sfx", DEFAULT_VOLUME_SFX)
                self._volume_voice = saved.get("volume_voice", DEFAULT_VOLUME_VOICE)
            else:
                self._volume = DEFAULT_VOLUME
            # 自动恢复 BGM 播放
            if self._bgm_path:
                self._start_bgm_simple(self._bgm_path)

    # ── BGM 音量 ──────────────────────────────────────────────

    @property
    def volume_bgm(self) -> int:
        return self._volume_bgm

    @volume_bgm.setter
    def volume_bgm(self, val: int) -> None:
        old = self._volume_bgm
        self._volume_bgm = max(0, min(100, val))
        if old == self._volume_bgm:
            return
        # 更新 duck 音量（如果处于闪避状态）
        if self._bgm_ducked:
            self._bgm_original_vol = self._volume_bgm
            self._bgm_duck_vol = max(1, int(self._volume_bgm * BGM_DUCK_RATIO / 100))
        # 重启 BGM 应用新音量
        if self._bgm_playing and not self._muted:
            self.restart_bgm()

    def set_volume_bgm(self, val: int) -> None:
        self.volume_bgm = val

    # ── SFX 音量 ──────────────────────────────────────────────

    @property
    def volume_sfx(self) -> int:
        return self._volume_sfx

    @volume_sfx.setter
    def volume_sfx(self, val: int) -> None:
        self._volume_sfx = max(0, min(100, val))

    def set_volume_sfx(self, val: int) -> None:
        self.volume_sfx = val

    # ── Voice 音量 ────────────────────────────────────────────

    @property
    def volume_voice(self) -> int:
        return self._volume_voice

    @volume_voice.setter
    def volume_voice(self, val: int) -> None:
        self._volume_voice = max(0, min(100, val))

    def set_volume_voice(self, val: int) -> None:
        self.volume_voice = val

    # ── 各通道启用状态 ──────────────────────────────────────

    @property
    def sfx_enabled(self) -> bool:
        return self._sfx_enabled

    @sfx_enabled.setter
    def sfx_enabled(self, val: bool) -> None:
        self._sfx_enabled = val

    @property
    def voice_enabled(self) -> bool:
        return self._voice_enabled

    @voice_enabled.setter
    def voice_enabled(self, val: bool) -> None:
        self._voice_enabled = val

    @property
    def voice_playing(self) -> bool:
        return self._voice_playing

    @property
    def bgm_playing(self) -> bool:
        return self._bgm_playing

    # ====================================================================
    #  BGM 播放
    # ====================================================================

    def play_bgm(self, path: str, loop_point: Optional[float] = None,
                 crossfade: bool = True) -> None:
        """播放背景音乐（支持交叉淡入淡出）。

        Args:
            path: 音频文件路径或名称。
            loop_point: 循环点（秒数），到达音频末尾后跳转到此位置。
            crossfade: 如果正在播放 BGM，是否交叉淡入淡出。
        """
        if self._muted:
            return

        resolved = _resolve_audio_path(path)
        if not os.path.exists(resolved):
            print(f"[音频] BGM 文件不存在: {resolved}")
            return

        self._bgm_loop_point = loop_point

        # 同一首不重播
        if self._bgm_playing and self._bgm_path == resolved:
            return

        old_path = self._bgm_path
        old_proc = self._bgm_process
        self._bgm_path = resolved

        # 尝试交叉淡入淡出
        if crossfade and self._bgm_playing and old_path and old_proc:
            if self._do_crossfade(old_path, resolved):
                return

        # 后备：直接切换
        self.stop_bgm()
        self._start_bgm_simple(resolved)

    def _do_crossfade(self, old_path: str, new_path: str) -> bool:
        """执行交叉淡入淡出切换 BGM（无爆音）。

        Returns:
            True 表示 crossfade 已启动，False 表示失败。
        """
        vol = self._effective_volume(
            self._bgm_duck_vol if self._bgm_ducked else self._volume_bgm
        )

        # 使用 ffmpeg acrossfade 生成混合音频并通过 ffplay 播放
        player = _play_crossfade_pipe(old_path, new_path, vol, fade_d=2.0)
        if player is None:
            return False

        # 终止旧 BGM
        old_proc = self._bgm_process
        self._bgm_playing = False
        self._bgm_stop_event.set()
        self._cleanup_process(old_proc)
        self._bgm_process = player
        self._register_process(player)
        self._bgm_playing = True

        # 等待 crossfade 完成后启动循环 BGM
        def _on_crossfade_done():
            try:
                player.wait(timeout=5)
            except Exception:
                pass
            self._cleanup_process(player)
            self._bgm_process = None
            if self._bgm_playing and self._bgm_path == new_path:
                self._start_bgm_simple(new_path)

        threading.Thread(target=_on_crossfade_done, daemon=True).start()
        return True

    def _start_bgm_simple(self, path: str) -> None:
        """直接启动 BGM 循环播放（无淡入淡出）。"""
        self._bgm_stop_event.clear()
        self._bgm_playing = True
        self._bgm_thread = threading.Thread(
            target=self._bgm_loop, args=(path,), daemon=True)
        self._bgm_thread.start()

    def _bgm_loop(self, path: str) -> None:
        """BGM 循环播放线程。"""
        vol = self._effective_volume(
            self._bgm_duck_vol if self._bgm_ducked else self._volume_bgm
        )

        if _BACKEND in ("ffplay", "afplay"):
            proc = _play_with_backend(path, volume=vol, loop=True)
            self._bgm_process = proc
            self._register_process(proc)
            if proc:
                try:
                    proc.wait()
                except Exception:
                    pass
            self._cleanup_process(proc)
            self._bgm_process = None
            if not self._bgm_stop_event.is_set():
                self._bgm_playing = False
                if self.on_bgm_end:
                    self.on_bgm_end()

        elif _BACKEND in ("aplay",):
            # aplay 不支持循环，循环播放需反复启动
            while not self._bgm_stop_event.is_set():
                if self._bgm_loop_point is not None:
                    ss = self._bgm_loop_point
                else:
                    ss = None
                proc = _play_with_backend(path, volume=vol, loop=False, ss=ss)
                self._bgm_process = proc
                self._register_process(proc)
                if proc:
                    try:
                        proc.wait()
                    except Exception:
                        pass
                self._cleanup_process(proc)
            self._bgm_process = None
            if not self._bgm_stop_event.is_set():
                self._bgm_playing = False
                if self.on_bgm_end:
                    self.on_bgm_end()

        elif _BACKEND == "winsound":
            # winsound 异步循环播放
            _play_with_backend(path, loop=True)
            # 等待停止信号
            self._bgm_stop_event.wait()

    def stop_bgm(self) -> None:
        """停止背景音乐。"""
        self._bgm_playing = False
        self._bgm_stop_event.set()
        if _BACKEND == "winsound":
            import winsound
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        self._cleanup_process(self._bgm_process)
        self._bgm_process = None

    def restart_bgm(self) -> None:
        """以当前音量/状态重启 BGM。"""
        path = self._bgm_path
        if path and not self._muted:
            self.stop_bgm()
            self._start_bgm_simple(path)

    # ====================================================================
    #  BGM 闪避（Ducking）
    # ====================================================================

    def _apply_bgm_duck(self) -> None:
        """播放语音时降低 BGM 音量。"""
        if (not self._bgm_ducking_enabled or not self._bgm_playing
                or self._bgm_ducked or self._muted):
            return

        self._bgm_ducked = True
        self._bgm_original_vol = self._volume_bgm
        duck_vol = max(1, int(self._volume_bgm * BGM_DUCK_RATIO / 100))
        self._bgm_duck_vol = duck_vol

        # 重启 BGM 以应用降低的音量
        if self._bgm_path:
            self.stop_bgm()
            self._bgm_thread = threading.Thread(
                target=self._bgm_loop, args=(self._bgm_path,), daemon=True)
            self._bgm_thread.start()

    def _restore_bgm_from_duck(self) -> None:
        """语音结束后恢复 BGM 音量。"""
        if not self._bgm_ducked:
            return

        self._bgm_ducked = False
        self._bgm_duck_vol = 0

        if self._bgm_path and not self._muted:
            self.stop_bgm()
            self._start_bgm_simple(self._bgm_path)

    # ====================================================================
    #  SFX（音效）
    # ====================================================================

    def play_sfx(self, path: str) -> None:
        """播放音效（排入队列，避免重叠）。

        Args:
            path: 音频文件路径或名称。
        """
        if not self._sfx_enabled or self._muted or self._volume_sfx == 0:
            return

        resolved = _resolve_audio_path(path)
        if not os.path.exists(resolved):
            print(f"[音频] SFX 文件不存在: {resolved}")
            return

        self._sfx_queue.append(resolved)

        if not self._sfx_running:
            self._sfx_running = True
            self._sfx_stop_event.clear()
            self._sfx_thread = threading.Thread(
                target=self._sfx_worker, daemon=True)
            self._sfx_thread.start()

    def _sfx_worker(self) -> None:
        """SFX 队列处理线程。"""
        while self._sfx_queue and not self._sfx_stop_event.is_set():
            sfx_path = self._sfx_queue.popleft()
            self._play_sfx_once(sfx_path)
        self._sfx_running = False

    def _play_sfx_once(self, path: str) -> None:
        """播放单个 SFX（同步等待）。"""
        vol = self._effective_volume(self._volume_sfx)

        if _BACKEND in ("ffplay", "afplay", "aplay"):
            proc = _play_with_backend(path, volume=vol, loop=False)
            self._register_process(proc)
            if proc:
                try:
                    proc.wait(timeout=30)
                except Exception:
                    pass
                self._cleanup_process(proc)
        elif _BACKEND == "winsound":
            import winsound
            try:
                winsound.PlaySound(path, winsound.SND_FILENAME)
            except Exception as e:
                print(f"[音频] winsound SFX 失败: {e}")

    def stop_sfx(self) -> None:
        """停止所有音效并清空队列。"""
        self._sfx_queue.clear()
        self._sfx_stop_event.set()
        self._sfx_running = False

    def clear_sfx_queue(self) -> None:
        """清空音效队列。"""
        self._sfx_queue.clear()

    # ====================================================================
    #  Voice（语音）
    # ====================================================================

    def play_voice(self, path: str) -> None:
        """播放语音（独立于 BGM 和 SFX）。

        新语音将覆盖旧语音。播放时自动触发 BGM 闪避。

        Args:
            path: 语音文件路径或名称。
        """
        if not self._voice_enabled or self._muted or self._volume_voice == 0:
            return

        resolved = _resolve_audio_path(path, search_dir=VOICE_DIR)
        if not os.path.exists(resolved):
            print(f"[音频] 语音文件不存在: {resolved}")
            return

        # 触发 BGM 闪避
        self._apply_bgm_duck()

        self.stop_voice()
        self._voice_path = resolved

        vol = self._effective_volume(self._volume_voice)
        proc = _play_with_backend(resolved, volume=vol, loop=False)
        if proc:
            self._voice_process = proc
            self._register_process(proc)
            self._voice_playing = True
            self._voice_thread = threading.Thread(
                target=self._voice_monitor, args=(proc,), daemon=True)
            self._voice_thread.start()
        elif _BACKEND == "winsound":
            # winsound 同步播放（阻塞）
            import winsound
            try:
                winsound.PlaySound(resolved, winsound.SND_FILENAME)
            except Exception as e:
                print(f"[音频] winsound 语音失败: {e}")
            self._voice_playing = False
            self._voice_path = None
            self._restore_bgm_from_duck()
            if self.on_voice_end:
                self.on_voice_end()

    def _voice_monitor(self, proc: Optional[subprocess.Popen]) -> None:
        """监控语音进程，结束后回调并恢复 BGM。"""
        if proc is None:
            return
        try:
            proc.wait()
        except Exception:
            pass
        self._voice_playing = False
        if self._voice_process is proc:
            self._voice_process = None
        self._cleanup_process(proc)

        # 恢复 BGM 音量
        self._restore_bgm_from_duck()

        if self.on_voice_end:
            self.on_voice_end()

    def stop_voice(self) -> None:
        """停止当前语音播放。"""
        self._voice_playing = False
        self._cleanup_process(self._voice_process)
        self._voice_process = None
        self._voice_path = None

    # ====================================================================
    #  内部工具
    # ====================================================================

    def _stop_all_playback(self) -> None:
        """停止所有正在播放的音频。"""
        self.stop_bgm()
        self.stop_voice()
        self.stop_sfx()

    # ====================================================================
    #  清理
    # ====================================================================

    def shutdown(self) -> None:
        """释放音频资源：停止所有播放，清理所有子进程。"""
        self._stop_all_playback()
        self._cleanup_all_processes()
