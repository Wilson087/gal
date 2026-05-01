"""
Layer Manager — 多层绘制管理器
===============================
使用 pyglet.graphics.OrderedGroup + Batch 管理 6 个渲染层。
提供背景设置、精灵增删、淡入淡出、特效占位。

::

    from graphics.layer import LayerManager, Layer

    lm = LayerManager(width=1280, height=720)
    lm.set_background(bg_image)
    actor = lm.show_sprite(Layer.MID, chara_img, (640, 200))
    actor.fade_to(0, 1.0)
    lm.update(dt)
    lm.draw()
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

import pyglet.graphics
import pyglet.image
import pyglet.shapes
import pyglet.sprite
from pyglet.graphics import Batch, OrderedGroup  # type: ignore[attr-defined]

from .sprite_actor import SpriteActor, linear

logger = logging.getLogger(__name__)


class Layer(Enum):
    """渲染层枚举，值即绘制顺序（小 → 大 = 远 → 近）。"""

    BG = 0        # 背景
    BEHIND = 1    # 立绘后层
    MID = 2       # 立绘中层
    FRONT = 3     # 立绘前层
    EFFECTS = 4   # 特效层
    UI = 5        # UI 层


class LayerManager:
    """多层绘制管理器。

    所有精灵加入同一个 Batch，按 Layer 的 OrderedGroup 排序。
    覆盖层（fade_out/fade_in）为独立 pyglet.shapes.Rectangle，
    不参与 Batch，单独绘制。

    构造参数 width / height 为窗口尺寸，
    集成时从 AppConfig 读取传入，不硬编码常量。
    """

    def __init__(self, width: int, height: int) -> None:
        self.width: int = width
        self.height: int = height

        self._batch: Batch = Batch()
        self._groups: dict[Layer, OrderedGroup] = {
            layer: OrderedGroup(layer.value) for layer in Layer
        }

        # 每层精灵列表
        self._sprites: dict[Layer, list[SpriteActor]] = {
            layer: [] for layer in Layer
        }
        self._bg_actor: SpriteActor | None = None

        # 淡入淡出覆盖层
        self._overlay: pyglet.shapes.Rectangle | None = None
        self._overlay_opacity: int = 0
        self._fade_tween: _FadeTween | None = None

        logger.info(
            "LayerManager 已初始化: %dx%d, %d 层",
            width, height, len(Layer),
        )

    # ── 背景 ──────────────────────────────────────────────

    def set_background(self, image: pyglet.image.ImageData) -> None:
        """设置背景图像。若已有旧背景则自动替换并释放。

        Args:
            image: 已加载的图像数据（来自 ResourceManager.get_image）。
        """
        if self._bg_actor is not None:
            self._bg_actor.delete()
        self._bg_actor = SpriteActor(
            image, x=0, y=0,
            batch=self._batch, group=self._groups[Layer.BG],
        )
        # 背景缩放到窗口大小（cover 模式）
        if image.width > 0 and image.height > 0:
            sx = self.width / image.width
            sy = self.height / image.height
            s = max(sx, sy)
            self._bg_actor.set_position(
                (self.width - image.width * s) / 2,
                (self.height - image.height * s) / 2,
            )
            self._bg_actor._sprite.scale = s
        logger.debug("背景已设置")

    # ── 精灵 ──────────────────────────────────────────────

    def show_sprite(
        self,
        layer: Layer,
        image: pyglet.image.ImageData,
        position: tuple[float, float],
    ) -> SpriteActor:
        """在指定层添加精灵。

        坐标原点在窗口**左下角**，与 pyglet 坐标系统一致。
        X 向右增大，Y 向上增大。

        Args:
            layer: 渲染层（Layer 枚举）。
            image: 已加载图像。
            position: (x, y) 精灵左下角坐标。

        Returns:
            SpriteActor，可用于后续动画 / 移除。
        """
        actor = SpriteActor(
            image, x=position[0], y=position[1],
            batch=self._batch, group=self._groups[layer],
        )
        self._sprites[layer].append(actor)
        logger.debug("精灵已添加: layer=%s pos=(%d,%d)", layer.name, position[0], position[1])
        return actor

    def remove_sprite(self, actor: SpriteActor) -> None:
        """从任意层移除精灵并释放。

        若 actor 未在任何层中，静默忽略（no-op）。

        Args:
            actor: 要移除的 SpriteActor。
        """
        for layer in Layer:
            layer_sprites = self._sprites[layer]
            if actor in layer_sprites:
                layer_sprites.remove(actor)
                actor.delete()
                logger.debug("精灵已移除: layer=%s", layer.name)
                return
        # 不在任何层中 —— 静默忽略

    # ── 全屏淡入淡出 ──────────────────────────────────────

    def fade_out(
        self,
        duration: float,
        color: tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """全屏淡出到指定颜色。

        若已有 overlay 存在，先释放旧的再创建新的，防止泄漏。

        Args:
            duration: 淡出时长（秒）。
            color: 目标颜色 (R, G, B)，默认黑色。可用于白屏过渡 (255,255,255)
                   或红色负伤效果 (255,0,0)。
        """
        # 释放旧 overlay 防止泄漏
        if self._overlay is not None:
            self._overlay.delete()
            self._overlay = None

        r, g, b = color
        self._overlay = pyglet.shapes.Rectangle(
            x=0, y=0, width=self.width, height=self.height,
            color=(r, g, b),
        )
        self._overlay.opacity = 0
        self._fade_tween = _FadeTween(
            start=0, target=255, duration=duration, direction="out",
        )
        logger.debug("fade_out: duration=%.2f color=(%d,%d,%d)", duration, r, g, b)

    def fade_in(
        self,
        duration: float,
        color: tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """全屏淡入（从覆盖色恢复到透明）。

        若当前无 overlay，先创建。

        Args:
            duration: 淡入时长（秒）。
            color: 覆盖颜色 (R, G, B)，应与 fade_out 时一致。
        """
        if self._overlay is not None:
            self._overlay.delete()

        r, g, b = color
        self._overlay = pyglet.shapes.Rectangle(
            x=0, y=0, width=self.width, height=self.height,
            color=(r, g, b),
        )
        self._overlay.opacity = 255
        self._fade_tween = _FadeTween(
            start=255, target=0, duration=duration, direction="in",
        )
        logger.debug("fade_in: duration=%.2f color=(%d,%d,%d)", duration, r, g, b)

    # ── 特效占位 ──────────────────────────────────────────

    def fog(self, density: float) -> None:
        """雾化全屏效果（TODO）。

        Args:
            density: 雾浓度 [0.0, 1.0]。
        """

    def screen_shake(self, intensity: float, duration: float) -> None:
        """屏幕震动效果（TODO）。

        Args:
            intensity: 震动强度（像素）。
            duration: 持续时间（秒）。
        """

    # ── 批量操作 ──────────────────────────────────────────

    def clear_all(self) -> None:
        """清空所有精灵和背景，保留遮盖层。"""
        if self._bg_actor is not None:
            self._bg_actor.delete()
            self._bg_actor = None
        for layer in Layer:
            for actor in self._sprites[layer]:
                actor.delete()
            self._sprites[layer].clear()
        logger.debug("clear_all: 所有精灵已清空（overlay 保留）")

    def update(self, dt: float) -> None:
        """推进所有精灵动画 + 淡入淡出补间。

        Args:
            dt: delta 时间（秒）。
        """
        if dt <= 0:
            return

        # 背景
        if self._bg_actor is not None:
            self._bg_actor.update(dt)

        # 各层精灵 + 防御已删除残留
        for layer in Layer:
            stale: list[SpriteActor] = []
            for actor in self._sprites[layer]:
                if not actor.alive:
                    stale.append(actor)
                    continue
                actor.update(dt)
            for actor in stale:
                self._sprites[layer].remove(actor)

        # 淡入淡出
        self._update_fade(dt)

    def draw(self) -> None:
        """绘制一帧：先 Batch（精灵），再 overlay（若有）。"""
        self._batch.draw()
        if self._overlay is not None and self._overlay_opacity > 0:
            self._overlay.draw()

    # ── Fade 内部 ─────────────────────────────────────────

    def _update_fade(self, dt: float) -> None:
        tween = self._fade_tween
        overlay = self._overlay
        if tween is None or overlay is None:
            return

        tween.elapsed += dt
        if tween.duration <= 0:
            progress = 1.0
        else:
            progress = tween.elapsed / tween.duration

        if progress >= 1.0:
            self._overlay_opacity = tween.target
            overlay.opacity = self._overlay_opacity
            if tween.target == 0:
                # fade_in 完成 → 释放 overlay
                overlay.delete()
                self._overlay = None
                self._overlay_opacity = 0
            self._fade_tween = None
        else:
            self._overlay_opacity = int(
                tween.start + (tween.target - tween.start) * progress
            )
            overlay.opacity = self._overlay_opacity


# ── Fade 补间内部类 ────────────────────────────────────────

class _FadeTween:
    """全屏淡入淡出补间状态（内部使用）。"""

    __slots__ = ("start", "target", "duration", "elapsed", "direction")

    def __init__(
        self, start: int, target: int, duration: float, direction: str,
    ) -> None:
        self.start = start
        self.target = target
        self.duration = duration
        self.elapsed: float = 0.0
        self.direction = direction
