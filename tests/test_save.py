"""
SaveSystem 单元测试
===================
全文件系统操作，无 pyglet 依赖。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from core.state import CharEntry, SaveData
from systems.save_system import SaveSystem


# ── Fixture ────────────────────────────────────────────────

@pytest.fixture
def ss(tmp_path: Path) -> SaveSystem:
    return SaveSystem(save_root=tmp_path / "saves")


# ── 1. 正常存取 ───────────────────────────────────────────

def test_save_load_roundtrip(ss: SaveSystem) -> None:
    data = SaveData(
        script_file="scene01.ws",
        label_name="start",
        line_index=5,
        flags={"met_hero": True},
        vars={"score": 100},
        background_id="bg_classroom",
        bgm_file="bgm01",
    )
    assert ss.save(1, data)
    loaded = ss.load(1)
    assert loaded is not None
    assert loaded.script_file == "scene01.ws"
    assert loaded.label_name == "start"
    assert loaded.line_index == 5
    assert loaded.flags == {"met_hero": True}
    assert loaded.vars == {"score": 100}
    assert loaded.background_id == "bg_classroom"
    assert loaded.bgm_file == "bgm01"


# ── 2. CharEntry 序列化 ──────────────────────────────────

def test_char_entry_roundtrip(ss: SaveSystem) -> None:
    data = SaveData(
        characters_on_screen=[
            CharEntry(char_id="rei", pose="smile", position="center", opacity=255),
            CharEntry(char_id="shinji", pose="normal", position="left", opacity=200),
        ],
    )
    assert ss.save(0, data)
    loaded = ss.load(0)
    assert loaded is not None
    assert len(loaded.characters_on_screen) == 2
    assert loaded.characters_on_screen[0].char_id == "rei"
    assert loaded.characters_on_screen[0].opacity == 255
    assert loaded.characters_on_screen[1].position == "left"


# ── 3. checksum 防篡改 ───────────────────────────────────

def test_checksum_reject(ss: SaveSystem) -> None:
    data = SaveData(script_file="test")
    ss.save(1, data)

    # 直接篡改存档文件
    path = ss._slot_path(1)
    raw = json.loads(path.read_text("utf-8"))
    raw["data"]["script_file"] = "hacked"
    path.write_text(json.dumps(raw))

    loaded = ss.load(1)
    assert loaded is None  # checksum 不匹配


# ── 4. 版本迁移 ──────────────────────────────────────────

def test_version_migration(ss: SaveSystem) -> None:
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
    path = ss._slot_path(5)
    path.write_text(json.dumps(payload, ensure_ascii=False))

    loaded = ss.load(5)
    assert loaded is not None
    assert loaded.version == 2
    assert loaded.char_affection == {}


# ── 5. 空槽位返回 None ───────────────────────────────────

def test_load_nonexistent(ss: SaveSystem) -> None:
    assert ss.load(99) is None


# ── 6. 损坏 JSON 返回 None ────────────────────────────────

def test_corrupt_json(ss: SaveSystem) -> None:
    path = ss._slot_path(3)
    path.write_text("not valid json", encoding="utf-8")
    assert ss.load(3) is None


# ── 7. 槽位列表 ──────────────────────────────────────────

def test_list_slots(ss: SaveSystem) -> None:
    ss.save(1, SaveData())
    ss.save(5, SaveData())
    ss.save(10, SaveData())
    assert ss.list_slots() == [1, 5, 10]


# ── 8. 删除存档 ──────────────────────────────────────────

def test_delete(ss: SaveSystem) -> None:
    ss.save(2, SaveData())
    assert ss.load(2) is not None
    ss.delete(2)
    assert ss.load(2) is None


# ── 9. 缩略图路径 ────────────────────────────────────────

def test_thumbnail_path(ss: SaveSystem) -> None:
    path = ss.get_thumbnail_path(3)
    assert path.name == "slot_003_thumb.png"
    assert path.parent == ss._root


# ── 10. 缩略图保存 ───────────────────────────────────────

def test_save_thumbnail(ss: SaveSystem) -> None:
    ok = ss.save_thumbnail(1, b"fake_png_bytes")
    assert ok
    thumb = ss.get_thumbnail_path(1)
    assert thumb.is_file()
    assert thumb.read_bytes() == b"fake_png_bytes"


# ── 11. 槽位越界 ─────────────────────────────────────────

def test_slot_out_of_range(ss: SaveSystem) -> None:
    assert ss.save(-1, SaveData()) is False
    assert ss.save(9999, SaveData()) is False


# ── 12. 原子写入 ──────────────────────────────────────────

def test_atomic_write(ss: SaveSystem) -> None:
    """验证原子写入：若 .tmp 存在但未完成，旧存档不受影响。"""
    data = SaveData(script_file="original")
    ss.save(1, data)

    # 模拟中途崩溃：只写 .tmp 不完成 replace
    tmp_path = ss._slot_path(1).with_suffix(".json.tmp")
    bad_payload = {"data": {"script_file": "corrupted"}, "checksum": "deadbeef"}
    tmp_path.write_text(json.dumps(bad_payload))

    # 加载时应仍然读取旧文件（有效的）
    loaded = ss.load(1)
    assert loaded is not None
    assert loaded.script_file == "original"

    # cleanup tmp
    tmp_path.unlink()


# ── 13. timestamp 自动生成 ───────────────────────────────

def test_timestamp_auto() -> None:
    data = SaveData()
    assert data.timestamp != ""
    assert "T" in data.timestamp  # ISO format
