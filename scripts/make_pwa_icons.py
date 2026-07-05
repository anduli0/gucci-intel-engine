#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate PWA home-screen icons (Gucci web stripe: green/red/green). Stdlib only."""
import struct
import zlib
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "app" / "ui"
GREEN = (0x17, 0x5E, 0x3D)
RED = (0xA9, 0x16, 0x22)


def stripe_color(y, size):
    third = size / 3.0
    return RED if third <= y < 2 * third else GREEN


def make_png(size, path):
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter: none
        r, g, b = stripe_color(y, size)
        raw.extend(bytes((r, g, b, 255)) * size)

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    path.write_bytes(png)
    print(f"{path.name}: {size}x{size}, {len(png)} bytes")


for s, name in ((180, "icon-180.png"), (192, "icon-192.png"), (512, "icon-512.png")):
    make_png(s, UI / name)
