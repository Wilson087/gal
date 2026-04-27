"""
屏幕特效模块
=============
提供转场过渡、画面滤镜、粒子系统（天气）、震动/闪光等视觉效果。

所有函数均为基于 tkinter Canvas 的无状态工具函数。

转场效果:
    - crossfade: 白色遮罩淡入淡出（兼容原版）
    - slide: 滑入（左/右）
    - blinds: 百叶窗
    - ripple: 涟漪展开

画面滤镜:
    - sepia: 褐色调（回忆/过去）
    - night: 夜蓝色（夜晚场景）
    - memory: 紫色调（记忆/幻想）
    - noise: 老电影噪点

粒子系统:
    - snow: 飘雪
    - rain: 雨丝

屏幕效果:
    - shake: 画面震动
    - flash: 画面闪烁
"""

import math
import random
import tkinter as tk
from typing import Callable, Optional

from .constants import (
    BG_FADE_INTERVAL,
    COLOR_OVERLAY,
    FILTER_COLORS,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
)
from .renderer import render_background


# ========================================================================
#  转场效果
# ========================================================================

def transition_crossfade(canvas: tk.Canvas, old_bg_id: str, new_bg_id: str,
                          width: int, height: int,
                          on_complete: Optional[Callable] = None,
                          duration: int = 600) -> None:
    """交叉淡入淡出：白色遮罩渐入 → 切换背景 → 白色遮罩渐出。

    Args:
        canvas: 目标 Canvas。
        old_bg_id: 旧背景 ID（保留以备后用）。
        new_bg_id: 新背景 ID。
        width: 画布宽度。
        height: 画布高度。
        on_complete: 完成回调。
        duration: 总时长（ms）。
    """
    steps = max(4, duration // BG_FADE_INTERVAL // 2) * 2
    half = steps // 2
    step = 0

    overlay = canvas.create_rectangle(
        0, 0, width, height,
        fill=COLOR_OVERLAY, stipple="gray12",
        outline="", tags="transition_overlay",
    )

    stipple_prog = ["gray12", "gray25", "gray50", "gray75", ""]

    def _step():
        nonlocal step
        step += 1

        if step <= half:
            # 渐入白色
            idx = int((step / half) * (len(stipple_prog) - 1))
            idx = min(idx, len(stipple_prog) - 1)
            try:
                canvas.itemconfig(overlay, stipple=stipple_prog[idx])
            except tk.TclError:
                pass
            canvas.after(BG_FADE_INTERVAL, _step)

        elif step == half + 1:
            # 切换背景
            render_background(canvas, new_bg_id, width, height)
            try:
                canvas.itemconfig(overlay, stipple="")
            except tk.TclError:
                pass
            canvas.after(BG_FADE_INTERVAL // 2, _step)

        elif step <= steps:
            # 渐出白色
            progress = (step - half - 1) / half
            idx = int(progress * (len(stipple_prog) - 1))
            idx = min(idx, len(stipple_prog) - 1)
            rev_idx = len(stipple_prog) - 1 - idx
            try:
                canvas.itemconfig(overlay, stipple=stipple_prog[rev_idx])
            except tk.TclError:
                pass
            canvas.after(BG_FADE_INTERVAL, _step)

        else:
            # 完成
            try:
                canvas.delete(overlay)
            except tk.TclError:
                pass
            if on_complete:
                on_complete()

    _step()


def transition_slide(canvas: tk.Canvas, old_bg_id: str, new_bg_id: str,
                      width: int, height: int,
                      on_complete: Optional[Callable] = None,
                      direction: str = "left", duration: int = 500) -> None:
    """滑动转场：用白色遮罩模拟滑动效果。

    实际实现：白色遮罩从一侧滑向另一侧，逐渐揭露新背景。

    Args:
        canvas: 目标 Canvas。
        old_bg_id: 旧背景 ID。
        new_bg_id: 新背景 ID。
        width: 画布宽度。
        height: 画布高度。
        on_complete: 完成回调。
        direction: "left"(新背景从左滑入) 或 "right"(新背景从右滑入)。
        duration: 总时长（ms）。
    """
    # 渲染新背景
    render_background(canvas, new_bg_id, width, height)

    steps = max(8, duration // 30)
    step = 0

    # 创建遮罩条（沿移动方向的一组垂直矩形）
    strip_count = 20
    strip_width = width / strip_count
    strips: list[int] = []

    # 生成遮罩条排列：direction="left"时从右到左覆盖
    order = list(range(strip_count))
    if direction == "right":
        order = list(reversed(order))

    for i in order:
        x0 = i * strip_width
        strip = canvas.create_rectangle(
            int(x0), 0, int(x0 + strip_width + 1), height,
            fill=COLOR_OVERLAY, outline="", tags="transition_overlay",
        )
        strips.append(strip)

    def _step():
        nonlocal step
        step += 1
        if step > strip_count:
            # 完成
            for s in strips:
                try:
                    canvas.delete(s)
                except tk.TclError:
                    pass
            if on_complete:
                on_complete()
            return

        # 逐步移除遮罩条（从方向侧开始）
        reveal_idx = step - 1
        if reveal_idx < len(strips):
            try:
                canvas.delete(strips[reveal_idx])
            except tk.TclError:
                pass

        canvas.after(duration // strip_count, _step)

    _step()


def transition_blinds(canvas: tk.Canvas, old_bg_id: str, new_bg_id: str,
                       width: int, height: int,
                       on_complete: Optional[Callable] = None,
                       count: int = 8, duration: int = 500) -> None:
    """百叶窗转场：画面分为多条垂直条，依次切换。

    Args:
        canvas: 目标 Canvas。
        old_bg_id: 旧背景 ID。
        new_bg_id: 新背景 ID。
        width: 画布宽度。
        height: 画布高度。
        on_complete: 完成回调。
        count: 条数。
        duration: 总时长（ms）。
    """
    # 渲染新背景
    render_background(canvas, new_bg_id, width, height)

    steps = 10  # 每条的动画步数
    strip_w = width / count
    interval = duration // (count * steps)

    # 为每条创建覆盖矩形
    blinds: list[dict] = []
    for i in range(count):
        x0 = i * strip_w
        bar = canvas.create_rectangle(
            int(x0), 0, int(x0 + strip_w), height,
            fill=COLOR_OVERLAY, outline="", tags="transition_overlay",
        )
        blinds.append({"id": bar, "col": i})

    def _animate_blinds():
        remaining = [b for b in blinds if b["id"] is not None]
        if not remaining:
            if on_complete:
                on_complete()
            return

        # 随机选一条去掉
        target = random.choice(remaining)
        try:
            canvas.delete(target["id"])
        except tk.TclError:
            pass
        target["id"] = None

        canvas.after(interval, _animate_blinds)

    _animate_blinds()


def transition_ripple(canvas: tk.Canvas, old_bg_id: str, new_bg_id: str,
                       width: int, height: int,
                       on_complete: Optional[Callable] = None,
                       duration: int = 800) -> None:
    """涟漪转场：从画面中心扩散的圆环。

    Args:
        canvas: 目标 Canvas。
        old_bg_id: 旧背景 ID。
        new_bg_id: 新背景 ID。
        width: 画布宽度。
        height: 画布高度。
        on_complete: 完成回调。
        duration: 总时长（ms）。
    """
    # 渲染新背景
    render_background(canvas, new_bg_id, width, height)

    cx, cy = width // 2, height // 2
    max_r = int(math.sqrt(width ** 2 + height ** 2) / 2)
    steps = 20
    interval = duration // steps
    step = 0

    # 白色遮罩覆盖全屏
    overlay = canvas.create_rectangle(
        0, 0, width, height,
        fill=COLOR_OVERLAY, outline="", tags="transition_overlay",
    )

    def _step():
        nonlocal step
        step += 1
        if step > steps:
            try:
                canvas.delete(overlay)
            except tk.TclError:
                pass
            if on_complete:
                on_complete()
            return

        # 用圆形裁剪区域：在遮罩上挖洞
        r = int(max_r * (step / steps))
        # 在遮罩之上画一个镂空圆（用背景色或透明）
        # tkinter 不能真正镂空，所以我们用取巧方式：
        # 在遮罩之上叠加一个背景色圆（变相显示新背景）
        try:
            canvas.delete("ripple_circle")
        except tk.TclError:
            pass
        canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill="#000000", outline="", tags="ripple_circle",
        )
        # raise 这个圆到最顶层
        canvas.tag_raise("ripple_circle")

        canvas.after(interval, _step)

    _step()


# 转场效果注册表
TRANSITION_FUNCTIONS = {
    "crossfade": transition_crossfade,
    "slide_left": transition_slide,
    "slide_right": lambda c, o, n, w, h, oc=None, d=500: transition_slide(
        c, o, n, w, h, oc, direction="right", duration=d),
    "blinds": transition_blinds,
    "ripple": transition_ripple,
    "none": lambda c, o, n, w, h, oc=None, d=0: (
        render_background(c, n, w, h) or (oc and oc())),
}


# ========================================================================
#  屏幕滤镜
# ========================================================================

# 当前活动的滤镜 ID（用于清理）
_filter_overlay_id: Optional[int] = None


def apply_filter(canvas: tk.Canvas, filter_name: str,
                 width: int, height: int,
                 intensity: float = 0.3) -> Optional[int]:
    """在画布上施加颜色滤镜。

    Args:
        canvas: 目标 Canvas。
        filter_name: 滤镜名（FILTER_NONE / FILTER_SEPIA / FILTER_NIGHT / FILTER_MEMORY）。
        width: 画布宽度。
        height: 画布高度。
        intensity: 滤镜强度 0.0-1.0。

    Returns:
        滤镜遮罩的 Canvas 对象 ID，或 None。
    """
    global _filter_overlay_id
    # 清除旧滤镜
    remove_filter(canvas)

    if filter_name == FILTER_NONE:
        return None

    color = FILTER_COLORS.get(filter_name)
    if color is None:
        return None

    # 用 stipple + 颜色近似透明度效果
    stipple_map = {
        0.1: "gray12",
        0.2: "gray12",
        0.3: "gray25",
        0.4: "gray25",
        0.5: "gray50",
        0.6: "gray50",
        0.7: "gray75",
        0.8: "gray75",
        0.9: "",
        1.0: "",
    }
    stipple = stipple_map.get(intensity * 10 / 10, "gray25")

    overlay_id = canvas.create_rectangle(
        0, 0, width, height,
        fill=color, stipple=stipple,
        outline="", tags="screen_filter",
    )
    canvas.tag_lower(overlay_id, "transition_overlay" if canvas.find_withtag("transition_overlay") else "all")
    _filter_overlay_id = overlay_id
    return overlay_id


def remove_filter(canvas: tk.Canvas) -> None:
    """移除画面滤镜。"""
    global _filter_overlay_id
    try:
        canvas.delete("screen_filter")
    except tk.TclError:
        pass
    _filter_overlay_id = None


# ========================================================================
#  噪点效果
# ========================================================================

_noise_running: bool = False
_noise_dots: list[int] = []


def start_noise(canvas: tk.Canvas, width: int, height: int,
                density: float = 0.005) -> None:
    """启动老电影噪点效果。

    在画布上随机绘制半透明小点，定时刷新。

    Args:
        canvas: 目标 Canvas。
        width: 画布宽度。
        height: 画布高度。
        density: 噪点密度（占画面比例）。
    """
    global _noise_running, _noise_dots
    stop_noise(canvas)
    _noise_running = True
    _noise_dots = []

    count = int(width * height * density * 0.01)
    count = max(10, min(200, count))

    def _tick():
        global _noise_running, _noise_dots
        if not _noise_running:
            return

        # 清除旧噪点
        for dot_id in _noise_dots:
            try:
                canvas.delete(dot_id)
            except tk.TclError:
                pass
        _noise_dots = []

        # 生成新噪点
        for _ in range(count):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(1, 3)
            gray = random.randint(180, 255)
            color = f"#{gray:02x}{gray:02x}{gray:02x}"
            dot = canvas.create_rectangle(
                x, y, x + size, y + size,
                fill=color, outline="",
                tags="noise_dot",
            )
            _noise_dots.append(dot)

        canvas.after(100, _tick)

    _tick()


def stop_noise(canvas: tk.Canvas) -> None:
    """停止噪点效果。"""
    global _noise_running, _noise_dots
    _noise_running = False
    try:
        canvas.delete("noise_dot")
    except tk.TclError:
        pass
    _noise_dots = []


# ========================================================================
#  粒子系统（天气）
# ========================================================================

_particle_running: bool = False
_particle_items: list[int] = []


def start_snow(canvas: tk.Canvas, width: int, height: int,
               count: int = 60) -> None:
    """启动飘雪效果。

    Args:
        canvas: 目标 Canvas。
        width: 画布宽度。
        height: 画布高度。
        count: 雪花数量。
    """
    global _particle_running, _particle_items
    stop_particles(canvas)
    _particle_running = True
    _particle_items = []

    particles = []
    for _ in range(count):
        particles.append({
            "x": random.randint(0, width),
            "y": random.randint(-height, 0),
            "speed_y": random.uniform(1, 3),
            "speed_x": random.uniform(-0.5, 0.5),
            "size": random.randint(2, 5),
            "opacity": random.choice(["gray12", "gray25", "gray50"]),
            "swing": random.uniform(0, math.pi * 2),
        })

    def _tick():
        global _particle_running, _particle_items
        if not _particle_running:
            return

        # 清除旧帧
        for item_id in _particle_items:
            try:
                canvas.delete(item_id)
            except tk.TclError:
                pass
        _particle_items = []

        for p in particles:
            p["swing"] += 0.05
            p["x"] += p["speed_x"] + math.sin(p["swing"]) * 0.5
            p["y"] += p["speed_y"]

            # 循环
            if p["y"] > height + 5:
                p["y"] = random.randint(-10, -5)
                p["x"] = random.randint(0, width)

            dot = canvas.create_oval(
                int(p["x"] - p["size"] / 2),
                int(p["y"] - p["size"] / 2),
                int(p["x"] + p["size"] / 2),
                int(p["y"] + p["size"] / 2),
                fill="white", stipple=p["opacity"],
                outline="", tags="particle",
            )
            _particle_items.append(dot)

        canvas.after(40, _tick)

    _tick()


def start_rain(canvas: tk.Canvas, width: int, height: int,
               count: int = 80) -> None:
    """启动下雨效果。

    Args:
        canvas: 目标 Canvas。
        width: 画布宽度。
        height: 画布高度。
        count: 雨丝数量。
    """
    global _particle_running, _particle_items
    stop_particles(canvas)
    _particle_running = True
    _particle_items = []

    particles = []
    for _ in range(count):
        particles.append({
            "x": random.randint(0, width),
            "y": random.randint(-height, 0),
            "speed_y": random.uniform(5, 12),
            "speed_x": random.uniform(-2, -1),
            "length": random.randint(8, 20),
        })

    def _tick():
        global _particle_running, _particle_items
        if not _particle_running:
            return

        for item_id in _particle_items:
            try:
                canvas.delete(item_id)
            except tk.TclError:
                pass
        _particle_items = []

        for p in particles:
            p["x"] += p["speed_x"]
            p["y"] += p["speed_y"]

            if p["y"] > height + 10:
                p["y"] = random.randint(-20, -10)
                p["x"] = random.randint(0, width)

            line = canvas.create_line(
                int(p["x"]), int(p["y"]),
                int(p["x"] + p["speed_x"] * 0.5),
                int(p["y"] - p["length"]),
                fill="white", stipple="gray25",
                tags="particle", width=1,
            )
            _particle_items.append(line)

        canvas.after(30, _tick)

    _tick()


def stop_particles(canvas: tk.Canvas) -> None:
    """停止所有粒子效果。"""
    global _particle_running, _particle_items
    _particle_running = False
    try:
        canvas.delete("particle")
    except tk.TclError:
        pass
    _particle_items = []


# ========================================================================
#  画面震动
# ========================================================================

_shake_running: bool = False


def start_shake(canvas: tk.Canvas, duration: float = 0.5,
                intensity: int = 8) -> None:
    """画面震动效果。

    通过周期性移动 Canvas 上所有内容实现震动。

    Args:
        canvas: 目标 Canvas。
        duration: 震动持续时间（秒）。
        intensity: 震动幅度（像素）。
    """
    global _shake_running
    _shake_running = True

    steps = int(duration / 0.03)
    step = 0

    def _tick():
        global _shake_running
        if not _shake_running or step >= steps:
            # 复位
            try:
                canvas.scan_dragto(0, 0, gain=1)
            except tk.TclError:
                pass
            _shake_running = False
            return

        offset_x = random.randint(-intensity, intensity)
        offset_y = random.randint(-intensity, intensity)

        # Canvas 没有整体移动的方法，scan_mark/scan_dragto 可以
        # 但会累积移动。我们用另一种方式：
        # 记录初始位置，每次回到原点再移动

        try:
            # 清除之前偏移：回到原点
            # 直接使用 scan 系统
            if step == 0:
                canvas.scan_mark(0, 0)
            canvas.scan_dragto(offset_x, offset_y, gain=1)
        except tk.TclError:
            pass

        step += 1
        canvas.after(30, _tick)

    _tick()


def stop_shake(canvas: tk.Canvas) -> None:
    """停止画面震动。"""
    global _shake_running
    _shake_running = False
    try:
        canvas.scan_dragto(0, 0, gain=1)
    except tk.TclError:
        pass


# ========================================================================
#  画面闪烁
# ========================================================================

def start_flash(canvas: tk.Canvas, color: str = "#ffffff",
                duration: float = 0.3) -> None:
    """画面闪烁效果（短暂的全屏颜色覆盖）。

    Args:
        canvas: 目标 Canvas。
        color: 闪烁颜色。
        duration: 持续时间（秒）。
    """
    w = canvas.winfo_width() or WINDOW_WIDTH
    h = canvas.winfo_height() or WINDOW_HEIGHT

    flash_id = canvas.create_rectangle(
        0, 0, w, h,
        fill=color, outline="", tags="flash_overlay",
    )
    canvas.tag_raise(flash_id)

    fade_steps = 5
    interval = int(duration * 1000 / fade_steps)

    def _fade_out(step: int = 0):
        if step >= fade_steps:
            try:
                canvas.delete(flash_id)
            except tk.TclError:
                pass
            return
        # 用 stipple 逐步变透明
        stipple = ["", "gray75", "gray50", "gray25", "gray12"][step]
        try:
            canvas.itemconfig(flash_id, stipple=stipple)
        except tk.TclError:
            pass
        canvas.after(interval, _fade_out, step + 1)

    _fade_out(0)
