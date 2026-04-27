"""
剧本构建模块 (Script Builder)
==============================
提供 NovelScript / Scene 等类和函数，用于以面向对象方式构建剧本字典。

用法::

    from gal_lib.scriptbuilder import NovelScript, Scene

    script = NovelScript("星之回响", "1.0")

    scene = Scene("start", bg="__demo_bg_room__", left="__demo_char_mystery__")
    scene.dialogue("???", "你终于醒了。")
    scene.dialogue("主角", "这里是……？我什么都想不起来了。")
    scene.choices(
        ("询问对方身份", "ask_name"),
        ("观察周围环境", "observe"),
        ("保持沉默", "silent"),
    )
    script.add_scene(scene)

    # 编译为 dict，可直接传给 VNGame.load_script()
    data = script.build()
    game.load_script(data)

    # 导出为 JSON 文件
    script.save_json("my_script.json")
    # 或使用函数式方式
    from gal_lib.scriptbuilder import export_json
    export_json(data, "my_script.json")
"""

import json
from typing import Optional


class Scene:
    """场景构建器，链式调用添加对话与选项。"""

    def __init__(self, scene_id: str, bg: str = "",
                 left: Optional[str] = None,
                 right: Optional[str] = None,
                 bgm: Optional[str] = None) -> None:
        """初始化场景。

        Args:
            scene_id: 场景唯一标识。
            bg: 背景标识符。
            left: 左侧立绘标识符。
            right: 右侧立绘标识符。
            bgm: 背景音乐路径（.wav），None 表示不改变当前 BGM。
        """
        self.id = scene_id
        self.bg = bg
        self.left = left
        self.right = right
        self.bgm = bgm
        self.dialogues: list[dict] = []
        self._choices: Optional[list[dict]] = None

    def dialogue(self, speaker: str, text: str,
                 left: Optional[str] = None,
                 right: Optional[str] = None,
                 sfx: Optional[str] = None) -> "Scene":
        """添加一句对白。

        Args:
            speaker: 说话角色名。
            text: 对白文本。
            left: 本句切换左侧立绘。
            right: 本句切换右侧立绘。
            sfx: 本句播放的音效路径（.wav）。
        """
        entry: dict[str, str] = {"speaker": speaker, "text": text}
        if left is not None:
            entry["character_left"] = left
        if right is not None:
            entry["character_right"] = right
        if sfx is not None:
            entry["sfx"] = sfx
        self.dialogues.append(entry)
        return self

    def choices(self, *options: tuple[str, str]) -> "Scene":
        """添加选项分支。每个参数为 (显示文字, 目标场景ID)。"""
        self._choices = [
            {"text": text, "next_scene": next_scene}
            for text, next_scene in options
        ]
        return self

    def build(self) -> dict:
        """编译为场景字典，与剧本 JSON 格式兼容。"""
        result: dict = {
            "id": self.id,
            "background": self.bg,
            "characters": {"left": self.left, "right": self.right},
            "dialogue": self.dialogues,
        }
        if self.bgm is not None:
            result["bgm"] = self.bgm
        if self._choices:
            result["choices"] = self._choices
        return result


class NovelScript:
    """顶级剧本容器，持有一组场景并提供编译功能。"""

    def __init__(self, title: str, version: str = "1.0") -> None:
        self.title = title
        self.version = version
        self._scenes: list[Scene] = []

    def add_scene(self, scene: Scene) -> "NovelScript":
        """添加一个场景。"""
        self._scenes.append(scene)
        return self

    def build(self) -> dict:
        """编译为完整的剧本字典，可直接传给 VNGame.load_script()。"""
        return {
            "title": self.title,
            "version": self.version,
            "scenes": [s.build() for s in self._scenes],
        }

    def save_json(self, filepath: str, ensure_ascii: bool = False,
                  indent: int = 2) -> str:
        """将剧本导出为 JSON 文件。

        Args:
            filepath: 输出文件路径。
            ensure_ascii: 是否将非 ASCII 字符转义（默认 False，保留中文）。
            indent: JSON 缩进空格数（默认 2）。

        Returns:
            写入的文件路径（同 filepath）。
        """
        data = self.build()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
        return filepath


# ========================================================================
#  类继承方式（ScriptScene / ScriptBase）
# ========================================================================

class ScriptScene(Scene):
    """用类继承定义场景的基类。

    子类通过类属性声明场景元数据，在 define() 中定义对白和选项。

    用法::

        class Opening(ScriptScene):
            id = "start"
            bg = "__demo_bg_room__"
            left = "__demo_char_mystery__"

            def define(self):
                self.say("???", "你终于醒了。")
                self.say("主角", "这里是……？")
                self.ask(
                    ("询问对方身份", "ask_name"),
                    ("保持沉默", "silent"),
                )
    """

    id: str = ""
    bg: str = ""
    left: Optional[str] = None
    right: Optional[str] = None
    bgm: Optional[str] = None

    def __init__(self) -> None:
        super().__init__(self.id, self.bg, self.left, self.right, self.bgm)

    def define(self) -> None:
        """重写此方法，在其中调用 self.say() / self.ask() 定义场景内容。"""
        pass

    def say(self, speaker: str, text: str,
            left: Optional[str] = None,
            right: Optional[str] = None,
            sfx: Optional[str] = None) -> "ScriptScene":
        """添加一句对白（dialogue 的别名，与 define() 搭配更自然）。"""
        self.dialogue(speaker, text, left, right, sfx)
        return self

    def ask(self, *options: tuple[str, str]) -> "ScriptScene":
        """添加选项分支（choices 的别名）。"""
        self.choices(*options)
        return self

    def build(self) -> dict:
        """编译场景：先调用 define() 填充内容，再生成字典。"""
        self.dialogues = []
        self._choices = None
        self.define()
        return super().build()


class ScriptBase(NovelScript):
    """用类继承定义完整剧本的基类。

    子类通过类属性声明标题/版本，在 scenes 列表中列出场景类。

    用法::

        class MyGame(ScriptBase):
            title = "星之回响"
            version = "1.0"
            scenes = [Opening, Ending]

        if __name__ == "__main__":
            import tkinter as tk
            from gal_lib import VNGame

            root = tk.Tk()
            app = VNGame(root)
            app.load_script(MyGame().build())
            app.start_game()
            root.mainloop()
    """

    title: str = ""
    version: str = "1.0"
    scenes: list = []  # ScriptScene 子类的列表

    def __init__(self) -> None:
        super().__init__(self.title, self.version)

    def build(self) -> dict:
        """实例化所有场景类并编译完整剧本。"""
        self._scenes = []
        for scene_cls in self.scenes:
            self.add_scene(scene_cls())
        return super().build()


# ========================================================================
#  便捷函数（函数式风格）
# ========================================================================

def make_dialogue(speaker: str, text: str,
                  sfx: Optional[str] = None, **kwargs) -> dict:
    """创建一句对白条目字典。

    Args:
        speaker: 说话角色名。
        text: 对白文本。
        sfx: 本句音效路径（可选）。
        **kwargs: 其他字段（如 character_left, character_right）。
    """
    entry: dict = {"speaker": speaker, "text": text}
    if sfx is not None:
        entry["sfx"] = sfx
    entry.update(kwargs)
    return entry


def make_choice(text: str, next_scene: str) -> dict:
    """创建一个选项条目字典。"""
    return {"text": text, "next_scene": next_scene}


def make_scene(scene_id: str, bg: str = "",
               left: Optional[str] = None,
               right: Optional[str] = None,
               bgm: Optional[str] = None,
               dialogues: Optional[list[dict]] = None,
               choices: Optional[list[dict]] = None) -> dict:
    """创建一个场景字典（纯函数版本）。

    Args:
        scene_id: 场景 ID。
        bg: 背景标识符。
        left: 左侧立绘。
        right: 右侧立绘。
        bgm: 背景音乐路径（可选）。
        dialogues: 对白列表。
        choices: 选项列表。
    """
    scene: dict = {
        "id": scene_id,
        "background": bg,
        "characters": {"left": left, "right": right},
        "dialogue": dialogues or [],
    }
    if bgm is not None:
        scene["bgm"] = bgm
    if choices:
        scene["choices"] = choices
    return scene


# ========================================================================
#  JSON 导出工具函数
# ========================================================================

def export_json(script: dict, filepath: str,
                ensure_ascii: bool = False, indent: int = 2) -> str:
    """将剧本字典导出为 JSON 文件。

    同时兼容 NovelScript.build() 的输出和手动构建的 dict。

    Args:
        script: 剧本字典（需包含 title、version、scenes 字段）。
        filepath: 输出文件路径。
        ensure_ascii: 是否转义非 ASCII 字符（默认 False，保留中文）。
        indent: JSON 缩进空格数。

    Returns:
        写入的文件路径。

    Raises:
        IOError: 文件写入失败时抛出。
    """
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=ensure_ascii, indent=indent)
    return filepath
