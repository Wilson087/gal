"""
剧本数据模块
=============
提供剧本加载与验证功能。
"""

import json
from typing import Any


def load_from_file(filepath: str) -> dict:
    """从 JSON 文件加载剧本数据。

    Args:
        filepath: JSON 剧本文件路径。

    Returns:
        解析后的剧本字典。

    Raises:
        FileNotFoundError: 文件不存在。
        json.JSONDecodeError: JSON 格式错误。
    """
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_script(script: dict) -> list[str]:
    """验证剧本数据结构完整性，返回所有格式错误信息。

    Args:
        script: 要验证的剧本字典。

    Returns:
        错误信息列表，为空表示剧本有效。
    """
    errors: list[str] = []

    if not isinstance(script, dict):
        return ["剧本必须是 dict 类型"]

    if "scenes" not in script or not isinstance(script["scenes"], list):
        return ["剧本缺少 'scenes' 字段或字段类型不是 list"]

    scene_ids: set[str] = set()
    for i, scene in enumerate(script["scenes"]):
        if not isinstance(scene, dict):
            errors.append(f"scenes[{i}] 不是 dict 类型")
            continue
        sid = scene.get("id", f"(索引 {i})")
        if not isinstance(sid, str) or not sid:
            errors.append(f"scenes[{i}] 缺少有效 'id' 字段")
        elif sid in scene_ids:
            errors.append(f"场景 id '{sid}' 重复")
        else:
            scene_ids.add(sid)

        if "dialogue" not in scene or not isinstance(scene["dialogue"], list):
            errors.append(f"场景 '{sid}' 缺少 'dialogue' 字段或类型不是 list")
        else:
            for j, entry in enumerate(scene["dialogue"]):
                if not isinstance(entry, dict) or "text" not in entry:
                    errors.append(f"场景 '{sid}' dialogue[{j}] 缺少 'text' 字段")

        if "choices" in scene:
            if not isinstance(scene["choices"], list):
                errors.append(f"场景 '{sid}' 'choices' 类型不是 list")
            else:
                for j, choice in enumerate(scene["choices"]):
                    if not isinstance(choice, dict):
                        errors.append(f"场景 '{sid}' choices[{j}] 不是 dict")
                        continue
                    if "text" not in choice:
                        errors.append(f"场景 '{sid}' choices[{j}] 缺少 'text'")
                    ns = choice.get("next_scene", "")
                    if not isinstance(ns, str) or not ns:
                        errors.append(f"场景 '{sid}' choices[{j}] 缺少有效的 'next_scene'")

    return errors
