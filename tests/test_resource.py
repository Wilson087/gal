"""
ResourceManager 单元测试
========================
全部 mock pyglet / PIL / 文件系统，零 GPU 依赖，CI 可跑。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── mock pyglet（必须在导入 ResourceManager 之前注入）─────
_mock_pyglet = MagicMock()
_mock_pyglet_image = MagicMock()
_mock_pyglet_media = MagicMock()
sys.modules["pyglet"] = _mock_pyglet
sys.modules["pyglet.image"] = _mock_pyglet_image
sys.modules["pyglet.media"] = _mock_pyglet_media
# "import pyglet.image" 实际走 _mock_pyglet.image 属性 → 需绑定
_mock_pyglet.image = _mock_pyglet_image
_mock_pyglet.media = _mock_pyglet_media

# ── mock PIL ─────────────────────────────────────────────
_mock_pil = MagicMock()
_mock_pil_image = MagicMock()
sys.modules["PIL"] = _mock_pil
sys.modules["PIL.Image"] = _mock_pil_image

from systems.resource import (
    ResourceManager,
    _PreloadedImage,
    _PreloadedAudio,
)


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_mocks() -> None:
    """每个测试前重置 mock 状态。"""
    _mock_pyglet.reset_mock()
    _mock_pyglet_image.reset_mock()
    _mock_pyglet_media.reset_mock()
    _mock_pil.reset_mock()
    _mock_pil_image.reset_mock()
    # reset_mock 保留子属性，但确保 image/media 绑定仍在
    _mock_pyglet.image = _mock_pyglet_image
    _mock_pyglet.media = _mock_pyglet_media
    # reset_mock() 不清 side_effect / return_value，手动清除避免跨测试泄露
    _mock_pyglet_image.load.side_effect = None
    _mock_pyglet_image.load.return_value = MagicMock()
    _mock_pyglet_media.load.side_effect = None
    _mock_pyglet_media.load.return_value = MagicMock()


@pytest.fixture
def mock_image_data() -> MagicMock:
    """返回一个模拟的 ImageData 对象。"""
    img = MagicMock()
    img.get_texture.return_value = None
    return img


@pytest.fixture
def mock_audio_source() -> MagicMock:
    """返回一个模拟的 Source 对象。"""
    return MagicMock()


@pytest.fixture
def rm(tmp_path: Path) -> ResourceManager:
    """创建使用真实临时目录的 ResourceManager。"""
    return ResourceManager(data_root=str(tmp_path), max_images=3, max_audio=2)


# ── 1. 缓存命中 ──────────────────────────────────────────

def test_cache_hit(rm: ResourceManager) -> None:
    """同一路径两次 get_image，第二次命中缓存，不重复加载。"""
    with patch.object(Path, "is_file", return_value=True):
        img1 = rm.get_image("bg/room.png")
        img2 = rm.get_image("bg/room.png")

    assert img1 is img2  # 同一对象（缓存命中）
    assert _mock_pyglet_image.load.call_count == 1  # 仅加载一次


# ── 2. LRU 逐出 ──────────────────────────────────────────

def test_lru_eviction(rm: ResourceManager) -> None:
    """max_images=3，加载 4 张图像，第一张被逐出。"""
    imgs = []
    for _ in range(4):
        m = MagicMock()
        m.get_texture.return_value = None
        imgs.append(m)
    _mock_pyglet_image.load.side_effect = imgs

    with patch.object(Path, "is_file", return_value=True):
        rm.get_image("a.png")
        rm.get_image("b.png")
        rm.get_image("c.png")
        rm.get_image("d.png")  # a 被逐出

    assert "a.png" not in rm._image_cache
    assert "b.png" in rm._image_cache
    assert "c.png" in rm._image_cache
    assert "d.png" in rm._image_cache


# ── 3. 文件不存在 ────────────────────────────────────────

def test_file_not_found(rm: ResourceManager) -> None:
    """不存在的路径返回 None。"""
    with patch.object(Path, "is_file", return_value=False):
        result = rm.get_image("missing.png")

    assert result is None
    _mock_pyglet_image.load.assert_not_called()


# ── 4. 后台预加载图像 ────────────────────────────────────

def test_preload_image(rm: ResourceManager) -> None:
    """preload_image 后 worker 将 _PreloadedImage 入缓存，
    主线程 get 时自动转为 ImageData。"""
    pil_mock = MagicMock()
    pil_mock.width = 64
    pil_mock.height = 64
    pil_mock.tobytes.return_value = b"\xff" * (64 * 64 * 4)
    _mock_pil_image.open.return_value.convert.return_value = pil_mock

    with patch.object(Path, "is_file", return_value=True):
        rm.preload_image("bg/room.png")
        time.sleep(0.3)
        result = rm.get_image("bg/room.png")

    # ImageData 被调用以将预加载数据转为 pyglet 对象
    _mock_pyglet_image.ImageData.assert_called_once()


# ── 5. clear_scene(keep_audio=True) ────────────────────────

def test_clear_scene_keep_audio(
    rm: ResourceManager, mock_image_data: MagicMock, mock_audio_source: MagicMock
) -> None:
    """清图像，保留音频。"""
    _mock_pyglet_image.load.return_value = mock_image_data
    _mock_pyglet_media.load.return_value = mock_audio_source

    with patch.object(Path, "is_file", return_value=True):
        rm.get_image("bg.png")
        rm.get_audio("bgm.ogg")
        assert len(rm._image_cache) == 1
        assert len(rm._audio_cache) == 1

        rm.clear_scene(keep_audio=True)

    assert len(rm._image_cache) == 0
    assert len(rm._audio_cache) == 1


# ── 6. clear_scene(keep_audio=False) ───────────────────────

def test_clear_scene_all(
    rm: ResourceManager, mock_image_data: MagicMock, mock_audio_source: MagicMock
) -> None:
    """全清。"""
    _mock_pyglet_image.load.return_value = mock_image_data
    _mock_pyglet_media.load.return_value = mock_audio_source

    with patch.object(Path, "is_file", return_value=True):
        rm.get_image("bg.png")
        rm.get_audio("bgm.ogg")
        rm.clear_scene(keep_audio=False)

    assert len(rm._image_cache) == 0
    assert len(rm._audio_cache) == 0


# ── 7. 路径穿越 ───────────────────────────────────────────

def test_path_traversal_rejected(rm: ResourceManager) -> None:
    """路径穿越 DATA_ROOT 抛出 ValueError。"""
    with pytest.raises(ValueError, match="路径穿越"):
        rm._resolve_path("../etc/passwd")


# ── 8. 逐出时 dispose ──────────────────────────────────────

def test_dispose_called_on_evict(rm: ResourceManager) -> None:
    """LRU 逐出时调用纹理 delete。"""
    tex_mock = MagicMock()
    img_with_tex = MagicMock()
    img_with_tex.get_texture.return_value = tex_mock

    imgs: list[MagicMock] = [img_with_tex]
    for _ in range(3):
        m = MagicMock()
        m.get_texture.return_value = None
        imgs.append(m)

    with patch.object(
        _mock_pyglet_image, "load", side_effect=imgs
    ), patch.object(Path, "is_file", return_value=True):
        rm.get_image("a.png")
        rm.get_image("b.png")
        rm.get_image("c.png")
        rm.get_image("d.png")  # a 被逐出

    tex_mock.delete.assert_called_once()


# ── 9. 场景版本过滤旧任务 ─────────────────────────────────

def test_scene_version_skips_stale_preload(rm: ResourceManager) -> None:
    """旧场景版本的预加载任务被 worker 丢弃。"""
    with patch.object(Path, "is_file", return_value=True):
        # 场景 0
        rm.preload_image("v0.png")
        # 模拟 clear_scene → 版本号递增
        rm._scene_version += 1
        rm.preload_image("v1.png")
        time.sleep(0.5)

    # v0.png 不应在缓存中（任务被丢弃）
    assert "v0.png" not in rm._image_cache


# ── 10. 并发预加载 + clear ─────────────────────────────────

def test_concurrent_preload_and_clear(rm: ResourceManager) -> None:
    """一边 preload 多个文件，一边立刻 clear_scene，无死锁，缓存最终空。"""
    pil_mock = MagicMock()
    pil_mock.width = 32
    pil_mock.height = 32
    pil_mock.tobytes.return_value = b"\x00" * (32 * 32 * 4)
    _mock_pil_image.open.return_value.convert.return_value = pil_mock

    with patch.object(Path, "is_file", return_value=True):
        for i in range(5):
            rm.preload_image(f"img_{i}.png")

        # 立即清场景
        rm.clear_scene(keep_audio=False)
        time.sleep(0.3)

    assert len(rm._image_cache) == 0


# ── 11. shutdown ───────────────────────────────────────────

def test_shutdown_clean(tmp_path: Path) -> None:
    """shutdown 排空队列 + join worker。"""
    r = ResourceManager(data_root=str(tmp_path), max_images=2, max_audio=1)
    assert r._worker.is_alive()

    r.shutdown()

    # daemon 线程可能在退出时仍 alive，但不能有异常
    assert not r._running


# ── 12. 预加载音频 get 转换 ───────────────────────────────

def test_preload_audio_conversion(rm: ResourceManager) -> None:
    """_PreloadedAudio → get_audio 时通过 BytesIO 转 Source。"""
    with patch.object(Path, "is_file", return_value=True), patch.object(
        Path, "read_bytes", return_value=b"FAKE_OGG_DATA"
    ):
        rm.preload_audio("bgm/title.ogg")
        time.sleep(0.3)
        result = rm.get_audio("bgm/title.ogg")

    # pyglet.media.load 被调用以创建 Source
    _mock_pyglet_media.load.assert_called_once()
    assert result is not None


# ── 13. release_image ─────────────────────────────────────

def test_release_image_dispose(rm: ResourceManager) -> None:
    """release_image 从缓存移除并 dispose。"""
    tex_mock = MagicMock()
    mock_img = MagicMock()
    mock_img.get_texture.return_value = tex_mock

    with patch.object(
        _mock_pyglet_image, "load", return_value=mock_img
    ), patch.object(Path, "is_file", return_value=True):
        rm.get_image("bg.png")
        assert "bg.png" in rm._image_cache

        rm.release_image("bg.png")
        assert "bg.png" not in rm._image_cache

    tex_mock.delete.assert_called_once()
