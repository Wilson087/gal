"""
剧本数据模块
=============
提供演示剧本数据、剧本加载与验证功能。

公开变量:
    DEMO_SCRIPT : dict — 内置演示剧本（"星之回响"）

公开函数:
    load_from_file(filepath) -> dict
    validate_script(script) -> list[str]
"""

import json
from typing import Any

# ========================================================================
#  内置演示剧本 — "星之回响"
# ========================================================================

DEMO_SCRIPT: dict[str, Any] = {
    "title": "星之回响",
    "version": "1.0",
    "scenes": [
        {
            "id": "start",
            "background": "__demo_bg_room__",
            "characters": {"left": "__demo_char_mystery__", "right": None},
            "dialogue": [
                {"speaker": "???",   "text": "你终于醒了。"},
                {"speaker": "主角",  "text": "这里是……？我什么都想不起来了。"},
                {"speaker": "???",   "text": "这里是星落之谷。你已经昏迷三天了。"},
            ],
            "choices": [
                {"text": "询问对方身份",     "next_scene": "ask_name"},
                {"text": "观察周围环境",     "next_scene": "observe"},
                {"text": "保持沉默",         "next_scene": "silent"},
            ],
        },
        {
            "id": "ask_name",
            "background": "__demo_bg_room__",
            "characters": {"left": "__demo_char_girl__", "right": None},
            "dialogue": [
                {"speaker": "主角",  "text": "请问你是……？"},
                {"speaker": "少女",  "text": "我叫星野，是这座山谷的守护者。"},
                {"speaker": "星野",  "text": "你误入了山谷的结界，所以才会昏迷。"},
                {"speaker": "主角",  "text": "结界？我完全不知道这些……"},
                {"speaker": "星野",  "text": "看来你确实什么都不记得了。慢慢来吧。"},
            ],
            "choices": [
                {"text": "询问更多关于结界的事", "next_scene": "ask_barrier"},
                {"text": "道谢并准备离开",       "next_scene": "leave"},
            ],
        },
        {
            "id": "observe",
            "background": "__demo_bg_valley__",
            "characters": {"left": "__demo_char_mystery__", "right": None},
            "dialogue": [
                {"speaker": "主角",  "text": "（环顾四周）这是一个被群山环绕的山谷……"},
                {"speaker": "主角",  "text": "空气中飘浮着奇怪的光点。"},
                {"speaker": "???",   "text": "那些是星尘，是结界的一部分。"},
                {"speaker": "???",   "text": "你能看到它们，说明你身上也有灵力。"},
                {"speaker": "主角",  "text": "灵力？我只是一个普通人……"},
            ],
            "choices": [
                {"text": "让她继续说下去",   "next_scene": "ask_barrier"},
                {"text": "表示想离开这里",   "next_scene": "leave"},
            ],
        },
        {
            "id": "silent",
            "background": "__demo_bg_room__",
            "characters": {"left": "__demo_char_mystery__", "right": None},
            "dialogue": [
                {"speaker": "???",   "text": "……你不打算说点什么吗？"},
                {"speaker": "主角",  "text": "（沉默不语）"},
                {"speaker": "???",   "text": "好吧，看来你还需要时间适应。"},
                {"speaker": "???",   "text": "我叫星野，是这座山谷的守护者。"},
                {"speaker": "主角",  "text": "……星野？"},
                {"speaker": "星野",  "text": "对。你已经昏迷三天了，能活下来算是奇迹。"},
            ],
            "choices": [
                {"text": "询问结界的事",           "next_scene": "ask_barrier"},
                {"text": "请求她送自己离开",       "next_scene": "leave"},
            ],
        },
        {
            "id": "ask_barrier",
            "background": "__demo_bg_valley__",
            "characters": {"left": "__demo_char_girl__", "right": None},
            "dialogue": [
                {"speaker": "星野",  "text": "这座山谷的结界是为了封印远古的灾厄而设的。"},
                {"speaker": "星野",  "text": "你能够穿过结界进来，说明你与这封印有某种联系。"},
                {"speaker": "主角",  "text": "我？与封印有联系？这太荒谬了……"},
                {"speaker": "星野",  "text": "我知道这很难接受，但星尘在你周围的反应不会说谎。"},
                {"speaker": "星野",  "text": "或许你正是预言中提到的那个「觉醒者」。"},
            ],
            "choices": [
                {"text": "接受命运，留下来帮忙",   "next_scene": "ending_a"},
                {"text": "拒绝相信，坚持离开",     "next_scene": "ending_b"},
            ],
        },
        {
            "id": "leave",
            "background": "__demo_bg_room__",
            "characters": {"left": "__demo_char_girl__", "right": None},
            "dialogue": [
                {"speaker": "星野",  "text": "你想离开？"},
                {"speaker": "星野",  "text": "但是结界已经认你为主了，没有你解开，任何人都出不去。"},
                {"speaker": "主角",  "text": "什么？！"},
                {"speaker": "星野",  "text": "所以，你暂时只能留在这里了。"},
                {"speaker": "星野",  "text": "等你准备好之后，我带你去看结界核心。"},
            ],
            "choices": [
                {"text": "了解结界详情",   "next_scene": "ask_barrier"},
                {"text": "无奈接受",       "next_scene": "ending_a"},
            ],
        },
        {
            "id": "ending_a",
            "background": "__demo_bg_valley__",
            "characters": {"left": "__demo_char_girl__", "right": "__demo_char_hero__"},
            "dialogue": [
                {"speaker": "星野",  "text": "太好了！有你帮忙，封印一定能稳定下来。"},
                {"speaker": "主角",  "text": "虽然我还是不太明白……但我会尽力。"},
                {"speaker": "星野",  "text": "来吧，我带你去看结界核心。你的故事，才刚刚开始。"},
            ],
        },
        {
            "id": "ending_b",
            "background": "__demo_bg_room__",
            "characters": {"left": "__demo_char_girl__", "right": None},
            "dialogue": [
                {"speaker": "星野",  "text": "……我明白了。"},
                {"speaker": "星野",  "text": "我不会强迫你。但结界不会轻易放你走。"},
                {"speaker": "星野",  "text": "等你改变主意了，随时告诉我。"},
            ],
        },
    ],
}


# ========================================================================
#  剧本工具函数
# ========================================================================

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
