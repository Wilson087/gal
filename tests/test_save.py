"""
SaveSystem 单元测试
===================
全文件系统操作，无 pyglet 依赖。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

# core.__init__ 会加载 game.py → import pyglet，需提前 mock
import tests._mocks  # noqa: F401

from src.core.state import CharEntry, SaveData
from src.systems.save_system import SaveSystem


class TestSaveSystem(unittest.TestCase):
    """SaveSystem 存取/校验/版本迁移 测试。"""

    def setUp(self) -> None:
        self._tmpdir = Path(tempfile.mkdtemp())
        self.ss = SaveSystem(save_root=self._tmpdir / "saves")

    def tearDown(self) -> None:
        shutil.rmtree(str(self._tmpdir), ignore_errors=True)

    # ── 1. 正常存取 ───────────────────────────────────────────

    def test_save_load_roundtrip(self) -> None:
        data = SaveData(
            script_file="scene01.ws",
            label_name="start",
            line_index=5,
            flags={"met_hero": True},
            vars={"score": 100},
            background_id="bg_classroom",
            bgm_file="bgm01",
        )
        self.assertTrue(self.ss.save(1, data))
        loaded = self.ss.load(1)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.script_file, "scene01.ws")
        self.assertEqual(loaded.label_name, "start")
        self.assertEqual(loaded.line_index, 5)
        self.assertEqual(loaded.flags, {"met_hero": True})
        self.assertEqual(loaded.vars, {"score": 100})
        self.assertEqual(loaded.background_id, "bg_classroom")
        self.assertEqual(loaded.bgm_file, "bgm01")

    # ── 2. CharEntry 序列化 ──────────────────────────────────

    def test_char_entry_roundtrip(self) -> None:
        data = SaveData(
            characters_on_screen=[
                CharEntry(char_id="rei", pose="smile", position="center", opacity=255),
                CharEntry(char_id="shinji", pose="normal", position="left", opacity=200),
            ],
        )
        self.assertTrue(self.ss.save(0, data))
        loaded = self.ss.load(0)
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded.characters_on_screen), 2)
        self.assertEqual(loaded.characters_on_screen[0].char_id, "rei")
        self.assertEqual(loaded.characters_on_screen[0].opacity, 255)
        self.assertEqual(loaded.characters_on_screen[1].position, "left")

    # ── 3. checksum 防篡改 ───────────────────────────────────

    def test_checksum_reject(self) -> None:
        data = SaveData(script_file="test")
        self.ss.save(1, data)

        # 直接篡改存档文件
        path = self.ss._slot_path(1)
        raw = json.loads(path.read_text("utf-8"))
        raw["data"]["script_file"] = "hacked"
        path.write_text(json.dumps(raw))

        loaded = self.ss.load(1)
        self.assertIsNone(loaded)  # checksum 不匹配

    # ── 4. 版本迁移 ──────────────────────────────────────────

    def test_version_migration(self) -> None:
        # 手动写入旧版格式（v1，无 char_affection）
        old_data = {
            "version": 1,
            "timestamp": "",
            "script_file": "old.ws",
            "label_name": "",
            "line_index": 0,
            "flags": {},
            "vars": {},
            "background_id": "",
            "characters_on_screen": [],
            "bgm_file": "",
            "dialogue_history": [],
            "extra_data": {},
        }
        payload = {
            "data": old_data,
            "checksum": hashlib.md5(
                json.dumps(old_data, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        }
        path = self.ss._slot_path(5)
        path.write_text(json.dumps(payload, ensure_ascii=False))

        loaded = self.ss.load(5)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.version, 2)
        self.assertEqual(loaded.char_affection, {})

    # ── 5. 空槽位返回 None ───────────────────────────────────

    def test_load_nonexistent(self) -> None:
        self.assertIsNone(self.ss.load(99))

    # ── 6. 损坏 JSON 返回 None ────────────────────────────────

    def test_corrupt_json(self) -> None:
        path = self.ss._slot_path(3)
        path.write_text("not valid json", encoding="utf-8")
        self.assertIsNone(self.ss.load(3))

    # ── 7. 槽位列表 ──────────────────────────────────────────

    def test_list_slots(self) -> None:
        self.ss.save(1, SaveData())
        self.ss.save(5, SaveData())
        self.ss.save(10, SaveData())
        self.assertEqual(self.ss.list_slots(), [1, 5, 10])

    # ── 8. 删除存档 ──────────────────────────────────────────

    def test_delete(self) -> None:
        self.ss.save(2, SaveData())
        self.assertIsNotNone(self.ss.load(2))
        self.ss.delete(2)
        self.assertIsNone(self.ss.load(2))

    # ── 9. 缩略图路径 ────────────────────────────────────────

    def test_thumbnail_path(self) -> None:
        path = self.ss.get_thumbnail_path(3)
        self.assertEqual(path.name, "slot_003_thumb.png")
        self.assertEqual(path.parent, self.ss._root)

    # ── 10. 缩略图保存 ───────────────────────────────────────

    def test_save_thumbnail(self) -> None:
        ok = self.ss.save_thumbnail(1, b"fake_png_bytes")
        self.assertTrue(ok)
        thumb = self.ss.get_thumbnail_path(1)
        self.assertTrue(thumb.is_file())
        self.assertEqual(thumb.read_bytes(), b"fake_png_bytes")

    # ── 11. 槽位越界 ─────────────────────────────────────────

    def test_slot_out_of_range(self) -> None:
        self.assertFalse(self.ss.save(-1, SaveData()))
        self.assertFalse(self.ss.save(9999, SaveData()))

    # ── 12. 原子写入 ──────────────────────────────────────────

    def test_atomic_write(self) -> None:
        """验证原子写入：若 .tmp 存在但未完成，旧存档不受影响。"""
        data = SaveData(script_file="original")
        self.ss.save(1, data)

        # 模拟中途崩溃：只写 .tmp 不完成 replace
        tmp_path = self.ss._slot_path(1).with_suffix(".json.tmp")
        bad_payload = {"data": {"script_file": "corrupted"}, "checksum": "deadbeef"}
        tmp_path.write_text(json.dumps(bad_payload))

        # 加载时应仍然读取旧文件（有效的）
        loaded = self.ss.load(1)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.script_file, "original")

        # cleanup tmp
        tmp_path.unlink()

    # ── 13. timestamp 自动生成 ───────────────────────────────

    def test_timestamp_auto(self) -> None:
        data = SaveData()
        self.assertNotEqual(data.timestamp, "")
        self.assertIn("T", data.timestamp)  # ISO format
