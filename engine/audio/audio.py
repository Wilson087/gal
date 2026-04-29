"""
音频引擎模块
============
三通道音频引擎（BGM/SFX/Voice），基于 pyglet.media.Player。
"""

import glob
import os
import pyglet

from ..core.constants import AUDIO_DIR, BGM_VOLUME_DEFAULT, SFX_VOLUME_DEFAULT, VOICE_VOLUME_DEFAULT
from ..core.logger import Logger

log = Logger("Audio")

_AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")


class AudioEngine:
    """三通道音频引擎。

    BGM 循环播放，SFX 一次性，Voice 独立通道 + BGM 闪避。
    """

    def __init__(self) -> None:
        self.bgm_player = pyglet.media.Player()
        self.sfx_player = pyglet.media.Player()
        self.voice_player = pyglet.media.Player()

        self._bgm_volume = BGM_VOLUME_DEFAULT
        self._sfx_volume = SFX_VOLUME_DEFAULT
        self._voice_volume = VOICE_VOLUME_DEFAULT
        self._bgm_ducking = False
        self._bgm_full_volume = BGM_VOLUME_DEFAULT

        self.bgm_player.volume = self._bgm_volume
        self.sfx_player.volume = self._sfx_volume
        self.voice_player.volume = self._voice_volume

        # 路径解析缓存
        self._path_cache: dict[str, str] = {}
        self._audio_index: dict[str, str] | None = None

    def _build_audio_index(self) -> None:
        """构建 AUDIO_DIR 下所有音频文件的 {base: full_path} 索引。"""
        if self._audio_index is not None:
            return
        self._audio_index = {}
        if os.path.isdir(AUDIO_DIR):
            for f in os.listdir(AUDIO_DIR):
                full = os.path.join(AUDIO_DIR, f)
                if os.path.isfile(full):
                    base, _ = os.path.splitext(f)
                    self._audio_index[base] = full
                    # 同时以文件名本身为 key（方便模糊匹配）
                    self._audio_index[f] = full

    def _resolve_path(self, path: str) -> str:
        """解析音频文件路径，自动尝试常见扩展名（带缓存）。"""
        if not path:
            return ""

        # 缓存命中
        if path in self._path_cache:
            cached = self._path_cache[path]
            if os.path.exists(cached):
                return cached

        # 绝对路径直接返回
        if os.path.isabs(path) and os.path.exists(path):
            self._path_cache[path] = path
            return path

        # 拼接 AUDIO_DIR
        dir_path = os.path.join(AUDIO_DIR, path)

        # 直接路径存在
        if os.path.exists(dir_path):
            self._path_cache[path] = dir_path
            return dir_path

        # 尝试常见扩展名
        for ext in _AUDIO_EXTENSIONS:
            test_path = dir_path + ext
            if os.path.exists(test_path):
                self._path_cache[path] = test_path
                return test_path

        # 构建文件索引（首次使用时扫描一次）
        self._build_audio_index()
        if self._audio_index:
            base = os.path.basename(path)
            name_no_ext = os.path.splitext(base)[0]

            # 精确匹配（无扩展名）
            if name_no_ext in self._audio_index:
                self._path_cache[path] = self._audio_index[name_no_ext]
                return self._path_cache[path]

            # 精确匹配（含扩展名）
            if base in self._audio_index:
                self._path_cache[path] = self._audio_index[base]
                return self._path_cache[path]

            # 大小写不敏感匹配
            lower_query = name_no_ext.lower()
            for key, full in self._audio_index.items():
                if key.lower() == lower_query:
                    self._path_cache[path] = full
                    return full

            # 前缀匹配：仅当查询 ≥ 3 字符且键以查询开头
            if len(name_no_ext) >= 3:
                for key, full in self._audio_index.items():
                    key_lower = key.lower()
                    if key_lower.startswith(lower_query):
                        # 确保匹配到自然边界（下划线之后或开头）
                        remainder = key_lower[len(lower_query):]
                        if not remainder or remainder.startswith("_") or remainder.startswith("."):
                            self._path_cache[path] = full
                            return full

        return dir_path

    def play_bgm(self, path: str) -> None:
        """加载并循环播放 BGM。

        Args:
            path: BGM 文件路径或文件名。
        """
        if not path:
            return
        full = self._resolve_path(path)
        try:
            source = pyglet.media.load(full)
        except Exception as e:
            log.error("BGM 加载失败: %s - %s", full, e)
            return

        self.bgm_player.next_source()
        self.bgm_player.queue(source)
        self.bgm_player.loop = True
        self.bgm_player.play()

    def stop_bgm(self) -> None:
        """停止 BGM。"""
        log.debug("停止 BGM")
        self.bgm_player.pause()
        self.bgm_player.delete()
        self.bgm_player = pyglet.media.Player()
        self.bgm_player.volume = self._bgm_volume
        self._bgm_ducking = False

    def play_sfx(self, path: str) -> None:
        """播放一次性 SFX。

        Args:
            path: SFX 文件路径或文件名。
        """
        if not path:
            return
        full = self._resolve_path(path)
        log.debug("播放 SFX: %s -> %s", path, full)
        try:
            source = pyglet.media.load(full)
        except Exception as e:
            log.error("SFX 加载失败: %s - %s", full, e)
            return

        self.sfx_player.next_source()
        self.sfx_player.queue(source)
        self.sfx_player.play()

    def play_voice(self, path: str) -> None:
        """播放语音。

        触发 BGM ducking（语音播放时降低 BGM 音量）。

        Args:
            path: 语音文件路径或文件名。
        """
        if not path:
            return
        full = self._resolve_path(path)
        log.debug("播放语音: %s -> %s", path, full)
        try:
            source = pyglet.media.load(full)
        except Exception as e:
            log.error("Voice 加载失败: %s - %s", full, e)
            return

        if self.bgm_player.playing and not self._bgm_ducking:
            self._bgm_full_volume = self._bgm_volume
            self.bgm_player.volume = self._bgm_volume * 0.5
            self._bgm_ducking = True

        self.voice_player.next_source()
        self.voice_player.queue(source)
        self.voice_player.play()

    def update_ducking(self) -> None:
        """检查语音播放状态，恢复 BGM 音量。"""
        if self._bgm_ducking and not self.voice_player.playing:
            log.debug("BGM 闪避结束，音量恢复 %.2f", self._bgm_full_volume)
            self.bgm_player.volume = self._bgm_full_volume
            self._bgm_ducking = False

    @property
    def voice_playing(self) -> bool:
        return self.voice_player.playing

    @property
    def bgm_playing(self) -> bool:
        return self.bgm_player.playing

    @property
    def bgm_volume(self) -> float:
        return self._bgm_volume

    @bgm_volume.setter
    def bgm_volume(self, value: float) -> None:
        self._bgm_volume = max(0.0, min(1.0, value))
        self.bgm_player.volume = self._bgm_volume

    @property
    def sfx_volume(self) -> float:
        return self._sfx_volume

    @sfx_volume.setter
    def sfx_volume(self, value: float) -> None:
        self._sfx_volume = max(0.0, min(1.0, value))
        self.sfx_player.volume = self._sfx_volume

    @property
    def voice_volume(self) -> float:
        return self._voice_volume

    @voice_volume.setter
    def voice_volume(self, value: float) -> None:
        self._voice_volume = max(0.0, min(1.0, value))
        self.voice_player.volume = self._voice_volume

    def shutdown(self) -> None:
        """关闭音频引擎，清理资源。"""
        self.bgm_player.delete()
        self.sfx_player.delete()
        self.voice_player.delete()
