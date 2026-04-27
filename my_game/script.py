"""时空回廊 — 剧本定义

使用 ScriptBuilder 继承方式编写的一个短篇视觉小说。
"""

from gal_lib.scriptbuilder import ScriptBase, ScriptScene

# ------------------------------------------------------------------ #
#  场景定义
# ------------------------------------------------------------------ #

class Start(ScriptScene):
    """醒来"""
    id = "start"
    bg = "__my_bg_lab__"
    left = "__my_char_protagonist__"

    def define(self):
        self.say("林夕", "我……这是在哪儿？")
        self.say("???",   "你醒了。这里是时空实验室，你是第47号实验体。")
        self.say("林夕", "实验体？我什么都想不起来了……")
        self.say("???",   "记忆清除的副作用。你的编号是 LX-47，名字叫林夕。")
        self.say("林夕", "林夕……这名字我好像有点印象。")
        self.ask(
            ("环顾四周",   "explore"),
            ("追问实验细节", "question"),
        )


class Question(ScriptScene):
    """追问博士"""
    id = "question"
    bg = "__my_bg_lab__"
    left = "__my_char_mystery__"
    right = "__my_char_protagonist__"

    def define(self):
        self.say("林夕", "到底是什么实验？为什么我在这里？")
        self.say("???",
                 "时空穿梭实验。你是迄今唯一成功的实验体——"
                 "你曾在时间洪流中存活了整整三分钟。")
        self.say("林夕", "三分钟……感觉就像过了一辈子。")
        self.say("???",   "那三分钟改变了你，也改变了我们对你认知。")
        self.say("???",   "你的记忆里残留着时间裂隙的碎片。")
        self.say("???",   "如果你想找回完整的记忆，就去记忆庭院看看吧。")
        self.ask(
            ("前往记忆庭院", "garden"),
            ("在实验室里再走走", "explore"),
        )


class Explore(ScriptScene):
    """探索实验室"""
    id = "explore"
    bg = "__my_bg_lab__"
    left = "__my_char_protagonist__"

    def define(self):
        self.say("林夕", "（环顾实验室，各种仪器闪烁着微光）")
        self.say("林夕",
                 "桌上有一份实验日志，封面写着「Project Chronos — LX 系列」。")
        self.say("林夕", "（翻开日志……）")
        self.say("林夕",
                 "「LX-47 表现出前所未有的时间亲和力。"
                 "他的意识在时间裂隙中不仅存活下来，还在反向影响裂隙本身。」")
        self.say("林夕", "影响时间裂隙……这说的是我吗？")
        self.say("???",   "没错。你是第一个能反过来影响时间裂隙的人。")
        self.say("???",   "你的记忆碎片散落在时间裂隙里，汇聚成了——")
        self.say("???",   "——记忆庭院。去那里，你就能拼凑出真相。")
        self.ask(
            ("前往记忆庭院", "garden"),
            ("继续探索实验室", "lab_deep"),
        )


class LabDeep(ScriptScene):
    """实验室深处"""
    id = "lab_deep"
    bg = "__my_bg_lab__"
    right = "__my_char_protagonist__"

    def define(self):
        self.say("林夕", "（实验室深处有一面巨大的显示屏）")
        self.say("显示屏",
                 "「警告：时间裂隙稳定性下降。建议立即停止 LX 系列实验。」")
        self.say("林夕", "停止实验？难道之前发生过什么事故？")
        self.say("???",   "……LX-23 的实验确实出过意外。")
        self.say("???",   "他的意识被困在时间裂隙里，再也没有回来。")
        self.say("林夕", "什么？！那我现在……")
        self.say("???",
                 "你是不同的。LX-23 是被裂隙吞噬，而你是在影响裂隙。")
        self.say("???",   "你的记忆在裂隙里种下了一片庭院。")
        self.say("林夕", "（沉默片刻）我必须去那里看看。")
        self.ask(
            ("前往记忆庭院", "garden"),
        )


class Garden(ScriptScene):
    """记忆庭院"""
    id = "garden"
    bg = "__my_bg_garden__"
    left = "__my_char_protagonist__"
    right = "__my_char_companion__"

    def define(self):
        self.say("林夕", "（眼前的景象令人窒息——无尽的银色花海在微风中摇曳）")
        self.say("林夕", "这些花……好熟悉。")
        self.say("艾达", "你来了。我就知道你会来的。")
        self.say("林夕", "你是……？")
        self.say("艾达",
                 "我是艾达。你不记得我了，对吗？也是……")
        self.say("艾达",
                 "这些银花是你记忆的具象化。每一朵都代表一段被遗忘的过去。")
        self.say("林夕", "（伸手触碰一朵花，瞬间涌入大量画面）")
        self.say("林夕", "这是……我和一个女孩在庭院里……")
        self.say("艾达", "那是我。我们曾经是恋人。")
        self.say("艾达",
                 "你为了治好我的绝症，自愿参加了时空实验。"
                 "你想回到过去改变一切。")
        self.say("林夕", "（震惊）我……我是为了你？")
        self.say("艾达",
                 "但实验出了偏差。你确实回到了过去，"
                 "可每回来一次，你的记忆就会被清除一部分。")
        self.say("艾达",
                 "这是你第47次醒来。每一次，你都会重新选择。")
        self.ask(
            ("握住艾达的手", "ending_a"),
            ("退缩——我承受不了这些", "ending_b"),
        )


class EndA(ScriptScene):
    """结局 A：跨越时间"""
    id = "ending_a"
    bg = "__my_bg_garden__"
    left = "__my_char_companion__"
    right = "__my_char_protagonist__"

    def define(self):
        self.say("林夕", "（握住艾达的手）无论重来多少次，我都会选择记住你。")
        self.say("艾达", "（微笑中带着泪光）你还是和以前一样固执。")
        self.say("林夕",
                 "这47次醒来，每一次我都选择了你。\n"
                 "即使记忆被抹去，心还记得。")
        self.say("艾达",
                 "也许这就是你影响时间裂隙的方式——\n"
                 "用爱在时间的洪流里刻下坐标。")
        self.say("林夕", "我们重新开始吧。这一次，我不会再让自己忘记你。")
        self.say("艾达", "好。这一次，我们一起面对。")
        self.say("", "—— 时空回廊 · 跨越时间的约定 ——")


class EndB(ScriptScene):
    """结局 B：无限孤独"""
    id = "ending_b"
    bg = "__my_bg_corridor__"
    left = "__my_char_protagonist__"

    def define(self):
        self.say("林夕", "（后退一步）对不起……我……我需要时间消化这些。")
        self.say("艾达", "（眼神黯淡下来）我明白。每一次，你都是这么说的。")
        self.say("林夕", "每一次？")
        self.say("艾达",
                 "每一次醒来，我都会在这里等你。\n"
                 "每一次，你都会在知道真相后选择逃避。")
        self.say("艾达",
                 "然后遗忘，再次醒来，再次选择。\n"
                 "这就是你的第47次循环。")
        self.say("林夕", "（看着自己的双手）那我……永远都无法打破这个循环吗？")
        self.say("艾达",
                 "只有你能回答这个问题。\n"
                 "等你准备好了，我会一直在记忆庭院等你。")
        self.say("", "—— 时空回廊 · 无尽的轮回 ——")


# ------------------------------------------------------------------ #
#  剧本
# ------------------------------------------------------------------ #

class CorridorOfTime(ScriptBase):
    """时空回廊 — 完整剧本"""
    title = "时空回廊"
    version = "1.0"
    scenes = [
        Start,
        Question,
        Explore,
        LabDeep,
        Garden,
        EndA,
        EndB,
    ]
