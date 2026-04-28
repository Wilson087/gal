"""
立绘管理模块
============
管理左右立绘 Sprite 的加载、切换、淡入淡出和说话动画。
"""

import os
import math
from typing import Optional

import pyglet
from pyglet.graphics import Batch, Group

from .constants import (
    IMAGES_DIR, WINDOW_WIDTH, WINDOW_HEIGHT,
    CHAR_X_LEFT_RATIO, CHAR_X_RIGHT_RATIO, CHAR_Y_BOTTOM_MARGIN,
    CHAR_FADE_DURATION, CHAR_SPEAK_FLOAT_AMOUNT,
    CHAR_SPEAK_BOUNCE_STEPS, CHAR_ANIMATION_INTERVAL,
    PLACEHOLDER_COLORS,
)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """将十六进制颜色转为 RGB 元组。"""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


class CharacterSprite:
    """单个立绘 Sprite 的管理封装，支持淡入淡出和说话浮动。"""

    def __init__(self, char_id: str, batch: Batch, group: Group) -> None:
        self.char_id = char_id
        self.batch = batch
        self.group = group
        self.sprite: Optional[pyglet.sprite.Sprite] = None
        self.target_opacity: int = 0
        self._fade_speed: float = 0.0
        self._fading_in: bool = False
        self._fading_out: bool = False
        self._orig_y: float = 0.0
        self._speak_offset: float = 0.0

        self._load_image()

    def _load_image(self) -> None:
        """加载立绘图片，失败时创建彩色占位。"""
        path = os.path.join(IMAGES_DIR, f"{self.char_id}.png")
        try:
            img = pyglet.image.load(path)
            self.sprite = pyglet.sprite.Sprite(img, batch=self.batch, group=self.group)
        except Exception:
            self._create_placeholder()

    def _create_placeholder(self) -> None:
        """为缺失的立绘文件创建彩色占位矩形。"""
        color = PLACEHOLDER_COLORS.get(self.char_id, (100, 100, 100))
        img = pyglet.image.SolidColorImagePattern(
            (*color, 255)
        ).create_image(170, 400)
        self.sprite = pyglet.sprite.Sprite(img, batch=self.batch, group=self.group)

    def set_position(self, x: float, y: float) -> None:
        if self.sprite:
            self.sprite.update(x=x, y=y)
            self._orig_y = y

    def set_scale(self, scale: float) -> None:
        if self.sprite:
            self.sprite.update(scale=scale)

    def set_opacity(self, opacity: int) -> None:
        if self.sprite:
            self.sprite.opacity = opacity

    def start_fade_in(self, duration: float = CHAR_FADE_DURATION) -> None:
        self.target_opacity = 255
        self._fade_speed = 255 / (duration * 60) if duration > 0 else 255
        self._fading_in = True
        self._fading_out = False
        self.set_opacity(0)

    def start_fade_out(self, duration: float = CHAR_FADE_DURATION) -> None:
        self.target_opacity = 0
        self._fade_speed = 255 / (duration * 60) if duration > 0 else 255
        self._fading_out = True
        self._fading_in = False

    def update_fade(self) -> bool:
        """更新淡入淡出。返回 True 表示动画仍在进行。"""
        if not self.sprite:
            return False
        if self._fading_in:
            new_opacity = int(min(255, self.sprite.opacity + self._fade_speed))
            self.sprite.opacity = new_opacity
            if new_opacity >= 255:
                self._fading_in = False
        elif self._fading_out:
            new_opacity = int(max(0, self.sprite.opacity - self._fade_speed))
            self.sprite.opacity = new_opacity
            if new_opacity <= 0:
                self._fading_out = False
                return False
        return self._fading_in or self._fading_out

    def apply_shake(self, dx: float, dy: float) -> None:
        if self.sprite:
            self.sprite.x += dx
            self.sprite.y += dy

    def set_speak_offset(self, offset: float) -> None:
        if self.sprite:
            self.sprite.y = self._orig_y + offset

    def delete(self) -> None:
        if self.sprite:
            self.sprite.delete()
            self.sprite = None


class CharacterManager:
    """管理左右两侧立绘的显示、切换和说话动画。"""

    def __init__(self, app: "AVGApplication") -> None:
        self.app = app
        self.left: Optional[CharacterSprite] = None
        self.right: Optional[CharacterSprite] = None

        self._left_group = Group(order=1)
        self._right_group = Group(order=2)

        self._speaking_side: Optional[str] = None
        self._speak_timer: float = 0.0
        self._speak_step: int = 0

    def set_characters(self, char_data: dict) -> None:
        """根据场景/对话中的 char_data 更新立绘。

        Args:
            char_data: {"left": char_id, "right": char_id}。
        """
        self._update_side("left", char_data.get("left"))
        self._update_side("right", char_data.get("right"))

    def _update_side(self, side: str, char_id: Optional[str]) -> None:
        """更新单侧立绘。"""
        current = self.left if side == "left" else self.right
        current_id = current.char_id if current else None

        if char_id == current_id:
            return

        # 删除旧立绘
        if current:
            current.delete()

        if not char_id:
            if side == "left":
                self.left = None
            else:
                self.right = None
            return

        group = self._left_group if side == "left" else self._right_group
        spr = CharacterSprite(char_id, self.app.main_batch, group)

        x = int(WINDOW_WIDTH * CHAR_X_LEFT_RATIO if side == "left" else WINDOW_WIDTH * CHAR_X_RIGHT_RATIO)
        y = CHAR_Y_BOTTOM_MARGIN
        spr.set_position(x, y)
        spr.start_fade_in()

        if side == "left":
            self.left = spr
        else:
            self.right = spr

    def start_speaking(self, side: str) -> None:
        """启动指定侧立绘说话浮动动画。"""
        self._speaking_side = side
        self._speak_step = 0
        self._speak_timer = 0.0

    def stop_speaking(self) -> None:
        """停止说话动画。"""
        if self._speaking_side:
            spr = self.left if self._speaking_side == "left" else self.right
            if spr:
                spr.set_speak_offset(0)
        self._speaking_side = None
        self._speak_step = 0

    def update(self, dt: float) -> None:
        """每帧更新立绘动画。"""
        # 更新淡入淡出
        if self.left:
            self.left.update_fade()
        if self.right:
            self.right.update_fade()

        # 说话浮动动画
        if self._speaking_side:
            self._speak_timer += dt
            if self._speak_timer >= CHAR_ANIMATION_INTERVAL:
                self._speak_timer = 0.0
                bounce_table = [0, -CHAR_SPEAK_FLOAT_AMOUNT,
                                -CHAR_SPEAK_FLOAT_AMOUNT // 2, 0]
                offset = bounce_table[self._speak_step % len(bounce_table)]
                spr = self.left if self._speaking_side == "left" else self.right
                if spr:
                    spr.set_speak_offset(offset)
                self._speak_step += 1

    def clear(self) -> None:
        """清除所有立绘。"""
        self.stop_speaking()
        if self.left:
            self.left.delete()
            self.left = None
        if self.right:
            self.right.delete()
            self.right = None

    def apply_shake(self, dx: float, dy: float) -> None:
        """应用震动偏移。"""
        if self.left:
            self.left.apply_shake(dx, dy)
        if self.right:
            self.right.apply_shake(dx, dy)
