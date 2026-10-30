#!/usr/bin/env python3
"""Generate the shared Bench Notes icon set with the standard library only.

Output (assets/icons): icon.png (512), 32x32.png, 128x128.png, 128x128@2x.png,
icon.icns (PNG-compressed icns), icon.ico (PNG-compressed ico).
The generated files are committed; re-run only if the design changes.
"""
import struct
import sys
import zlib
from pathlib import Path

BG = (37, 99, 235, 255)      # blue
PAPER = (255, 255, 255, 255)
LINE = (148, 163, 184, 255)


def render(size):
    """Rounded blue square with a white 'page' and three grey text lines."""
    px = bytearray(size * size * 4)
    r_out = size * 0.22

    def inside_round(x, y, x0, y0, x1, y1, r):
        if x < x0 or x >= x1 or y < y0 or y >= y1:
            return False
        cx = min(max(x, x0 + r), x1 - r)
        cy = min(max(y, y0 + r), y1 - r)
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r

    s = size
    for y in range(size):
        for x in range(size):
            color = (0, 0, 0, 0)
            if inside_round(x + 0.5, y + 0.5, 0, 0, s, s, r_out):
                color = BG
                if inside_round(x + 0.5, y + 0.5, s * 0.24, s * 0.18, s * 0.76, s * 0.82, s * 0.05):
                    color = PAPER
                    for i in range(3):
                        ly = s * (0.34 + i * 0.14)
                        if s * 0.32 <= x < s * 0.68 and ly <= y < ly + s * 0.045:
                            color = LINE
            i = (y * size + x) * 4
            px[i:i + 4] = bytes(color)
    return bytes(px)


def png(size):
    raw = render(size)
    rows = b"".join(b"\x00" + raw[y * size * 4:(y + 1) * size * 4] for y in range(size))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9))
            + chunk(b"IEND", b""))


def icns(pngs):
    # ic07=128, ic08=256, ic09=512 (PNG payloads)
    parts = b""
    for tag, size in ((b"ic07", 128), (b"ic08", 256), (b"ic09", 512)):
        parts += tag + struct.pack(">I", 8 + len(pngs[size])) + pngs[size]
    return b"icns" + struct.pack(">I", 8 + len(parts)) + parts


def ico(pngs, sizes=(16, 32, 48, 64, 128, 256)):
    head = struct.pack("<HHH", 0, 1, len(sizes))
    entries, blobs, offset = b"", b"", 6 + 16 * len(sizes)
    for s in sizes:
        data = pngs[s]
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return head + entries + blobs


def main():
    out = Path(__file__).resolve().parent.parent / "assets" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    sizes = {16, 32, 48, 64, 128, 256, 512}
    pngs = {s: png(s) for s in sorted(sizes)}
    (out / "icon.png").write_bytes(pngs[512])
    (out / "32x32.png").write_bytes(pngs[32])
    (out / "128x128.png").write_bytes(pngs[128])
    (out / "128x128@2x.png").write_bytes(pngs[256])
    (out / "icon.icns").write_bytes(icns(pngs))
    (out / "icon.ico").write_bytes(ico(pngs))
    print("wrote icons to", out)


if __name__ == "__main__":
    sys.exit(main())
