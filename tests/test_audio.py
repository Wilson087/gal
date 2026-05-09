"""
AudioManager 单元测试
=====================
全 mock pyglet.media.Player + clock，零音频设备依赖。
mock 环境由 tests/_mocks.py 注入。
"""

from __future__ import annotations

import sys
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

import tests._mocks  # noqa: F401 — pyglet mock setup

from src.audio.audio_manager import AudioManager

# 引用 _mocks.py 注入的 mock
_mock_pyglet = sys.modules["pyglet"]
_mock_pyglet_media = sys.modules["pyglet.media"]


def _bgm(am: AudioManager) -> Any:
    return am._bgm_player


def _voice(am: AudioManager) -> Any:
    return am._voice_player


def _se_player(am: AudioManager, i: int) -> Any:
    return am._se_players[i]


class TestAudioManager(unittest.TestCase):
    """AudioManager 3 通道音频测试。"""

    def setUp(self) -> None:
        """每个测试前重置 mock 并创建 AudioManager。"""
        for key in ("pyglet", "pyglet.media"):
            sys.modules[key].reset_mock()
        _mock_pyglet.media = _mock_pyglet_media
        _mock_pyglet.clock = MagicMock()
        _mock_pyglet_media.Player.return_value = MagicMock()

        bus = MagicMock()
        self.am = AudioManager(event_bus=bus)

    @property
    def _mock_source(self) -> MagicMock:
        return MagicMock()

    # ── 1. BGM 播放 ──────────────────────────────────────────

    def test_play_bgm(self) -> None:
        src = self._mock_source
        self.am.play_bgm(src, volume=0.8, loop=True)
        p = _bgm(self.am)
        self.assertIsNotNone(p)
        p.queue.assert_called_once_with(src)
        p.play.assert_called()
        self.assertTrue(p.loop)
        self.assertEqual(p.volume, 0.8)

    # ── 2. BGM 立即停止 ──────────────────────────────────────

    def test_stop_bgm_immediate(self) -> None:
        src = self._mock_source
        self.am.play_bgm(src)
        self.am.stop_bgm(fade_out=0.0)
        p = _bgm(self.am)
        self.assertIsNotNone(p)
        p.pause.assert_called()

    # ── 3. BGM 淡出 — fade_step ──────────────────────────────

    def test_stop_bgm_fade_out(self) -> None:
        src = self._mock_source
        self.am.play_bgm(src, volume=0.8, loop=True)
        p = _bgm(self.am)
        self.assertIsNotNone(p)
        p.volume = 0.8

        self.am.stop_bgm(fade_out=2.0)
        self.assertTrue(self.am._fade_active)
        self.assertEqual(self.am._fade_duration, 2.0)

        # 模拟 2 秒淡出
        self.am._fade_step(1.0)
        self.assertAlmostEqual(p.volume, 0.4)  # 降到一半

        self.am._fade_step(1.0)
        self.assertFalse(self.am._fade_active)
        p.pause.assert_called()

    # ── 4. Voice 播放 ────────────────────────────────────────

    def test_play_voice(self) -> None:
        src = self._mock_source
        self.am.play_voice(src, volume=0.9)
        p = _voice(self.am)
        self.assertIsNotNone(p)
        p.queue.assert_called_once_with(src)
        p.play.assert_called()
        self.assertEqual(p.volume, 0.9)

    # ── 5. Voice 打断 ────────────────────────────────────────

    def test_play_voice_interrupts(self) -> None:
        src = self._mock_source
        self.am.play_voice(src)
        p = _voice(self.am)
        self.assertIsNotNone(p)
        p.playing = True

        src2 = MagicMock()
        self.am.play_voice(src2)
        p.pause.assert_called()
        p.queue.assert_called_with(src2)

    # ── 6. SE 播放 + 轮转 ────────────────────────────────────

    def test_play_se_round_robin(self) -> None:
        src = self._mock_source
        self.assertEqual(self.am._se_index, 0)
        self.am.play_se(src)
        self.assertEqual(self.am._se_index, 1)
        p0 = _se_player(self.am, 0)
        p0.queue.assert_called_once_with(src)
        p0.play.assert_called()

    # ── 7. SE 覆盖 ────────────────────────────────────────────

    def test_play_se_wraps_around(self) -> None:
        src = self._mock_source
        for _ in range(8):
            self.am.play_se(src)
        self.assertEqual(self.am._se_index, 0)
        # 第 9 次覆盖第 1 个
        self.am.play_se(src)
        self.assertEqual(self.am._se_index, 1)

    # ── 8. set_volume ────────────────────────────────────────

    def test_set_volume(self) -> None:
        self.am.set_volume("bgm", 0.5)
        self.assertEqual(self.am._volumes["bgm"], 0.5)
        p = _bgm(self.am)
        self.assertIsNotNone(p)
        self.assertEqual(p.volume, 0.5)

    # ── 9. set_volume 无效通道 ───────────────────────────────

    def test_set_volume_invalid_channel(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.am.set_volume("master", 0.5)
        self.assertIn("无效音频通道", str(ctx.exception))

    # ── 10. pause_all / resume_all ────────────────────────────

    def test_pause_resume_all(self) -> None:
        src = self._mock_source
        self.am.play_bgm(src)
        p = _bgm(self.am)
        self.assertIsNotNone(p)
        p.playing = True

        self.am.pause_all()
        self.assertIn(p, self.am._paused_players)
        p.pause.assert_called()

        self.am.resume_all()
        self.assertEqual(len(self.am._paused_players), 0)
        p.play.assert_called()

    # ── 11. 音频设备不可用 ───────────────────────────────────

    def test_audio_unavailable_skips(self) -> None:
        with patch.object(AudioManager, "_detect_audio", return_value=False):
            am2 = AudioManager()
            src = self._mock_source
            am2.play_bgm(src)
            am2.play_voice(src)
            am2.play_se(src)
            am2.pause_all()
            am2.resume_all()
            # 无播放器，不应崩溃
            self.assertIsNone(am2._bgm_player)

    # ── 12. pause_all 只恢复当时在播的 ──────────────────────

    def test_resume_only_restores_paused(self) -> None:
        src = self._mock_source
        self.am.play_bgm(src)
        p = _bgm(self.am)
        p.playing = True

        self.am.pause_all()
        self.assertIn(p, self.am._paused_players)

        # 手动清除 paused_players 模拟不在记录中的 player
        self.am._paused_players.clear()
        # 重置 mock 计数以排除 play_bgm 的初始 play()
        p.play.reset_mock()
        self.am.resume_all()
        p.play.assert_not_called()

    # ── 13. 事件发布 ─────────────────────────────────────────

    def test_bgm_start_event(self) -> None:
        src = self._mock_source
        self.am.play_bgm(src)
        bus: Any = self.am._event_bus
        self.assertIsNotNone(bus)
        bus.emit.assert_called()

    def test_bgm_end_event(self) -> None:
        src = self._mock_source
        self.am.play_bgm(src)
        self.am.stop_bgm(fade_out=0.0)
        bus: Any = self.am._event_bus
        self.assertIsNotNone(bus)
        bus.emit.assert_called()
