"""
矢量图绘制模块
==============
提供基于 dict / JSON / SVG 的矢量图形定义与 Canvas 绘制。

用法::

    # 定义矢量图
    char_def = {
        "width": 170, "height": 400,
        "shapes": [
            {"type": "rect", "x": 20, "y": 100, "w": 130, "h": 280, "fill": "#8E44AD"},
            {"type": "circle", "cx": 85, "cy": 70, "r": 40, "fill": "#8E44AD"},
            {"type": "text", "x": 85, "y": 28, "text": "???",
             "fill": "#fff", "font": ("微软雅黑", 14, "bold")},
        ],
    }

    # 注册
    from gal_lib.vectorgraphics import register
    register("my_char", char_def)

    # 在 engine 中：渲染器会优先使用注册的矢量图
"""

import importlib.resources
import json
import math
import re
import tkinter as tk
from typing import Any, Optional


# ========================================================================
#  注册表
# ========================================================================

_VECTOR_REGISTRY: dict[str, dict] = {}

# 图片缓存，防止 tk.PhotoImage 被垃圾回收
_image_refs: list[tk.PhotoImage] = []


def register(sprite_id: str, definition: dict) -> None:
    """注册一个矢量图定义，sprite_id 与占位符 ID 共用命名空间。"""
    _VECTOR_REGISTRY[sprite_id] = definition


def register_from_json(sprite_id: str, filepath: str) -> None:
    """从 JSON 文件加载并注册矢量图。"""
    with open(filepath, "r", encoding="utf-8") as f:
        register(sprite_id, json.load(f))


def register_from_svg(sprite_id: str, filepath: str) -> None:
    """从 SVG 文件加载并注册矢量图。"""
    with open(filepath, "r", encoding="utf-8") as f:
        svg_def = parse_svg(f.read())
        register(sprite_id, svg_def)


def get_definition(sprite_id: str) -> Optional[dict]:
    """获取已注册的矢量图定义。"""
    return _VECTOR_REGISTRY.get(sprite_id)


def has_definition(sprite_id: str) -> bool:
    """检查是否存在对应的矢量图注册。"""
    return sprite_id in _VECTOR_REGISTRY


def list_definitions() -> list[str]:
    """列出所有已注册的 sprite ID。"""
    return list(_VECTOR_REGISTRY.keys())


# ========================================================================
#  资源加载（importlib.resources）
# ========================================================================

def register_from_resource(sprite_id: str, package: str, resource_name: str) -> None:
    """从包资源（JSON 文件）注册矢量图定义。

    Args:
        sprite_id: 精灵 ID（与占位符共用命名空间）。
        package: 包名（如 ``"my_game.resources.vectors"``）。
        resource_name: JSON 文件名（如 ``"protagonist.json"``）。
    """
    text = importlib.resources.files(package).joinpath(resource_name).read_text(encoding="utf-8")
    definition = json.loads(text)
    register(sprite_id, definition)


def load_all_vectors_from_package(package: str) -> list[str]:
    """扫描指定包目录下的所有 ``.json`` 文件，自动注册为矢量图。

    文件名（不含 ``.json``）直接作为 sprite_id 使用。

    Args:
        package: 包名（如 ``"my_game.resources.vectors"``）。

    Returns:
        成功注册的 sprite ID 列表。
    """
    registered: list[str] = []
    pkg = importlib.resources.files(package)
    if not pkg.is_dir():
        return registered
    for entry in sorted(pkg.iterdir(), key=lambda e: e.name):
        if entry.suffix.lower() == ".json":
            sid = entry.stem
            try:
                definition = json.loads(entry.read_text(encoding="utf-8"))
                register(sid, definition)
                registered.append(sid)
            except json.JSONDecodeError:
                continue
    return registered


def register_from_base64(sprite_id: str, b64_data: str,
                         width: int = 170, height: int = 400) -> None:
    """注册 base64 编码的 PNG 图片为精灵。

    ``b64_data`` 可以直接嵌入在 JSON 矢量定义中，实现自包含的图片资源。

    Args:
        sprite_id: 精灵 ID。
        b64_data: PNG 文件的 base64 编码字符串。
        width: 视口设计宽度。
        height: 视口设计高度。
    """
    register(sprite_id, {
        "width": width, "height": height,
        "shapes": [
            {"type": "image", "data": b64_data,
             "x": 0, "y": 0, "w": width, "h": height},
        ],
    })


def register_png(sprite_id: str, package: str, resource_path: str,
                 width: int = 170, height: int = 400) -> None:
    """注册 PNG 图片为精灵（立绘／背景）。

    图片在首次渲染时加载——需要 tkinter 主循环已启动（``root.mainloop`` 之前
    调用 ``root.update()`` 亦可）。注册本身不创建 ``PhotoImage``。

    Args:
        sprite_id: 精灵 ID。
        package: 包名（如 ``"my_game.resources.images"``）。
        resource_path: 资源相对路径（如 ``"protagonist.png"``）。
        width: 视口设计宽度（默认 170）。
        height: 视口设计高度（默认 400）。
    """
    register(sprite_id, {
        "width": width, "height": height,
        "shapes": [
            {"type": "image", "_src_pkg": package, "_src_path": resource_path,
             "x": 0, "y": 0, "w": width, "h": height},
        ],
    })


def load_all_images_from_package(package: str,
                                 width: int = 170, height: int = 400) -> list[str]:
    """扫描包目录下的所有 ``.png`` 文件，自动注册为精灵。

    文件名（不含 ``.png``）直接作为 sprite_id。

    Args:
        package: 包名（如 ``"my_game.resources.images"``）。
        width: 视口设计宽度。
        height: 视口设计高度。

    Returns:
        成功注册的 sprite ID 列表。
    """
    registered: list[str] = []
    pkg = importlib.resources.files(package)
    if not pkg.is_dir():
        return registered
    for entry in sorted(pkg.iterdir(), key=lambda e: e.name):
        if entry.suffix.lower() == ".png":
            sid = entry.stem
            register_png(sid, package, entry.name, width, height)
            registered.append(sid)
    return registered


# ========================================================================
#  矢量图绘制（核心）
# ========================================================================

def render(canvas: tk.Canvas, definition: dict,
           dest_x: int, dest_y: int, *,
           width: Optional[int] = None,
           height: Optional[int] = None,
           anchor: str = "s",
           tags: str = "") -> list[int]:
    """在 Canvas 上绘制矢量图。

    Args:
        canvas: 目标 Canvas 控件。
        definition: 矢量图定义 dict。
        dest_x, dest_y: 绘制位置的坐标。
        width, height: 输出尺寸（默认使用定义中的设计尺寸）。
        anchor: 对齐方式，同 tkinter 锚点。
                "s" = 底部居中（角色），"nw" = 左上角对齐（背景）。
        tags: 附加的 Canvas tag。

    Returns:
        所有绘制项的 Canvas 对象 ID 列表。
    """
    vw = definition.get("width", 170)
    vh = definition.get("height", 400)

    ow = width or vw
    oh = height or vh
    sx = ow / vw if vw else 1.0
    sy = oh / vh if vh else 1.0

    # 根据 anchor 计算视图左上角在屏幕上的坐标
    if anchor == "s":
        ox = dest_x - ow / 2
        oy = dest_y - oh
    elif anchor == "center":
        ox = dest_x - ow / 2
        oy = dest_y - oh / 2
    else:  # "nw" 或其他
        ox = dest_x
        oy = dest_y

    shapes = definition.get("shapes", [])
    items: list[int] = []

    for shape in shapes:
        item = _draw_shape(canvas, shape, ox, oy, sx, sy, tags)
        if item is not None:
            items.append(item)

    return items


def _draw_shape(canvas: tk.Canvas, shape: dict,
                ox: int, oy: int, sx: float, sy: float,
                tags: str) -> Optional[int]:
    """绘制单个形状，返回 Canvas 对象 ID。"""
    stype = shape["type"]
    tag = tags or shape.get("tags", "")
    kw = {}
    if tag:
        kw["tags"] = tag

    # 公共样式
    fill = shape.get("fill", "")
    outline = shape.get("outline", "")
    stroke_width = shape.get("width", shape.get("stroke_width", 1))
    stipple = shape.get("stipple", "")

    if stype == "rect":
        return canvas.create_rectangle(
            ox + shape["x"] * sx,
            oy + shape["y"] * sy,
            ox + (shape["x"] + shape["w"]) * sx,
            oy + (shape["y"] + shape["h"]) * sy,
            fill=fill, outline=outline, width=stroke_width,
            stipple=stipple, **kw,
        )

    elif stype == "circle":
        r = shape["r"] * sx
        cx = ox + shape["cx"] * sx
        cy = oy + shape["cy"] * sy
        return canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill=fill, outline=outline, width=stroke_width,
            stipple=stipple, **kw,
        )

    elif stype == "oval":
        return canvas.create_oval(
            ox + shape["x"] * sx,
            oy + shape["y"] * sy,
            ox + (shape["x"] + shape["w"]) * sx,
            oy + (shape["y"] + shape["h"]) * sy,
            fill=fill, outline=outline, width=stroke_width,
            stipple=stipple, **kw,
        )

    elif stype == "polygon":
        pts = shape["points"]
        coords = []
        for i in range(0, len(pts), 2):
            coords.append(ox + pts[i] * sx)
            coords.append(oy + pts[i + 1] * sy)
        return canvas.create_polygon(
            *coords, fill=fill, outline=outline, width=stroke_width,
            stipple=stipple, smooth=shape.get("smooth", False), **kw,
        )

    elif stype == "line":
        pts = shape["points"]
        coords = []
        for i in range(0, len(pts), 2):
            coords.append(ox + pts[i] * sx)
            coords.append(oy + pts[i + 1] * sy)
        return canvas.create_line(
            *coords, fill=outline or fill, width=stroke_width,
            stipple=stipple, smooth=shape.get("smooth", False), **kw,
        )

    elif stype == "text":
        font = shape.get("font", ("微软雅黑", 12))
        return canvas.create_text(
            ox + shape["x"] * sx,
            oy + shape["y"] * sy,
            text=shape["text"],
            fill=fill or outline,
            font=font,
            anchor=shape.get("anchor", "center"),
            angle=shape.get("angle", 0),
            **kw,
        )

    elif stype == "image":
        return _draw_image(canvas, shape, ox, oy, sx, sy, **kw)

    return None


def _draw_image(canvas: tk.Canvas, shape: dict,
                ox: int, oy: int, sx: float, sy: float,
                **kw) -> Optional[int]:
    """绘制 PNG 图片（支持文件路径与 base64 嵌入）。"""
    src = shape.get("src", "")
    pkg = shape.get("_src_pkg", "")
    path = shape.get("_src_path", "")
    data = shape.get("data", "")

    photo: Optional[tk.PhotoImage] = None

    # ── 1) 从文件路径加载（"package:path" 或绝对路径） ─────────
    if src:
        try:
            if ":" in src:
                pkg_name, rel_path = src.split(":", 1)
                full_path = str(importlib.resources.files(pkg_name).joinpath(rel_path))
            else:
                full_path = src
            photo = _cached_photo(full_path)
        except Exception:
            return None

    # ── 2) 从包资源（register_png 注册） ───────────────────────
    elif pkg and path:
        cache_key = f"{pkg}:{path}"
        try:
            full_path = str(importlib.resources.files(pkg).joinpath(path))
            photo = _cached_photo(full_path, cache_key)
        except Exception:
            return None

    # ── 3) base64 嵌入数据 ─────────────────────────────────────
    elif data:
        cache_key = f"__b64__{hash(data)}"
        try:
            photo = _cached_photo_b64(data, cache_key)
        except Exception:
            return None

    if photo is None:
        return None

    # 图片位置（左上角对齐）
    ix = ox + shape.get("x", 0) * sx
    iy = oy + shape.get("y", 0) * sy

    # 整数缩放（zoom / subsample），近似匹配目标尺寸
    target_w = shape.get("w", 0)
    target_h = shape.get("h", 0)
    if target_w and target_h and sx > 0 and sy > 0:
        iw, ih = photo.width(), photo.height()
        if iw and ih:
            need_w = target_w * sx
            need_h = target_h * sy
            scale_x = need_w / iw
            scale_y = need_h / ih
            if scale_x >= 1 and scale_y >= 1:
                zx = max(1, int(scale_x))
                zy = max(1, int(scale_y))
                if zx > 1 or zy > 1:
                    scaled = photo.zoom(zx, zy)
                    _image_refs.append(scaled)
                    photo = scaled
            elif scale_x < 1 and scale_y < 1:
                sx_int = max(1, int(1 / scale_x)) if scale_x > 0 else 1
                sy_int = max(1, int(1 / scale_y)) if scale_y > 0 else 1
                if sx_int > 1 or sy_int > 1:
                    scaled = photo.subsample(sx_int, sy_int)
                    _image_refs.append(scaled)
                    photo = scaled

    return canvas.create_image(ix, iy, image=photo, anchor="nw", **kw)


def _cached_photo(filepath: str, cache_key: Optional[str] = None) -> tk.PhotoImage:
    """从文件加载 PhotoImage 并缓存，防止 GC。"""
    key = cache_key or filepath
    for ref in _image_refs:
        if hasattr(ref, "_cache_key") and ref._cache_key == key:
            return ref
    photo = tk.PhotoImage(file=filepath)
    photo._cache_key = key
    _image_refs.append(photo)
    return photo


def _cached_photo_b64(data: str, cache_key: str) -> tk.PhotoImage:
    """从 base64 数据创建 PhotoImage 并缓存，防止 GC。"""
    for ref in _image_refs:
        if getattr(ref, "_cache_key", None) == cache_key:
            return ref
    photo = tk.PhotoImage(data=data)
    photo._cache_key = cache_key
    _image_refs.append(photo)
    return photo


# ========================================================================
#  便捷构建函数
# ========================================================================

def group(*shapes: dict) -> dict:
    """辅助函数：将多个形状合并为一个组（直接展开）。

    用法::

        sprite = group(
            {"type": "rect", "x": 0, "y": 0, "w": 100, "h": 200, "fill": "red"},
            {"type": "circle", "cx": 50, "cy": 30, "r": 20, "fill": "blue"},
        )
    """
    result: dict[str, Any] = {"width": 170, "height": 400, "shapes": []}
    for s in shapes:
        if isinstance(s, dict) and "shapes" in s:
            result["shapes"].extend(s["shapes"])
        elif isinstance(s, dict):
            result["shapes"].append(s)
    return result


def make_shape(type_: str, **kwargs) -> dict:
    """创建单个形状 dict。"""
    shape: dict = {"type": type_}
    shape.update(kwargs)
    return shape


# ========================================================================
#  简单 SVG 解析（基本形状子集）
# ========================================================================

def parse_svg(svg_text: str) -> dict:
    """将简单的 SVG 文本解析为矢量图定义 dict。

    支持的 SVG 元素: svg, g, rect, circle, ellipse, polygon, polyline, line, text
    支持的属性: fill, stroke, stroke-width, transform="translate(x,y)"
    不支持的: <path>, CSS 样式, 渐变, 滤镜

    Args:
        svg_text: SVG XML 文本。

    Returns:
        与 dict 格式兼容的矢量图定义。
    """
    result: dict[str, Any] = {"shapes": []}

    # 提取 viewBox / width / height
    svg_match = re.search(r'<svg[^>]*>', svg_text, re.DOTALL)
    if svg_match:
        svg_tag = svg_match.group()
        wm = re.search(r'width="([^"]*)"', svg_tag)
        hm = re.search(r'height="([^"]*)"', svg_tag)
        vm = re.search(r'viewBox="([^"]*)"', svg_tag)
        if vm:
            parts = vm.group(1).split()
            if len(parts) == 4:
                result["width"] = _parse_svg_len(parts[2])
                result["height"] = _parse_svg_len(parts[3])
        else:
            if wm:
                result["width"] = _parse_svg_len(wm.group(1))
            if hm:
                result["height"] = _parse_svg_len(hm.group(1))

    # 递归解析元素
    for shape in _svg_parse_elements(svg_text):
        result["shapes"].append(shape)

    return result


# SVG 通用匹配器：<tag ...>...</tag> 或 <tag .../>
_SVG_TAG_RE = re.compile(
    r'<(\w+)([^>]*?)(?:>(.*?)</\1>|\s*/>)', re.DOTALL,
)


def _svg_parse_elements(xml_text: str, tx: float = 0, ty: float = 0):
    """递归解析 SVG 元素，支持 transform 传递。"""
    for m in _SVG_TAG_RE.finditer(xml_text):
        tag = m.group(1).lower()
        attr_str = m.group(2)
        inner = m.group(3)

        attrs = _parse_attrs(attr_str)

        # 计算局部变换偏移
        local_x, local_y = tx, ty
        if "transform" in attrs:
            tm = re.match(
                r'translate\s*\(\s*([\d.-]+)\s*,?\s*([\d.-]*)\s*\)',
                attrs["transform"],
            )
            if tm:
                local_x += float(tm.group(1))
                local_y += float(tm.group(2)) if tm.group(2) else 0

        # svg / g → 递归解析子元素
        if tag in ("svg", "g") and inner:
            yield from _svg_parse_elements(inner, local_x, local_y)
            continue

        if tag not in ("rect", "circle", "ellipse", "polygon",
                       "polyline", "line", "text"):
            continue

        shape: dict = {"type": _svg_tag_to_type(tag)}
        fill = attrs.get("fill", "")
        stroke = attrs.get("stroke", "")
        sw = attrs.get("stroke-width", "")

        if fill and fill != "none":
            shape["fill"] = fill
        if stroke and stroke != "none":
            shape["outline"] = stroke
        if sw:
            shape["width"] = _parse_svg_len(sw)

        if tag == "rect":
            shape["x"] = _parse_svg_len(attrs.get("x", "0")) + local_x
            shape["y"] = _parse_svg_len(attrs.get("y", "0")) + local_y
            shape["w"] = _parse_svg_len(attrs.get("width", "0"))
            shape["h"] = _parse_svg_len(attrs.get("height", "0"))

        elif tag == "circle":
            shape["cx"] = _parse_svg_len(attrs.get("cx", "0")) + local_x
            shape["cy"] = _parse_svg_len(attrs.get("cy", "0")) + local_y
            shape["r"] = _parse_svg_len(attrs.get("r", "0"))

        elif tag in ("ellipse", "oval"):
            cx = _parse_svg_len(attrs.get("cx", "0")) + local_x
            cy = _parse_svg_len(attrs.get("cy", "0")) + local_y
            rx = _parse_svg_len(attrs.get("rx", "0"))
            ry = _parse_svg_len(attrs.get("ry", "0"))
            shape["x"] = cx - rx
            shape["y"] = cy - ry
            shape["w"] = rx * 2
            shape["h"] = ry * 2

        elif tag in ("polygon", "polyline"):
            pts = [float(n) for n in re.findall(r'[\d.-]+',
                                                 attrs.get("points", ""))]
            if tag == "polyline" and len(pts) >= 4:
                shape["type"] = "line"
            shape["points"] = pts
            if local_x or local_y:
                for i in range(0, len(pts), 2):
                    shape["points"][i] += local_x
                    shape["points"][i + 1] += local_y

        elif tag == "line":
            shape["points"] = [
                _parse_svg_len(attrs.get("x1", "0")) + local_x,
                _parse_svg_len(attrs.get("y1", "0")) + local_y,
                _parse_svg_len(attrs.get("x2", "0")) + local_x,
                _parse_svg_len(attrs.get("y2", "0")) + local_y,
            ]

        elif tag == "text":
            shape["x"] = _parse_svg_len(attrs.get("x", "0")) + local_x
            shape["y"] = _parse_svg_len(attrs.get("y", "0")) + local_y
            shape["text"] = (inner or "").strip()
            fs = attrs.get("font-size", "14")
            shape["font"] = ("微软雅黑", _parse_svg_len(fs))
            shape["anchor"] = attrs.get("text-anchor", "start")

        if "fill" not in shape and "outline" not in shape:
            shape["fill"] = ""

        yield shape


def _parse_svg_len(val: str) -> float:
    """解析 SVG 长度值（去掉单位后缀）。"""
    return float(re.sub(r'[^0-9.\-]', '', val))


def _svg_tag_to_type(tag: str) -> str:
    mapping = {
        "rect": "rect", "circle": "circle", "ellipse": "oval",
        "polygon": "polygon", "polyline": "line", "line": "line",
        "text": "text",
    }
    return mapping.get(tag, "rect")


def _iter_svg_elements(svg_text: str):
    """迭代 SVG 中的所有基本元素，使用单次扫描避免重复。"""
    # 匹配两种形式：<tag>content</tag> 或 <tag .../>
    combined = re.compile(
        r'<(\w+)([^>]*?)(?:>(.*?)</\1>|\s*/>)',
        re.DOTALL,
    )
    for m in combined.finditer(svg_text):
        tag = m.group(1).lower()
        attr_str = m.group(2)
        inner = m.group(3)  # None 或空字符串表示自闭合

        attrs = _parse_attrs(attr_str)

        if tag in ("svg", "g"):
            if inner:
                yield from _iter_svg_elements(inner)
            continue

        if tag not in ("rect", "circle", "ellipse", "polygon", "polyline", "line", "text"):
            continue

        yield tag, attrs, (inner or "")


def _parse_attrs(attr_str: str) -> dict[str, str]:
    """解析 SVG 属性字符串为 dict。"""
    attrs: dict[str, str] = {}
    for m in re.finditer(r'(\w[\w-]*)\s*=\s*"([^"]*)"', attr_str):
        attrs[m.group(1)] = m.group(2)
    return attrs


# ========================================================================
#  内置占位角色矢量图定义（替换 renderer.py 的几何图形）
# ========================================================================

_DEMO_CHARACTERS: dict[str, dict] = {
    "__demo_char_mystery__": {
        "width": 170, "height": 400,
        "shapes": [
            # 披风身体
            {"type": "polygon", "points": [15, 0, 155, 0, 140, 280, 120, 340, 50, 340, 30, 280],
             "fill": "#8E44AD"},
            # 头部
            {"type": "circle", "cx": 85, "cy": 40, "r": 38, "fill": "#8E44AD"},
            # 兜帽阴影
            {"type": "oval", "x": 55, "y": 25, "w": 60, "h": 30,
             "fill": "#6C3483"},
            # 眼睛（两个白点）
            {"type": "circle", "cx": 73, "cy": 36, "r": 4, "fill": "#ecf0f1"},
            {"type": "circle", "cx": 97, "cy": 36, "r": 4, "fill": "#ecf0f1"},
            # 名字
            {"type": "text", "x": 85, "y": 388, "text": "???",
             "fill": "#ecf0f1", "font": ("微软雅黑", 14, "bold")},
        ],
    },
    "__demo_char_girl__": {
        "width": 170, "height": 400,
        "shapes": [
            # 裙子身体
            {"type": "polygon", "points": [30, 0, 140, 0, 155, 160, 155, 280, 115, 340, 55, 340, 15, 280, 15, 160],
             "fill": "#E91E63"},
            # 上半身
            {"type": "rect", "x": 35, "y": 100, "w": 100, "h": 80, "fill": "#C2185B"},
            # 头部
            {"type": "circle", "cx": 85, "cy": 42, "r": 38, "fill": "#E91E63"},
            # 头发
            {"type": "oval", "x": 48, "y": 10, "w": 74, "h": 45, "fill": "#AD1457"},
            # 眼睛
            {"type": "circle", "cx": 73, "cy": 38, "r": 5, "fill": "#ecf0f1"},
            {"type": "circle", "cx": 97, "cy": 38, "r": 5, "fill": "#ecf0f1"},
            # 嘴巴
            {"type": "line", "points": [78, 52, 92, 52],
             "fill": "#ecf0f1", "width": 2},
            # 名字
            {"type": "text", "x": 85, "y": 388, "text": "星野",
             "fill": "#ecf0f1", "font": ("微软雅黑", 14, "bold")},
        ],
    },
    "__demo_char_hero__": {
        "width": 170, "height": 400,
        "shapes": [
            # 外套（宽肩）
            {"type": "polygon", "points": [15, 0, 155, 0, 160, 120, 155, 300, 120, 340, 50, 340, 15, 300, 10, 120],
             "fill": "#3498DB"},
            # 内衬
            {"type": "rect", "x": 40, "y": 100, "w": 90, "h": 100, "fill": "#2980B9"},
            # 头部
            {"type": "circle", "cx": 85, "cy": 40, "r": 38, "fill": "#3498DB"},
            # 头发
            {"type": "oval", "x": 50, "y": 8, "w": 70, "h": 40, "fill": "#1F618D"},
            # 眼睛
            {"type": "circle", "cx": 73, "cy": 36, "r": 4, "fill": "#ecf0f1"},
            {"type": "circle", "cx": 97, "cy": 36, "r": 4, "fill": "#ecf0f1"},
            # 嘴巴（微笑）
            {"type": "line", "points": [78, 50, 85, 55, 92, 50],
             "fill": "#ecf0f1", "smooth": True, "width": 2},
            # 名字
            {"type": "text", "x": 85, "y": 388, "text": "主角",
             "fill": "#ecf0f1", "font": ("微软雅黑", 14, "bold")},
        ],
    },
}


_DEMO_BACKGROUNDS: dict[str, dict] = {
    "__demo_bg_room__": {
        "width": 160, "height": 100,
        "shapes": [
            {"type": "rect", "x": 0, "y": 0, "w": 160, "h": 100, "fill": "#2C3E50"},
            # 窗户
            {"type": "rect", "x": 20, "y": 20, "w": 30, "h": 40, "fill": "#1A252F",
             "outline": "#5D6D7E", "width": 2},
            # 窗框十字
            {"type": "line", "points": [35, 20, 35, 60, 20, 40, 50, 40],
             "fill": "#5D6D7E", "width": 1},
            # 桌子
            {"type": "rect", "x": 80, "y": 55, "w": 60, "h": 8, "fill": "#5D4037"},
            {"type": "rect", "x": 85, "y": 63, "w": 6, "h": 37, "fill": "#5D4037"},
            {"type": "rect", "x": 129, "y": 63, "w": 6, "h": 37, "fill": "#5D4037"},
            # 烛光
            {"type": "circle", "cx": 110, "cy": 48, "r": 6, "fill": "#F39C12"},
            {"type": "circle", "cx": 110, "cy": 48, "r": 10, "fill": "#F39C12",
             "stipple": "gray25"},
            # 文字
            {"type": "text", "x": 8, "y": 8, "text": "昏暗的房间",
             "fill": "#ecf0f1", "font": ("微软雅黑", 10), "anchor": "w"},
        ],
    },
    "__demo_bg_valley__": {
        "width": 160, "height": 100,
        "shapes": [
            {"type": "rect", "x": 0, "y": 0, "w": 160, "h": 100, "fill": "#1E8449"},
            # 天空渐变（近似）
            {"type": "rect", "x": 0, "y": 0, "w": 160, "h": 40, "fill": "#1A5276"},
            # 山脉
            {"type": "polygon", "points": [0, 40, 30, 15, 60, 35, 90, 10, 120, 30, 160, 20, 160, 40],
             "fill": "#154360"},
            # 远山
            {"type": "polygon", "points": [0, 45, 40, 30, 70, 42, 110, 28, 140, 38, 160, 32, 160, 50],
             "fill": "#1A5276"},
            # 星尘光点
            {"type": "circle", "cx": 30, "cy": 18, "r": 1.5, "fill": "#F1C40F"},
            {"type": "circle", "cx": 70, "cy": 12, "r": 1, "fill": "#F1C40F"},
            {"type": "circle", "cx": 100, "cy": 22, "r": 1.5, "fill": "#F1C40F"},
            {"type": "circle", "cx": 130, "cy": 14, "r": 1, "fill": "#F1C40F"},
            {"type": "circle", "cx": 50, "cy": 8, "r": 1, "fill": "#F1C40F"},
            # 地面
            {"type": "rect", "x": 0, "y": 50, "w": 160, "h": 50, "fill": "#1E8449"},
            # 文字
            {"type": "text", "x": 8, "y": 8, "text": "星落之谷",
             "fill": "#ecf0f1", "font": ("微软雅黑", 10), "anchor": "w"},
        ],
    },
}


def register_defaults() -> None:
    """注册内置的矢量图占位角色和背景。"""
    for sid, defn in _DEMO_CHARACTERS.items():
        if sid not in _VECTOR_REGISTRY:
            register(sid, defn)
    for sid, defn in _DEMO_BACKGROUNDS.items():
        if sid not in _VECTOR_REGISTRY:
            register(sid, defn)
