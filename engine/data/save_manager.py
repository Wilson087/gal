"""
存档系统模块
============
100 槽位存档系统，支持截图缩略图、快存/快读、JSON 持久化。
"""

from __future__ import annotations

import base64
import io
import json
import os
import time
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..app import AVGApplication

from pyglet.image import get_buffer_manager
from pyglet.image.codecs.png import PNGImageEncoder

from ..core.logger import Logger

log = Logger("Save")

_SAVE_DIR = "saves"
_SAVE_TEMPLATE = "save_{:02d}.json"
_QUICK_SLOT = 0


class SaveManager:
    """存档管理器。

    槽位 0 为快速存档/读档专用，槽位 1-99 为手动存档。
    每页显示 10 个槽位。
    """

    MAX_SLOTS = 100
    SLOTS_PER_PAGE = 10

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        os.makedirs(_SAVE_DIR, exist_ok=True)

    # ── 公共接口 ────────────────────────────────────────────

    def quick_save(self) -> bool:
        """快速保存到槽位 0。"""
        return self._save_slot(_QUICK_SLOT)

    def quick_load(self) -> bool:
        """从槽位 0 快速读取。"""
        return self._load_slot(_QUICK_SLOT)

    def save(self, slot_index: int) -> bool:
        """保存到指定槽位（1-99）。"""
        if not (1 <= slot_index < self.MAX_SLOTS):
            return False
        return self._save_slot(slot_index)

    def load(self, slot_index: int) -> bool:
        """从指定槽位读取（1-99）。"""
        if not (1 <= slot_index < self.MAX_SLOTS):
            return False
        return self._load_slot(slot_index)

    def delete_slot(self, slot_index: int) -> None:
        """删除指定槽位的存档。"""
        path = self._slot_path(slot_index)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    def get_slot_info(self, slot_index: int) -> Optional[dict]:
        """获取槽位元数据。

        Returns:
            dict 或 None（空槽位）:
            - timestamp: 存档时间字符串
            - scene_id: 场景 ID
            - chapter_title: 场景标题
            - game_title: 游戏标题
            - dialogue_index: 对话索引
            - variables: 变量快照
            - screenshot_base64: 缩略图 base64（小尺寸）
        """
        path = self._slot_path(slot_index)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "timestamp": data.get("timestamp", ""),
                "scene_id": data.get("scene_id", ""),
                "chapter_title": data.get("chapter_title", ""),
                "game_title": data.get("game_title", ""),
                "dialogue_index": data.get("dialogue_index", 0),
                "variables": data.get("variables", {}),
                "screenshot_base64": data.get("screenshot", ""),
            }
        except (json.JSONDecodeError, OSError):
            return None

    def get_page_count(self) -> int:
        """获取总页数。"""
        return (self.MAX_SLOTS + self.SLOTS_PER_PAGE - 1) // self.SLOTS_PER_PAGE

    def get_slots_for_page(self, page: int) -> list[int]:
        """获取指定页的槽位索引列表。"""
        start = page * self.SLOTS_PER_PAGE
        end = min(start + self.SLOTS_PER_PAGE, self.MAX_SLOTS)
        return list(range(start, end))

    # ── 内部实现 ────────────────────────────────────────────

    def _save_slot(self, slot_index: int) -> bool:
        """实际保存逻辑。"""
        sm = self.app.scene_manager
        if not sm.current_scene_id:
            log.debug("保存失败: 无当前场景")
            return False
        log.debug("保存槽位 %d: %s[%d]", slot_index, sm.current_scene_id, sm.dialogue_index)

        # 截图
        screenshot_b64 = self._capture_screenshot()

        data = {
            "version": "0.1.0",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "scene_id": sm.current_scene_id,
            "dialogue_index": sm.dialogue_index,
            "variables": dict(self.app.variable_bank.variables),
            "chapter_title": sm.current_scene_id,
            "game_title": sm.title,
            "history": [],
            "screenshot": screenshot_b64,
        }

        # 保存到临时文件后重命名（防崩溃）
        path = self._slot_path(slot_index)
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            return True
        except OSError:
            return False

    def _load_slot(self, slot_index: int) -> bool:
        """实际读取逻辑。"""
        path = self._slot_path(slot_index)
        if not os.path.exists(path):
            log.debug("读取失败: 槽位 %d 不存在", slot_index)
            return False
        log.debug("读取槽位 %d", slot_index)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False

        sm = self.app.scene_manager
        sm.restore_from_save(data)
        return True

    def _capture_screenshot(self) -> str:
        """捕获当前画面，缩放为缩略图，base64 编码。

        Returns:
            base64 编码的 PNG 数据，失败时返回空字符串。
        """
        try:
            color_buffer = get_buffer_manager().get_color_buffer()
            image = color_buffer.get_image_data()

            # 直接编码为 PNG bytes
            buf = io.BytesIO()
            encoder = PNGImageEncoder()
            encoder.encode(image, "", buf)
            png_bytes = buf.getvalue()
            b64 = base64.b64encode(png_bytes).decode("ascii")
            log.debug("截图完成: %d bytes (base64)", len(b64))
            return b64
        except Exception as e:
            log.error("截图失败: %s", e)
            return ""

    def _slot_path(self, slot_index: int) -> str:
        return os.path.join(_SAVE_DIR, _SAVE_TEMPLATE.format(slot_index))
