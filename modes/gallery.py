"""
鉴赏模式 — CG 画廊 / 音乐欣赏 / 立绘鉴赏
=========================================
独立于剧本系统的特殊模式，通过 GameState 切换进入。
所有 UI 绘制在 Layer.UI 层上，使用 pyglet 基础图形。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pyglet.graphics
import pyglet.image
import pyglet.shapes
import pyglet.sprite
import pyglet.text
from pyglet.graphics import Batch, Group
from pyglet.window import key as _key

from core.events import Event, EventBus, GameState

logger = logging.getLogger(__name__)


# ── 字体 ──────────────────────────────────────────────────────

_FONT = "Microsoft YaHei"

# ── 百分比定位 ────────────────────────────────────────────────

def _pctx(pct: float, width: int) -> int:
    return int(width * pct / 100.0)


def _pcty(pct: float, height: int) -> int:
    return int(height * pct / 100.0)


# ══════════════════════════════════════════════════════════════
# CG 画廊
# ══════════════════════════════════════════════════════════════

class CGGallery:
    """CG 画廊 — 缩略图网格 + 全屏查看。

    从 JSON 配置文件读取 CG 列表，根据旗标判断解锁状态。
    未解锁显示灰色占位，已解锁可点击放大查看并左右翻页。
    """

    _COLS = 4
    _THUMB_W = 260
    _THUMB_H = 160
    _PADDING = 16
    _PLACEHOLDER_COLOR = (50, 50, 60)
    _OVERLAY_COLOR = (0, 0, 0)
    _OVERLAY_ALPHA = 220

    def __init__(
        self,
        batch: Batch,
        ui_group: Group,
        width: int,
        height: int,
        resource_manager: Any,
        flags: dict[str, bool],
        config_path: str,
        event_bus: EventBus | None = None,
    ) -> None:
        self._batch = batch
        self._group = ui_group
        self._width = width
        self._height = height
        self._rm = resource_manager
        self._flags = flags
        self._config_path = config_path
        self._event_bus = event_bus

        # 配置数据
        self._cg_list: list[dict[str, Any]] = []

        # 网格模式
        self._grid_items: list[dict[str, Any]] = []
        self._scroll_offset: float = 0.0
        self._max_scroll: float = 0.0
        self._hover_index: int = -1
        self._grid_overlay: pyglet.shapes.Rectangle | None = None
        self._grid_title: pyglet.text.Label | None = None
        self._grid_back_hint: pyglet.text.Label | None = None

        # 全屏查看模式
        self._viewing: bool = False
        self._view_index: int = 0
        self._full_sprite: pyglet.sprite.Sprite | None = None
        self._overlay: pyglet.shapes.Rectangle | None = None
        self._arrow_left: pyglet.text.Label | None = None
        self._arrow_right: pyglet.text.Label | None = None
        self._title_label: pyglet.text.Label | None = None
        self._back_hint: pyglet.text.Label | None = None

        # 事件回调引用（供 off 使用）
        self._on_key_ref: Any = None

    # ── 生命周期 ──────────────────────────────────────────

    def load_config(self) -> None:
        """从 JSON 加载 CG 列表。"""
        try:
            data = json.loads(Path(self._config_path).read_text("utf-8"))
            self._cg_list = data.get("cgs", [])
            logger.info("CG 画廊配置已加载: %d 张", len(self._cg_list))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            logger.warning("CG 画廊配置加载失败: %s", e)
            self._cg_list = []

    def show(self) -> None:
        """进入画廊（网格模式）。"""
        self._viewing = False
        self._cleanup_full_view()
        self._build_grid()
        if self._event_bus:
            self._on_key_ref = self._event_bus.on(Event.KEY_PRESS, self._on_key)

    def hide(self) -> None:
        """退出画廊。"""
        self._viewing = False
        self._cleanup_grid()
        self._cleanup_full_view()
        if self._event_bus and self._on_key_ref:
            self._event_bus.off(Event.KEY_PRESS, self._on_key_ref)
            self._on_key_ref = None

    def update(self, dt: float) -> None:
        """更新悬停高亮。"""
        if self._viewing or not self._grid_items:
            return
        for i, item in enumerate(self._grid_items):
            bg = item.get("bg")
            if bg is None:
                continue
            if i == self._hover_index:
                bg.color = (80, 80, 110)
            else:
                bg.color = (40, 40, 60) if item.get("unlocked") else self._PLACEHOLDER_COLOR

    def draw(self) -> None:
        """全屏查看时绘制遮罩和 CG 图像。"""
        if self._viewing and self._overlay is not None:
            self._overlay.draw()
        if self._viewing and self._full_sprite is not None:
            self._full_sprite.draw()

    # ── 输入 ──────────────────────────────────────────────

    def handle_click(self, x: float, y: float) -> bool:
        """处理点击。

        Returns:
            True 如果点击被消费。
        """
        if self._viewing:
            return self._click_full_view(x, y)
        return self._click_grid(x, y)

    def handle_scroll(self, dy: float) -> None:
        """滚轮滚动网格。"""
        if not self._viewing:
            self._scroll_offset = max(
                0.0, min(self._max_scroll, self._scroll_offset - dy * 40)
            )
            self._apply_scroll()

    def handle_mouse_motion(self, x: float, y: float) -> None:
        """更新悬停索引。"""
        if self._viewing:
            return
        self._hover_index = -1
        for i, item in enumerate(self._grid_items):
            bg = item.get("bg")
            if bg is None:
                continue
            if bg.x <= x <= bg.x + bg.width and bg.y <= y <= bg.y + bg.height:
                self._hover_index = i
                return

    # ── 键盘 ──────────────────────────────────────────────

    def handle_exit(self) -> bool:
        """ESC 或返回按钮 —— 退出画廊或返回网格。

        Returns:
            True 表示完全退出画廊模式。
        """
        if self._viewing:
            self._exit_full_view()
            return False
        return True

    def _on_key(self, **kwargs: Any) -> None:
        """键盘事件回调（订阅 KEY_PRESS）。"""
        symbol = int(kwargs.get("symbol", 0))
        if symbol == _key.ESCAPE:
            # 由 Game 层处理退出
            pass
        elif self._viewing:
            if symbol == _key.LEFT:
                self._nav_full_view(-1)
            elif symbol == _key.RIGHT:
                self._nav_full_view(1)

    # ── 网格模式 ──────────────────────────────────────────

    def _build_grid(self) -> None:
        """构建缩略图网格。"""
        self._cleanup_grid()

        # 背景遮罩（放在 batch 中，位于网格项之下，使主菜单背景不抢眼）
        self._grid_overlay = pyglet.shapes.Rectangle(
            x=0, y=0, width=self._width, height=self._height,
            color=(0, 0, 0),
            batch=self._batch, group=self._group,
        )
        self._grid_overlay.opacity = 160

        start_x = _pctx(5, self._width)
        grid_w = _pctx(90, self._width)
        cell_w = (grid_w - (self._COLS - 1) * self._PADDING) // self._COLS
        cell_h = self._THUMB_H
        y_base = _pctx(65, self._height)

        if not self._cg_list:
            self._grid_title = pyglet.text.Label(
                "CG 画廊", font_name=_FONT, font_size=28,
                x=self._width // 2, y=_pctx(92, self._height),
                color=(220, 220, 240, 255),
                anchor_x="center", anchor_y="center",
                batch=self._batch, group=self._group,
            )
            self._grid_back_hint = pyglet.text.Label(
                "ESC 返回", font_name=_FONT, font_size=12,
                x=_pctx(95, self._width), y=_pctx(95, self._height),
                color=(150, 150, 150, 255),
                anchor_x="right",
                batch=self._batch, group=self._group,
            )
            return

        for i, cg in enumerate(self._cg_list):
            unlocked = self._flags.get(cg.get("unlock_flag", ""), False)
            col = i % self._COLS
            row = i // self._COLS
            cx = start_x + col * (cell_w + self._PADDING)
            cy = y_base - row * (cell_h + self._PADDING + 20)  # 20 for title

            # 背景矩形
            color = (40, 40, 60) if unlocked else self._PLACEHOLDER_COLOR
            bg = pyglet.shapes.Rectangle(
                x=cx, y=cy, width=cell_w, height=cell_h,
                color=color, batch=self._batch, group=self._group,
            )

            # 缩略图 sprite（若解锁且图片存在）
            thumb_sprite = None
            if unlocked:
                thumb_path = cg.get("thumbnail", "")
                if thumb_path:
                    img = self._rm.get_image(thumb_path)
                    if img is not None:
                        try:
                            thumb_sprite = pyglet.sprite.Sprite(
                                img, x=cx, y=cy,
                                batch=self._batch, group=self._group,
                            )
                            sw = cell_w / img.width
                            sh = cell_h / img.height
                            s = min(sw, sh)
                            thumb_sprite.scale = s
                            thumb_sprite.x = cx + (cell_w - img.width * s) / 2
                            thumb_sprite.y = cy + (cell_h - img.height * s) / 2
                        except Exception:
                            pass

            # 标题标签
            title = cg.get("title", "") if unlocked else "???"
            title_label = pyglet.text.Label(
                title, font_name=_FONT, font_size=12,
                x=cx + cell_w // 2, y=cy - 16,
                color=(200, 200, 200, 255) if unlocked else (100, 100, 100, 255),
                anchor_x="center", anchor_y="top",
                width=cell_w,
                batch=self._batch, group=self._group,
            )

            self._grid_items.append({
                "bg": bg,
                "thumb": thumb_sprite,
                "title_label": title_label,
                "unlocked": unlocked,
                "cg_data": cg,
                "cell_x": cx, "cell_y": cy,
                "cell_w": cell_w, "cell_h": cell_h,
            })

        # 计算可滚动范围
        rows = (len(self._cg_list) + self._COLS - 1) // self._COLS
        total_h = rows * (cell_h + self._PADDING + 20)
        visible_h = self._height - _pctx(20, self._height)
        self._max_scroll = max(0.0, total_h - visible_h)

        # 标题
        self._grid_title = pyglet.text.Label(
            "CG 画廊", font_name=_FONT, font_size=28,
            x=self._width // 2, y=_pctx(92, self._height),
            color=(220, 220, 240, 255),
            anchor_x="center", anchor_y="center",
            batch=self._batch, group=self._group,
        )

        # 返回提示
        self._grid_back_hint = pyglet.text.Label(
            "ESC 返回", font_name=_FONT, font_size=12,
            x=_pctx(95, self._width), y=_pctx(95, self._height),
            color=(150, 150, 150, 255),
            anchor_x="right",
            batch=self._batch, group=self._group,
        )

    def _apply_scroll(self) -> None:
        """将滚动偏移应用到所有网格项。"""
        # 重新计算位置...
        start_x = _pctx(5, self._width)
        grid_w = _pctx(90, self._width)
        cell_w = (grid_w - (self._COLS - 1) * self._PADDING) // self._COLS
        cell_h = self._THUMB_H
        y_base = _pctx(65, self._height)

        for i, item in enumerate(self._grid_items):
            col = i % self._COLS
            row = i // self._COLS
            cx = start_x + col * (cell_w + self._PADDING)
            cy = y_base - row * (cell_h + self._PADDING + 20) + self._scroll_offset
            bg = item.get("bg")
            if bg:
                bg.x = cx
                bg.y = cy
            thumb = item.get("thumb")
            if thumb:
                thumb.x = cx + (cell_w - thumb.width * thumb.scale) / 2
                thumb.y = cy + (cell_h - thumb.height * thumb.scale) / 2
            tl = item.get("title_label")
            if tl:
                tl.x = cx + cell_w // 2
                tl.y = cy - 16

    def _click_grid(self, x: float, y: float) -> bool:
        """网格模式点击处理。"""
        for i, item in enumerate(self._grid_items):
            bg = item.get("bg")
            if bg is None:
                continue
            if bg.x <= x <= bg.x + bg.width and bg.y <= y <= bg.y + bg.height:
                if item.get("unlocked"):
                    self._enter_full_view(i)
                return True
        return False

    def _cleanup_grid(self) -> None:
        """清理网格所有对象。"""
        for item in self._grid_items:
            for key in ("bg", "thumb", "title_label"):
                obj = item.get(key)
                if obj is not None:
                    obj.delete()
        self._grid_items.clear()
        self._scroll_offset = 0.0
        self._hover_index = -1
        if self._grid_overlay is not None:
            self._grid_overlay.delete()
            self._grid_overlay = None
        if self._grid_title is not None:
            self._grid_title.delete()
            self._grid_title = None
        if self._grid_back_hint is not None:
            self._grid_back_hint.delete()
            self._grid_back_hint = None

    # ── 全屏查看 ──────────────────────────────────────────

    def _enter_full_view(self, index: int) -> None:
        """进入全屏查看模式。"""
        self._viewing = True
        self._view_index = index
        self._build_full_view()

    def _exit_full_view(self) -> None:
        """退出全屏查看，回到网格。"""
        self._viewing = False
        self._cleanup_full_view()

    def _build_full_view(self) -> None:
        """构建全屏查看 UI。"""
        self._cleanup_full_view()

        self._overlay = pyglet.shapes.Rectangle(
            x=0, y=0, width=self._width, height=self._height,
            color=self._OVERLAY_COLOR,
        )
        self._overlay.opacity = self._OVERLAY_ALPHA

        cg = self._cg_list[self._view_index]
        full_path = cg.get("full", "")
        if full_path:
            img = self._rm.get_image(full_path)
            if img is not None:
                try:
                    max_w = self._width * 0.85
                    max_h = self._height * 0.85
                    s = min(max_w / img.width, max_h / img.height, 1.0)
                    self._full_sprite = pyglet.sprite.Sprite(
                        img,
                        x=(self._width - img.width * s) / 2,
                        y=(self._height - img.height * s) / 2,
                    )
                    self._full_sprite.scale = s
                except Exception:
                    pass

        # 导航箭头
        arrow_y = self._height // 2
        self._arrow_left = pyglet.text.Label(
            "◀", font_name=_FONT, font_size=36,
            x=_pctx(5, self._width), y=arrow_y,
            color=(255, 255, 255, 200),
            anchor_x="left", anchor_y="center",
        )
        self._arrow_right = pyglet.text.Label(
            "▶", font_name=_FONT, font_size=36,
            x=_pctx(95, self._width), y=arrow_y,
            color=(255, 255, 255, 200),
            anchor_x="right", anchor_y="center",
        )

        # 标题
        self._title_label = pyglet.text.Label(
            f"{self._view_index + 1} / {len(self._cg_list)}  {cg.get('title', '')}",
            font_name=_FONT, font_size=16,
            x=self._width // 2, y=_pctx(5, self._height),
            color=(220, 220, 220, 255),
            anchor_x="center",
        )

        # 返回提示
        self._back_hint = pyglet.text.Label(
            "ESC / 点击空白返回", font_name=_FONT, font_size=12,
            x=_pctx(95, self._width), y=_pctx(95, self._height),
            color=(150, 150, 150, 255),
            anchor_x="right",
        )

        # 只显示已解锁 CG 的导航
        self._update_full_nav_visibility()

    def _click_full_view(self, x: float, y: float) -> bool:
        """全屏模式点击处理。"""
        # 左箭头区域
        if x < _pctx(10, self._width):
            self._nav_full_view(-1)
            return True
        # 右箭头区域
        if x > _pctx(90, self._width):
            self._nav_full_view(1)
            return True
        # 图片区域外 → 返回网格
        if self._full_sprite is not None:
            s = self._full_sprite
            if not (s.x <= x <= s.x + s.width * s.scale and s.y <= y <= s.y + s.height * s.scale):
                self._exit_full_view()
                return True
        else:
            # 图片加载失败：点击在非箭头区域即返回
            if _pctx(10, self._width) <= x <= _pctx(90, self._width):
                self._exit_full_view()
                return True
        return True

    def _nav_full_view(self, direction: int) -> None:
        """全屏模式下左右翻页（仅已解锁 CG）。"""
        n = len(self._cg_list)
        for _ in range(n):
            self._view_index = (self._view_index + direction) % n
            if self._flags.get(self._cg_list[self._view_index].get("unlock_flag", ""), False):
                break
        self._build_full_view()

    def _update_full_nav_visibility(self) -> None:
        """根据是否有可导航项控制箭头可见性。"""
        unlocked = [
            i for i, cg in enumerate(self._cg_list)
            if self._flags.get(cg.get("unlock_flag", ""), False)
        ]
        has_prev = len(unlocked) > 1
        has_next = len(unlocked) > 1
        if self._arrow_left:
            self._arrow_left.visible = has_prev
        if self._arrow_right:
            self._arrow_right.visible = has_next

    def _cleanup_full_view(self) -> None:
        """清理全屏查看对象。"""
        for obj in (self._full_sprite, self._overlay,
                     self._arrow_left, self._arrow_right,
                     self._title_label, self._back_hint):
            if obj is not None:
                obj.delete()
        self._full_sprite = None
        self._overlay = None
        self._arrow_left = None
        self._arrow_right = None
        self._title_label = None
        self._back_hint = None


# ══════════════════════════════════════════════════════════════
# 音乐欣赏
# ══════════════════════════════════════════════════════════════

class MusicRoom:
    """音乐欣赏 — BGM 列表 + 播放/暂停 + 进度条。

    从 JSON 配置读取曲目列表，根据旗标解锁。
    播放控制通过 AudioManager 实现。
    """

    _ROW_H = 48
    _ENTRY_COLOR = (30, 30, 50)
    _ENTRY_ALPHA = 200
    _HOVER_COLOR = (60, 60, 100)
    _PLAYING_COLOR = (80, 60, 40)

    def __init__(
        self,
        batch: Batch,
        ui_group: Group,
        width: int,
        height: int,
        resource_manager: Any,
        audio_manager: Any,
        flags: dict[str, bool],
        config_path: str,
    ) -> None:
        self._batch = batch
        self._group = ui_group
        self._width = width
        self._height = height
        self._rm = resource_manager
        self._audio = audio_manager
        self._flags = flags
        self._config_path = config_path

        self._tracks: list[dict[str, Any]] = []
        self._row_items: list[dict[str, Any]] = []
        self._scroll_offset: float = 0.0
        self._max_scroll: float = 0.0
        self._hover_index: int = -1
        self._playing_index: int = -1
        self._progress: float = 0.0

        self._back_hint: pyglet.text.Label | None = None

    # ── 生命周期 ──────────────────────────────────────────

    def load_config(self) -> None:
        """从 JSON 加载曲目列表。"""
        try:
            data = json.loads(Path(self._config_path).read_text("utf-8"))
            self._tracks = data.get("tracks", [])
            logger.info("音乐欣赏配置已加载: %d 首", len(self._tracks))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            logger.warning("音乐欣赏配置加载失败: %s", e)
            self._tracks = []

    def show(self) -> None:
        """进入音乐欣赏。"""
        self._build_list()

    def hide(self) -> None:
        """退出音乐欣赏。"""
        self._stop_playback()
        self._cleanup_list()

    def update(self, dt: float) -> None:
        """更新进度条和悬停高亮。"""
        for i, item in enumerate(self._row_items):
            bg = item.get("bg")
            if bg is None:
                continue
            if i == self._playing_index:
                bg.color = self._PLAYING_COLOR
            elif i == self._hover_index:
                bg.color = self._HOVER_COLOR
            else:
                bg.color = self._ENTRY_COLOR
            # 更新进度条
            progress_bar = item.get("progress_bar")
            if progress_bar and i == self._playing_index:
                # 简易进度模拟
                self._progress = (self._progress + dt * 0.02) % 1.0
                max_w = item.get("progress_max_w", 1)
                progress_bar.width = int(max_w * self._progress)

    # ── 输入 ──────────────────────────────────────────────

    def handle_click(self, x: float, y: float) -> bool:
        """处理点击 — 播放/暂停切换。"""
        for i, item in enumerate(self._row_items):
            bg = item.get("bg")
            if bg is None:
                continue
            if bg.x <= x <= bg.x + bg.width and bg.y <= y <= bg.y + bg.height:
                if item.get("unlocked"):
                    self._toggle_play(i)
                return True
        return False

    def handle_scroll(self, dy: float) -> None:
        """滚轮滚动列表。"""
        self._scroll_offset = max(
            0.0, min(self._max_scroll, self._scroll_offset - dy * 40)
        )
        self._apply_scroll()

    def handle_mouse_motion(self, x: float, y: float) -> None:
        """悬停索引。"""
        self._hover_index = -1
        for i, item in enumerate(self._row_items):
            bg = item.get("bg")
            if bg is None:
                continue
            if bg.x <= x <= bg.x + bg.width and bg.y <= y <= bg.y + bg.height:
                self._hover_index = i
                return

    # ── 播放控制 ──────────────────────────────────────────

    def _toggle_play(self, index: int) -> None:
        """播放或暂停指定曲目。"""
        if self._playing_index == index:
            # 暂停当前
            self._audio.stop_bgm(fade_out=0.0)
            self._playing_index = -1
            return

        # 播放新曲目
        self._stop_playback()
        track = self._tracks[index]
        source = self._rm.get_audio(track.get("file", ""))
        if source is not None:
            self._audio.play_bgm(source, volume=0.6, loop=False)
            self._playing_index = index
            self._progress = 0.0

    def _stop_playback(self) -> None:
        """停止播放。"""
        self._audio.stop_bgm(fade_out=0.0)
        self._playing_index = -1
        self._progress = 0.0

    # ── UI 构建 ───────────────────────────────────────────

    def _build_list(self) -> None:
        """构建曲目列表。"""
        self._cleanup_list()

        list_x = _pctx(10, self._width)
        list_w = _pctx(80, self._width)
        y = self._height - _pctx(15, self._height)

        for i, track in enumerate(self._tracks):
            unlocked = self._flags.get(track.get("unlock_flag", ""), False)
            row_y = y - i * (self._ROW_H + 4)

            bg = pyglet.shapes.Rectangle(
                x=list_x, y=row_y, width=list_w, height=self._ROW_H,
                color=self._ENTRY_COLOR,
                batch=self._batch, group=self._group,
            )
            bg.opacity = self._ENTRY_ALPHA

            display_name = track.get("title", "???") if unlocked else "???"
            name_color = (255, 255, 255, 255) if unlocked else (100, 100, 100, 255)
            name_label = pyglet.text.Label(
                display_name, font_name=_FONT, font_size=18,
                x=list_x + 16, y=row_y + self._ROW_H // 2,
                color=name_color,
                anchor_y="center",
                batch=self._batch, group=self._group,
            )

            # 播放/暂停图标
            icon_text = "▶" if unlocked else ""
            icon_label = pyglet.text.Label(
                icon_text, font_name=_FONT, font_size=16,
                x=list_x + list_w - 32, y=row_y + self._ROW_H // 2,
                color=(180, 200, 180, 255),
                anchor_x="right", anchor_y="center",
                batch=self._batch, group=self._group,
            )

            # 进度条（细线，默认隐藏）
            progress_bar = pyglet.shapes.Rectangle(
                x=list_x, y=row_y + 2, width=0, height=3,
                color=(200, 180, 100),
                batch=self._batch, group=self._group,
            )
            progress_bar.visible = False

            self._row_items.append({
                "bg": bg,
                "name_label": name_label,
                "icon_label": icon_label,
                "progress_bar": progress_bar,
                "progress_max_w": list_w,
                "unlocked": unlocked,
                "track": track,
            })

        rows = len(self._tracks)
        total_h = rows * (self._ROW_H + 4)
        visible_h = self._height - _pctx(20, self._height)
        self._max_scroll = max(0.0, total_h - visible_h)

        # 返回提示
        self._back_hint = pyglet.text.Label(
            "ESC 返回", font_name=_FONT, font_size=12,
            x=_pctx(95, self._width), y=_pctx(95, self._height),
            color=(150, 150, 150, 255),
            anchor_x="right",
        )

    def _apply_scroll(self) -> None:
        list_x = _pctx(10, self._width)
        list_w = _pctx(80, self._width)
        y_base = self._height - _pctx(15, self._height)
        for i, item in enumerate(self._row_items):
            row_y = y_base - i * (self._ROW_H + 4) + self._scroll_offset
            bg = item.get("bg")
            if bg:
                bg.x = list_x
                bg.y = row_y
            nl = item.get("name_label")
            if nl:
                nl.x = list_x + 16
                nl.y = row_y + self._ROW_H // 2
            il = item.get("icon_label")
            if il:
                il.x = list_x + list_w - 32
                il.y = row_y + self._ROW_H // 2
            pb = item.get("progress_bar")
            if pb:
                pb.x = list_x
                pb.y = row_y + 2

    def _cleanup_list(self) -> None:
        for item in self._row_items:
            for key in ("bg", "name_label", "icon_label", "progress_bar"):
                obj = item.get(key)
                if obj is not None:
                    obj.delete()
        self._row_items.clear()
        self._scroll_offset = 0.0
        self._hover_index = -1
        if self._back_hint:
            self._back_hint.delete()
            self._back_hint = None


# ══════════════════════════════════════════════════════════════
# 立绘鉴赏（柚子社特色）
# ══════════════════════════════════════════════════════════════

class CharacterViewer:
    """立绘鉴赏 — 自由组合差分部件 + 截图保存。

    从 JSON 配置加载角色及其差分部件列表。
    点击部件区域切换变体，支持拖拽切换和截图。
    """

    _PANEL_COLOR = (20, 20, 40)
    _PANEL_ALPHA = 220
    _BUTTON_COLOR = (60, 60, 80)

    def __init__(
        self,
        batch: Batch,
        ui_group: Group,
        width: int,
        height: int,
        resource_manager: Any,
        config_path: str,
    ) -> None:
        self._batch = batch
        self._group = ui_group
        self._sprite_group: Group = pyglet.graphics.Group(order=3)  # FRONT 层，低于 UI
        self._width = width
        self._height = height
        self._rm = resource_manager
        self._config_path = config_path

        self._characters: dict[str, dict[str, Any]] = {}
        self._current_char: str = ""

        # 部件状态: { "表情": 0, "服装": 0 }  → 当前索引
        self._part_selections: dict[str, int] = {}
        # 当前显示的部件名（只显示一个部件，不叠加）
        self._active_part: str = ""
        # 当前显示的 sprite
        self._current_sprite: pyglet.sprite.Sprite | None = None

        # UI
        self._char_buttons: list[dict[str, Any]] = []
        self._part_buttons: list[dict[str, Any]] = []
        self._screenshot_btn: pyglet.shapes.Rectangle | None = None
        self._screenshot_label: pyglet.text.Label | None = None
        self._back_hint: pyglet.text.Label | None = None
        self._panel_bg: pyglet.shapes.Rectangle | None = None
        self._status_label: pyglet.text.Label | None = None
        self._title_label: pyglet.text.Label | None = None

    # ── 生命周期 ──────────────────────────────────────────

    def load_config(self) -> None:
        """加载角色差分配置。"""
        try:
            data = json.loads(Path(self._config_path).read_text("utf-8"))
            self._characters = data.get("characters", {})
            logger.info("立绘鉴赏配置已加载: %d 个角色", len(self._characters))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            logger.warning("立绘鉴赏配置加载失败: %s", e)
            self._characters = {}

    def show(self) -> None:
        """进入立绘鉴赏。"""
        keys = list(self._characters.keys())
        if keys:
            self._current_char = keys[0]
            self._select_character(self._current_char)
        self._build_ui()
        self._refresh_display()

    def hide(self) -> None:
        """退出立绘鉴赏。"""
        self._cleanup_sprites()
        self._cleanup_ui()

    def update(self, dt: float) -> None:
        """空 —— 纯交互驱动。"""

    # ── 输入 ──────────────────────────────────────────────

    def handle_click(self, x: float, y: float) -> bool:
        """处理点击 — 角色选择 / 部件切换 / 截图。"""
        # 角色按钮
        for btn in self._char_buttons:
            r = btn.get("rect")
            if r and r.x <= x <= r.x + r.width and r.y <= y <= r.y + r.height:
                char_id = btn.get("char_id", "")
                if char_id and char_id != self._current_char:
                    self._current_char = char_id
                    self._select_character(char_id)
                    self._refresh_display()
                return True

        # 部件切换按钮
        for btn in self._part_buttons:
            r = btn.get("rect")
            if r and r.x <= x <= r.x + r.width and r.y <= y <= r.y + r.height:
                part_name = btn.get("part", "")
                self._cycle_part(part_name)
                return True

        # 截图按钮
        if self._screenshot_btn is not None:
            r = self._screenshot_btn
            if r.x <= x <= r.x + r.width and r.y <= y <= r.y + r.height:
                self._take_screenshot()
                return True

        return False

    def handle_mouse_motion(self, x: float, y: float) -> None:
        """空 —— 纯点击交互。"""

    # ── 角色选择 ──────────────────────────────────────────

    def _select_character(self, char_id: str) -> None:
        """切换到指定角色并初始化部件选择。"""
        char_data = self._characters.get(char_id)
        if char_data is None:
            return
        self._part_selections = {}
        parts = char_data.get("parts", {})
        for part_name in parts:
            self._part_selections[part_name] = 0
        # 默认显示第一个部件
        part_names = list(parts.keys())
        self._active_part = part_names[0] if part_names else ""

    def _cycle_part(self, part_name: str) -> None:
        """切换指定部件的变体 (0 → 1 → 2 → ... → 0)。"""
        char_data = self._characters.get(self._current_char)
        if char_data is None:
            return
        parts = char_data.get("parts", {})
        variants = parts.get(part_name, [])
        if not variants:
            return
        current = self._part_selections.get(part_name, 0)
        self._part_selections[part_name] = (current + 1) % len(variants)
        self._active_part = part_name
        self._refresh_part(part_name)

    # ── 显示更新 ──────────────────────────────────────────

    def _refresh_display(self) -> None:
        """显示当前角色的当前部件。只显示一个部件，不叠加。"""
        self._cleanup_sprites()
        char_data = self._characters.get(self._current_char)
        if char_data is None:
            return

        parts = char_data.get("parts", {})
        # 确保 _active_part 有效
        if self._active_part not in parts:
            part_names = list(parts.keys())
            self._active_part = part_names[0] if part_names else ""
            if not self._active_part:
                return

        self._load_sprite(self._active_part, self._part_selections.get(self._active_part, 0))

    def _refresh_part(self, part_name: str) -> None:
        """刷新指定部件的 sprite（切换变体）。"""
        self._cleanup_sprites()
        char_data = self._characters.get(self._current_char)
        if char_data is None:
            return
        idx = self._part_selections.get(part_name, 0)
        self._load_sprite(part_name, idx)

    def _load_sprite(self, part_name: str, variant_idx: int) -> None:
        """加载指定部件的指定变体为当前 sprite。"""
        char_data = self._characters.get(self._current_char)
        if char_data is None:
            return
        parts = char_data.get("parts", {})
        variants = parts.get(part_name, [])
        if variant_idx >= len(variants):
            return

        center_x = self._width // 2
        center_y = self._height // 2
        img_path = variants[variant_idx]
        img = self._rm.get_image(img_path)
        if img is None:
            return

        sprite: pyglet.sprite.Sprite | None = None
        try:
            sprite = pyglet.sprite.Sprite(
                img, x=center_x, y=center_y,
                batch=self._batch, group=self._sprite_group,
            )
            sprite.x = center_x - img.width / 2
            sprite.y = center_y - img.height / 2
        except Exception:
            if sprite is not None:
                try:
                    sprite.delete()
                except Exception:
                    pass
                sprite = None
        self._current_sprite = sprite

    # ── 截图 ──────────────────────────────────────────────

    def _take_screenshot(self) -> None:
        """保存当前组合截图到文件。"""
        try:
            import datetime

            from PIL import Image

            buf = pyglet.image.get_buffer_manager().get_color_buffer()
            raw_data: Any = buf.get_image_data()  # type: ignore[no-untyped-call]
            pitch = raw_data.width * 4
            raw = raw_data.get_data("RGBA", pitch)
            pil_img = Image.frombytes("RGBA", (raw_data.width, raw_data.height), raw)
            pil_img = pil_img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{self._current_char}_{timestamp}.png"
            pil_img.save(filename)
            logger.info("截图已保存: %s", filename)
            if self._status_label:
                self._status_label.text = f"已保存: {filename}"
        except Exception as e:
            logger.error("截图失败: %s", e)
            if self._status_label:
                self._status_label.text = "截图失败"

    # ── UI 构建 ───────────────────────────────────────────

    def _build_ui(self) -> None:
        """构建 UI 面板。"""
        self._cleanup_ui()

        # 左侧面板背景
        panel_w = _pctx(18, self._width)
        self._panel_bg = pyglet.shapes.Rectangle(
            x=0, y=0, width=panel_w, height=self._height,
            color=self._PANEL_COLOR,
            batch=self._batch, group=self._group,
        )
        self._panel_bg.opacity = self._PANEL_ALPHA

        # 标题
        self._title_label = pyglet.text.Label(
            "立绘鉴赏", font_name=_FONT, font_size=20,
            x=panel_w // 2, y=_pctx(95, self._height),
            color=(220, 220, 240, 255),
            anchor_x="center", anchor_y="center",
            batch=self._batch, group=self._group,
        )

        # 角色选择按钮
        btn_x = _pctx(2, self._width)
        btn_y = self._height - _pctx(15, self._height)
        btn_w = _pctx(14, self._width)
        btn_h = 36

        for char_id in self._characters:
            char_data = self._characters.get(char_id, {})
            name = char_data.get("name", char_id)
            selected = char_id == self._current_char
            color = (120, 140, 200) if selected else self._BUTTON_COLOR
            rect = pyglet.shapes.Rectangle(
                x=btn_x, y=btn_y, width=btn_w, height=btn_h,
                color=color,
                batch=self._batch, group=self._group,
            )
            label = pyglet.text.Label(
                name, font_name=_FONT, font_size=14,
                x=btn_x + btn_w // 2, y=btn_y + btn_h // 2,
                color=(255, 255, 255, 255),
                anchor_x="center", anchor_y="center",
                batch=self._batch, group=self._group,
            )
            self._char_buttons.append({
                "rect": rect, "label": label, "char_id": char_id,
            })
            btn_y -= btn_h + 4

        # 部件切换按钮
        part_btn_x = _pctx(2, self._width)
        part_btn_y = btn_y - 20
        char_data = self._characters.get(self._current_char, {})
        parts = char_data.get("parts", {})

        for part_name in parts:
            # 当前变体名称
            idx = self._part_selections.get(part_name, 0)
            variants = parts.get(part_name, [])
            current_variant = variants[idx].split("/")[-1] if idx < len(variants) else "—"
            variant_label = pyglet.text.Label(
                current_variant, font_name=_FONT, font_size=12,
                x=part_btn_x + 8, y=part_btn_y - 5,
                width=btn_w - 16,
                color=(150, 150, 150, 255),
                batch=self._batch, group=self._group,
            )
            # 切换按钮
            cycle_btn = pyglet.shapes.Rectangle(
                x=part_btn_x, y=part_btn_y - 30, width=btn_w, height=24,
                color=self._BUTTON_COLOR,
                batch=self._batch, group=self._group,
            )
            cycle_label = pyglet.text.Label(
                "切换 ▶", font_name=_FONT, font_size=12,
                x=part_btn_x + btn_w // 2, y=part_btn_y - 18,
                color=(255, 255, 255, 255),
                anchor_x="center", anchor_y="center",
                batch=self._batch, group=self._group,
            )
            self._part_buttons.append({
                "rect": cycle_btn, "label": cycle_label,
                "part": part_name, "variant_label": variant_label,
            })
            part_btn_y -= 50

        # 截图按钮
        ss_x = _pctx(2, self._width)
        ss_y = _pctx(5, self._height)
        self._screenshot_btn = pyglet.shapes.Rectangle(
            x=ss_x, y=ss_y, width=btn_w, height=36,
            color=self._BUTTON_COLOR,
            batch=self._batch, group=self._group,
        )
        self._screenshot_label = pyglet.text.Label(
            "截图保存", font_name=_FONT, font_size=14,
            x=ss_x + btn_w // 2, y=ss_y + 18,
            color=(255, 255, 255, 255),
            anchor_x="center", anchor_y="center",
            batch=self._batch, group=self._group,
        )

        # 状态标签
        self._status_label = pyglet.text.Label(
            "", font_name=_FONT, font_size=12,
            x=ss_x + btn_w + 16, y=ss_y + 18,
            width=self._width - ss_x - btn_w - 24,
            color=(180, 180, 180, 255),
            anchor_y="center",
            batch=self._batch, group=self._group,
        )

        # 返回提示
        self._back_hint = pyglet.text.Label(
            "ESC 返回", font_name=_FONT, font_size=12,
            x=_pctx(95, self._width), y=_pctx(95, self._height),
            color=(150, 150, 150, 255),
            anchor_x="right",
        )

    def _cleanup_sprites(self) -> None:
        """清理当前 sprite。"""
        if self._current_sprite is not None:
            try:
                self._current_sprite.delete()
            except Exception:
                pass
            self._current_sprite = None

    def _cleanup_ui(self) -> None:
        """清理所有 UI 对象。"""
        self._cleanup_sprites()
        for btn_list in (self._char_buttons, self._part_buttons):
            for btn in btn_list:
                for key in ("rect", "label", "variant_label", "name_label"):
                    obj = btn.get(key)
                    if obj is not None:
                        obj.delete()
        self._char_buttons.clear()
        self._part_buttons.clear()
        for obj in (self._screenshot_btn, self._screenshot_label,
                     self._back_hint, self._panel_bg, self._status_label,
                     self._title_label):
            if obj is not None:
                obj.delete()
        self._screenshot_btn = None
        self._screenshot_label = None
        self._back_hint = None
        self._panel_bg = None
        self._status_label = None
        self._title_label = None
