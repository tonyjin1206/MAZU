#!/usr/bin/env python3
"""生成 MTS 桌面应用图标：以 VI 设计 LOGO-dark.svg 为源，产出 icon.png / icon.icns / icon.ico

用法: cd electron && ../backend/venv/bin/python make_icons.py
依赖: Pillow (backend venv)；qlmanage + iconutil (macOS 自带)
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SVG = HERE.parent / "docs" / "vi-design" / "LOGO-dark.svg"
SIZE = 1024
# LOGO-dark.svg viewBox 923x923，圆角半径 153.84 → 比例
RADIUS_RATIO = 153.837 / 923


def render_svg() -> Image.Image:
    """qlmanage 把 SVG 渲染成 1024px PNG"""
    out = subprocess.run(
        ["qlmanage", "-t", "-s", str(SIZE), "-o", str(HERE), str(SVG)],
        check=True, capture_output=True,
    )
    rendered = HERE / f"{SVG.name}.png"
    img = Image.open(rendered).convert("RGBA")
    rendered.unlink()
    if img.size != (SIZE, SIZE):
        img = img.resize((SIZE, SIZE), Image.LANCZOS)
    return img


def round_corners(img: Image.Image) -> Image.Image:
    """SVG 白底矩形的四角转透明（圆角半径与源 SVG 一致）"""
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    r = int(img.size[0] * RADIUS_RATIO)
    d.rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1], radius=r, fill=255)
    img.putalpha(mask)
    return img


def main():
    img = round_corners(render_svg())

    png = HERE / "icon.png"
    img.save(png)
    print(f"✅ {png}")

    ico = HERE / "icon.ico"
    img.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"✅ {ico}")

    iconset = HERE / "icon.iconset"
    iconset.mkdir(exist_ok=True)
    for s in (16, 32, 64, 128, 256, 512, 1024):
        img.resize((s, s), Image.LANCZOS).save(iconset / f"icon_{s}x{s}.png")
        if s <= 512:
            img.resize((s * 2, s * 2), Image.LANCZOS).save(iconset / f"icon_{s}x{s}@2x.png")
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "icon.icns")],
        check=True,
    )
    for f in iconset.glob("*.png"):
        f.unlink()
    iconset.rmdir()
    print(f"✅ {HERE / 'icon.icns'}")


if __name__ == "__main__":
    main()
