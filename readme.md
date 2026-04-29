# Visual Novel Engine V2.5

基于 **pyglet 2.1+** 的现代视觉小说引擎，从零重写。
事件驱动架构，弱引用事件总线，惰性加载 + LRU 缓存资源管理。

## 项目结构

```
├── config.py              # 全局常量 + AppConfig dataclass
├── core/
│   ├── events.py          # Event 枚举 + EventBus（弱引用观察者模式）
│   └── game.py            # Game 引擎中枢 —— 持有所有子系统引用
├── systems/
│   └── resource.py        # ResourceManager —— 惰性加载 + LRU 缓存 + 后台预加载
├── main.py                # GameWindow 入口（vsync / 60fps / 焦点暂停）
└── tests/
    ├── test_event_bus.py  # EventBus 冒烟测试（7 个）
    └── test_resource.py   # ResourceManager 测试（13 个，全 mock）
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
| `ESC` | 退出 |
| 鼠标左键 | 推进对话 / 点击交互 |

## 核心设计

### EventBus — 弱引用事件总线

```python
from core.events import EventBus, Event

bus = EventBus()
bus.on(Event.CLICK, my_handler)          # 订阅（自动弱引用包装）
bus.emit(Event.CLICK, x=100, y=200)      # 触发
bus.off(Event.CLICK, my_handler)         # 退订
```

- **弱引用**：监听对象被删除后回调自动失效，不阻止 GC。
- **惰性清理**：`emit()` 时自动回收死引用，无后台线程。
- **错误隔离**：单个回调异常不影响其他监听器。
- **Event 枚举**：预定义 15 个事件名，IDE 自动补全，杜绝裸字符串打错。

### Game — 引擎中枢

`Game` 类是纯 Python（不依赖 pyglet），持有 12 个子系统槽位（按 Layer 0→10 排列）。各子系统通过 `register(name, subsystem)` 注入，槽位不存在时抛 `AttributeError`。

```
Layer  0: variable_bank, resource_manager  (无依赖)
Layer  2: audio                            (依赖 resource_manager)
Layer  3: save_system                      (依赖 variable_bank)
Layer  5: scene_manager                    (依赖 resource_manager)
Layer  7: dialogue_system                  (依赖 scene + character)
Layer 10: ui_manager, layers               (依赖全部上层)
```

### ResourceManager — 惰性加载 + LRU 缓存 + 后台预加载

```python
from systems.resource import ResourceManager

rm = ResourceManager(data_root="resources", max_images=32, max_audio=16)

# 获取资源（惰性加载）
img = rm.get_image("images/bg/classroom.png")
bgm = rm.get_audio("bgm/title.ogg")

# 后台预加载（不阻塞主线程）
rm.preload_image("images/chara/alice.png")

# 场景切换
rm.clear_scene(keep_audio=True)   # 保留 BGM
rm.shutdown()                     # 安全关闭
```

- **LRU 缓存**：图像 / 音频独立 `OrderedDict`，容量可配，超出逐出最久未用。
- **后台预加载**：daemon 线程 + `queue.Queue`，PIL 解码在后台（不碰 OpenGL），主线程取时才构造 GPU 对象。
- **路径安全**：`..` 穿越检测，抛 `ValueError`。
- **场景版本号**：`clear_scene` 自动丢弃旧场景的预加载任务。
- **Pillow 可选**：未安装时降级为同步加载。

### GameWindow — 主窗口

`pyglet.window.Window` 子类，提供：

- **vsync 开启 + 60fps**：`clock.schedule_interval(game.update, 1/60)`
- **焦点暂停**：`on_deactivate` → `game.paused = True`；`on_draw` 首帧自动恢复
- **窗口缩放**：最小 640×360，resize 事件广播
- **日志**：标准 `logging` 模块，级别 / 文件路径由 `AppConfig` 控制

## 配置

所有魔术字符串收敛到 `config.py`：

```python
from config import AppConfig

config = AppConfig(
    width=1280, height=720,
    debug=True,
    log_level=logging.DEBUG,
    log_file="logs/engine.log",
)
```

## 开发

```bash
# 类型检查（mypy --strict）
mypy . --strict

# 运行测试（全 mock，无 GPU 依赖）
pytest tests/ -v
```

- **Python 3.10+**
- **mypy `--strict` 零错误**
- **20 个单元测试**（7 个 EventBus + 13 个 ResourceManager）
- 所有测试 mock 掉 pyglet / PIL / 文件系统，CI 可跑

## License

MIT
