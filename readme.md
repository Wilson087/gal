# Visual Novel Engine V2.5

基于 **pyglet 2.1+** 的现代视觉小说引擎，从零重写。
事件驱动架构，弱引用事件总线，状态机分发，惰性加载 + LRU 缓存资源管理。

## 项目结构

```
├── config.py                  # 全局常量 + AppConfig dataclass
├── main.py                    # GameWindow 入口（vsync / 60fps / 焦点暂停）
├── core/
│   ├── events.py              # Event 枚举 + GameState 枚举 + EventBus
│   ├── game.py                # Game 中枢 — 12 子系统 + 状态机分发
│   └── state.py               # SaveData / CharEntry 存档数据容器
├── audio/
│   └── audio_manager.py       # AudioManager — 3 通道音频（BGM/Voice/SE）
├── graphics/
│   ├── sprite_actor.py        # SpriteActor — 精灵封装 + 补间动画
│   ├── layer.py               # LayerManager — 6 层渲染 + 淡入淡出
│   └── ui.py                  # UIManager — 对话框 / 选项 / 回看 / 设置
├── script/
│   ├── commands.py            # Command ABC + 11 具体指令
│   ├── parser.py              # .ws 脚本解析器
│   └── executor.py            # ScriptExecutor — 生成器驱动脚本执行
├── systems/
│   ├── resource.py            # ResourceManager — LRU 缓存 + 后台预加载
│   └── save_system.py         # SaveSystem — JSON + MD5 + 原子写入
├── modes/
│   └── gallery.py             # 鉴赏模式 — CG 画廊 / 音乐欣赏 / 立绘鉴赏
├── resources/
│   ├── data/                  # JSON 配置（gallery / music / characters）
│   └── scripts/               # 剧本文件（title.ws / prologue.ws）
└── tests/
    ├── conftest.py             # 统一 mock 环境
    ├── test_event_bus.py       # 7 个
    ├── test_resource.py        # 13 个
    ├── test_sprite_actor.py    # 17 个
    ├── test_layer.py           # 13 个
    ├── test_audio.py           # 14 个
    ├── test_script.py          # 22 个
    ├── test_save.py            # 13 个
    └── test_ui.py              # 27 个
```

## 快速开始

```bash
# 安装依赖
pip install pyglet Pillow

# 启动引擎
python main.py
```

### 窗口操作

| 按键 | 功能 |
|------|------|
| `F11` | 全屏切换 |
| `ESC` | 退出 / 鉴赏模式返回 |
| 鼠标左键 | 推进对话 / 点击交互 |
| 鼠标滚轮 | 回看滚动 / 画廊滚动 |
| `↑ ↓` | 选项菜单导航 |
| `Enter` | 选项确认 |

## 核心设计

### GameState 状态机

引擎按 `GameState` 枚举分发 update / draw / 输入：

```
TITLE → NOVEL → CG_GALLERY / MUSIC_ROOM / CHARACTER_VIEWER
  ↑        ↓
  └────────┘ (scene_end / ESC)
```

- **TITLE**: 标题画面（剧本驱动，BGM + 选项菜单）
- **NOVEL**: 视觉小说模式（脚本执行 + 图层渲染 + UI）
- **CG_GALLERY**: CG 画廊（缩略图网格 → 全屏翻页）
- **MUSIC_ROOM**: 音乐欣赏（列表 + 播放/暂停 + 进度条）
- **CHARACTER_VIEWER**: 立绘鉴赏（部件切换 + 截图保存）

### EventBus — 弱引用事件总线

```python
from core.events import EventBus, Event

bus = EventBus()
bus.on(Event.CLICK, my_handler)          # 订阅（自动弱引用包装）
bus.emit(Event.CLICK, x=100, y=200)      # 触发
bus.off(Event.CLICK, my_handler)         # 退订（按 __func__ + __self__ 身份比对）
```

- **弱引用**：监听对象被删除后回调自动失效，不阻止 GC。
- **惰性清理**：`emit()` 时自动回收死引用，无后台线程。
- **错误隔离**：单个回调异常不影响其他监听器。
- **15 个预定义事件** + 任意裸字符串事件。

### Game — 引擎中枢

`Game` 类持有 12 个子系统槽位。`init_subsystems(window)` 按 Layer 0→10 构造并注册全部子系统：

```
Layer  0: flags / variable_bank      — 独立 dict（非共享引用）
Layer  1: resource_manager           — 资源加载 / LRU 缓存
Layer  2: audio                      — 3 通道音频 (BGM/Voice/SE)
Layer  3: save_system                — JSON+MD5 原子存档
Layer  4: script_executor            — .ws 剧本执行
Layer 10: layers / ui_manager        — 6 层渲染 + 对话框/选项/回看/设置
附加:     cg_gallery / music_room / character_viewer
```

`update(dt)` / `draw()` / `on_click()` / `handle_mouse_*` 全部按 `GameState` 分发。

### .ws 剧本系统

```
@scene classroom           # 场景切换
@bgm bgm01                 # BGM
@show rei smile at center  # 显示立绘（支持多词位置如 "far left"）
@hide rei                  # 隐藏立绘
@flag met_rei true         # 设置旗标
@if met_rei                # 条件分支
@jump target               # 无条件跳转
@label target              # 跳转标签
@choice                    # 选项菜单
"一起吃饭": jump lunch
"拒绝": jump decline
"玲，早上好～"              # 对话（逗号前为说话人，无逗号即旁白）
"前辈，今天天气真好～"[voice:rei_001]  # 带语音的对话
@end                       # 场景结束
```

- **生成器驱动**：阻塞命令（对话/选项）yield 等待下一帧，非阻塞命令自动推进。
- **无限循环保护**：连续执行超过 `MAX_SCRIPT_ADVANCE=1000` 条强制停止。
- **选项处理**：选项菜单通过 `"choice"` / `"choice_selected"` 事件与 UI 联动。

### ResourceManager — 惰性加载 + LRU 缓存 + 后台预加载

```python
from systems.resource import ResourceManager

rm = ResourceManager(data_root="resources", max_images=32, max_audio=16)
img = rm.get_image("images/bg/classroom.png")
bgm = rm.get_audio("bgm/title.ogg")
rm.preload_image("images/chara/alice.png")  # 后台预加载
rm.clear_scene(keep_audio=True)             # 场景切换
rm.shutdown()
```

- **LRU 缓存**：图像 / 音频独立 `OrderedDict`，容量可配。
- **后台预加载**：daemon 线程 + `queue.Queue`，PIL 解码在后台（不碰 OpenGL）。
- **路径安全**：`..` 穿越检测（`os.sep` 精确前缀匹配）。
- **场景版本号**：`clear_scene` 自动丢弃旧场景预加载任务。
- **PIL 可选**：未安装时跳过预加载，降级为同步 `pyglet.image.load()`。

### SpriteActor — 精灵 + 补间动画

```python
actor = SpriteActor(image, x=640, y=360, batch=batch, group=group)
actor.move_to(800, 400, 1.0, easing=ease_in_out_quad).fade_to(128, 0.5)
actor.update(dt)
actor.delete()
```

- **4 种补间**：`move_to` / `fade_to` / `scale_to` / `rotate_to`，链式调用。
- **覆盖规则**：同名属性互相覆盖，不同属性并行运行。
- **NaN 防护**：`duration` 必须为有限非负值。
- **生命周期**：自维护 `_deleted` 标志，不依赖 pyglet 私有 API。

### LayerManager — 6 层渲染

```python
lm = LayerManager(width=1280, height=720)
lm.set_background(bg_image)
actor = lm.show_sprite(Layer.MID, chara_img, (640, 200))
lm.fade_out(1.0, color=(0, 0, 0))
lm.fade_in(0.5)
lm.update(dt)
lm.draw()
```

- **6 层**：`BG → BEHIND → MID → FRONT → EFFECTS → UI`，`Group(order=N)` + 共享 `Batch`。
- **层管理器开放 API**：`batch` 属性 + `get_group(layer)` 供 UI 和鉴赏模式使用。
- **淡入淡出**：可配置覆盖颜色，自动释放旧 overlay。
- **死精灵清理**：即使 `dt=0` 也清理已删除 actor。

### AudioManager — 3 通道音频

```python
audio = AudioManager(event_bus=events)
audio.play_bgm(source, volume=0.8, loop=True)
audio.play_voice(source, volume=1.0)
audio.play_se(source, volume=0.6)
audio.stop_bgm(fade_out=2.0)
audio.set_volume("bgm", 0.5)
audio.pause_all()
audio.resume_all()
```

- **BGM**：淡出完成后自动 `unschedule`，无定时器泄漏。
- **Voice**：新语音自动中断上一句。
- **SE**：8 播放器池，round-robin 分配。
- **set_volume**：主动取消进行中的淡出。

### UI 模块

| 组件 | 功能 |
|------|------|
| `DialogBox` | 打字机效果 + 说话人 + 闪烁点击提示 + 对话历史自动记录 |
| `ChoiceMenu` | 垂直按钮列表 + 键盘上下/回车 + 鼠标悬停高亮 + 选中 emit 事件 |
| `BacklogViewer` | 全屏半透明遮罩 + 滚轮滚动 + 点击空白关闭 |
| `SettingsPanel` | BGM/Voice/SE 音量滑块 + 文本速度滑块 + 全屏切换 |
| `UIManager` | 事件路由（settings > backlog > choice > dialog） |

- 百分比定位，分辨率无关。
- 依赖注入（Batch / Group / EventBus / AudioManager）。
- 交互逻辑与绘制分离，可纯状态测试。

### SaveSystem — 存档管理

```python
ss = SaveSystem(save_root="saves")
ss.save(slot=1, data=save_data)       # 原子写入（.tmp → os.replace）
loaded = ss.load(slot=1)              # MD5 校验 + 版本迁移
ss.list_slots()
ss.delete(slot=1)
ss.save_thumbnail(slot=1, png_bytes)
```

- **JSON + MD5**：checksum 防篡改。
- **原子写入**：先写 `.tmp`，`os.replace` 替换，中途崩溃不损坏旧存档。
- **版本迁移**：v1→v2（char_affection 字段），未来版本拒绝加载。
- **缩略图**：独立 PNG 文件，不嵌入 JSON。
- **槽位边界**：所有方法校验 `[0, MAX_SAVE_SLOTS)`。

### 鉴赏模式

| 模式 | 说明 |
|------|------|
| `CGGallery` | 4 列缩略图网格 → 点击全屏查看 → 左右翻页（仅已解锁）。未解锁灰色占位。 |
| `MusicRoom` | 垂直曲目列表 + 播放/暂停 + 进度条。按旗标解锁。 |
| `CharacterViewer` | 角色部件分层叠放 → 点击切换变体 → 截图保存 PNG。 |

JSON 配置文件路径从 `AppConfig` 读取。

## 配置

```python
from config import AppConfig
import logging

config = AppConfig(
    width=1280, height=720,
    debug=True,
    log_level=logging.DEBUG,
    log_file="logs/engine.log",
    gallery_data="resources/data/gallery.json",
    character_data="resources/data/characters.json",
)
```

全部常量收敛到 `config.py`，`AppConfig` 所有字段有默认值。

## 开发

```bash
# 类型检查（mypy --strict）
mypy . --strict

# 运行测试（全 mock，零 GPU 依赖）
pytest tests/ -v
```

- **Python 3.10+**
- **mypy `--strict` 零错误**（14 source files）
- **126 个单元测试**：event_bus(7) + resource(13) + sprite_actor(17) + layer(13) + audio(14) + script(22) + save(13) + ui(27)
- 全部测试 mock 掉 pyglet / PIL，CI 可跑

## License

MIT
