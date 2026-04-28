# gal-lib-pyglet — 基于 pyglet 的现代视觉小说引擎

## 概述

gal-lib-pyglet 是一个从零构建的视觉小说引擎，基于 **pyglet 2.1+**，使用 Python 3.10+。
引擎采用模块化架构，提供完整的视觉小说开发体验。

本项目为 **engine-v2** 分支，是对旧版 (gal_lib/ + visual_novel.py) 的完全重写。

## 功能特性

- **对话系统** — 打字机效果，支持 `{b}`/`{i}`/`{color}`/`{speed}`/`{w}`/`{shake}` 等富文本标记
- **选项分支** — 条件过滤 (`if` 表达式)，变量驱动分支流程
- **角色立绘** — 左右双立绘，淡入淡出切换，说话浮动动画
- **背景管理** — 4 种适配模式 (cover/fit/stretch/original)，窗口自适应
- **音频引擎** — 三通道 (BGM/SFX/Voice)，BGM 自动 ducking，多格式支持
- **特效系统** — 镜头转场 (淡入淡出/滑动/百叶窗/涟漪)，画面滤镜 (sepia/night/memory)，粒子效果 (雪/雨)，屏幕震动
- **存档系统** — 100 槽位，截图缩略图，快速存档/读档 (F5/F9)
- **历史记录** — 对话历史回溯，点击跳转
- **设置面板** — 5 标签页 (显示/音频/文本/游戏/操作)，所有设置即时生效
- **主菜单** — 新游戏/继续/载入/剧本选择/设置/退出
- **工具栏** — 底部 15 按钮常驻工具栏
- **剧本选择** — 扫描 `scripts/` 目录，动态加载任意剧本
- **快照回退** — 场景快照栈，支持逐句后退
- **配置持久化** — JSON 配置，原子写入，窗口位置记忆

## 环境要求

- Python 3.10+
- pyglet >= 2.1

## 快速开始

```bash
# 安装依赖
pip install pyglet>=2.1

# 启动游戏
python main.py
```

## 项目结构

```
gal-lib-pyglet/
├── main.py                  # 启动入口
├── config.json              # 用户配置（自动生成）
├── pyproject.toml           # 项目元数据
├── .gitignore
├── engine/                  # 引擎核心
│   ├── app.py               # 主应用窗口，子系统编排
│   ├── scene_manager.py     # 场景状态机，对话推进
│   ├── dialogue.py          # 对话显示，打字机效果
│   ├── choice.py            # 选项分支系统
│   ├── character.py         # 角色立绘管理
│   ├── background_manager.py# 背景加载与适配
│   ├── audio.py             # 三通道音频引擎
│   ├── effects.py           # 转场/滤镜/粒子/震动
│   ├── config.py            # 配置数据类与持久化
│   ├── variable.py          # 运行时变量系统
│   ├── save_manager.py      # 存档管理
│   ├── history_manager.py   # 历史记录
│   ├── rich_text.py         # 富文本标记解析
│   ├── script_loader.py     # 剧本加载与验证
│   ├── main_menu.py         # 主菜单界面
│   ├── ui_manager.py        # UI 编排器（工具栏/面板/通知）
│   ├── settings_panel.py    # 设置面板
│   ├── save_load_panel.py   # 存档/读档面板
│   ├── history_panel.py     # 历史记录面板
│   ├── style.py             # 样式定义
│   ├── layout.py            # 布局容器（HBox/VBox/Grid）
│   ├── frame.py             # Frame 容器
│   ├── logger.py            # 日志系统
│   └── constants.py         # 全局常量
├── scripts/                 # 剧本文件 (.json)
│   └── harukanaru_sora.json # 示例剧本
├── audio/                   # 音频资源
├── resources/
│   ├── images/              # 图片资源（背景/立绘）
│   └── fonts/               # 字体文件
├── saves/                   # 存档文件（自动生成）
└── logs/                    # 运行日志（自动生成）
```

## 剧本格式

剧本以 JSON 格式存放于 `scripts/` 目录，引擎启动时会扫描该目录下的所有 `.json` 文件。

### 基本结构

```json
{
  "title": "游戏标题",
  "version": "1.0",
  "character_colors": {
    "角色名": [R, G, B, A]
  },
  "scenes": [
    {
      "id": "scene_001",
      "background": "bg_room",
      "bgm": "bgm_peaceful",
      "characters": {
        "left": "char_girl",
        "right": "char_boy"
      },
      "dialogue": [
        {
          "speaker": "角色名",
          "text": "对话内容",
          "voice": "voice_file",
          "sfx": "sfx_file"
        }
      ],
      "choices": [
        {
          "text": "选项文字",
          "next_scene": "scene_002",
          "if": "variable > 5"
        }
      ]
    }
  ]
}
```

### 富文本标记

| 标记 | 说明 |
|------|------|
| `{b}{/b}` | 粗体 |
| `{i}{/i}` | 斜体 |
| `{color=#rrggbb}{/color}` | 文字颜色 |
| `{speed=N}{/speed}` | 打字速度倍率 |
| `{w=N}` | 暂停 N 秒 |
| `{shake}` | 文字震动 |
| `{font=字体名}{/font}` | 字体切换 |

## 操作说明

| 按键 | 功能 |
|------|------|
| 空格 / Enter | 推进对话 |
| ESC | 打开/关闭设置 |
| F5 | 快速保存 |
| F9 | 快速读取 |
| Ctrl + S | 打开存档界面 |
| Ctrl + L | 打开读档界面 |
| H | 历史记录 |
| A | 切换自动播放 |
| 按住 Ctrl | 快进文本 |
| F11 | 全屏切换 |

底部工具栏同时提供全部功能的按钮入口。

## License

MIT
