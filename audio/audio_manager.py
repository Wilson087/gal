"""
Audio Manager — 三通道音频管理
===============================
BGM（循环）/ Voice（单次）/ SE（最多 8 同播）。

Source 由外部加载（ResourceManager），本模块只负责播放。

用法::

    from audio.audio_manager import AudioManager

    audio = AudioManager(event_bus=game.events)
    audio.play_bgm(bgm_source, volume=0.8, loop=True)
    audio.play_voice(voice_source, volume=1.0)
    audio.play_se(click_source, volume=0.6)
    audio.stop_bgm(fade_out=2.0)
    audio.pause_all()
    audio.resume_all()
"""

from __future__ import annotations

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

import pyglet.media

if TYPE_CHECKING:
    from core.events import EventBus

logger = logging.getLogger(__name__)

# 事件名字符串 —— 如需提升为引擎级事件，可在 core.events.Event 枚举中新增别名
_EVT_BGM_START = "audio:bgm_start"
_EVT_BGM_END = "audio:bgm_end"
_EVT_VOICE_END = "audio:voice_end"


class AudioManager:
    """三通道音频管理器。

    - **BGM**：单播放器，默认循环。支持平滑淡出。
    - **Voice**：单播放器，新语音自动打断旧语音。
    - **SE**：池化（默认 8 个播放器），轮转复用。
      SE 为低优先级，可能被新音效打断；重要信息勿通过 SE 传达。
    """

    SE_POOL_SIZE: int = 8

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus: EventBus | None = event_bus

        # ── 设备检测 ──────────────────────────────────────
        self._audio_available: bool = self._detect_audio()

        # ── 播放器 ────────────────────────────────────────
        self._bgm_player: pyglet.media.Player | None = None
        self._voice_player: pyglet.media.Player | None = None
        self._se_players: list[pyglet.media.Player] = []
        self._se_index: int = 0

        if self._audio_available:
            self._bgm_player = pyglet.media.Player()
            self._voice_player = pyglet.media.Player()
            self._se_players = [
                pyglet.media.Player() for _ in range(self.SE_POOL_SIZE)
            ]
            self._setup_eos_handlers()
        else:
            logger.warning("音频设备不可用 —— 所有 play_* 方法静默跳过")

        # ── 音量 ──────────────────────────────────────────
        self._volumes: dict[str, float] = {
            "bgm": 0.8, "voice": 1.0, "se": 0.6,
        }

        # ── 淡出状态 ──────────────────────────────────────
        self._fade_active: bool = False
        self._fade_start_vol: float = 0.0
        self._fade_elapsed: float = 0.0
        self._fade_duration: float = 0.0

        # ── pause/resume 状态追踪 ─────────────────────────
        # pause_all 时记录当时正在播放的 player，resume_all 只恢复这些
        self._paused_players: set[pyglet.media.Player] = set()

        logger.info("AudioManager 已初始化: available=%s", self._audio_available)

    # ── BGM ───────────────────────────────────────────────

    def play_bgm(
        self, source: pyglet.media.Source, volume: float = 0.8, loop: bool = True,
    ) -> None:
        """播放或替换 BGM。

        Args:
            source: 已加载的音频 Source。
            volume: 播放音量 [0.0, 1.0]。
            loop: 是否循环播放。
        """
        if not self._audio_available or self._bgm_player is None:
            return

        try:
            player = self._bgm_player
            # 取消进行中的淡出
            self._cancel_fade()

            player.loop = loop
            volume = max(0.0, min(1.0, volume))
            self._volumes["bgm"] = volume
            player.volume = volume
            player.queue(source)
            player.play()
            self._emit(_EVT_BGM_START, channel="bgm")
            logger.debug("BGM 播放: loop=%s vol=%.2f", loop, volume)
        except Exception:
            logger.error("BGM 播放失败", exc_info=True)

    def stop_bgm(self, fade_out: float = 0.0) -> None:
        """停止 BGM，可选淡出。

        Args:
            fade_out: 淡出时长（秒）。0 表示立即停止。
        """
        if not self._audio_available or self._bgm_player is None:
            return

        try:
            if fade_out <= 0.0:
                self._cancel_fade()
                self._bgm_player.pause()
                self._bgm_player.next_source()  # 清空队列
                self._emit(_EVT_BGM_END, channel="bgm", reason="stop")
                logger.debug("BGM 立即停止")
            else:
                self._start_fade_out(fade_out)
        except Exception:
            logger.error("BGM 停止失败", exc_info=True)

    # ── Voice ─────────────────────────────────────────────

    def play_voice(self, source: pyglet.media.Source, volume: float = 1.0) -> None:
        """播放语音，自动打断上一句。

        Args:
            source: 已加载的音频 Source。
            volume: 播放音量 [0.0, 1.0]。
        """
        if not self._audio_available or self._voice_player is None:
            return

        try:
            player = self._voice_player
            if player.playing:
                player.pause()
                player.next_source()
            volume = max(0.0, min(1.0, volume))
            self._volumes["voice"] = volume
            player.volume = volume
            player.queue(source)
            player.play()
            logger.debug("Voice 播放: vol=%.2f", volume)
        except Exception:
            logger.error("Voice 播放失败", exc_info=True)

    # ── SE ────────────────────────────────────────────────

    def play_se(self, source: pyglet.media.Source, volume: float = 0.6) -> None:
        """播放音效，轮转复用 SE 播放器池。

        SE 为低优先级，短时间内密集调用时新音效可能覆盖未播完的旧音效。
        重要信息（如剧情提示）不应通过 SE 传达。

        Args:
            source: 已加载的音频 Source。
            volume: 播放音量 [0.0, 1.0]。
        """
        if not self._audio_available or not self._se_players:
            return

        try:
            player = self._se_players[self._se_index]
            self._se_index = (self._se_index + 1) % self.SE_POOL_SIZE

            if player.playing:
                player.pause()
                player.next_source()
            volume = max(0.0, min(1.0, volume))
            self._volumes["se"] = volume
            player.volume = volume
            player.queue(source)
            player.play()
        except Exception:
            logger.error("SE 播放失败", exc_info=True)

    # ── 音量 ──────────────────────────────────────────────

    def set_volume(self, channel: str, volume: float) -> None:
        """设置通道基准音量。

        Args:
            channel: ``"bgm"`` / ``"voice"`` / ``"se"``。
            volume: 音量 [0.0, 1.0]。

        Raises:
            ValueError: 无效通道名。
        """
        if channel not in self._volumes:
            raise ValueError(f"无效音频通道: {channel!r}，可选: bgm / voice / se")

        volume = max(0.0, min(1.0, volume))
        self._volumes[channel] = volume

        if channel == "bgm" and self._bgm_player is not None:
            self._cancel_fade()
            self._bgm_player.volume = volume
        elif channel == "voice" and self._voice_player is not None:
            self._voice_player.volume = volume
        elif channel == "se":
            for p in self._se_players:
                p.volume = volume

        logger.debug("音量: %s → %.2f", channel, volume)

    # ── 全局控制 ──────────────────────────────────────────

    def pause_all(self) -> None:
        """暂停所有播放器，记录状态供 resume_all 恢复。"""
        if not self._audio_available:
            return

        for player in self._iter_players():
            if player.playing and player not in self._paused_players:
                self._paused_players.add(player)
                player.pause()

        logger.debug("全体暂停: %d 个播放器", len(self._paused_players))

    def resume_all(self) -> None:
        """恢复 pause_all 暂停的播放器。"""
        if not self._audio_available:
            return

        count = 0
        for player in list(self._paused_players):
            try:
                player.play()
                count += 1
            except Exception:
                logger.warning("恢复播放失败", exc_info=True)
        self._paused_players.clear()

        logger.debug("全体恢复: %d 个播放器", count)

    # ── 淡出内部实现 ─────────────────────────────────────

    def _start_fade_out(self, duration: float) -> None:
        """开始 BGM 平滑淡出。"""
        if self._bgm_player is None:
            return

        # 取消旧淡出
        self._cancel_fade()

        self._fade_start_vol = self._bgm_player.volume  # type: ignore[assignment]
        self._fade_elapsed = 0.0
        self._fade_duration = duration
        self._fade_active = True
        pyglet.clock.schedule_interval(self._fade_step, 0.05)
        logger.debug("BGM 淡出开始: duration=%.2f from_vol=%.2f", duration, self._fade_start_vol)

    def _fade_step(self, dt: float) -> None:
        """淡出的一步（由 clock 每 50ms 调用）。"""
        if self._bgm_player is None or self._fade_duration <= 0:
            self._cancel_fade()
            return

        self._fade_elapsed += dt
        t = min(self._fade_elapsed / self._fade_duration, 1.0)
        self._bgm_player.volume = self._fade_start_vol * (1.0 - t)

        if t >= 1.0:
            self._bgm_player.pause()
            self._bgm_player.next_source()
            self._fade_active = False
            pyglet.clock.unschedule(self._fade_step)
            self._emit(_EVT_BGM_END, channel="bgm", reason="fade_out")
            logger.debug("BGM 淡出完成")

    def _cancel_fade(self) -> None:
        """取消进行中的淡出定时器。"""
        if self._fade_active:
            pyglet.clock.unschedule(self._fade_step)
            self._fade_active = False

    # ── EOS 回调 ──────────────────────────────────────────

    def _setup_eos_handlers(self) -> None:
        """注册 on_eos 回调以便发布事件。"""
        if self._bgm_player is not None:

            def _on_bgm_eos() -> None:
                self._emit(_EVT_BGM_END, channel="bgm", reason="eos")

            self._bgm_player.on_eos = _on_bgm_eos  # type: ignore[method-assign]

        if self._voice_player is not None:

            def _on_voice_eos() -> None:
                self._emit(_EVT_VOICE_END, channel="voice")

            self._voice_player.on_eos = _on_voice_eos  # type: ignore[method-assign]

    # ── 设备检测 ──────────────────────────────────────────

    @staticmethod
    def _detect_audio() -> bool:
        """探测音频设备是否可用。"""
        try:
            p = pyglet.media.Player()
            return True
        except Exception:
            return False

    # ── 内部工具 ──────────────────────────────────────────

    def _iter_players(self) -> list[pyglet.media.Player]:
        """返回所有播放器的扁平列表。"""
        players: list[pyglet.media.Player] = []
        if self._bgm_player is not None:
            players.append(self._bgm_player)
        if self._voice_player is not None:
            players.append(self._voice_player)
        players.extend(self._se_players)
        return players

    def _emit(self, event: str, **kwargs: Any) -> None:
        """通过事件总线发布事件（若已注入）。

        如需将 audio:* 事件提升为引擎级事件，
        可在 core.events.Event 枚举中新增别名。
        """
        if self._event_bus is not None:
            self._event_bus.emit(event, **kwargs)
