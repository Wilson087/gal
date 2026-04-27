"""
音频引擎模块
============
提供背景音乐（BGM）和音效（SFX）的播放功能。

支持两种后端（自动检测，优先选择 ffplay）:
  1. ffplay (FFmpeg) — 支持几乎所有音频格式 (mp3, ogg, flac, wav, m4a...)
  2. winsound      — Windows 内置，仅 .wav，零依赖

用法:
    from gal_lib.audio import AudioEngine

    audio = AudioEngine()
    audio.play_bgm("path/to/bgm.mp3")
    audio.play_sfx("path/to/sfx.ogg")
    audio.set_volume(60)
    audio.stop_bgm()
"""

import atexit
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from .constants import AUDIO_DIR, DEFAULT_VOLUME


# ========================================================================
#  后端检测
# ========================================================================

def _check_ffplay() -> bool:
    """检查系统中是否安装了 ffplay。"""
    return shutil.which("ffplay") is not None


def _detect_backend() -> str:
    """检测当前平台可用的最佳音频后端。

    优先级: ffplay > winsound > none

    Returns:
        "ffplay"   — FFmpeg 套件中的 ffplay (支持所有格式)
        "winsound" — Windows 内置 (仅 .wav)
        "none"     — 无可用后端
    """
    if _check_ffplay():
        return "ffplay"
    if sys.platform == "win32":
        try:
            import winsound  # noqa: F401
            return "winsound"
        except ImportError:
            pass
    return "none"


_BACKEND = _detect_backend()


def _resolve_audio_path(path: str) -> str:
    """解析音频文件路径：相对路径从 AUDIO_DIR 搜索，绝对路径直接使用。

    Args:
        path: 文件路径（相对或绝对）。

    Returns:
        解析后的绝对路径字符串，文件不存在时返回原值。
    """
    p = Path(path)
    if p.is_absolute():
        return str(p)
    # 尝试 AUDIO_DIR / path
    candidate = AUDIO_DIR / p
    if candidate.exists():
        return str(candidate)
    # ffplay 后端：尝试常见扩展名
    if _BACKEND == "ffplay":
        for ext in [".mp3", ".ogg", ".wav", ".flac", ".m4a", ".opus", ".wma"]:
            candidate2 = AUDIO_DIR / f"{p}{ext}"
            if candidate2.exists():
                return str(candidate2)
    # winsound 后端：尝试 .wav
    if not p.suffix:
        candidate2 = AUDIO_DIR / f"{p}.wav"
        if candidate2.exists():
            return str(candidate2)
    return str(p)


# ========================================================================
#  音频引擎
# ========================================================================

class AudioEngine:
    """音频引擎：管理 BGM 与 SFX 播放。

    自动选择最佳可用后端（ffplay > winsound > none）。

    属性:
        volume (int): 音量 0–100。
        bgm_enabled (bool): 是否启用背景音乐。
        sfx_enabled (bool): 是否启用音效。
    """

    def __init__(self) -> None:
        self.volume: int = DEFAULT_VOLUME
        self.bgm_enabled: bool = True
        self.sfx_enabled: bool = True

        # BGM 状态
        self._bgm_path: Optional[str] = None
        self._bgm_playing: bool = False
        self._bgm_process: Optional[subprocess.Popen] = None  # ffplay 进程
        self._bgm_thread: Optional[threading.Thread] = None   # winsound 线程
        self._bgm_stop: threading.Event = threading.Event()

        # 进程退出时自动停止音频
        atexit.register(self.shutdown)

    # ------------------------------------------------------------------
    #  属性
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """当前平台是否有可用的音频后端。"""
        return _BACKEND != "none"

    @property
    def backend_name(self) -> str:
        """当前使用的音频后端名称。"""
        return _BACKEND

    # ------------------------------------------------------------------
    #  音量
    # ------------------------------------------------------------------

    def set_volume(self, vol: int) -> None:
        """设置音量。

        ffplay 后端：实时调节音量（0 = 静音，100 = 最大）。
        winsound 后端：音量 0 时静音，>0 时以系统音量播放。

        Args:
            vol: 音量值 0–100。
        """
        old_vol = self.volume
        self.volume = max(0, min(100, vol))

        if self.volume == 0:
            self.stop_bgm()
        elif self._bgm_path and (old_vol == 0 or self._bgm_playing):
            # 音量从 0 调大 → 恢复 BGM；播放中调音量 → 用新音量重启
            self.stop_bgm()
            time.sleep(0.05)
            self.play_bgm(self._bgm_path)

    def get_volume(self) -> int:
        """获取当前音量。

        Returns:
            0–100 的整数值。
        """
        return self.volume

    # ------------------------------------------------------------------
    #  BGM
    # ------------------------------------------------------------------

    def play_bgm(self, path: str) -> None:
        """播放背景音乐（循环播放）。

        如果已有 BGM 正在播放且路径相同，则不跳转。
        路径相同时先 stop_bgm() 再 play_bgm() 可强制重启。

        Args:
            path: 音频文件路径，相对路径从 AUDIO_DIR 搜索。
        """
        if not self.bgm_enabled or self.volume == 0:
            return

        resolved = _resolve_audio_path(path)

        # 同一首歌正在播放 → 不做任何事
        if self._bgm_playing and self._bgm_path == resolved:
            return

        self.stop_bgm()
        self._bgm_path = resolved
        self._bgm_stop.clear()

        if not os.path.exists(resolved):
            return

        if _BACKEND == "ffplay":
            self._bgm_playing = True
            self._bgm_thread = threading.Thread(
                target=self._bgm_loop_ffplay,
                daemon=True,
            )
            self._bgm_thread.start()
        elif _BACKEND == "winsound":
            self._bgm_playing = True
            self._bgm_thread = threading.Thread(
                target=self._bgm_loop_winsound,
                daemon=True,
            )
            self._bgm_thread.start()

    def _bgm_loop_ffplay(self) -> None:
        """ffplay 后端 BGM 循环播放。"""
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            self._bgm_process = subprocess.Popen(
                [
                    "ffplay", "-nodisp", "-autoexit", "-loop", "0",
                    "-volume", str(self.volume),
                    self._bgm_path,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
            )
            self._bgm_process.wait()
        except Exception:
            pass
        finally:
            self._bgm_process = None
            # 如果不是被主动停止的（进程意外退出），标记为未播放
            if not self._bgm_stop.is_set():
                self._bgm_playing = False

    def _bgm_loop_winsound(self) -> None:
        """winsound 后端 BGM 循环播放线程。"""
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
        """停止背景音乐。"""
        self._bgm_playing = False
        self._bgm_stop.set()

        if _BACKEND == "ffplay":
            if self._bgm_process:
                try:
                    self._bgm_process.terminate()
                    self._bgm_process.wait(timeout=2)
                except Exception:
                    try:
                        self._bgm_process.kill()
                    except Exception:
                        pass
                self._bgm_process = None
        elif _BACKEND == "winsound":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

    # ------------------------------------------------------------------
    #  SFX
    # ------------------------------------------------------------------

    def play_sfx(self, path: str) -> None:
        """播放音效。

        SFX 播放时会短暂中断 BGM，播放完成后自动恢复 BGM。

        Args:
            path: 音频文件路径，相对路径从 AUDIO_DIR 搜索。
        """
        if not self.sfx_enabled or self.volume == 0:
            return

        resolved = _resolve_audio_path(path)
        if not os.path.exists(resolved):
            return

        # 在后台线程播放 SFX，播放完后恢复 BGM
        thread = threading.Thread(
            target=self._sfx_play_and_restore_bgm,
            args=(resolved,),
            daemon=True,
        )
        thread.start()

    def _sfx_play_and_restore_bgm(self, sfx_path: str) -> None:
        """播放 SFX 并在完成后恢复 BGM。

        Args:
            sfx_path: 已解析的 SFX 文件绝对路径。
        """
        was_bgm_playing = self._bgm_playing
        prev_bgm = self._bgm_path

        # 停止 BGM（避免混音冲突）
        if was_bgm_playing:
            self.stop_bgm()
            time.sleep(0.05)

        if _BACKEND == "ffplay":
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            try:
                subprocess.run(
                    [
                        "ffplay", "-nodisp", "-autoexit",
                        "-volume", str(self.volume),
                        sfx_path,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    startupinfo=startupinfo,
                    timeout=60,  # 防止意外卡住
                )
            except Exception:
                pass
        elif _BACKEND == "winsound":
            import winsound
            try:
                winsound.PlaySound(sfx_path, winsound.SND_FILENAME)
            except Exception:
                pass

        # 恢复 BGM
        if was_bgm_playing and prev_bgm:
            self.play_bgm(prev_bgm)

    # ------------------------------------------------------------------
    #  清理
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """释放音频资源（停止所有播放）。"""
        self.stop_bgm()
