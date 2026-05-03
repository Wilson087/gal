@scene 学校-校门
@bgm bgm01
@show 春日野穹 校服-S at center

"四月。樱花瓣在微风中飘落，校门前站满了新入学的面孔。"
"又是一个寻常的春天——但对我来说，这个春天却格外不同。"

"你" "春日野穹，早上好。"
"春日野穹" "前辈，早上好～"
@show 春日野穹 校服-M at center

@flag met_sora true

"你" "今天是你第一次值日，有什么不明白的地方随时问我。"
"春日野穹" "谢谢前辈！我会努力的。"

@scene 学校-教室
@show 春日野穹 校服-S at center

"教室里已经空无一人，夕阳从窗外斜斜地照进来。"
"穹正认真地擦着黑板，粉笔灰在光线中飞舞。"

"春日野穹" "前辈，你为什么愿意帮我？"
"你" "唔……因为你看起来需要帮助？"

@flag cg001_seen true
@flag bgm01_heard true

"你" "穹，今天辛苦了。"
"春日野穹" "前辈也是！明天见！"

@bgm bgm02

@scene 家-客厅

"回到家中，手机上收到了穹的消息。"
"春日野穹" "「前辈，今天真的谢谢你了！明天一起回家吧？」"

@choice
"好的，明天一起走": jump walk_home
"抱歉，明天有社团活动": jump busy_tomorrow

@label walk_home
@flag agreed_walk true

"你" "穹，好啊，明天一起回家。"
"春日野穹" "太好了！那放学后在校门口见！"

@jump after_choice

@label busy_tomorrow
@flag declined_walk true

"你" "抱歉，明天有社团活动……"
"春日野穹" "这样啊……没关系，前辈先忙吧～"

@jump after_choice

@label after_choice

@scene 学校-教室
@show 春日野穹 校服-S at center

"第二天放学后。"
@if agreed_walk
"校门口，穹已经等在那里，看到我时脸上露出了灿烂的笑容。"
@show 春日野穹 校服-M at center
@jump walk_scene

@if declined_walk
"我刚走出教室，就看到穹抱着一叠书迎面走来。"
"春日野穹" "前辈！刚好碰到你，帮我拿一下好吗？"
"你" "当然可以。"
@jump walk_scene

@label walk_scene

@flag cg002_seen true
@flag bgm02_heard true

@bgm bgm01

@scene 商场
@show 春日野穹 校服-S at center

"周末，约穹一起去商场。"
"你" "这里的可丽饼很好吃哦。"

@flag cg003_seen true
@flag bgm03_heard true

"你" "穹，有什么想买的东西吗？"
"春日野穹" "嗯……我想买个发饰，前辈帮我挑一个吧？"

@choice
"这个红色的很适合你": jump red_ribbon
"蓝色的更配你的气质": jump blue_ribbon
"都很好看，你选哪个我都喜欢": jump any_ribbon

@label red_ribbon
@flag chose_red true

"你" "这个红色的，衬你的发色。"
"春日野穹" "真的吗？那我要这个！"

@jump after_shop

@label blue_ribbon
@flag chose_blue true

"你" "蓝色的，很配你温柔的气质。"
"春日野穹" "前辈……"

@jump after_shop

@label any_ribbon
@flag chose_any true

"你" "这两个颜色都很好看，看你喜欢哪个。"
"春日野穹" "那……这个蓝色的吧，因为和前辈的眼睛颜色一样。"

@jump after_shop

@label after_shop

@bgm bgm02

@scene 家-门口
@show 春日野穹 校服-S at center

"傍晚，送穹回到家门口。"
"春日野穹" "今天真的很开心，谢谢你陪我来。"

"你" "穹，今天谢谢了。"
"你" "下次再一起出来吧。"

"春日野穹" "嗯！前辈，我有个东西想给你……"
"（穹从包里拿出一个小盒子）"

@flag cg003_seen true

"春日野穹" "这是我自己做的饼干，虽然可能不太好看……"
"你" "你做的？那我一定要尝尝。"

"春日野穹" "前辈……其实从第一次见到你开始，我就一直……"
"你" "嗯？"
"春日野穹" "没什么！明天学校见！"

@bgm bgm01

@scene 学校-校门
@show 春日野穹 校服-S at center

"四月很快就过去了。"
"但我和穹的故事，才刚刚开始。"

@flag prologue_clear true
@flag bgm01_heard true
@flag bgm02_heard true

@end
