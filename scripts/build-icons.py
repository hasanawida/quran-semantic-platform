"""توليد أيقونات PNG لتطبيق الهاتف من شعار المنصة، بلا أي تبعية خارجية.

iOS يتجاهل أيقونات SVG في البيان (manifest) ويستعمل apple-touch-icon بصيغة
PNG، ولذلك تُبنى الأيقونات هنا بدل الاعتماد على SVG وحده.

الرسم متجهي مبسّط (مستطيل مستدير + كتاب + نقطة) يُرسم في مخزن بكسلات
بتنعيم حواف (4×4 supersampling)، ثم يُكتب ملف PNG يدويًا بـ zlib.
المخرجات حتمية: نفس المدخلات تعطي نفس البايتات.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "apps" / "web" / "public"

BRAND = (0x1D, 0x5C, 0x42)
INK = (0xFA, 0xF9, 0xF5)
SS = 4  # معامل التنعيم


def _rounded_rect(x: float, y: float, w: float, h: float, r: float):
    def inside(px: float, py: float) -> bool:
        if not (x <= px <= x + w and y <= py <= y + h):
            return False
        for cx, cy in (
            (x + r, y + r),
            (x + w - r, y + r),
            (x + r, y + h - r),
            (x + w - r, y + h - r),
        ):
            if (px < x + r or px > x + w - r) and (py < y + r or py > y + h - r):
                if (px - cx) ** 2 + (py - cy) ** 2 > r * r:
                    continue
                return True
        if (x + r <= px <= x + w - r) or (y + r <= py <= y + h - r):
            return True
        return False

    return inside


def _stroke_rect(x: float, y: float, w: float, h: float, t: float):
    def inside(px: float, py: float) -> bool:
        outer = x <= px <= x + w and y <= py <= y + h
        inner = x + t <= px <= x + w - t and y + t <= py <= y + h - t
        return outer and not inner

    return inside


def _disc(cx: float, cy: float, r: float):
    def inside(px: float, py: float) -> bool:
        return (px - cx) ** 2 + (py - cy) ** 2 <= r * r

    return inside


def _hline(x0: float, x1: float, y: float, t: float):
    def inside(px: float, py: float) -> bool:
        return x0 <= px <= x1 and y - t / 2 <= py <= y + t / 2

    return inside


def render(size: int, *, maskable: bool = False) -> bytes:
    """يعيد بكسلات RGBA للأيقونة بالحجم المطلوب."""
    # الشكل مرسوم على شبكة 64×64 ثم يُقاس
    scale = size / 64
    pad = 8 if maskable else 0  # هامش أمان لقصّ الأنظمة للأيقونة القابلة للقناع
    inner = 64 - 2 * pad

    def to_grid(px: float, py: float) -> tuple[float, float]:
        return (px / scale, py / scale)

    corner = 64 if maskable else 14
    bg = _rounded_rect(0, 0, 64, 64, corner / 2 if maskable else corner)
    book = _stroke_rect(
        pad + inner * 0.22,
        pad + inner * 0.16,
        inner * 0.56,
        inner * 0.62,
        max(1.6, inner * 0.055),
    )
    spine = _hline(
        pad + inner * 0.22,
        pad + inner * 0.78,
        pad + inner * 0.86,
        max(1.6, inner * 0.055),
    )
    dot = _disc(pad + inner * 0.5, pad + inner * 0.44, inner * 0.055)

    pixels = bytearray()
    for y in range(size):
        row = bytearray()
        for x in range(size):
            r_acc = g_acc = b_acc = a_acc = 0
            for sy in range(SS):
                for sx in range(SS):
                    gx, gy = to_grid(x + (sx + 0.5) / SS, y + (sy + 0.5) / SS)
                    if not bg(gx, gy):
                        continue
                    color = BRAND
                    if book(gx, gy) or spine(gx, gy) or dot(gx, gy):
                        color = INK
                    r_acc += color[0]
                    g_acc += color[1]
                    b_acc += color[2]
                    a_acc += 255
            samples = SS * SS
            if a_acc == 0:
                row += bytes((0, 0, 0, 0))
            else:
                covered = a_acc // 255
                row += bytes(
                    (
                        r_acc // covered,
                        g_acc // covered,
                        b_acc // covered,
                        a_acc // samples,
                    )
                )
        pixels += b"\x00" + row  # مرشّح السطر: None
    return bytes(pixels)


def write_png(path: Path, size: int, raw: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


TARGETS = [
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-maskable-512.png", 512, True),
    ("apple-touch-icon.png", 180, False),
]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, size, maskable in TARGETS:
        write_png(OUT_DIR / name, size, render(size, maskable=maskable))
        print(f"  {name}: {(OUT_DIR / name).stat().st_size:,} بايت")
    print("تم توليد الأيقونات في", OUT_DIR)


if __name__ == "__main__":
    main()
