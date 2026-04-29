"""
场景管理器模块
==============
管理场景跳转、对话推进、立绘/音频/变量集成。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..app import AVGApplication

from ..core.constants import (
    CHARACTER_NAME_COLORS, DEFAULT_TRANSITION,
)
from ..core.script_loader import load_from_file, validate_script
from ..core.rich_text import strip_rich_tags
from ..core.logger import Logger

log = Logger("Scene")


class SceneSnapshot:
    """对话推进前的完整场景快照，用于回退时恢复现场。"""

    def __init__(self, scene_id: str, dialogue_index: int,
                 bg_id: str = "", characters: Optional[dict] = None,
                 bgm: str = "", variables: Optional[dict] = None,
                 filter_name: str = "",
                 weather: str = ""):
        self.scene_id = scene_id
        self.dialogue_index = dialogue_index
        self.bg_id = bg_id
        self.characters = characters or {}
        self.bgm = bgm
        self.variables = variables or {}
        self.filter_name = filter_name
        self.weather = weather


class SceneManager:
    """场景状态机，负责场景切换和游戏流程控制。"""

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        self.script: dict = {}
        self.scenes_dict: dict[str, dict] = {}
        self.current_scene_id: Optional[str] = None
        self.dialogue_index: int = 0
        self._game_ended: bool = False
        self._choosing: bool = False
        # 快照栈（用于回退）：每个元素是 SceneSnapshot
        self._snapshot_stack: list[SceneSnapshot] = []
        # 回退锁定：防止 go_back 后 next_dialogue 重复记录刚恢复的状态
        self._history_locked: bool = False

    def load_script(self, source: str | dict) -> None:
        """加载并验证剧本。

        Args:
            source: JSON 文件路径或剧本字典。
        """
        if isinstance(source, str):
            self.script = load_from_file(source)
        elif isinstance(source, dict):
            self.script = source
        else:
            raise TypeError("source 必须是文件路径 (str) 或剧本字典 (dict)")

        errors = validate_script(self.script)
        if errors:
            detail = "\n".join(errors[:5])
            raise ValueError(f"剧本格式错误 ({len(errors)} 项):\n{detail}")

        self.scenes_dict = {s["id"]: s for s in self.script["scenes"]}

        # 读取角色名颜色配置
        char_colors = self.script.get("character_colors", {})
        CHARACTER_NAME_COLORS.update(char_colors)

        log.info("剧本 '%s' 加载完成, %d 个场景",
                 self.script.get('title', ''), len(self.scenes_dict))

    def start_first_scene(self) -> None:
        """从第一个场景开始游戏。"""
        if not self.scenes_dict:
            log.warning("没有可用场景")
            return

        self.app.variable_bank.reset()
        self.dialogue_index = 0

        # 找第一个场景
        first_id = None
        for sid in self.scenes_dict:
            first_id = sid
            break

        if first_id:
            self.jump_to_scene(first_id)

    def jump_to_scene(self, scene_id: str,
                      transition: str = DEFAULT_TRANSITION) -> None:
        """跳转到指定场景。

        Args:
            scene_id: 目标场景 ID。
            transition: 转场效果类型。
        """
        # 清理当前状态
        self.app.dialogue_system.clear()
        self.app.choice_system.hide()
        self.app.character_manager.stop_speaking()

        self.dialogue_index = 0
        self.current_scene_id = scene_id
        self._choosing = False
        self._game_ended = False

        scene = self.scenes_dict.get(scene_id)
        if scene is None:
            log.warning("场景 '%s' 不存在", scene_id)
            return

        # 处理场景级音效
        if "sfx" in scene:
            self.app.audio_engine.play_sfx(scene["sfx"])

        # 处理场景级滤镜
        if "filter" in scene:
            intensity = scene.get("filter_intensity", 0.3)
            self.app.effect_system.apply_filter(scene["filter"], intensity)
        else:
            self.app.effect_system.remove_filter()

        # 处理场景级天气
        weather = scene.get("weather", "").lower()
        if weather == "snow":
            self.app.effect_system.start_snow(scene.get("weather_count", 60))
        elif weather == "rain":
            self.app.effect_system.start_rain(scene.get("weather_count", 80))
        else:
            self.app.effect_system.stop_particles()

        # BGM 切换
        if "bgm" in scene:
            bgm_path = scene.get("bgm")
            if bgm_path:
                self.app.audio_engine.play_bgm(bgm_path)
            else:
                self.app.audio_engine.stop_bgm()

        def _after_bg():
            # 更新立绘
            self.app.character_manager.set_characters(
                scene.get("characters", {}))
            # 场景级 voice
            scene_voice = scene.get("voice")
            if scene_voice:
                self.app.audio_engine.play_voice(scene_voice)
            # 显示第一句对话
            self._show_current_dialogue()

        # 背景切换（带转场）
        bg_id = scene.get("background", "")
        log.debug("场景 '%s': background=%s bgm=%s weather=%s",
                  scene_id, bg_id, scene.get("bgm"), scene.get("weather"))
        self.app.background_manager.set_background(bg_id, transition, _after_bg)

    def _show_current_dialogue(self) -> None:
        """根据当前 dialogue_index 显示对白或选项。"""
        sid = self.current_scene_id
        if sid is None:
            return
        scene = self.scenes_dict.get(sid)
        if scene is None:
            return

        dialogues = scene.get("dialogue", [])
        choices = scene.get("choices")

        if self.dialogue_index < len(dialogues):
            entry = dialogues[self.dialogue_index]
            speaker = entry.get("speaker", "")
            text = entry.get("text", "")

            log.info("%s[%d]: speaker=%r text=%r",
                     self.current_scene_id, self.dialogue_index,
                     speaker, text[:40])

            # 每句内立绘变化
            char_changed = False
            if "character_left" in entry or "character_right" in entry:
                char_data = {}
                if "character_left" in entry:
                    char_data["left"] = entry["character_left"]
                if "character_right" in entry:
                    char_data["right"] = entry["character_right"]
                self.app.character_manager.set_characters(char_data)
                char_changed = True

            # 音效
            sfx_path = entry.get("sfx")
            if sfx_path:
                self.app.audio_engine.play_sfx(sfx_path)

            # 语音
            voice_path = entry.get("voice")
            if voice_path:
                self.app.audio_engine.play_voice(voice_path)

            # 变量操作
            if "set_var" in entry:
                for k, v in entry["set_var"].items():
                    self.app.variable_bank.set(k, v)

            # 说话动画
            if speaker:
                self._start_speaking_for(speaker)

            # 显示对话
            self.app.dialogue_system.show_dialogue(text, speaker, entry)

            # 记录到历史
            if hasattr(self.app, 'history_manager') and self.current_scene_id:
                self.app.history_manager.record(speaker, text,
                                                self.current_scene_id,
                                                self.dialogue_index)

        elif choices:
            # 有选项分支
            self._choosing = True
            self.app.choice_system.show_choices(choices)

        else:
            # 无对话无选项 => 场景结束
            self.end_scene()

    def _start_speaking_for(self, speaker: str) -> None:
        """根据说话者启动对应立绘的说话动画。"""
        sid = self.current_scene_id
        if sid is None:
            return
        scene = self.scenes_dict.get(sid)
        if not scene:
            return

        chars = dict(scene.get("characters", {}))
        # 检查当前 entry 是否有立绘覆盖
        dialogues = scene.get("dialogue", [])
        if self.dialogue_index < len(dialogues):
            entry = dialogues[self.dialogue_index]
            if "character_left" in entry:
                chars["left"] = entry["character_left"]
            if "character_right" in entry:
                chars["right"] = entry["character_right"]

        target_side = None
        # 检查哪一侧的角色名匹配说话者
        side_map = {"left": None, "right": None}
        left_id = chars.get("left")
        right_id = chars.get("right")

        if left_id and self._char_matches_speaker(left_id, speaker):
            target_side = "left"
        elif right_id and self._char_matches_speaker(right_id, speaker):
            target_side = "right"
        elif left_id:
            target_side = "left"
        elif right_id:
            target_side = "right"

        if target_side:
            self.app.character_manager.start_speaking(target_side)

    def _char_matches_speaker(self, char_id: str, speaker: str) -> bool:
        """判断立绘 ID 是否匹配说话者。"""
        # 简单实现：角色名出现在立绘 ID 中
        return speaker in char_id or char_id in speaker

    def _make_snapshot(self) -> SceneSnapshot:
        """创建当前场景的快照。"""
        app = self.app
        bg_id = app.background_manager.current_bg_id or ""
        bgm = ""
        if app.audio_engine.bgm_playing and app.audio_engine.bgm_player.source:
            bgm = getattr(app.audio_engine.bgm_player.source, "_filename", "")
        return SceneSnapshot(
            scene_id=self.current_scene_id or "",
            dialogue_index=self.dialogue_index,
            bg_id=bg_id,
            characters={
                "left": getattr(app.character_manager.left, "char_id", None),
                "right": getattr(app.character_manager.right, "char_id", None),
            },
            bgm=bgm,
            variables=dict(app.variable_bank.variables),
        )

    def _restore_snapshot(self, snap: SceneSnapshot) -> None:
        """从快照恢复场景状态。"""
        app = self.app
        # 恢复背景
        if snap.bg_id:
            app.background_manager.set_background(snap.bg_id, "none")
        # 恢复立绘
        if snap.characters:
            app.character_manager.set_characters(snap.characters)
        # 恢复 BGM
        if snap.bgm:
            app.audio_engine.play_bgm(snap.bgm)
        # 恢复变量
        app.variable_bank.variables = dict(snap.variables)
        # 定位到目标对话
        self.current_scene_id = snap.scene_id
        self.dialogue_index = snap.dialogue_index
        self._show_current_dialogue()

    def next_dialogue(self) -> None:
        """推进到下一句对白。"""
        if self._choosing or self._game_ended:
            return
        if self.current_scene_id is None:
            return
        log.debug("推进对话: %s[%d]", self.current_scene_id, self.dialogue_index + 1)

        # 记录当前状态的完整快照（用于"后退"功能）
        # 回退锁定期间不记录（防止 go_back → next 死循环）
        if not self._history_locked:
            self._snapshot_stack.append(self._make_snapshot())
        self._history_locked = False

        self.app.character_manager.stop_speaking()
        self.dialogue_index += 1
        self._show_current_dialogue()

    def go_back(self) -> bool:
        """回退到上一句对话（恢复完整场景状态）。

        Returns:
            True 回退成功，False 无历史可退。
        """
        if not self._snapshot_stack:
            log.warning("没有可回退的历史")
            return False

        snap = self._snapshot_stack.pop()
        log.debug("回退到: %s[%d]", snap.scene_id, snap.dialogue_index)
        self._history_locked = True
        self._restore_snapshot(snap)
        return True

    def go_to_previous_choice(self) -> None:
        """跳转到上一个选项分支点。"""
        for snap in reversed(self._snapshot_stack):
            scene = self.scenes_dict.get(snap.scene_id)
            if scene and scene.get("choices"):
                self._history_locked = True
                self.jump_to_scene(snap.scene_id)
                self.dialogue_index = 0
                return
        log.warning("没有找到上一个选择点")

    def end_scene(self) -> None:
        """场景结束。"""
        self._game_ended = True
        self.app.dialogue_system._text_label.text = "—— END ——"
        self.app.dialogue_system._next_label_visible = False
        self.app.dialogue_system._next_label.opacity = 0
        log.info("场景 '%s' 结束", self.current_scene_id)

    # ──── 存档数据接口 ──────────────────────────────────

    def get_save_data(self) -> dict:
        """获取当前游戏状态快照（用于存档）。"""
        return {
            "scene_id": self.current_scene_id or "",
            "dialogue_index": self.dialogue_index,
            "variables": dict(self.app.variable_bank.variables),
            "chapter_title": self.current_scene_id or "",
            "game_title": self.title,
        }

    def restore_from_save(self, data: dict) -> None:
        """从存档数据恢复游戏状态。"""
        self.app.variable_bank.variables = data.get("variables", {}).copy()
        self.jump_to_scene(data.get("scene_id", self.first_scene))
        self.dialogue_index = data.get("dialogue_index", 0)
        self._show_current_dialogue()

    @property
    def is_choosing(self) -> bool:
        return self._choosing

    @property
    def is_ended(self) -> bool:
        return self._game_ended

    @property
    def title(self) -> str:
        return self.script.get("title", "Visual Novel")

    @property
    def first_scene(self) -> str:
        for sid in self.scenes_dict:
            return sid
        return ""
