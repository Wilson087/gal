"""
音频引擎模块
============
提供背景音乐（BGM）和音效（SFX）的播放功能。

支持两种后端（自动检测，优先选择 ffplay）:
  1. ffplay (FFmpeg) — 支持几乎所有音频格式 (mp3, ogg, flac, wav, m4a...)
  2. winsound      — Windows 内置，仅 .wav，零依赖

音量控制:
  仅支持静音（0）和 100% 两档。
  set_volume(0) 静音，set_volume(>0) 恢复 100% 音量。

用法:
    from gal_lib.audio import AudioEngine

    audio = AudioEngine()
    audio.play_bgm("path/to/bgm.mp3")
    audio.play_sfx("path/to/sfx.ogg")
    audio.set_volume(0)       # 静音
    audio.set_volume(100)     # 恢复
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
    return shutil.which("ffplay") is not None


def _detect_backend() -> str:
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
    p = Path(path)
    if p.is_absolute():
        return str(p)
    candidate = AUDIO_DIR / p
    if candidate.exists():
        return str(candidate)
    if _BACKEND == "ffplay":
        for ext in [".mp3", ".ogg", ".wav", ".flac", ".m4a", ".opus", ".wma"]:
            c2 = AUDIO_DIR / f"{p}{ext}"
            if c2.exists():
                return str(c2)
    if not p.suffix:
        c2 = AUDIO_DIR / f"{p}.wav"
        if c2.exists():
            return str(c2)
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
        return _BACKEND != "none"

    @property
    def backend_name(self) -> str:
        return _BACKEND

    # ------------------------------------------------------------------
    #  音量（仅支持静音 / 100% 两档）
    # ------------------------------------------------------------------

    def set_volume(self, vol: int) -> None:
        """设置音量（仅支持 0 = 静音，>0 = 100%）。

        Args:
            vol: 0 为静音，>0 为 100% 音量。
        """
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

    # ------------------------------------------------------------------
    #  BGM
    # ------------------------------------------------------------------

    def play_bgm(self, path: str) -> None:
        """播放背景音乐（循环播放）。

        ffplay 后端使用 -volume 参数设定初始音量，
        音量变更时通过重启 BGM 应用新音量。

        Args:
            path: 音频文件路径，相对路径从 AUDIO_DIR 搜索。
        """
        if not self.bgm_enabled or self.volume == 0:
            return

        resolved = _resolve_audio_path(path)

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

        thread = threading.Thread(
            target=self._sfx_play_and_restore_bgm,
            args=(resolved,),
            daemon=True,
        )
        thread.start()

    def _sfx_play_and_restore_bgm(self, sfx_path: str) -> None:
        """播放 SFX 并在完成后恢复 BGM。"""
        was_bgm_playing = self._bgm_playing
        prev_bgm = self._bgm_path

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
                    timeout=60,
                )
            except Exception:
                pass
        elif _BACKEND == "winsound":
            import winsound
            try:
                winsound.PlaySound(sfx_path, winsound.SND_FILENAME)
            except Exception:
                pass

        if was_bgm_playing and prev_bgm:
            self.play_bgm(prev_bgm)

    # ------------------------------------------------------------------
    #  清理
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """释放音频资源（停止所有播放）。"""
        self.stop_bgm()
