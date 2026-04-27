# gal-lib — 视觉小说游戏引擎

基于 Python 标准库（tkinter）的视觉小说（Galgame）引擎，零第三方依赖。

## 快速开始

```bash
# 运行演示剧本
python run_game.py

# 或运行独立版游戏
python visual_novel.py

# 运行"时空回廊"剧本
python run_my_game.py
```

## 功能特性

- **剧本驱动** — JSON 格式定义剧情数据，结构清晰
- **对话系统** — 底部面板角色名+对白，逐字打字机效果
- **立绘系统** — 左右双立绘切换，带淡入淡出过渡
- **背景切换** — Canvas 背景切换，白色淡入淡出
- **选项分支** — 多选项分支，点击跳转指定场景
- **音频引擎** — BGM 循环播放 + 每句对白独立音效
  - 自动检测 ffplay（支持 mp3/ogg/flac/wav）或降级 winsound（仅 wav）
  - 实时音量调节（Windows COM 接口，不重启音频）
  - 窗口关闭自动停止播放，atexit 双重兜底
- **存档/读档** — S 键存档 / L 键读档（pickle 序列化）
- **文本历史** — H 键查看最近对白
- **设置面板** — Esc 键打开，调节文字速度与音量

## 操作方式

| 按键 | 功能 |
|------|------|
| Space / 鼠标左键 | 推进对话 / 跳过打字效果 |
| S | 存档 |
| L | 读档 |
| H | 文本历史 |
| Esc | 设置面板 |

## 项目结构

```
gal/
├── run_game.py              # 启动入口（演示剧本）
├── run_my_game.py           # "时空回廊"启动入口
├── visual_novel.py          # 单文件独立版引擎
├── pyproject.toml            # 项目元数据
├── audio/                   # 音频资源目录（放 BGM / SFX）
├── saves/                   # 存档目录（自动创建）
├── tests/                   # 单元测试
└── gal_lib/                 # 核心库
    ├── __init__.py           # 导出 VNGame, DEMO_SCRIPT, AudioEngine ...
    ├── constants.py          # 窗口尺寸、颜色、字体等常量
    ├── script.py             # 演示剧本数据 + 加载/验证函数
    ├── renderer.py           # Canvas 渲染函数（背景、立绘、遮罩）
    ├── engine.py             # VNGame 主引擎类
    ├── audio.py              # AudioEngine 音频引擎
    ├── scriptbuilder.py      # 面向对象剧本构建器
    └── vectorgraphics.py     # 矢量图绘制与图片加载
```

## 剧本格式

```json
{
  "title": "游戏标题",
  "scenes": [
    {
      "id": "scene1",
      "background": "__bg_room__",
      "bgm": "music.mp3",
      "characters": { "left": "__char_girl__", "right": null },
      "dialogue": [
        { "speaker": "角色", "text": "对白内容", "sfx": "click.wav" }
      ],
      "choices": [
        { "text": "选项文字", "next_scene": "scene2" }
      ]
    }
  ]
}
```

也支持 Python 代码构建剧本：

```python
from gal_lib.scriptbuilder import NovelScript, Scene

script = NovelScript("我的游戏")
scene = Scene("start", bg="...", left="...", bgm="bgm.mp3")
scene.dialogue("角色", "对白", sfx="sfx.wav")
scene.choices(("选项", "next_scene"))
script.add_scene(scene)
game.load_script(script.build())
```

## 音频资源

将音频文件放入 `audio/` 目录，在剧本中用相对路径引用：

- 有 ffmpeg（推荐）：支持 mp3 / ogg / flac / wav / m4a / opus 等
- 无 ffmpeg：仅支持 .wav（自动降级 winsound）

## 依赖

- Python 3.10+
- 零第三方 Python 包
- FFmpeg（可选，用于全格式音频支持 + 实时音量调节）

## License

MIT
