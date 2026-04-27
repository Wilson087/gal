"""剧本加载与验证测试"""

import pytest
from gal_lib.script import validate_script, DEMO_SCRIPT


class TestValidateScript:
    """validate_script 功能测试"""

    def test_valid_demo_script(self):
        """演示剧本应是有效的。"""
        errors = validate_script(DEMO_SCRIPT)
        assert errors == [], f"演示剧本验证失败: {errors}"

    def test_missing_scenes(self):
        """缺少 scenes 应返回错误。"""
        errors = validate_script({})
        assert len(errors) > 0

    def test_scenes_not_list(self):
        """scenes 不是 list 应返回错误。"""
        errors = validate_script({"scenes": "bad"})
        assert len(errors) > 0

    def test_scene_missing_id(self):
        """场景缺少 id 应报错。"""
        script = {"scenes": [{"dialogue": [{"text": "hi"}]}]}
        errors = validate_script(script)
        assert any("id" in e for e in errors)

    def test_scene_missing_dialogue(self):
        """场景缺少 dialogue 应报错。"""
        script = {"scenes": [{"id": "s1"}]}
        errors = validate_script(script)
        assert any("dialogue" in e for e in errors)

    def test_choice_missing_next_scene(self):
        """选项缺少 next_scene 应报错。"""
        script = {"scenes": [
            {"id": "s1", "dialogue": [{"text": "hi"}],
             "choices": [{"text": "opt"}]}
        ]}
        errors = validate_script(script)
        assert any("next_scene" in e for e in errors)

    def test_duplicate_scene_id(self):
        """重复场景 id 应报错。"""
        script = {"scenes": [
            {"id": "dup", "dialogue": [{"text": "a"}]},
            {"id": "dup", "dialogue": [{"text": "b"}]},
        ]}
        errors = validate_script(script)
        assert any("重复" in e for e in errors)
