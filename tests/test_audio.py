"""
AudioManager 单元测试
=====================
全 mock pyglet.media.Player + clock，零音频设备依赖。
mock 环境由 tests/conftest.py 统一注入。
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from audio.audio_manager import AudioManager

# 引用 conftest 注入的 mock
_mock_pyglet = sys.modules["pyglet"]
_mock_pyglet_media = sys.modules["pyglet.media"]


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_mocks() -> None:
    """每个测试前重置 mock。"""
    for key in ("pyglet", "pyglet.media"):
        sys.modules[key].reset_mock()
    _mock_pyglet.media = _mock_pyglet_media  # type: ignore[attr-defined]
    _mock_pyglet.clock = MagicMock()  # type: ignore[attr-defined]
    _mock_pyglet_media.Player.return_value = MagicMock()


@pytest.fixture
def mock_source() -> MagicMock:
    return MagicMock()


@pytest.fixture
def am() -> AudioManager:
    """创建 AudioManager，注入 mock EventBus。"""
    bus = MagicMock()
    return AudioManager(event_bus=bus)


# ── 辅助：把 pyglet Player 当作 MagicMock 断言 ────────────

def _bgm(am: AudioManager) -> Any:
    return am._bgm_player


def _voice(am: AudioManager) -> Any:
    return am._voice_player


def _se_player(am: AudioManager, i: int) -> Any:
    return am._se_players[i]


# ── 1. BGM 播放 ──────────────────────────────────────────

def test_play_bgm(am: AudioManager, mock_source: MagicMock) -> None:
    am.play_bgm(mock_source, volume=0.8, loop=True)
    p = _bgm(am)
    assert p is not None
    p.queue.assert_called_once_with(mock_source)
    p.play.assert_called()
    assert p.loop is True
    assert p.volume == 0.8


# ── 2. BGM 立即停止 ──────────────────────────────────────

def test_stop_bgm_immediate(am: AudioManager, mock_source: MagicMock) -> None:
    am.play_bgm(mock_source)
    am.stop_bgm(fade_out=0.0)
    p = _bgm(am)
    assert p is not None
    p.pause.assert_called()


# ── 3. BGM 淡出 — fade_step ──────────────────────────────

def test_stop_bgm_fade_out(am: AudioManager, mock_source: MagicMock) -> None:
    am.play_bgm(mock_source, volume=0.8, loop=True)
    p = _bgm(am)
    assert p is not None
    p.volume = 0.8

    am.stop_bgm(fade_out=2.0)
    assert am._fade_active is True
    assert am._fade_duration == 2.0

    # 模拟 2 秒淡出
    am._fade_step(1.0)
    assert p.volume == pytest.approx(0.4)  # 降到一半

    am._fade_step(1.0)
    assert am._fade_active is False
    p.pause.assert_called()


# ── 4. Voice 播放 ────────────────────────────────────────

def test_play_voice(am: AudioManager, mock_source: MagicMock) -> None:
    am.play_voice(mock_source, volume=0.9)
    p = _voice(am)
    assert p is not None
    p.queue.assert_called_once_with(mock_source)
    p.play.assert_called()
    assert p.volume == 0.9


# ── 5. Voice 打断 ────────────────────────────────────────

def test_play_voice_interrupts(am: AudioManager, mock_source: MagicMock) -> None:
    am.play_voice(mock_source)
    p = _voice(am)
    assert p is not None
    p.playing = True

    src2 = MagicMock()
    am.play_voice(src2)
    p.pause.assert_called()
    p.queue.assert_called_with(src2)


# ── 6. SE 播放 + 轮转 ────────────────────────────────────

def test_play_se_round_robin(am: AudioManager, mock_source: MagicMock) -> None:
    assert am._se_index == 0
    am.play_se(mock_source)
    assert am._se_index == 1
    p0 = _se_player(am, 0)
    p0.queue.assert_called_once_with(mock_source)
    p0.play.assert_called()


# ── 7. SE 覆盖 ────────────────────────────────────────────

def test_play_se_wraps_around(am: AudioManager, mock_source: MagicMock) -> None:
    for _ in range(8):
        am.play_se(mock_source)
    assert am._se_index == 0
    # 第 9 次覆盖第 1 个
    am.play_se(mock_source)
    assert am._se_index == 1


# ── 8. set_volume ────────────────────────────────────────

def test_set_volume(am: AudioManager) -> None:
    am.set_volume("bgm", 0.5)
    assert am._volumes["bgm"] == 0.5
    p = _bgm(am)
    assert p is not None
    assert p.volume == 0.5


# ── 9. set_volume 无效通道 ───────────────────────────────

def test_set_volume_invalid_channel(am: AudioManager) -> None:
    with pytest.raises(ValueError, match="无效音频通道"):
        am.set_volume("master", 0.5)


# ── 10. pause_all / resume_all ────────────────────────────

def test_pause_resume_all(am: AudioManager, mock_source: MagicMock) -> None:
    am.play_bgm(mock_source)
    p = _bgm(am)
    assert p is not None
    p.playing = True

    am.pause_all()
    assert p in am._paused_players
    p.pause.assert_called()

    am.resume_all()
    assert len(am._paused_players) == 0
    p.play.assert_called()


# ── 11. 音频设备不可用 ───────────────────────────────────

def test_audio_unavailable_skips(mock_source: MagicMock) -> None:
    with patch.object(AudioManager, "_detect_audio", return_value=False):
        am2 = AudioManager()
        am2.play_bgm(mock_source)
        am2.play_voice(mock_source)
        am2.play_se(mock_source)
        am2.pause_all()
        am2.resume_all()
        # 无播放器，不应崩溃
        assert am2._bgm_player is None


# ── 12. pause_all 只恢复当时在播的 ──────────────────────

def test_resume_only_restores_paused(am: AudioManager, mock_source: MagicMock) -> None:
    am.play_bgm(mock_source)
    p = _bgm(am)
    p.playing = True

    am.pause_all()
    assert p in am._paused_players  # pause_all 记录了它

    # 手动清除 paused_players 模拟不在记录中的 player
    am._paused_players.clear()
    # 重置 mock 计数以排除 play_bgm 的初始 play()
    p.play.reset_mock()
    am.resume_all()
    p.play.assert_not_called()


# ── 13. 事件发布 ─────────────────────────────────────────

def test_bgm_start_event(am: AudioManager, mock_source: MagicMock) -> None:
    am.play_bgm(mock_source)
    bus: Any = am._event_bus
    assert bus is not None
    bus.emit.assert_called()


def test_bgm_end_event(am: AudioManager, mock_source: MagicMock) -> None:
    am.play_bgm(mock_source)
    am.stop_bgm(fade_out=0.0)
    bus: Any = am._event_bus
    assert bus is not None
    bus.emit.assert_called()
