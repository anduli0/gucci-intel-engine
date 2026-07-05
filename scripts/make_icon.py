#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate app/gucci.ico (32x32, Gucci web-stripe: green/red/green). Stdlib only."""
import struct
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "gucci.ico"
SIZE = 32
GREEN = (0x17, 0x5E, 0x3D)
RED = (0xA9, 0x16, 0x22)


def row_color(y):
    # y in image coordinates (0 = top)
    if y < 11 or y >= 21:
        return GREEN
    return RED


def main():
    # BMP pixel data is bottom-up, BGRA
    xor = bytearray()
    for y in range(SIZE - 1, -1, -1):
        r, g, b = row_color(y)
        # subtle gold border, 1px
        for x in range(SIZE):
            if x == 0 or x == SIZE - 1 or y == 0 or y == SIZE - 1:
                xor += bytes((0x4B, 0xA2, 0xC9, 0xFF))  # gold BGRA
            else:
                xor += bytes((b, g, r, 0xFF))
    and_mask = bytes(SIZE * 4)  # 32 rows x 4 bytes, all opaque

    bih = struct.pack("<IiiHHIIiiII", 40, SIZE, SIZE * 2, 1, 32, 0,
                      len(xor) + len(and_mask), 0, 0, 0, 0)
    image = bih + bytes(xor) + and_mask
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", SIZE, SIZE, 0, 0, 1, 32, len(image), 22)
    OUT.write_bytes(header + entry + image)
    print(f"icon written: {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
