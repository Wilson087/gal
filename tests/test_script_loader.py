"""剧本加载与验证单元测试。"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.core.script_loader import validate_script


class TestScriptValidation:
    def test_valid_minimal_script(self):
        script = {
            "title": "test",
            "scenes": [
                {
                    "id": "scene1",
                    "dialogue": [
                        {"speaker": "", "text": "hello"}
                    ]
                }
            ]
        }
        errors = validate_script(script)
        assert len(errors) == 0

    def test_missing_scenes(self):
        errors = validate_script({"title": "test"})
        assert len(errors) == 1
        assert "scenes" in errors[0]

    def test_not_a_dict(self):
        errors = validate_script([])
        assert len(errors) == 1
        assert "dict" in errors[0]

    def test_missing_scene_id(self):
        script = {
            "scenes": [
                {"dialogue": [{"text": "hello"}]}
            ]
        }
        errors = validate_script(script)
        assert any("id" in e for e in errors)

    def test_duplicate_scene_id(self):
        script = {
            "scenes": [
                {"id": "s1", "dialogue": [{"text": "a"}]},
                {"id": "s1", "dialogue": [{"text": "b"}]},
            ]
        }
        errors = validate_script(script)
        assert any("重复" in e for e in errors)

    def test_missing_dialogue(self):
        script = {
            "scenes": [
                {"id": "s1"}
            ]
        }
        errors = validate_script(script)
        assert any("dialogue" in e for e in errors)

    def test_dialogue_entry_missing_text(self):
        script = {
            "scenes": [
                {
                    "id": "s1",
                    "dialogue": [
                        {"speaker": "test"}
                    ]
                }
            ]
        }
        errors = validate_script(script)
        assert any("text" in e for e in errors)

    def test_choice_missing_text(self):
        script = {
            "scenes": [
                {
                    "id": "s1",
                    "dialogue": [{"text": "hello"}],
                    "choices": [{"next_scene": "s2"}]
                }
            ]
        }
        errors = validate_script(script)
        assert any("text" in e for e in errors)

    def test_choice_missing_next_scene(self):
        script = {
            "scenes": [
                {
                    "id": "s1",
                    "dialogue": [{"text": "hello"}],
                    "choices": [{"text": "go"}]
                }
            ]
        }
        errors = validate_script(script)
        assert any("next_scene" in e for e in errors)

    def test_choices_not_a_list(self):
        script = {
            "scenes": [
                {
                    "id": "s1",
                    "dialogue": [{"text": "hello"}],
                    "choices": "invalid"
                }
            ]
        }
        errors = validate_script(script)
        assert any("choices" in e for e in errors)

    def test_scene_not_dict(self):
        script = {
            "scenes": ["not a dict"]
        }
        errors = validate_script(script)
        assert any("dict" in e for e in errors)

    def test_multiple_errors(self):
        script = {
            "scenes": [
                {"id": "", "dialogue": "bad"},
                {"id": "dupe", "dialogue": [{}]},
                {"id": "dupe", "dialogue": [{"text": "ok"}]},
            ]
        }
        errors = validate_script(script)
        assert len(errors) >= 3
