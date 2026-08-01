#!/usr/bin/env python
"""يرسم أيقونات المنصة PNG من هندسة الشعار المعتمد (2026-08-01).

**لماذا رسمٌ لا تحويل:** لا محوِّل SVG في البيئة، والشكل هندسيٌّ محض —
مربعان متقاطعان (نجمة ثمانية)، ومصحفٌ مفتوح، وجذورٌ متفرعة. فيُرسم
بالإحداثيات نفسها التي في `apps/web/app/icon.svg` حرفًا بحرف، ويُرسم
بأربعة أضعاف المقاس ثم يُصغَّر — فتنعم الحواف بلا مكتبة تنعيم.

**والأصل هو SVG:** هذه مشتقاتٌ منه للتثبيت (PWA وiOS). فإن تغيّر الشعار
غُيِّر في `icon.svg` أولًا ثم أُعيد تشغيل هذا.

التشغيل:
    python scripts/brand/render_icons.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "apps" / "web" / "public"

# ألوان الهوية — تطابق رموز globals.css
GREEN = (13, 92, 70)
GOLD = (217, 184, 114)
GOLD_DEEP = (180, 138, 60)
PAGE = (247, 245, 239)
BG = (247, 245, 239)

SS = 4  # التنعيم: يُرسم بأربعة أضعاف ثم يُصغَّر


def _rotate(point: tuple[float, float], angle: float) -> tuple[float, float]:
    """يدوّر نقطةً حول مركز اللوحة (256، 256)."""
    x, y = point[0] - 256, point[1] - 256
    cos, sin = math.cos(angle), math.sin(angle)
    return (x * cos - y * sin + 256, x * sin + y * cos + 256)


def _bezier(p0, p1, p2, p3, steps: int = 24) -> list[tuple[float, float]]:
    """منحنى بيزيه تكعيبي — أقواسُ المصحف والجذور في الشعار بيزيهات."""
    points = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def draw_icon(size: int, pad_ratio: float = 0.0, background=BG) -> Image.Image:
    canvas = size * SS
    image = Image.new("RGB", (canvas, canvas), background)
    draw = ImageDraw.Draw(image)

    inset = canvas * pad_ratio
    scale = (canvas - 2 * inset) / 512

    def pt(point: tuple[float, float]) -> tuple[float, float]:
        return (inset + point[0] * scale, inset + point[1] * scale)

    def w(value: float) -> int:
        return max(1, round(value * scale))

    square = [(106, 106), (406, 106), (406, 406), (106, 406)]
    diamond = [_rotate(p, math.pi / 4) for p in square]

    # النجمة الثمانية: مربعان متقاطعان بحدٍّ ذهبي
    for shape in (square, diamond):
        draw.polygon([pt(p) for p in shape], fill=GREEN)
    for shape in (square, diamond):
        draw.line([pt(p) for p in shape] + [pt(shape[0])], fill=GOLD, width=w(13))

    # المصحف المفتوح: صفحتان يفصلهما ثنيٌ في الوسط
    left = (
        _bezier((256, 188), (232, 172), (206, 166), (176, 166))
        + [(176, 248)]
        + _bezier((176, 248), (206, 248), (232, 254), (256, 270))
    )
    right = (
        _bezier((256, 188), (280, 172), (306, 166), (336, 166))
        + [(336, 248)]
        + _bezier((336, 248), (306, 248), (280, 254), (256, 270))
    )
    for page in (left, right):
        draw.polygon([pt(p) for p in page], fill=PAGE)
    draw.line([pt(p) for p in left], fill=GOLD, width=w(9), joint="curve")
    draw.line([pt(p) for p in right], fill=GOLD, width=w(9), joint="curve")
    draw.line([pt((256, 188)), pt((256, 270))], fill=GOLD_DEEP, width=w(6))

    # الجذور: أصلٌ واحد وستة فروع — الإحداثيات نفسها التي في icon.svg
    draw.line([pt((256, 270)), pt((256, 300))], fill=GOLD, width=w(10))
    draw.line([pt((256, 300)), pt((256, 386))], fill=GOLD, width=w(7))
    branches = [
        ((256, 318), (206, 322), (176, 344)),
        ((256, 318), (306, 322), (336, 344)),
        ((256, 324), (214, 344), (198, 376)),
        ((256, 324), (298, 344), (314, 376)),
        ((256, 330), (242, 356), (236, 392)),
        ((256, 330), (270, 356), (276, 392)),
    ]
    for control_a, control_b, end in branches:
        curve = _bezier((256, 300), control_a, control_b, end)
        draw.line([pt(p) for p in curve], fill=GOLD, width=w(7), joint="curve")

    return image.resize((size, size), Image.LANCZOS)


def main() -> int:
    targets = [
        ("icon-192.png", 192, 0.0),
        ("icon-512.png", 512, 0.0),
        # القناع يُقتطع دائريًا في أندرويد، فيُترك هامشٌ آمن
        ("icon-maskable-512.png", 512, 0.14),
        ("apple-touch-icon.png", 180, 0.06),
    ]
    for name, size, pad in targets:
        path = OUT / name
        draw_icon(size, pad).save(path, "PNG", optimize=True)
        print(f"كُتب {name}: {size}×{size} ({path.stat().st_size:,} بايت)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
