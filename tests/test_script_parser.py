from collections.abc import Sequence
import unittest

from src.engine.game.script_parser import Persona, Scene, Dialogue, Data

class BrownFox(Persona):
    name = "Brown Fox"
    color = "#a05602"

class LazyDog(Persona):
    name = "Lazy Dog"
    color = "#F3B860"

class Forest(Scene):
    name = "Forest"

class Hello(Dialogue):
    def flow(self):
        # s =  self.scene(Forest)
        self.scene = Forest

        f = self.persona(BrownFox)
        f.say("Hello!")

        d = self.persona(LazyDog)
        d.say("Zzz...")

        self.narration("The quick brown fox jumps over the lazy dog.")

class TestScriptParser(unittest.TestCase):
    def test_persona(self):
        """
        测试角色数据生成
        """
        v = Data.to_value()
        BrownFox().build(v)
        self.assertEqual(v.close(), {
            "id": "BrownFox",
            "name": "Brown Fox", 
            "color": "#a05602"
        })

    def test_scene(self):
        """
        测试场景数据生成
        """
        v = Data.to_value()
        Forest().build(v)
        self.assertEqual(v.close(), {
            "id": "Forest",
            "name": "Forest"
        })

    def test_dialogue(self):
        """
        测试对话数据生成
        """
        v = Data.to_value()
        Hello().build(v)
        r = v.close()
        assert isinstance(r, dict)
        self.assertIn("id", r)
        self.assertEqual(r["id"], "Hello")
        self.assertIn("dialogue", r)
        self.assertIsInstance(r["dialogue"], Sequence)
        flow = [
            # {"type": "scene", "params": {"id": 0, "scene": "Forest"}},
            {"type": "scene", "params": {"scene": "Forest"}},
            {"type": "persona", "params": {"id": 0,"persona": "BrownFox"}},
            {"type": "say", "params": {"id": 0, "text": "Hello!"}},
            {"type": "persona", "params": {"id": 1, "persona": "LazyDog"}},
            {"type": "say", "params": {"id": 1, "text": "Zzz..."}},
            {"type": "narration", "params": {"text": "The quick brown fox jumps over the lazy dog."}},
            # {"type": "del_scene", "params": {"id": 0}},
            {"type": "del_persona", "params": {"id": 0}},
            {"type": "del_persona", "params": {"id": 1}}
        ]
        for rf, f in zip(r["dialogue"], flow):
            self.assertEqual(rf, f)