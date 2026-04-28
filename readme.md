# gal-lib — 视觉小说游戏引擎（现代化版 v2.0）

基于 Python tkinter 标准库，**零第三方依赖**的视觉小说游戏引擎。
从基础框架全面升级至商业级视觉小说引擎的用户体验水准。

## 快速开始

```bash
# 运行演示剧本（内置「星之回响」）
python run_game.py

# 或运行完整游戏「时空回廊」
python run_my_game.py
```

```python
import tkinter as tk
from gal_lib import VNGame, DEMO_SCRIPT

root = tk.Tk()
app = VNGame(root)
app.load_script(DEMO_SCRIPT)
app.start_game()
root.mainloop()
```

## 项目结构

```
gal/
├── gal_lib/                  # 引擎核心库
│   ├── __init__.py           # 包入口，导出 VNGame + 工具函数
│   ├── engine.py             # 主引擎 VNGame 类（场景/对话/存档/设置）
│   ├── audio.py              # 四通道音频引擎（BGM/SFX/Voice）
│   ├── renderer.py           # Canvas 渲染函数（背景/立绘/遮罩/圆角矩形）
│   ├── effects.py            # 视觉特效系统（转场/滤镜/粒子/震动/闪光）
│   ├── rich_text.py          # 富文本标记解析器 {w=} {shake} {color=}
│   ├── script.py             # 剧本加载与验证 + 内置 DEMO_SCRIPT
│   ├── scriptbuilder.py      # 面向对象剧本构建器
│   ├── constants.py          # 全局常量配置
│   └── vectorgraphics.py     # 矢量图渲染引擎（JSON/SVG/PNG）
├── my_game/                  # 示例游戏
│   ├── __init__.py           # 启动入口
│   ├── script.py             # 「时空回廊」剧本 (ScriptBuilder)
│   ├── harukanaru_sora.json  # 「夏空の轮廓」剧本 JSON
│   ├── constants.py          # 角色/背景注册 + PNG 素材注册
│   └── resources/
│       ├── vectors/          # 矢量精灵 JSON 定义（旧项目）
│       └── images/           # PNG 素材（背景・立绘）
├── audio/                    # 音频文件目录
│   └── 背景bgm01....flac     # 缘之空主题曲
├── voice/                    # 语音文件目录
├── saves/                    # 存档目录（自动创建）
├── run_game.py               # 演示剧本「星之回响」
├── run_my_game.py            # 「时空回廊」启动入口
├── run_haruka.py             # 「夏空の轮廓」启动入口
├── diagnose.py               # 素材诊断工具
└── visual_novel.py           # 单文件独立版引擎（旧版）
```

## 功能清单

### 一、对话与演出系统

| 功能 | 实现 |
|------|------|
| 打字机逐字效果 | 定时器驱动，支持变速 |
| **富文本标记** | `{w=0.5}` 暂停 / `{shake}` 震动 / `{color=#ff0000}` 变色 / `{speed=2}` 变速 |
| **说话浮动动画** | 角色说话时立绘上下浮动，语音结束即停止 |
| **口型同步模拟** | 语音播放期间立绘做缩放脉冲 |
| 角色名标签颜色 | 剧本通过 `character_colors` 配置 |
| 对话框位置切换 | 底部（默认）/ 顶部 / 全屏 |

### 二、音频系统

| 功能 | 说明 |
|------|------|
| BGM 循环播放 | ffplay `-loop 0` 或 winsound 循环 |
| SFX 播放 | 独立线程播放，自动恢复 BGM |
| **Voice 语音** | 独立 ffplay 进程，与 BGM 同时发声 |
| **BGM 交叉淡入淡出** | 双进程短暂重叠，旧进程渐静 + 新进程渐响 |
| **循环点支持** | `play_bgm(path, loop_point=秒数)` |
| **音效排队** | 队列 `deque` + 工作线程，防止 SFX 重叠 |
| **三通道独立音量** | BGM / SFX / Voice 各 0–100 独立滑块 |

### 三、视觉特效系统

#### 转场效果（4种）

| 效果 | 方法 | 实现方式 |
|------|------|----------|
| 淡入淡出 | `transition_crossfade` | 白色遮罩 stipple 渐入渐出 |
| 滑动 | `transition_slide` | 条状遮罩逐条揭露（左/右） |
| 百叶窗 | `transition_blinds` | 垂直条随机消失 |
| 涟漪 | `transition_ripple` | 白色遮罩 + 圆形镂空扩散 |

#### 屏幕滤镜

| 滤镜 | 色值 | 适用场景 |
|------|------|----------|
| sepia | `#704214` | 褐色回忆 / 过去 |
| night | `#1a2a5e` | 夜晚 / 压抑 |
| memory | `#4a2a4a` | 紫色幻想 / 记忆 |

#### 天气粒子

| 效果 | 粒子数 | 实现 |
|------|--------|------|
| 飘雪 | 60 | Canvas 白色椭圆 + 正弦摇摆 + 下落 |
| 雨丝 | 80 | Canvas 白色短线 + 斜向加速 |

#### 画面特效

| 效果 | 实现方式 |
|------|----------|
| 震动 | Canvas `scan_dragto` 随机偏移 |
| 闪光 | 全屏颜色矩形 + stipple 渐隐 |

### 四、系统功能

#### 存档 / 读档

- **多槽位**: 100 槽，分页显示（3×4 网格），前后翻页
- **存档信息**: 日期时间、对话摘要
- **快速存档**: F5 存档 / F9 读档
- **自动存档**: 框架预留位
- **数据完整**: 场景 + 索引 + 变量 + CG + 三通道音量 + 文字速度 + 历史

#### 设置菜单

| 设置项 | 交互方式 |
|--------|----------|
| 文字速度 | 滑块 10–200 ms/字 + 快速/普通/慢速/很慢 预设 |
| BGM 音量 | 滑块 0–100 |
| SFX 音量 | 滑块 0–100 |
| Voice 音量 | 滑块 0–100 |
| 全局静音 | 复选框 |
| 跳过模式 | 单选: 关闭 / 已读跳过 / 全部跳过 |
| 全屏切换 | 复选框 + F11 |
| 对话框位置 | 单选: 底部 / 顶部 / 全屏 |

#### 其他系统

| 功能 | 触发方式 |
|------|----------|
| 主菜单 | 启动自动显示（新游戏 / 继续 / 画廊 / 设置 / 退出） |
| 自动模式 | 按 `A` 键切换，文本长度 + 语音时长计算自动推进间隔 |
| 文本历史 | 完整滚动列表，含 🔊 语音重播按钮，支持滚轮 |
| 历史导出 | 导出为 UTF-8 .txt |
| CG 画廊 | 解锁式缩略图网格 |
| 快捷键 | S 存档 · L 读档 · H 历史 · Esc 设置 · F5 快速存档 · F9 快速读档 · F11 全屏 |

### 五、脚本系统进阶

#### 变量系统

```json
{
    "speaker": "系统",
    "text": "好感度 +1",
    "set_var": {"affection": "+1"}
}
```

引擎侧读取：`game.get_var("affection")` → 返回 1。

支持 `+N` / `-N` 相对赋值语法。

#### 条件分支

选项可用 `if` 字段控制显示条件：

```json
{
    "text": "表白",
    "next_scene": "good_ending",
    "if": "affection > 5"
}
```

支持的运算符: `>`, `<`, `>=`, `<=`, `==`, `!=`

#### 角色名颜色

剧本顶层配置角色名颜色：

```python
script["character_colors"] = {
    "林夕": "#3498DB",
    "艾达": "#E91E63"
}
```

## 示例剧本：「夏空の轮廓」

基于本引擎创作的《缘之空》同人短篇，位于 `my_game/harukanaru_sora.json`。

### 素材清单

**背景**（`my_game/resources/images/`，4:3 → 引擎自动 letterbox 居中）

| 文件 | 像素 | 场景用途 |
|------|------|----------|
| `家-卧室.png` | 800×600 | 悠的卧室 |
| `家-客厅.png` | 800×600 | 家中客厅 |
| `家-门口.png` | 800×600 | 玄关 / 走廊 |

**立绘**（`my_game/resources/images/`）

| 文件 | 像素 | 说明 |
|------|------|------|
| `春日野穹-哥特服装-L.png` | 956×608 | L=特写近景，用于亲密场景 |
| `春日野穹-哥特服装-M.png` | 557×528 | M=半身中景，用于中立场景 |
| `春日野穹-哥特服装-S.png` | 403×522 | S=全身远景，用于疏远场景 |
| `春日野穹-哥特服装-S-开心.png` | 403×522 | S尺寸 + 开心表情 |
| `春日野穹-哥特服装-S-不悦.png` | 403×522 | S尺寸 + 不悦表情 |
| `春日野穹-校服-*.png` | — | 校服版本（未使用） |

### 立绘命名规则

```
角色名-服装-尺寸[-表情].png
         ↑      ↑      ↑
        L/M/S  可选：开心/不悦
```

尺寸选择指导：
- **L**（大）—— 特写，用于亲密、情感强烈的场景
- **M**（中）—— 半身，标准对话构图
- **S**（小）—— 全身，用于疏远、距离感的画面

### 注册方式

在 `my_game/constants.py` 中用 `register_png()` 将 PNG 注册到引擎：

```python
from gal_lib.vectorgraphics import register_png

# 背景（全屏，引擎自动居中 letterbox）
register_png("家-卧室", "my_game.resources.images", "家-卧室.png", width=1920, height=1080)

# 立绘（底部锚点 anchor="s" 自动对齐）
register_png("春日野穹-哥特服装-L", "my_game.resources.images",
             "春日野穹-哥特服装-L.png", width=956, height=608)
```

注册后剧本中用 ID 引用：
```json
"background": "家-卧室",
"character_right": "春日野穹-哥特服装-L"
```

### 启动

```bash
python run_haruka.py
```

## 剧本格式

### JSON 完整字段

```json
{
    "title": "游戏标题",
    "version": "1.0",
    "character_colors": {"角色名": "#颜色值"},
    "scenes": [
        {
            "id": "scene_id",
            "background": "__bg_id__",
            "bgm": "music.mp3",
            "bgm_loop_point": 10.5,
            "filter": "sepia",
            "weather": "snow",
            "characters": {"left": "__char_a__", "right": "__char_b__"},
            "dialogue": [
                {
                    "speaker": "角色名",
                    "text": "对白文本 {color=#ff0000}红字{/color} {w=0.5}",
                    "character_left": "__new_char__",
                    "voice": "vo_001.wav",
                    "sfx": "sfx_click.wav",
                    "set_var": {"affection": "+1"}
                }
            ],
            "choices": [
                {
                    "text": "选项文字",
                    "next_scene": "target",
                    "if": "affection > 3",
                    "set_var": {"affection": "+2"}
                }
            ]
        }
    ]
}
```

### ScriptBuilder 继承方式

```python
from gal_lib.scriptbuilder import ScriptBase, ScriptScene

class Opening(ScriptScene):
    id = "start"
    bg = "__my_bg__"
    left = "__my_char__"
    bgm = "music.flac"

    def define(self):
        self.say("角色", "对白 {color=#ff0000}红字{/color}")
        self.say("角色", "语音", voice="vo_001.wav")
        self.ask(
            ("选项一", "scene_a"),
            ("选项二", "scene_b"),
        )

class MyGame(ScriptBase):
    title = "我的游戏"
    version = "1.0"
    scenes = [Opening]

app.load_script(MyGame().build())
```

## 操作方式

| 按键 | 功能 |
|------|------|
| Space / Enter / 鼠标左键 | 推进对话 / 跳过打字 |
| `A` | 切换自动模式 |
| `S` | 打开存档界面 |
| `L` | 打开读档界面 |
| `H` | 文本历史 |
| `Esc` | 设置面板 |
| `F5` | 快速存档 |
| `F9` | 快速读档 |
| `F11` | 全屏切换 |

## 音频资源

将音乐与音效放入 `audio/` 目录，语音放入 `voice/` 目录：

| 后端 | 支持格式 | 前置条件 |
|------|----------|----------|
| ffplay | mp3, ogg, flac, wav, m4a, opus, wma | 安装 FFmpeg |
| winsound | 仅 .wav | 无需安装 |

```python
audio.play_bgm("bgm.mp3")         # 从 audio/ 搜索
audio.play_voice("vo_001.wav")    # 从 voice/ 搜索
audio.play_sfx("click.wav")      # 从 audio/ 搜索
```

## 存档格式

存档使用 pickle 序列化，磁盘存储于 `saves/save_{slot}.dat`：

```python
{
    "scene_id": str,          # 当前场景 ID
    "dialogue_index": int,    # 对白索引
    "text_speed": int,        # 文字速度
    "volume": int,            # 全局音量
    "volume_bgm": int,        # BGM 音量
    "volume_sfx": int,        # SFX 音量
    "volume_voice": int,      # Voice 音量
    "history": list,          # 最近 50 条历史
    "variables": dict,        # 变量系统快照
    "unlocked_cgs": list,     # 已解锁 CG 列表
    "date": str,              # 存档时间
    "summary": str,           # 对话摘要
    "scene_title": str,       # 场景名称
}
```

## 技术限制

| 限制 | 说明 |
|------|------|
| 无真正 alpha 混合 | tkinter stipple 半色调抖动近似透明度 |
| 无截图缩略图 | 纯色占位 + 文字摘要（零依赖原则，无 PIL） |
| CG 无实际截图 | 仅显示场景名和颜色占位 |

## 依赖

- **Python** ≥ 3.10
- **FFmpeg**（可选）— 提供 ffplay 实现多格式音频 + 音量控制
- 无任何第三方 Python 包

## License

MIT
