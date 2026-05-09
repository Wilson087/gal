"""
ResourceManager 单元测试
========================
全部 mock pyglet / PIL / 文件系统，零 GPU 依赖，CI 可跑。
"""

from __future__ import annotations

import sys
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import tests._mocks  # noqa: F401 — pyglet + PIL mock setup

from src.systems.resource import (
    ResourceManager,
    _PreloadedImage,
    _PreloadedAudio,
)

# 引用 _mocks.py 注入的 mock
_mock_pyglet = sys.modules["pyglet"]
_mock_pyglet_image = sys.modules["pyglet.image"]
_mock_pyglet_media = sys.modules["pyglet.media"]
_mock_pil_image = sys.modules["PIL.Image"]


class TestResourceManager(unittest.TestCase):
    """ResourceManager LRU 缓存 + 预加载 测试。"""

    def setUp(self) -> None:
        """每个测试前重置 mock 并创建 ResourceManager。"""
        for key in ("pyglet", "pyglet.image", "pyglet.media", "PIL", "PIL.Image"):
            sys.modules[key].reset_mock()
        _mock_pyglet.image = _mock_pyglet_image
        _mock_pyglet.media = _mock_pyglet_media
        _mock_pyglet_image.load.side_effect = None
        _mock_pyglet_image.load.return_value = MagicMock()
        _mock_pyglet_media.load.side_effect = None
        _mock_pyglet_media.load.return_value = MagicMock()

        self._tmpdir = Path(tempfile.mkdtemp())
        self.rm = ResourceManager(data_root=str(self._tmpdir), max_images=3, max_audio=2)

    def tearDown(self) -> None:
        self.rm.shutdown()
        shutil.rmtree(str(self._tmpdir), ignore_errors=True)

    @property
    def _mock_image_data(self) -> MagicMock:
        img = MagicMock()
        img.get_texture.return_value = None
        return img

    # ── 1. 缓存命中 ──────────────────────────────────────────

    def test_cache_hit(self) -> None:
        """同一路径两次 get_image，第二次命中缓存，不重复加载。"""
        with patch.object(Path, "is_file", return_value=True):
            img1 = self.rm.get_image("bg/room.png")
            img2 = self.rm.get_image("bg/room.png")

        self.assertIs(img1, img2)  # 同一对象（缓存命中）
        self.assertEqual(_mock_pyglet_image.load.call_count, 1)  # 仅加载一次

    # ── 2. LRU 逐出 ──────────────────────────────────────────

    def test_lru_eviction(self) -> None:
        """max_images=3，加载 4 张图像，第一张被逐出。"""
        imgs = []
        for _ in range(4):
            m = MagicMock()
            m.get_texture.return_value = None
            imgs.append(m)
        _mock_pyglet_image.load.side_effect = imgs

        with patch.object(Path, "is_file", return_value=True):
            self.rm.get_image("a.png")
            self.rm.get_image("b.png")
            self.rm.get_image("c.png")
            self.rm.get_image("d.png")  # a 被逐出

        self.assertNotIn("a.png", self.rm._image_cache)
        self.assertIn("b.png", self.rm._image_cache)
        self.assertIn("c.png", self.rm._image_cache)
        self.assertIn("d.png", self.rm._image_cache)

    # ── 3. 文件不存在 ────────────────────────────────────────

    def test_file_not_found(self) -> None:
        """不存在的路径返回 None。"""
        with patch.object(Path, "is_file", return_value=False):
            result = self.rm.get_image("missing.png")

        self.assertIsNone(result)
        _mock_pyglet_image.load.assert_not_called()

    # ── 4. 后台预加载图像 ────────────────────────────────────

    def test_preload_image(self) -> None:
        """preload_image 后 worker 将 _PreloadedImage 入缓存，
        主线程 get 时自动转为 ImageData。"""
        pil_mock = MagicMock()
        pil_mock.width = 64
        pil_mock.height = 64
        pil_mock.tobytes.return_value = b"\xff" * (64 * 64 * 4)
        _mock_pil_image.open.return_value.convert.return_value = pil_mock

        with patch.object(Path, "is_file", return_value=True):
            self.rm.preload_image("bg/room.png")
            time.sleep(0.3)
            result = self.rm.get_image("bg/room.png")

        # ImageData 被调用以将预加载数据转为 pyglet 对象
        _mock_pyglet_image.ImageData.assert_called_once()

    # ── 5. clear_scene(keep_audio=True) ────────────────────────

    def test_clear_scene_keep_audio(self) -> None:
        """清图像，保留音频。"""
        _mock_pyglet_image.load.return_value = self._mock_image_data
        _mock_pyglet_media.load.return_value = MagicMock()

        with patch.object(Path, "is_file", return_value=True):
            self.rm.get_image("bg.png")
            self.rm.get_audio("bgm.ogg")
            self.assertEqual(len(self.rm._image_cache), 1)
            self.assertEqual(len(self.rm._audio_cache), 1)

            self.rm.clear_scene(keep_audio=True)

        self.assertEqual(len(self.rm._image_cache), 0)
        self.assertEqual(len(self.rm._audio_cache), 1)

    # ── 6. clear_scene(keep_audio=False) ───────────────────────

    def test_clear_scene_all(self) -> None:
        """全清。"""
        _mock_pyglet_image.load.return_value = self._mock_image_data
        _mock_pyglet_media.load.return_value = MagicMock()

        with patch.object(Path, "is_file", return_value=True):
            self.rm.get_image("bg.png")
            self.rm.get_audio("bgm.ogg")
            self.rm.clear_scene(keep_audio=False)

        self.assertEqual(len(self.rm._image_cache), 0)
        self.assertEqual(len(self.rm._audio_cache), 0)

    # ── 7. 路径穿越 ───────────────────────────────────────────

    def test_path_traversal_rejected(self) -> None:
        """路径穿越 DATA_ROOT 抛出 ValueError。"""
        with self.assertRaises(ValueError) as ctx:
            self.rm._resolve_path("../etc/passwd")
        self.assertIn("路径穿越", str(ctx.exception))

    # ── 8. 逐出时 dispose ──────────────────────────────────────

    def test_dispose_called_on_evict(self) -> None:
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
            self.rm.get_image("a.png")
            self.rm.get_image("b.png")
            self.rm.get_image("c.png")
            self.rm.get_image("d.png")  # a 被逐出

        tex_mock.delete.assert_called_once()

    # ── 9. 场景版本过滤旧任务 ─────────────────────────────────

    def test_scene_version_skips_stale_preload(self) -> None:
        """旧场景版本的预加载任务被 worker 丢弃。"""
        with patch.object(Path, "is_file", return_value=True):
            # 场景 0
            self.rm.preload_image("v0.png")
            # 模拟 clear_scene → 版本号递增
            self.rm._scene_version += 1
            self.rm.preload_image("v1.png")
            time.sleep(0.5)

        # v0.png 不应在缓存中（任务被丢弃）
        self.assertNotIn("v0.png", self.rm._image_cache)

    # ── 10. 并发预加载 + clear ─────────────────────────────────

    def test_concurrent_preload_and_clear(self) -> None:
        """一边 preload 多个文件，一边立刻 clear_scene，无死锁，缓存最终空。"""
        pil_mock = MagicMock()
        pil_mock.width = 32
        pil_mock.height = 32
        pil_mock.tobytes.return_value = b"\x00" * (32 * 32 * 4)
        _mock_pil_image.open.return_value.convert.return_value = pil_mock

        with patch.object(Path, "is_file", return_value=True):
            for i in range(5):
                self.rm.preload_image(f"img_{i}.png")

            # 立即清场景
            self.rm.clear_scene(keep_audio=False)
            time.sleep(0.3)

        self.assertEqual(len(self.rm._image_cache), 0)

    # ── 11. shutdown ───────────────────────────────────────────

    def test_shutdown_clean(self) -> None:
        """shutdown 排空队列 + join worker。"""
        r = ResourceManager(data_root=str(self._tmpdir), max_images=2, max_audio=1)
        self.assertTrue(r._worker.is_alive())

        r.shutdown()

        # daemon 线程可能在退出时仍 alive，但不能有异常
        self.assertFalse(r._running)

    # ── 12. 预加载音频 get 转换 ───────────────────────────────

    def test_preload_audio_conversion(self) -> None:
        """_PreloadedAudio → get_audio 时通过 BytesIO 转 Source。"""
        with patch.object(Path, "is_file", return_value=True), patch.object(
            Path, "read_bytes", return_value=b"FAKE_OGG_DATA"
        ):
            self.rm.preload_audio("bgm/title.ogg")
            time.sleep(0.3)
            result = self.rm.get_audio("bgm/title.ogg")

        # pyglet.media.load 被调用以创建 Source
        _mock_pyglet_media.load.assert_called_once()
        self.assertIsNotNone(result)

    # ── 13. release_image ─────────────────────────────────────

    def test_release_image_dispose(self) -> None:
        """release_image 从缓存移除并 dispose。"""
        tex_mock = MagicMock()
        mock_img = MagicMock()
        mock_img.get_texture.return_value = tex_mock

        with patch.object(
            _mock_pyglet_image, "load", return_value=mock_img
        ), patch.object(Path, "is_file", return_value=True):
            self.rm.get_image("bg.png")
            self.assertIn("bg.png", self.rm._image_cache)

            self.rm.release_image("bg.png")
            self.assertNotIn("bg.png", self.rm._image_cache)

        tex_mock.delete.assert_called_once()
