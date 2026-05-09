"""
Save System — 存档系统
=======================
JSON + MD5 校验，原子写入，版本迁移，缩略图独立存储。

用法::

    from systems.save_system import SaveSystem
    from core.state import SaveData

    ss = SaveSystem(save_root="saves")
    data = SaveData(script_file="scene01.ws", label_name="start")
    ss.save(1, data)
    loaded = ss.load(1)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from config import MAX_SAVE_SLOTS, SAVE_PATH
from core.state import SaveData

logger = logging.getLogger(__name__)

_SLOT_TEMPLATE = "slot_{:03d}.json"
_THUMB_TEMPLATE = "slot_{:03d}_thumb.png"
_CURRENT_VERSION = 2


class SaveSystem:
    """存档管理器。

    特性：
    - JSON + MD5 checksum 防篡改
    - 原子写入（先写 .tmp → os.replace），中途崩溃不损坏旧存档
    - 版本迁移（_migrate），旧版存档自动升级到最新格式
    - 缩略图独立 PNG 文件，不嵌入 JSON
    - 可注入存档目录，方便单元测试
    """

    def __init__(self, save_root: str | Path = SAVE_PATH) -> None:
        self._root: Path = Path(save_root)
        self._root.mkdir(parents=True, exist_ok=True)
        logger.debug("SaveSystem 已初始化: root=%s", self._root)

    # ── 保存 ──────────────────────────────────────────────

    def save(self, slot: int, data: SaveData) -> bool:
        """保存存档到指定槽位。

        原子写入：先写 .tmp 文件，完成后 os.replace 原子替换，
        中途崩溃不会损坏旧存档。

        Args:
            slot: 槽位编号 [0, MAX_SAVE_SLOTS)。
            data: 存档数据。

        Returns:
            True 表示保存成功；False 表示失败（槽位越界 / 磁盘满 / 无权限）。
        """
        if not (0 <= slot < MAX_SAVE_SLOTS):
            logger.error("存档槽位越界: %d (max=%d)", slot, MAX_SAVE_SLOTS)
            return False

        data.version = _CURRENT_VERSION
        data_dict = data.to_dict()

        # 计算 checksum
        raw_data = json.dumps(data_dict, ensure_ascii=False, sort_keys=True)
        checksum = hashlib.md5(raw_data.encode("utf-8")).hexdigest()

        payload = {
            "data": data_dict,
            "checksum": checksum,
        }

        path = self._slot_path(slot)
        tmp = path.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            logger.info("存档已保存: slot=%d", slot)
            return True
        except (OSError, PermissionError) as e:
            logger.error("存档保存失败 (slot=%d): %s", slot, e)
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            return False

    # ── 读取 ──────────────────────────────────────────────

    def load(self, slot: int) -> SaveData | None:
        """从指定槽位读取存档。

        步骤：读取 JSON → 验证 checksum → 版本迁移 → 构造 SaveData。

        Args:
            slot: 槽位编号。

        Returns:
            SaveData 或 None（无存档 / 校验失败 / 文件损坏）。
        """
        path = self._slot_path(slot)
        if not path.is_file():
            return None

        try:
            payload = json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("存档读取失败 (slot=%d): %s", slot, e)
            return None

        raw_data = payload.get("data")
        stored_checksum = payload.get("checksum")

        if not isinstance(raw_data, dict) or not isinstance(stored_checksum, str):
            logger.error("存档格式错误 (slot=%d): 缺少 data 或 checksum", slot)
            return None

        # 校验 checksum
        computed = hashlib.md5(
            json.dumps(raw_data, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if computed != stored_checksum:
            logger.error("存档校验失败 (slot=%d): checksum 不匹配", slot)
            return None

        # 版本迁移
        migrated = self._migrate(raw_data)

        try:
            data = SaveData.from_dict(migrated)
            logger.info("存档已读取: slot=%d, version=%d", slot, data.version)
            return data
        except Exception as e:
            logger.error("存档数据转换失败 (slot=%d): %s", slot, e)
            return None

    # ── 槽位管理 ──────────────────────────────────────────

    def list_slots(self) -> list[int]:
        """列出所有已使用的槽位编号（按从小到大排序）。"""
        slots: list[int] = []
        for f in self._root.glob("slot_*.json"):
            name = f.stem  # "slot_001"
            try:
                num = int(name.split("_")[1])
                slots.append(num)
            except (IndexError, ValueError):
                continue
        slots.sort()
        return slots

    def _check_slot(self, slot: int) -> bool:
        """校验槽位是否合法。"""
        if not (0 <= slot < MAX_SAVE_SLOTS):
            logger.error("存档槽位越界: %d (max=%d)", slot, MAX_SAVE_SLOTS)
            return False
        return True

    def delete(self, slot: int) -> bool:
        """删除指定槽位的存档和缩略图。

        Args:
            slot: 槽位编号。

        Returns:
            True 表示成功；False 表示失败。
        """
        if not self._check_slot(slot):
            return False
        deleted = False
        for p in (self._slot_path(slot), self._thumb_path(slot)):
            try:
                if p.is_file():
                    p.unlink()
                    deleted = True
            except OSError as e:
                logger.error("删除文件失败: %s — %s", p, e)
        if deleted:
            logger.info("存档已删除: slot=%d", slot)
        return deleted

    # ── 缩略图 ────────────────────────────────────────────

    def get_thumbnail_path(self, slot: int) -> Path:
        """返回缩略图文件路径（不论是否存在）。

        Args:
            slot: 槽位编号。
        """
        return self._thumb_path(slot)

    def save_thumbnail(self, slot: int, image_data: bytes) -> bool:
        """将图像字节直接写入缩略图文件。

        调用方（如 GameWindow）负责捕获当前帧为 PNG 字节后传入。

        Args:
            slot: 槽位编号。
            image_data: PNG 图像字节。

        Returns:
            True 表示成功。
        """
        if not self._check_slot(slot):
            return False
        path = self._thumb_path(slot)
        try:
            path.write_bytes(image_data)
            logger.debug("缩略图已保存: slot=%d", slot)
            return True
        except OSError as e:
            logger.error("缩略图保存失败 (slot=%d): %s", slot, e)
            return False

    # ── 版本迁移 ──────────────────────────────────────────

    def _migrate(self, raw: dict[str, object]) -> dict[str, object]:
        """将旧版存档数据迁移到当前版本。

        迁移历史：
            v1 → v2: 新增 char_affection 字段
        """
        version = int(raw.get("version", 1))  # type: ignore[call-overload]

        if version > _CURRENT_VERSION:
            logger.warning(
                "存档版本 %d 高于当前版本 %d，无法加载（请升级引擎）",
                version, _CURRENT_VERSION,
            )
            return raw  # 拒绝迁移，load() 中 _migrate 返回原数据

        if version < 2:
            raw.setdefault("char_affection", {})
            logger.debug("存档迁移: v1 → v2 (新增 char_affection)")

        # 未来: if version < 3: ...

        raw["version"] = _CURRENT_VERSION
        return raw

    # ── 内部路径 ──────────────────────────────────────────

    def _slot_path(self, slot: int) -> Path:
        return self._root / _SLOT_TEMPLATE.format(slot)

    def _thumb_path(self, slot: int) -> Path:
        return self._root / _THUMB_TEMPLATE.format(slot)
