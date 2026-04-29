"""
背景管理器模块
==============
管理背景 Sprite 的加载、适配、切换和转场。
支持 4 种适配模式，窗口 resize 时自动重算。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from ..app import AVGApplication

import pyglet
from pyglet.graphics import Group

from ..core.constants import IMAGES_DIR, COLOR_BG_DARK
from ..core.logger import Logger

log = Logger("BG")

# 适配模式常量
FIT_COVER = "cover"
FIT_FIT = "fit"
FIT_STRETCH = "stretch"
FIT_ORIGINAL = "original"

_FIT_MODES = (FIT_COVER, FIT_FIT, FIT_STRETCH, FIT_ORIGINAL)


class BackgroundManager:
    """背景管理器。

    支持 4 种适配模式：
    - COVER: 等比例铺满，裁剪超出部分（默认，无黑边）
    - FIT: 等比例完整显示，留黑边
    - STRETCH: 拉伸铺满
    - ORIGINAL: 1:1 居中显示
    """

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        self._group = Group(order=0)
        self._sprite: Optional[pyglet.sprite.Sprite] = None
        self.current_bg_id: Optional[str] = None
        self._fit_mode: str = FIT_COVER
        self._window_ref: Optional["pyglet.window.BaseWindow"] = None

        # 转场状态
        self._pending_bg_id: Optional[str] = None
        self._pending_callback: Optional[Callable] = None

        # 震动
        self._shake_offset: tuple[float, float] = (0.0, 0.0)

    def set_window(self, window: "pyglet.window.BaseWindow") -> None:
        """绑定窗口引用（用于获取窗口尺寸）。"""
        self._window_ref = window

    # ── 适配模式 ────────────────────────────────────────────

    def set_fit_mode(self, mode: str) -> None:
        """设置背景适配模式，立即重新计算布局。

        Args:
            mode: cover / fit / stretch / original
        """
        if mode not in _FIT_MODES:
            log.debug("未知适配模式: %s", mode)
            return
        log.debug("切换适配模式: %s", mode)
        self._fit_mode = mode
        self._recalculate_geometry()

    def get_fit_mode(self) -> str:
        return self._fit_mode

    def get_fit_mode_names(self) -> list[str]:
        return ["cover (裁剪)", "fit (留边)", "stretch (拉伸)", "original (原图)"]

    # ── 背景加载与切换 ──────────────────────────────────────

    def set_background(self, bg_id: str, transition: str = "crossfade",
                       on_ready: Optional[Callable] = None) -> None:
        """设置背景图片，带转场效果。

        Args:
            bg_id: 背景标识符（对应 resources/images/{bg_id}.png）。
            transition: 转场类型，详见 effect_system。
            on_ready: 背景就绪后调用。
        """
        if bg_id == self.current_bg_id and self._sprite:
            if on_ready:
                on_ready()
            return

        log.debug("切换背景: %s -> %s (转场=%s)", self.current_bg_id, bg_id, transition)

        new_sprite = self._load_background(bg_id)
        if new_sprite is None:
            if on_ready:
                on_ready()
            return

        self._pending_bg_id = bg_id
        self._pending_callback = on_ready
        old_sprite = self._sprite

        def _swap_bg():
            if old_sprite:
                old_sprite.delete()
            self._sprite = new_sprite
            self.current_bg_id = bg_id
            self._recalculate_geometry()
            if self._pending_callback:
                self._pending_callback()

        if old_sprite is None or transition == "none":
            new_sprite.opacity = 255
            self._sprite = new_sprite
            self.current_bg_id = bg_id
            self._recalculate_geometry()
            if on_ready:
                on_ready()
        else:
            self.app.effect_system.start_transition(
                transition, on_midpoint=_swap_bg)

    def _load_background(self, bg_id: str) -> Optional[pyglet.sprite.Sprite]:
        """加载背景图片，失败时创建纯色占位。

        Args:
            bg_id: 背景标识符。

        Returns:
            Sprite 对象或 None。
        """
        path = os.path.join(IMAGES_DIR, f"{bg_id}.png")
        try:
            img = pyglet.image.load(path)
        except Exception:
            color = COLOR_BG_DARK
            img = pyglet.image.SolidColorImagePattern(color).create_image(
                self._window_ref.width if self._window_ref else 1280,
                self._window_ref.height if self._window_ref else 720,
            )

        sprite = pyglet.sprite.Sprite(
            img, batch=self.app.main_batch, group=self._group)
        sprite.opacity = 255
        return sprite

    # ── 窗口缩放 ────────────────────────────────────────────

    def on_resize(self, width: int, height: int) -> None:
        """窗口尺寸变化时调用，重新计算背景几何。"""
        self._recalculate_geometry()

    def _recalculate_geometry(self) -> None:
        """根据当前窗口尺寸和适配模式计算 Sprite 变换。"""
        if not self._sprite:
            return
        if not self._window_ref:
            return

        win_w = self._window_ref.width
        win_h = self._window_ref.height
        if win_w == 0 or win_h == 0:
            return

        img_w = self._sprite.width
        img_h = self._sprite.height
        if img_w == 0 or img_h == 0:
            return

        win_ratio = win_w / win_h
        img_ratio = img_w / img_h

        if self._fit_mode == FIT_COVER:
            if win_ratio > img_ratio:
                scale = win_w / img_w
            else:
                scale = win_h / img_h
            x = (win_w - img_w * scale) / 2
            y = (win_h - img_h * scale) / 2
            self._sprite.update(scale=scale, x=x, y=y)

        elif self._fit_mode == FIT_FIT:
            if win_ratio > img_ratio:
                scale = win_h / img_h
            else:
                scale = win_w / img_w
            x = (win_w - img_w * scale) / 2
            y = (win_h - img_h * scale) / 2
            self._sprite.update(scale=scale, x=x, y=y)

        elif self._fit_mode == FIT_STRETCH:
            self._sprite.update(
                scale_x=win_w / img_w,
                scale_y=win_h / img_h,
                x=0, y=0,
            )

        else:  # FIT_ORIGINAL
            x = (win_w - img_w) / 2
            y = (win_h - img_h) / 2
            self._sprite.update(scale=1.0, x=x, y=y)

    # ── 震动 ────────────────────────────────────────────────

    def apply_shake(self, dx: float, dy: float) -> None:
        """应用震动偏移（累积方式，保持向后兼容）。"""
        self._shake_offset = (dx, dy)
        if self._sprite:
            self._sprite.x += dx
            self._sprite.y += dy

    def set_shake_offset(self, dx: float, dy: float,
                          saved: dict) -> None:
        """基于保存的原始位置设置绝对震动偏移。"""
        self._shake_offset = (dx, dy)
        if self._sprite and id(self._sprite) in saved:
            ox, oy = saved[id(self._sprite)]
            self._sprite.x = ox + dx
            self._sprite.y = oy + dy

    def reset_shake(self, saved: Optional[dict] = None) -> None:
        """重置震动偏移，恢复到保存的原始位置。"""
        if saved and self._sprite and id(self._sprite) in saved:
            ox, oy = saved[id(self._sprite)]
            self._sprite.x = ox
            self._sprite.y = oy
        self._shake_offset = (0.0, 0.0)

    # ── 清理 ────────────────────────────────────────────────

    def clear(self) -> None:
        """删除当前背景。"""
        if self._sprite:
            self._sprite.delete()
            self._sprite = None
        self.current_bg_id = None

    def get_sprite(self) -> Optional[pyglet.sprite.Sprite]:
        return self._sprite
