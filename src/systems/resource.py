"""
Resource Manager — 惰性加载 + LRU 缓存 + 后台预加载
=====================================================
管理图像（pyglet.image.ImageData）和音频（pyglet.media.Source）。

后台预加载机制：
    后台 daemon 线程使用 PIL 解码图像为原始像素 / 读取音频文件字节，
    存为 _PreloadedImage / _PreloadedAudio 中间对象，不涉及 OpenGL 调用。
    主线程 get_image/get_audio 时自动将中间对象转为 pyglet 对象。

可选依赖：
    PIL（Pillow）用于后台图像预加载解码。若未安装，preload_image 降级为
    后台读文件字节 + 主线程 pyglet.image.load，功能正常但预加载效果减弱。
    音频预加载仅需标准库，无额外依赖。

用法::

    from systems.resource import ResourceManager

    rm = ResourceManager(data_root="resources", max_images=32, max_audio=16)
    img = rm.get_image("images/bg/classroom.png")
    bgm = rm.get_audio("bgm/title.ogg")
    rm.clear_scene(keep_audio=True)
    rm.shutdown()
"""

from __future__ import annotations

import gc
import logging
import os
import queue
import threading
from collections import OrderedDict
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from types import ModuleType
from typing import Any, TYPE_CHECKING

# ── pyglet imports ────────────────────────────────────────

import pyglet
import pyglet.image
import pyglet.media

# ── PIL import（可选）─────────────────────────────────────
try:
    from PIL import Image as PILImage
    _HAS_PIL = True
except ImportError:
    if TYPE_CHECKING:
        from PIL import Image as PILImage
    else:
        PILImage = None
    _HAS_PIL = False

logger = logging.getLogger(__name__)

# ── 类型别名 ──────────────────────────────────────────────


@dataclass
class _PreloadedImage:
    """后台线程解码的原始像素数据。

    不含任何 pyglet / OpenGL 对象，线程安全。主线程 get_image()
    取到该类型时，用 ``pyglet.image.ImageData`` 包装（纯 CPU 操作）。
    """

    width: int
    height: int
    data: bytes
    format: str = "RGBA"


@dataclass
class _PreloadedAudio:
    """后台线程读取的音频文件字节。

    不含 pyglet.media.Source（需主线程构造）。主线程 get_audio()
    自动通过 BytesIO 喂给 pyglet.media.load。
    """

    data: bytes
    extension: str  # "ogg" | "mp3" | "wav" 等


# 缓存值可能为 pyglet 对象或预加载中间对象
_ImageCacheValue = (
    "pyglet.image.ImageData | _PreloadedImage"  # 仅文档用；运行时用 Any
)
_AudioCacheValue = (
    "pyglet.media.Source | _PreloadedAudio"
)

# 预加载队列元素: (scene_version, kind, relative_path)
_PreloadTask = tuple[int, str, str]


class ResourceManager:
    """资源管理器 —— 惰性加载 + LRU 淘汰 + 后台预加载。

    特性：
    - 图像和音频使用独立 LRU 缓存（OrderedDict）。
    - 后台 daemon 线程处理预加载任务，不阻塞主线程。
    - PIL 解码在后台完成，主线程仅做不动 OpenGL 的 ImageData 包装。
    - 路径穿越安全检查。
    - 场景切换时 clear_scene() 通过 scene_version 自动丢弃旧任务。
    """

    def __init__(
        self,
        data_root: str = "resources",
        max_images: int = 32,
        max_audio: int = 16,
    ) -> None:
        self._data_root: Path = Path(data_root).resolve()
        self._max_images: int = max_images
        self._max_audio: int = max_audio

        # LRU 缓存
        self._image_cache: OrderedDict[str, pyglet.image.ImageData | _PreloadedImage] = (
            OrderedDict()
        )
        self._audio_cache: OrderedDict[str, pyglet.media.Source | _PreloadedAudio] = (
            OrderedDict()
        )

        # 线程安全
        self._lock: threading.Lock = threading.Lock()
        self._queue: queue.Queue[_PreloadTask] = queue.Queue()
        self._running: bool = True
        self._scene_version: int = 0

        # 后台 worker daemon
        self._worker: threading.Thread = threading.Thread(
            target=self._worker_loop,
            name="resource-preloader",
            daemon=True,
        )
        self._worker.start()

        logger.info(
            "ResourceManager 已初始化: root=%s, max_images=%d, max_audio=%d, PIL=%s",
            self._data_root, max_images, max_audio, _HAS_PIL,
        )

    # ── 公开 API ──────────────────────────────────────────

    def get_image(self, path: str) -> pyglet.image.ImageData | None:
        """获取图像资源（惰性加载 + LRU 缓存）。

        若缓存命中且值为 _PreloadedImage，主线程安全转为 ImageData。

        Args:
            path: 相对 DATA_ROOT 的路径，如 ``"images/bg/classroom.png"``。

        Returns:
            ImageData 或 None（文件不存在 / 格式错误）。
        """
        key = _path_to_key(path)
        with self._lock:
            cached = self._image_cache.get(key)
            if cached is not None:
                self._touch(self._image_cache, key)
                if isinstance(cached, _PreloadedImage):
                    img = self._preloaded_to_image(cached)
                    self._image_cache[key] = img
                    return img
                return cached

        return self._load_image_sync(key, path)

    def get_audio(self, path: str) -> pyglet.media.Source | None:
        """获取音频资源（惰性加载 + LRU 缓存）。

        若缓存命中且值为 _PreloadedAudio，通过 BytesIO 构造 Source。

        Args:
            path: 相对 DATA_ROOT 的路径，如 ``"bgm/title.ogg"``。

        Returns:
            Source 或 None（文件不存在 / 格式错误）。
        """
        key = _path_to_key(path)
        with self._lock:
            cached = self._audio_cache.get(key)
            if cached is not None:
                self._touch(self._audio_cache, key)
                if isinstance(cached, _PreloadedAudio):
                    src = self._preloaded_to_audio(cached)
                    self._audio_cache[key] = src
                    return src
                return cached

        return self._load_audio_sync(key, path)

    def preload_image(self, path: str) -> None:
        """提交图像预加载任务到后台队列。

        Args:
            path: 相对 DATA_ROOT 的路径。
        """
        key = _path_to_key(path)
        with self._lock:
            if key in self._image_cache:
                return  # 已缓存，无需预加载
        self._queue.put((self._scene_version, "image", path))

    def preload_audio(self, path: str) -> None:
        """提交音频预加载任务到后台队列。

        Args:
            path: 相对 DATA_ROOT 的路径。
        """
        key = _path_to_key(path)
        with self._lock:
            if key in self._audio_cache:
                return
        self._queue.put((self._scene_version, "audio", path))

    def release_image(self, path: str) -> None:
        """主动释放指定图像缓存。

        Args:
            path: 相对 DATA_ROOT 的路径。
        """
        key = _path_to_key(path)
        with self._lock:
            cached = self._image_cache.pop(key, None)
        if cached is not None:
            self._dispose_image(cached)
            logger.debug("图像已释放: %s", key)

    def release_audio(self, path: str) -> None:
        """主动释放指定音频缓存。

        Args:
            path: 相对 DATA_ROOT 的路径。
        """
        key = _path_to_key(path)
        with self._lock:
            cached = self._audio_cache.pop(key, None)
        if cached is not None:
            self._dispose_audio(cached)
            logger.debug("音频已释放: %s", key)

    def clear_scene(self, keep_audio: bool = True) -> None:
        """清空场景资源。

        1. 递增 scene_version 使 worker 丢弃旧场景的预加载任务。
        2. 排空队列中当前版本之前的所有任务。
        3. 逐个 dispose 图像缓存（若 keep_audio=False 也清理音频）。
        4. 触发 gc.collect() 辅助回收 GPU / 内存。

        Args:
            keep_audio: True 时保留 BGM / 语音缓存（默认）。
        """
        with self._lock:
            self._scene_version += 1
            # 排空队列中属于旧版本的任务
            self._drain_queue_unsafe()

            # 图像
            for img in self._image_cache.values():
                self._dispose_image(img)
            self._image_cache.clear()

            # 音频
            if not keep_audio:
                for src in self._audio_cache.values():
                    self._dispose_audio(src)
                self._audio_cache.clear()

        gc.collect()
        logger.debug(
            "clear_scene done (keep_audio=%s, version=%d)",
            keep_audio, self._scene_version,
        )

    def shutdown(self) -> None:
        """安全关闭资源管理器。

        - 停止后台 worker。
        - 排空队列。
        - 清空所有缓存并释放。
        - daemon=True 保证即使 join 超时，进程退出时 OS 也会回收线程。
        """
        logger.info("ResourceManager 正在关闭...")
        self._running = False
        # 排空队列让 worker 尽快退出
        with self._lock:
            self._drain_queue_unsafe()
        self._worker.join(timeout=2.0)
        if self._worker.is_alive():
            logger.warning("Worker 线程未在 2 秒内退出（daemon 将随进程终止）")
        self.clear_scene(keep_audio=False)
        logger.info("ResourceManager 已关闭")

    # ── 同步加载 ──────────────────────────────────────────

    def _load_image_sync(self, key: str, path: str) -> pyglet.image.ImageData | None:
        """主线程同步加载图像（缓存未命中时）。"""
        try:
            full_path = self._resolve_path(path)
        except (ValueError, FileNotFoundError):
            return None
        try:
            img = pyglet.image.load(str(full_path))
        except Exception:
            logger.error("图像加载失败: %s", full_path, exc_info=True)
            return None
        with self._lock:
            self._insert_image_lru(key, img)  # type: ignore[arg-type]
        return img  # type: ignore[return-value]

    def _load_audio_sync(self, key: str, path: str) -> pyglet.media.Source | None:
        """主线程同步加载音频（缓存未命中时）。"""
        try:
            full_path = self._resolve_path(path)
        except (ValueError, FileNotFoundError):
            return None
        try:
            src = pyglet.media.load(str(full_path))
        except Exception:
            logger.error("音频加载失败: %s", full_path, exc_info=True)
            return None
        with self._lock:
            self._insert_audio_lru(key, src)
        return src

    # ── 路径安全 ──────────────────────────────────────────

    def _resolve_path(self, relative_path: str) -> Path:
        """安全解析相对路径，禁止越出 DATA_ROOT。

        Args:
            relative_path: 相对于 DATA_ROOT 的文件路径。

        Returns:
            解析后的绝对路径。

        Raises:
            ValueError: 路径穿越 DATA_ROOT。
            FileNotFoundError: 文件不存在。
        """
        resolved = (self._data_root / relative_path).resolve()
        root_str = str(self._data_root)
        resolved_str = str(resolved)
        if resolved_str != root_str and not resolved_str.startswith(root_str + os.sep):
            raise ValueError(f"路径穿越禁止: {relative_path} → {resolved}")
        if not resolved.is_file():
            raise FileNotFoundError(f"资源文件不存在: {resolved}")
        return resolved

    # ── LRU 操作 ──────────────────────────────────────────

    def _insert_image_lru(
        self, key: str, img: pyglet.image.ImageData | _PreloadedImage
    ) -> None:
        """将图像插入 LRU 缓存，必要时淘汰最久未用者。"""
        if key in self._image_cache:
            self._image_cache.move_to_end(key)
            self._image_cache[key] = img
            return
        if self._max_images > 0 and len(self._image_cache) >= self._max_images:
            evicted_key, evicted_val = self._image_cache.popitem(last=False)
            logger.debug("LRU 逐出图像: %s", evicted_key)
            self._dispose_image(evicted_val)
        self._image_cache[key] = img

    def _insert_audio_lru(
        self, key: str, src: pyglet.media.Source | _PreloadedAudio
    ) -> None:
        """将音频插入 LRU 缓存，必要时淘汰最久未用者。"""
        if key in self._audio_cache:
            self._audio_cache.move_to_end(key)
            self._audio_cache[key] = src
            return
        if self._max_audio > 0 and len(self._audio_cache) >= self._max_audio:
            evicted_key, evicted_val = self._audio_cache.popitem(last=False)
            logger.debug("LRU 逐出音频: %s", evicted_key)
            self._dispose_audio(evicted_val)
        self._audio_cache[key] = src

    @staticmethod
    def _touch(cache: OrderedDict[str, Any], key: str) -> None:
        """标记缓存项为最近使用。"""
        cache.move_to_end(key)

    # ── 预加载 → pyglet 对象转换（主线程） ───────────────

    @staticmethod
    def _preloaded_to_image(pre: _PreloadedImage) -> pyglet.image.ImageData:
        """将 _PreloadedImage 转为 pyglet ImageData（主线程安全）。"""
        pitch = pre.width * 4  # RGBA = 4 bytes/pixel
        return pyglet.image.ImageData(pre.width, pre.height, pre.format, pre.data, pitch=pitch)  # type: ignore[no-any-return, unused-ignore]

    @staticmethod
    def _preloaded_to_audio(pre: _PreloadedAudio) -> pyglet.media.Source:
        """将 _PreloadedAudio 转为 pyglet Source（主线程安全）。

        通过 BytesIO 包装字节数据，喂给 pyglet.media.load。
        """
        bio = BytesIO(pre.data)
        # 为 BytesIO 提供虚拟文件名以识别格式
        bio.name = f"preload.{pre.extension}"
        return pyglet.media.load(bio.name, file=bio)  # type: ignore[no-any-return, unused-ignore]

    # ── 释放资源 ──────────────────────────────────────────

    def _dispose_image(
        self, img: pyglet.image.ImageData | _PreloadedImage
    ) -> None:
        """释放图像相关 GPU / 内存资源。

        对 _PreloadedImage 仅丢弃引用（纯 CPU 数据，GC 自然回收）。
        对 ImageData 尝试删除底层纹理。
        """
        if isinstance(img, _PreloadedImage):
            return
        try:
            tex = img.get_texture()
            if tex is not None:
                tex.delete()
        except Exception:
            pass

    def _dispose_audio(self, src: pyglet.media.Source | _PreloadedAudio) -> None:
        """释放音频资源。

        注意：pyglet.media.Source 不提供显式 close / delete 接口。
        StaticSource 内部持有的 buffer 随引用释放由 GC 回收。
        此处仅记录日志；_PreloadedAudio 同样无需额外操作。
        """
        if isinstance(src, _PreloadedAudio):
            return
        # pyglet Source 无显式释放 —— 丢弃引用即可

    # ── 队列排空 ──────────────────────────────────────────

    def _drain_queue_unsafe(self) -> None:
        """排空预加载队列（需外部持有 self._lock）。"""
        count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                count += 1
            except queue.Empty:
                break
        if count:
            logger.debug("预加载队列已排空: %d 个任务", count)

    # ── 后台 Worker ───────────────────────────────────────

    def _worker_loop(self) -> None:
        """后台预加载线程主循环。

        循环检查 _running 标志；每项任务前校验 scene_version，
        若场景已切换则丢弃旧任务。
        """
        while self._running:
            try:
                scene_version, kind, path = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            # 场景版本校验：丢弃旧场景任务（读锁保护）
            with self._lock:
                current_version = self._scene_version
            if scene_version != current_version:
                logger.debug(
                    "丢弃旧场景预加载任务: v%d≠v%d %s %s",
                    scene_version, current_version, kind, path,
                )
                self._queue.task_done()
                continue

            try:
                if kind == "image":
                    self._preload_image_impl(path)
                else:
                    self._preload_audio_impl(path)
            except Exception:
                logger.error(
                    "预加载失败: %s %s", kind, path, exc_info=True,
                )
            finally:
                try:
                    self._queue.task_done()
                except ValueError:
                    pass  # 队列排空时可能重复调用 task_done

    def _preload_image_impl(self, path: str) -> None:
        """后台线程：解码图像为 _PreloadedImage（不涉及 GL）。"""
        full_path = self._resolve_path(path)
        key = _path_to_key(path)

        with self._lock:
            if key in self._image_cache:
                return

        if _HAS_PIL:
            pil_img = PILImage.open(full_path).convert("RGBA")
            pre = _PreloadedImage(
                width=pil_img.width,
                height=pil_img.height,
                data=pil_img.tobytes(),
                format="RGBA",
            )
            with self._lock:
                if key not in self._image_cache:
                    self._insert_image_lru(key, pre)
                    logger.debug("预加载完成(image): %s", key)
        else:
            # PIL 不可用：跳过预加载，get_image 会在主线程同步加载
            logger.debug("PIL 不可用，跳过预加载(image): %s", path)

    def _preload_audio_impl(self, path: str) -> None:
        """后台线程：读取音频文件字节（不涉及音频解码）。"""
        full_path = self._resolve_path(path)
        key = _path_to_key(path)

        with self._lock:
            if key in self._audio_cache:
                return

        pre = _PreloadedAudio(
            data=full_path.read_bytes(),
            extension=full_path.suffix.lstrip("."),
        )

        with self._lock:
            if key not in self._audio_cache:
                self._insert_audio_lru(key, pre)
                logger.debug("预加载完成(audio): %s", key)


# ── 工具函数 ──────────────────────────────────────────────


def _path_to_key(path: str) -> str:
    """将路径转为 POSIX 风格的缓存键。"""
    return Path(path).as_posix()
