"""
Sprite Actor — pyglet 精灵封装 + 补间动画
==========================================
与 ResourceManager 解耦，接收已加载的 ImageData。

动画覆盖规则：
    **同名属性动画互相覆盖，不同属性动画可并行运行。**
    例如：先 move_to(A, 1s)，0.3s 后再 move_to(B, 0.5s) → x/y 动画被覆盖，新目标为 B。
    同时 fade_to(128, 1s) 与 move_to 互不干扰，并行执行。

用法::

    from graphics.sprite_actor import SpriteActor, ease_in_out_quad

    actor = SpriteActor(image, x=640, y=360, batch=batch, group=group)
    actor.move_to(800, 400, 1.0, easing=ease_in_out_quad).fade_to(128, 0.5)
    while ...:
        actor.update(dt)
    actor.delete()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

import pyglet.image
import pyglet.sprite

logger = logging.getLogger(__name__)

# ── 缓动函数 ──────────────────────────────────────────────

EasingFunc = Callable[[float], float]


def linear(t: float) -> float:
    """线性缓动。f(t) = t"""
    return t


def ease_in_out_quad(t: float) -> float:
    """二次缓入缓出。

    t < 0.5 → 2t²
    t ≥ 0.5 → 1 - (-2t + 2)² / 2
    """
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 2 / 2.0


# ── 内部补间状态 ──────────────────────────────────────────


@dataclass
class _Tween:
    """单个属性的补间动画状态。可复用——elapsed 每帧累加。"""

    attr: str
    start: float
    target: float
    duration: float
    elapsed: float = 0.0
    easing: EasingFunc = linear


# ── SpriteActor ────────────────────────────────────────────


class SpriteActor:
    """封装 pyglet.sprite.Sprite，提供属性补间动画。

    属性动画相互独立：移动（x/y）、缩放（scale）、
    透明度（opacity）、旋转（rotation）可同时进行。
    """

    def __init__(
        self,
        image: pyglet.image.ImageData,
        x: float,
        y: float,
        batch: pyglet.graphics.Batch,
        group: pyglet.graphics.OrderedGroup,  # type: ignore[name-defined]
    ) -> None:
        self._sprite: pyglet.sprite.Sprite = pyglet.sprite.Sprite(
            image, x=x, y=y, batch=batch, group=group,
        )
        self._tweens: dict[str, _Tween] = {}

    # ── 只读属性 ──────────────────────────────────────────

    @property
    def sprite(self) -> pyglet.sprite.Sprite:
        """底层 pyglet Sprite（只读引用）。"""
        return self._sprite

    @property
    def x(self) -> float:
        return self._sprite.x

    @property
    def y(self) -> float:
        return self._sprite.y

    @property
    def opacity(self) -> int:
        return self._sprite.opacity

    @property
    def scale(self) -> float:
        return self._sprite.scale

    @property
    def rotation(self) -> float:
        return self._sprite.rotation

    @property
    def alive(self) -> bool:
        """精灵是否未被删除。"""
        return not self._sprite._delete  # type: ignore[attr-defined]

    # ── 补间动画 ──────────────────────────────────────────

    def move_to(
        self,
        x: float,
        y: float,
        duration: float,
        easing: EasingFunc = ease_in_out_quad,
    ) -> SpriteActor:
        """平滑移动到目标坐标。

        Args:
            x: 目标 X（窗口左下角原点，与 pyglet 一致）。
            y: 目标 Y。
            duration: 动画时长（秒）。0 表示瞬间到位。
            easing: 缓动函数。默认 ease_in_out_quad。

        Returns:
            self，支持链式调用。
        """
        self._set_tween("x", self._sprite.x, x, duration, easing)
        self._set_tween("y", self._sprite.y, y, duration, easing)
        return self

    def fade_to(
        self,
        opacity: int,
        duration: float,
        easing: EasingFunc = linear,
    ) -> SpriteActor:
        """平滑过渡透明度。

        Args:
            opacity: 目标透明度 [0, 255]。自动 clamp。
            duration: 动画时长（秒）。
            easing: 缓动函数。

        Returns:
            self，支持链式调用。
        """
        opacity = max(0, min(255, opacity))
        self._set_tween(
            "opacity", float(self._sprite.opacity), float(opacity),
            duration, easing,
        )
        return self

    def scale_to(
        self,
        scale: float,
        duration: float,
        easing: EasingFunc = ease_in_out_quad,
    ) -> SpriteActor:
        """平滑缩放。

        Args:
            scale: 目标缩放比。必须 > 0。
            duration: 动画时长（秒）。
            easing: 缓动函数。

        Returns:
            self，支持链式调用。

        Raises:
            ValueError: scale <= 0。
        """
        if scale <= 0:
            raise ValueError(f"scale 必须 > 0，收到: {scale}")
        self._set_tween("scale", self._sprite.scale, scale, duration, easing)
        return self

    def rotate_to(
        self,
        angle: float,
        duration: float,
        easing: EasingFunc = linear,
    ) -> SpriteActor:
        """平滑旋转。

        Args:
            angle: 目标角度（度）。
            duration: 动画时长（秒）。
            easing: 缓动函数。

        Returns:
            self，支持链式调用。
        """
        self._set_tween(
            "rotation", self._sprite.rotation, angle, duration, easing,
        )
        return self

    # ── 即时设置 ──────────────────────────────────────────

    def set_position(self, x: float, y: float) -> None:
        """瞬间移动到指定坐标（无动画）。"""
        self._sprite.update(x=x, y=y)
        self._tweens.pop("x", None)
        self._tweens.pop("y", None)

    def set_opacity(self, opacity: int) -> None:
        """瞬间设置透明度（无动画）。"""
        opacity = max(0, min(255, opacity))
        self._sprite.opacity = opacity
        self._tweens.pop("opacity", None)

    # ── 生命周期 ──────────────────────────────────────────

    def update(self, dt: float) -> None:
        """推进所有进行中的补间动画 dt 秒。

        duration == 0 的补间直接跳目标值（瞬移 / 瞬切），
        避免除零问题。

        Args:
            dt: 自上一帧起的 delta 时间（秒）。
        """
        if dt <= 0:
            return

        completed: list[str] = []
        for attr_name, tween in self._tweens.items():
            if tween.duration <= 0.0:
                # 瞬时完成
                self._apply_tween_attr(attr_name, tween.target)
                completed.append(attr_name)
                continue

            tween.elapsed += dt
            progress = tween.elapsed / tween.duration
            if progress >= 1.0:
                self._apply_tween_attr(attr_name, tween.target)
                completed.append(attr_name)
            else:
                eased = tween.easing(progress)
                val = tween.start + (tween.target - tween.start) * eased
                self._apply_tween_attr(attr_name, val)

        for name in completed:
            del self._tweens[name]

    def delete(self) -> None:
        """删除底层 Sprite 并清空动画状态。"""
        self._tweens.clear()
        self._sprite.delete()
        logger.debug("SpriteActor 已删除")

    # ── 内部 ──────────────────────────────────────────────

    def _set_tween(
        self,
        attr: str,
        start: float,
        target: float,
        duration: float,
        easing: EasingFunc,
    ) -> None:
        """设置或覆盖某属性的补间动画。"""
        if duration < 0:
            raise ValueError(f"duration 不能为负数: {duration}")
        if duration == 0.0:
            self._apply_tween_attr(attr, target)
            self._tweens.pop(attr, None)
            return
        self._tweens[attr] = _Tween(
            attr=attr, start=start, target=target,
            duration=duration, easing=easing,
        )

    def _apply_tween_attr(self, attr: str, value: float) -> None:
        """将补间值写入 sprite 对应属性。"""
        if attr in ("x", "y"):
            self._sprite.update(**{attr: value})
        elif attr == "opacity":
            self._sprite.opacity = int(value)
        elif attr == "scale":
            self._sprite.scale = value
        elif attr == "rotation":
            self._sprite.rotation = value
