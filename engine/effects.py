"""
视觉特效模块
============
场景转场、画面滤镜、粒子系统（雪/雨）、屏幕震动。
"""

import math
import random
from typing import Optional, Callable

import pyglet
from pyglet.graphics import Batch, Group

from .constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT,
    TRANSITION_DURATION, TRANSITION_CROSSFADE,
    TRANSITION_SLIDE_LEFT, TRANSITION_SLIDE_RIGHT,
    TRANSITION_BLINDS, TRANSITION_RIPPLE, TRANSITION_NONE,
    FILTER_COLORS, COLOR_OVERLAY,
)


class EffectSystem:
    """特效系统：转场、滤镜、粒子、震动。"""

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        self._overlay_group = Group(order=20)
        self._filter_group = Group(order=15)

        # 转场状态
        self._transition: Optional[dict] = None

        # 滤镜状态
        self._filter_sprite: Optional[pyglet.sprite.Sprite] = None

        # 粒子状态
        self._particles: list[dict] = []
        self._particle_type: str = "none"

        # 震动状态
        self._shake_time: float = 0.0
        self._shake_intensity: int = 0
        self._shake_offset: tuple[float, float] = (0.0, 0.0)

    # ====================================================================
    #  转场效果
    # ====================================================================

    def start_transition(self, transition_type: str, on_midpoint: Callable,
                         on_complete: Optional[Callable] = None) -> None:
        """开始转场效果。

        流程：遮罩渐入 → 调用 on_midpoint（切换内容） → 遮罩渐出

        Args:
            transition_type: 转场类型。
            on_midpoint: 遮罩完全覆盖时回调（用于切换背景等）。
            on_complete: 转场完成时回调。
        """
        if transition_type == TRANSITION_NONE:
            on_midpoint()
            if on_complete:
                on_complete()
            return

        self._transition = {
            "type": transition_type,
            "phase": "fade_in",  # fade_in, midpoint, fade_out
            "progress": 0.0,
            "duration": TRANSITION_DURATION,
            "half_duration": TRANSITION_DURATION / 2,
            "on_midpoint": on_midpoint,
            "on_complete": on_complete,
            "strips": [],
        }

        # 创建 overlay sprite（全屏白色覆盖）
        overlay_img = pyglet.image.SolidColorImagePattern(
            (255, 255, 255, 255)
        ).create_image(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._transition_overlay = pyglet.sprite.Sprite(
            overlay_img, batch=self.app.ui_batch, group=self._overlay_group,
        )
        self._transition_overlay.opacity = 0

        # 滑动/百叶窗需要 strips
        if transition_type in (TRANSITION_SLIDE_LEFT, TRANSITION_SLIDE_RIGHT, TRANSITION_BLINDS):
            self._init_strips(transition_type)

    def _init_strips(self, transition_type: str) -> None:
        """为滑动/百叶窗创建 strip sprite 列表。"""
        strip_count = 20
        strip_w = WINDOW_WIDTH / strip_count
        self._transition["strips"] = []
        for i in range(strip_count):
            img = pyglet.image.SolidColorImagePattern(
                (255, 255, 255, 255)
            ).create_image(int(strip_w + 1), WINDOW_HEIGHT)
            spr = pyglet.sprite.Sprite(
                img, batch=self.app.ui_batch, group=self._overlay_group,
            )
            spr.x = i * strip_w
            spr.opacity = 255
            self._transition["strips"].append({
                "sprite": spr,
                "index": i,
                "revealed": False,
            })

    def update(self, dt: float) -> None:
        """帧更新：驱动转场、粒子、震动。"""
        # 转场
        if self._transition:
            self._update_transition(dt)

        # 粒子
        if self._particle_type != "none":
            self._update_particles(dt)

        # 震动
        if self._shake_time > 0:
            self._shake_time -= dt
            self._shake_offset = (
                random.randint(-self._shake_intensity, self._shake_intensity),
                random.randint(-self._shake_intensity, self._shake_intensity),
            )
            # 应用到背景和立绘
            if hasattr(self.app, "background_manager"):
                self.app.background_manager.apply_shake(
                    self._shake_offset[0], self._shake_offset[1])
            if hasattr(self.app, "character_manager"):
                self.app.character_manager.apply_shake(
                    self._shake_offset[0], self._shake_offset[1])
        elif self._shake_offset != (0, 0):
            self._shake_offset = (0, 0)

    def _update_transition(self, dt: float) -> None:
        """更新转场动画。"""
        t = self._transition
        t["progress"] += dt

        if t["type"] == TRANSITION_CROSSFADE:
            self._update_crossfade(dt)
        elif t["type"] in (TRANSITION_SLIDE_LEFT, TRANSITION_SLIDE_RIGHT):
            self._update_slide(dt)
        elif t["type"] == TRANSITION_BLINDS:
            self._update_blinds(dt)
        elif t["type"] == TRANSITION_RIPPLE:
            self._update_ripple(dt)

    def _update_crossfade(self, dt: float) -> None:
        """淡入淡出转场更新。"""
        t = self._transition
        overlay = self._transition_overlay
        half = t["half_duration"]

        if t["phase"] == "fade_in":
            progress = min(1.0, t["progress"] / half)
            overlay.opacity = int(progress * 255)
            if progress >= 1.0:
                t["phase"] = "midpoint"
                t["progress"] = 0.0
                if t["on_midpoint"]:
                    t["on_midpoint"]()

        elif t["phase"] == "midpoint":
            t["phase"] = "fade_out"
            t["progress"] = 0.0

        elif t["phase"] == "fade_out":
            progress = min(1.0, t["progress"] / half)
            overlay.opacity = int((1.0 - progress) * 255)
            if progress >= 1.0:
                self._end_transition()

    def _update_slide(self, dt: float) -> None:
        """滑动转场更新。"""
        t = self._transition
        overlay = self._transition_overlay
        strips = t["strips"]
        total = len(strips)
        half = t["half_duration"]

        if t["phase"] == "fade_in":
            progress = min(1.0, t["progress"] / half)
            reveal_count = int(progress * total)
            if t["type"] == TRANSITION_SLIDE_LEFT:
                order = range(reveal_count)
            else:
                order = range(total - 1, total - 1 - reveal_count, -1)
            for i in range(total):
                revealed = (i < reveal_count) if t["type"] == TRANSITION_SLIDE_LEFT else (i >= total - reveal_count)
                strips[i]["sprite"].opacity = 0 if revealed else 255
                strips[i]["revealed"] = revealed

            if progress >= 1.0:
                t["phase"] = "midpoint"
                t["progress"] = 0.0
                if t["on_midpoint"]:
                    t["on_midpoint"]()

        elif t["phase"] == "midpoint":
            for s in strips:
                s["sprite"].opacity = 255
                s["revealed"] = False
            t["phase"] = "fade_out"
            t["progress"] = 0.0

        elif t["phase"] == "fade_out":
            progress = min(1.0, t["progress"] / half)
            reveal_count = int(progress * total)
            if t["type"] == TRANSITION_SLIDE_LEFT:
                order = range(reveal_count)
            else:
                order = range(total - 1, total - 1 - reveal_count, -1)
            for i in range(total):
                revealed = (i < reveal_count) if t["type"] == TRANSITION_SLIDE_LEFT else (i >= total - reveal_count)
                strips[i]["sprite"].opacity = 0 if revealed else 255
                strips[i]["revealed"] = revealed

            if progress >= 1.0:
                self._end_transition()

    def _update_blinds(self, dt: float) -> None:
        """百叶窗转场更新。"""
        t = self._transition
        strips = t["strips"]
        half = t["half_duration"]

        if t["phase"] == "fade_in":
            progress = min(1.0, t["progress"] / half)
            if progress >= 1.0:
                t["phase"] = "midpoint"
                t["progress"] = 0.0
                if t["on_midpoint"]:
                    t["on_midpoint"]()

        elif t["phase"] == "midpoint":
            t["phase"] = "fade_out"
            t["progress"] = 0.0

        elif t["phase"] == "fade_out":
            progress = min(1.0, t["progress"] / half)
            reveal_count = int(progress * len(strips))
            # 随机选择至多 reveal_count 条
            unrevealed = [s for s in strips if not s["revealed"]]
            to_reveal = min(reveal_count - sum(1 for s in strips if s["revealed"]), len(unrevealed))
            random.shuffle(unrevealed)
            for i in range(to_reveal):
                if i < len(unrevealed):
                    unrevealed[i]["sprite"].opacity = 0
                    unrevealed[i]["revealed"] = True

            if progress >= 1.0:
                self._end_transition()

    def _update_ripple(self, dt: float) -> None:
        """涟漪转场更新（简化：圆形扩散）。"""
        t = self._transition
        overlay = self._transition_overlay
        half = t["half_duration"]

        if t["phase"] == "fade_in":
            progress = min(1.0, t["progress"] / half)
            overlay.opacity = int(progress * 255)
            if progress >= 1.0:
                t["phase"] = "midpoint"
                t["progress"] = 0.0
                if t["on_midpoint"]:
                    t["on_midpoint"]()

        elif t["phase"] == "midpoint":
            t["phase"] = "fade_out"
            t["progress"] = 0.0

        elif t["phase"] == "fade_out":
            progress = min(1.0, t["progress"] / half)
            overlay.opacity = int((1.0 - progress) * 255)
            if progress >= 1.0:
                self._end_transition()

    def _end_transition(self) -> None:
        """结束转场，清理资源。"""
        if self._transition_overlay:
            self._transition_overlay.delete()
            self._transition_overlay = None

        if self._transition and self._transition.get("strips"):
            for s in self._transition["strips"]:
                s["sprite"].delete()

        on_complete = None
        if self._transition:
            on_complete = self._transition.get("on_complete")

        self._transition = None

        if on_complete:
            on_complete()

    # ====================================================================
    #  画面滤镜
    # ====================================================================

    def apply_filter(self, filter_name: str, intensity: float = 0.3) -> None:
        """应用画面滤镜。

        Args:
            filter_name: 滤镜名（sepia/night/memory）。
            intensity: 滤镜强度 0.0-1.0。
        """
        self.remove_filter()
        rgb = FILTER_COLORS.get(filter_name)
        if not rgb or filter_name == "none":
            return

        alpha = min(255, max(0, int(255 * intensity)))
        img = pyglet.image.SolidColorImagePattern(
            (*rgb, alpha)
        ).create_image(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._filter_sprite = pyglet.sprite.Sprite(
            img, batch=self.app.ui_batch, group=self._filter_group,
        )

    def remove_filter(self) -> None:
        """移除画面滤镜。"""
        if self._filter_sprite:
            self._filter_sprite.delete()
            self._filter_sprite = None

    # ====================================================================
    #  粒子系统：雪 / 雨
    # ====================================================================

    def start_snow(self, count: int = 60) -> None:
        """启动飘雪效果。"""
        self._particle_type = "snow"
        self._particles = []
        for _ in range(count):
            self._particles.append({
                "x": random.randint(0, WINDOW_WIDTH),
                "y": random.randint(0, WINDOW_HEIGHT),
                "speed_x": random.uniform(-0.3, 0.3),
                "speed_y": random.uniform(1.0, 2.5),
                "size": random.randint(2, 5),
                "phase": random.uniform(0, math.pi * 2),
            })

    def start_rain(self, count: int = 80) -> None:
        """启动下雨效果。"""
        self._particle_type = "rain"
        self._particles = []
        for _ in range(count):
            self._particles.append({
                "x": random.randint(0, WINDOW_WIDTH),
                "y": random.randint(0, WINDOW_HEIGHT),
                "speed_x": random.uniform(-2.0, -0.5),
                "speed_y": random.uniform(4.0, 8.0),
                "length": random.randint(8, 16),
            })

    def stop_particles(self) -> None:
        """停止所有粒子效果。"""
        self._particle_type = "none"
        self._particles = []

    def _update_particles(self, dt: float) -> None:
        """更新粒子位置。"""
        for p in self._particles:
            if self._particle_type == "snow":
                p["x"] += p["speed_x"] * dt * 60 + math.sin(p["phase"]) * 0.5
                p["y"] -= p["speed_y"] * dt * 60
                p["phase"] += 0.05
                if p["y"] < -10:
                    p["y"] = WINDOW_HEIGHT + 10
                    p["x"] = random.randint(0, WINDOW_WIDTH)
            elif self._particle_type == "rain":
                p["x"] += p["speed_x"] * dt * 60
                p["y"] -= p["speed_y"] * dt * 60
                if p["y"] < -20:
                    p["y"] = WINDOW_HEIGHT + 20
                    p["x"] = random.randint(0, WINDOW_WIDTH)

    def draw_particles(self) -> None:
        """在绘制帧时渲染粒子。"""
        if self._particle_type == "none" or not self._particles:
            return

        batch = self.app.ui_batch
        group = self._overlay_group

        for p in self._particles:
            if self._particle_type == "snow":
                shape = pyglet.shapes.Circle(
                    p["x"], p["y"], p["size"],
                    color=(255, 255, 255), batch=batch, group=group,
                )
            elif self._particle_type == "rain":
                shape = pyglet.shapes.Line(
                    p["x"], p["y"], p["x"] + p["speed_x"] * 2,
                    p["y"] - p["length"],
                    color=(180, 200, 220), batch=batch, group=group,
                )

    # ====================================================================
    #  屏幕震动
    # ====================================================================

    def start_shake(self, duration: float = 0.5, intensity: int = 8) -> None:
        """启动屏幕震动。

        Args:
            duration: 震动持续秒数。
            intensity: 震动最大像素偏移。
        """
        self._shake_time = duration
        self._shake_intensity = intensity

    def stop_shake(self) -> None:
        """停止屏幕震动。"""
        self._shake_time = 0.0
        self._shake_intensity = 0
        self._shake_offset = (0.0, 0.0)

    @property
    def shake_offset(self) -> tuple[float, float]:
        return self._shake_offset

    def get_is_transitioning(self) -> bool:
        """是否正在转场中。"""
        return self._transition is not None
