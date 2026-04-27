#!/usr/bin/env python3
"""诊断脚本：检查素材注册和加载是否正常。"""
import sys, os, json, tkinter as tk

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

print("=" * 50)
print("【1】检查 PNG 文件是否存在")
print("=" * 50)
from pathlib import Path
img_dir = Path(_root) / "my_game" / "resources" / "images"
for f in sorted(img_dir.glob("*.png")):
    size = f.stat().st_size
    print(f"  [OK] {f.name} ({size/1024:.0f} KB)")

print()
print("=" * 50)
print("【2】检查注册是否生效")
print("=" * 50)
from my_game import constants as _
from gal_lib.vectorgraphics import _VECTOR_REGISTRY, list_definitions
all_ids = list_definitions()
for sid in sorted(all_ids):
    if "春日野穹" in sid or "家-" in sid:
        print(f"  [OK] {sid}")
    elif sid.startswith("__my_"):
        pass  # 旧项目素材
print(f"  注册总数: {len(all_ids)}")

print()
print("=" * 50)
print("【3】检查 PNG 在 tkinter 中能否加载")
print("=" * 50)

root = tk.Tk()
root.withdraw()  # 隐藏窗口
errors = []
from gal_lib.vectorgraphics import _draw_shape, _cached_photo
import importlib.resources

for sid in ["家-卧室", "家-客厅", "家-门口",
            "春日野穹-哥特服装-S", "春日野穹-哥特服装-M", "春日野穹-哥特服装-L"]:
    vdef = _VECTOR_REGISTRY.get(sid)
    if not vdef:
        print(f"  [FAIL] {sid} 未注册")
        continue
    shape = vdef["shapes"][0]  # 第一个 shape 是 image
    pkg = shape.get("_src_pkg", "")
    path = shape.get("_src_path", "")
    try:
        full_path = str(importlib.resources.files(pkg).joinpath(path))
        photo = tk.PhotoImage(file=full_path)
        w, h = photo.width(), photo.height()
        print(f"  [OK] {sid} → {w}x{h} px ({full_path})")
    except Exception as e:
        print(f"  [FAIL] {sid} → {e}")
        errors.append(sid)

print()
if errors:
    print(f"[WARN] {len(errors)} 个图片加载失败，将使用几何占位符显示")
else:
    print("[OK] 所有图片加载正常")

root.destroy()
print()
print("=" * 50)
print("【4】检查 JSON 剧本格式")
print("=" * 50)
with open(os.path.join(_root, "my_game", "harukanaru_sora.json"), "r", encoding="utf-8") as f:
    script = json.load(f)
print(f"  标题: {script['title']}")
print(f"  场景数: {len(script['scenes'])}")
for s in script['scenes']:
    print(f"  [{s['id']}] bg={s['background']}, 对白={len(s['dialogue'])}句, "
          f"选项={'有' if 'choices' in s else '无'}")
print("[OK] 剧本格式正确")
print()
print("诊断完成，请将以上输出贴给开发者。")
