@scene 学校-校门
@bgm title_bgm

"Visual Novel Engine V2.5"
"—— 春日野穹 ——"

@label menu

@choice
"开始游戏": jump new_game
"继续游戏": jump load_game
"CG 画廊": jump cg_gallery
"音乐欣赏": jump music_room
"立绘鉴赏": jump character_viewer
"退出游戏": jump quit

@label new_game
@flag new_game true
@jump start_game

@label load_game
@flag load_game true
@jump start_game

@label cg_gallery
@flag open_gallery true
@jump start

@label music_room
@flag open_music true
@jump start

@label character_viewer
@flag open_viewer true
@jump start

@label quit
@flag quit_game true
@jump start

@label start_game
@end
