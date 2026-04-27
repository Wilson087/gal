"""
音频引擎模块
============
提供背景音乐（BGM）和音效（SFX）的播放功能。

支持两种后端（自动检测，优先选择 ffplay）:
  1. ffplay (FFmpeg) — 支持几乎所有音频格式 (mp3, ogg, flac, wav, m4a...)
  2. winsound      — Windows 内置，仅 .wav，零依赖

音量控制:
  - ffplay 后端：Windows 上通过 COM ISimpleAudioVolume 接口
    实时调节 ffplay 进程的音频会话音量，无停顿不重启。
  - winsound 后端：仅支持静音/非静音切换。

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
#  Windows 进程音频会话音量控制（COM ISimpleAudioVolume）
#  ctypes 实现，零依赖
# ========================================================================

if sys.platform == "win32":
    import ctypes
    from ctypes import (
        c_void_p, c_uint32, c_float, c_int, c_ulong, byref, POINTER,
        Structure, HRESULT, WinError,
    )
    from ctypes.wintypes import LPCWSTR, DWORD, HANDLE, BOOL

    # GUID 结构体（ctypes.wintypes 中可能没有）
    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_byte * 8),
        ]
        @classmethod
        def from_string(cls, s: str) -> "GUID":
            """从标准 GUID 字符串创建。"""
            parts = s.strip("{}").split("-")
            return cls(
                int(parts[0], 16), int(parts[1], 16), int(parts[2], 16),
                (ctypes.c_byte * 8)(
                    *[int(p, 16) for p in (
                        parts[3][:2], parts[3][2:],
                        parts[4][:2], parts[4][2:],
                        parts[4][4:6], parts[4][6:8],
                        parts[4][8:10], parts[4][10:12],
                    )]
                ),
            )

    # ── COM GUID ────────────────────────────────────────────────
    _GUID_NULL = (c_uint32 * 4)(0, 0, 0, 0)

    _CLSID_MMDeviceEnumerator = GUID(
        0xBCDE0395, 0xE52F, 0x467C,
        (ctypes.c_byte * 8)(0x8E, 0x3D, 0xC4, 0x57, 0x92, 0x92, 0x69, 0x2E),
    )

    _IID_IMMDeviceEnumerator = GUID(
        0xA95664D2, 0x9614, 0x4F35,
        (ctypes.c_byte * 8)(0xA7, 0x46, 0xDE, 0x8D, 0xB6, 0x36, 0x17, 0xE6),
    )

    _IID_IAudioSessionManager2 = GUID(
        0x77AA99A0, 0x1BD6, 0x484F,
        (ctypes.c_byte * 8)(0x8B, 0xC7, 0x2B, 0xB6, 0x54, 0x1C, 0x9A, 0x9B),
    )

    _IID_IAudioSessionEnumerator = GUID(
        0xE2F97BB4, 0x8917, 0x4E88,
        (ctypes.c_byte * 8)(0x8E, 0x15, 0x11, 0x09, 0xB7, 0xCA, 0x8B, 0x37),
    )

    _IID_ISimpleAudioVolume = GUID(
        0x87CE5498, 0x68D6, 0x44E5,
        (ctypes.c_byte * 8)(0x92, 0x15, 0x6D, 0xA4, 0x7E, 0xF8, 0x83, 0xD1),
    )

    # ── COM 接口 vtable 布局 ───────────────────────────────────
    class IMMDeviceEnumerator(c_void_p):
        pass

    class IAudioSessionManager2(c_void_p):
        pass

    class IAudioSessionEnumerator(c_void_p):
        pass

    class ISimpleAudioVolume(c_void_p):
        pass

    # QueryInterface + AddRef + Release 的偏移（标准 COM IUnknown）
    _IUNKNOWN_QI = 0
    _IUNKNOWN_ADDREF = 1
    _IUNKNOWN_RELEASE = 2

    def _com_query_interface(punk, iid, interface_cls):
        """QI → 获取指定接口指针。"""
        result = c_void_p()
        vtbl = ctypes.cast(punk, POINTER(POINTER(c_void_p)))[0]
        func = ctypes.cast(vtbl[_IUNKNOWN_QI], ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(GUID), POINTER(c_void_p)))
        hr = func(ctypes.cast(punk, c_void_p), byref(iid), byref(result))
        if hr != 0:
            return None
        return ctypes.cast(result, interface_cls)

    def _com_release(punk):
        """Release COM 接口。"""
        if punk is None:
            return
        vtbl = ctypes.cast(punk, POINTER(POINTER(c_void_p)))[0]
        func = ctypes.cast(vtbl[_IUNKNOWN_RELEASE], ctypes.CFUNCTYPE(c_ulong, c_void_p))
        func(ctypes.cast(punk, c_void_p))

    def _set_windows_process_volume(pid: int, volume_0to1: float) -> bool:
        """设置指定进程的 Windows 音频会话音量。

        Args:
            pid: 进程 ID。
            volume_0to1: 音量 0.0–1.0。

        Returns:
            True 成功，False 失败（会话未就绪等）。
        """
        if not (0 <= pid <= 65535):
            return False

        ole32 = ctypes.windll.ole32
        ole32.CoInitializeEx(None, 0)  # COINIT_APARTMENTTHREADED

        # CoCreateInstance → IMMDeviceEnumerator
        enum_ptr = c_void_p()
        hr = ole32.CoCreateInstance(
            byref(_CLSID_MMDeviceEnumerator),
            None, 1,  # CLSCTX_INPROC_SERVER
            byref(_IID_IMMDeviceEnumerator),
            byref(enum_ptr),
        )
        if hr != 0:
            return False

        dev = c_void_p()
        try:
            vtbl = ctypes.cast(enum_ptr, POINTER(POINTER(c_void_p)))[0]
            # IMMDeviceEnumerator::GetDefaultAudioEndpoint(index 4)
            GetDefaultAudioEndpoint = ctypes.cast(
                vtbl[4],
                ctypes.CFUNCTYPE(
                    HRESULT, c_void_p, c_int, c_int, POINTER(c_void_p),
                ),
            )
            hr = GetDefaultAudioEndpoint(
                ctypes.cast(enum_ptr, c_void_p),
                0, 0, byref(dev),
            )
            if hr != 0:
                return False

            # IMMDevice::Activate(index 3) → IAudioSessionManager2
            Activate = ctypes.cast(
                ctypes.cast(dev, POINTER(c_void_p))[0][3],
                ctypes.CFUNCTYPE(
                    HRESULT, c_void_p, POINTER(GUID), c_int, POINTER(c_void_p),
                ),
            )
            sess_mgr = c_void_p()
            hr = Activate(
                ctypes.cast(dev, c_void_p),
                byref(_IID_IAudioSessionManager2), 0, byref(sess_mgr),
            )
            if hr != 0:
                return False

            # IAudioSessionManager2::GetSessionEnumerator(index 5)
            vtbl_sm = ctypes.cast(sess_mgr, POINTER(POINTER(c_void_p)))[0]
            GetEnumerator = ctypes.cast(
                vtbl_sm[5],
                ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(c_void_p)),
            )
            enum_sessions = c_void_p()
            hr = GetEnumerator(ctypes.cast(sess_mgr, c_void_p), byref(enum_sessions))
            if hr != 0:
                return False

            # 遍历会话
            vtbl_es = ctypes.cast(enum_sessions, POINTER(POINTER(c_void_p)))[0]
            GetCount = ctypes.cast(
                vtbl_es[3],
                ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(c_int)),
            )
            GetSession = ctypes.cast(
                vtbl_es[4],
                ctypes.CFUNCTYPE(HRESULT, c_void_p, c_int, POINTER(c_void_p)),
            )

            count = c_int(0)
            hr = GetCount(ctypes.cast(enum_sessions, c_void_p), byref(count))
            if hr != 0:
                return False

            found = False
            for i in range(count.value):
                svc = c_void_p()
                hr = GetSession(ctypes.cast(enum_sessions, c_void_p), i, byref(svc))
                if hr != 0:
                    continue

                # IAudioSessionControl::GetProcessId(index 10)
                vtbl_svc = ctypes.cast(svc, POINTER(POINTER(c_void_p)))[0]
                GetProcessId = ctypes.cast(
                    vtbl_svc[10],
                    ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(DWORD)),
                )
                session_pid = DWORD(0)
                hr_pid = GetProcessId(ctypes.cast(svc, c_void_p), byref(session_pid))
                if hr_pid == 0 and session_pid.value == pid:
                    # QI → ISimpleAudioVolume
                    qi = ctypes.cast(
                        vtbl_svc[0],
                        ctypes.CFUNCTYPE(
                            HRESULT, c_void_p, POINTER(GUID), POINTER(c_void_p),
                        ),
                    )
                    simple = c_void_p()
                    hr_qi = qi(
                        ctypes.cast(svc, c_void_p),
                        byref(_IID_ISimpleAudioVolume), byref(simple),
                    )
                    if hr_qi == 0:
                        vtbl_sa = ctypes.cast(simple, POINTER(POINTER(c_void_p)))[0]
                        SetMasterVolume = ctypes.cast(
                            vtbl_sa[3],
                            ctypes.CFUNCTYPE(
                                HRESULT, c_void_p, c_float, POINTER(GUID),
                            ),
                        )
                        vol = c_float(max(0.0, min(1.0, volume_0to1)))
                        hr_set = SetMasterVolume(
                            ctypes.cast(simple, c_void_p), vol, byref(_GUID_NULL),
                        )
                        # Release simple
                        rel = ctypes.cast(
                            vtbl_sa[2],
                            ctypes.CFUNCTYPE(c_ulong, c_void_p),
                        )
                        rel(ctypes.cast(simple, c_void_p))
                        found = (hr_set == 0)
                    break
                # Release svc (will release simple too if we got it)
                rel_svc = ctypes.cast(
                    vtbl_svc[2],
                    ctypes.CFUNCTYPE(c_ulong, c_void_p),
                )
                rel_svc(ctypes.cast(svc, c_void_p))

            # Release enum_sessions
            rel_es = ctypes.cast(
                vtbl_es[2],
                ctypes.CFUNCTYPE(c_ulong, c_void_p),
            )
            rel_es(ctypes.cast(enum_sessions, c_void_p))
            return found
        except Exception:
            return False
        finally:
            if dev:
                try:
                    vtbl_dev = ctypes.cast(dev, POINTER(POINTER(c_void_p)))[0]
                    rel = ctypes.cast(vtbl_dev[2], ctypes.CFUNCTYPE(c_ulong, c_void_p))
                    rel(ctypes.cast(dev, c_void_p))
                except Exception:
                    pass

    def _set_windows_process_volume_safe(pid: int, volume_0to1: float) -> bool:
        """包装函数，捕获所有异常。"""
        try:
            return _set_windows_process_volume(pid, volume_0to1)
        except Exception:
            return False
else:
    def _set_windows_process_volume_safe(pid, volume_0to1):
        return False


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
    #  音量（实时调节，不重启播放）
    # ------------------------------------------------------------------

    def set_volume(self, vol: int) -> None:
        """设置音量。

        ffplay 后端（Windows）：通过 COM 接口实时调节 ffplay 进程的
        音频会话音量，无停顿不重启。

        winsound 后端：音量 0 时静音，>0 时以系统音量播放。

        Args:
            vol: 音量值 0–100。
        """
        old_vol = self.volume
        self.volume = max(0, min(100, vol))

        if self.volume == 0:
            self.stop_bgm()
        elif old_vol == 0 and self._bgm_path:
            # 从静音恢复：重启 BGM
            self.play_bgm(self._bgm_path)
        elif _BACKEND == "ffplay" and self._bgm_process and self._bgm_process.poll() is None:
            # ffplay 正在播放：通过 COM 实时调音量，不重启
            vol_0to1 = self.volume / 100.0
            _set_windows_process_volume_safe(self._bgm_process.pid, vol_0to1)

    def get_volume(self) -> int:
        return self.volume

    # ------------------------------------------------------------------
    #  BGM
    # ------------------------------------------------------------------

    def play_bgm(self, path: str) -> None:
        """播放背景音乐（循环播放）。

        ffplay 后端启动时不带 -volume 参数（使用系统默认音量），
        音量由 set_volume() 通过 COM 接口实时控制。

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
            # 不加 -volume 参数，音量通过 COM 接口实时控制
            self._bgm_process = subprocess.Popen(
                [
                    "ffplay", "-nodisp", "-autoexit", "-loop", "0",
                    self._bgm_path,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
            )
            # 启动后立即设置当前音量
            if sys.platform == "win32":
                vol_0to1 = self.volume / 100.0
                _set_windows_process_volume_safe(self._bgm_process.pid, vol_0to1)

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
