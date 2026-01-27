#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "pillow"]
# ///
"""
Render a 4x4 grid (16 icons) from a 16x16 icon pack zip.

This uses the HoloCube draw batch API and compresses pixels into horizontal runs
to keep requests reasonably small.

Example (zip):
    uv run --script examples/icon_pack_demo.py \
      --ip 192.168.7.80 \
      --zip "/Users/andrewjiang/Downloads/Kyrises_16x16_RPG_Icon_Pack_V1.3.zip" \
      --scale 2

Example (directory):
    uv run --script examples/icon_pack_demo.py \
      --ip 192.168.7.80 \
      --dir "assets/icons/free_pixel_food_16x16" \
      --scale 3
"""

from __future__ import annotations

import argparse
import io
import time
import os
import zipfile
from dataclasses import dataclass

from PIL import Image

from holocube_client import Color, HoloCube


@dataclass(frozen=True)
class GridSpec:
    cols: int = 4
    rows: int = 4
    icon_size: int = 16
    scale: int = 2
    gap: int = 8
    margin: int = 8

    def cell(self) -> int:
        return self.icon_size * self.scale + self.gap

    def grid_w(self) -> int:
        return self.cols * (self.icon_size * self.scale) + (self.cols - 1) * self.gap

    def grid_h(self) -> int:
        return self.rows * (self.icon_size * self.scale) + (self.rows - 1) * self.gap


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def iter_runs_row(img: Image.Image, y: int):
    """
    Yield (x0, x1_exclusive, hex_color) for non-transparent runs on row y.
    """
    w, _ = img.size
    px = img.load()
    run_color = None
    run_start = 0

    def flush(x: int):
        nonlocal run_color, run_start
        if run_color is not None:
            yield (run_start, x, run_color)
            run_color = None

    for x in range(w):
        r, g, b, a = px[x, y]
        if a == 0:
            yield from flush(x)
            continue
        c = rgb_to_hex((r, g, b))
        if run_color is None:
            run_color = c
            run_start = x
        elif c != run_color:
            yield from flush(x)
            run_color = c
            run_start = x

    yield from flush(w)


def load_first_16_icons(zip_path: str) -> list[tuple[str, Image.Image]]:
    """
    Load first 16 16x16 PNGs from Kyrise's pack (or any zip with 16x16 pngs).
    """
    out: list[tuple[str, Image.Image]] = []
    with zipfile.ZipFile(zip_path) as z:
        # prefer 16x16 folder if present
        names = [n for n in z.namelist() if n.lower().endswith(".png") and "/16x16/" in n.replace("\\", "/")]
        if not names:
            names = [n for n in z.namelist() if n.lower().endswith(".png")]
        names.sort()

        for n in names:
            if len(out) >= 16:
                break
            data = z.read(n)
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            if img.size != (16, 16):
                continue
            out.append((n.split("/")[-1], img))

    return out


def load_first_16_icons_from_dir(dir_path: str) -> list[tuple[str, Image.Image]]:
    out: list[tuple[str, Image.Image]] = []
    files: list[str] = []
    for root, _dirs, fn in os.walk(dir_path):
        for f in fn:
            if f.lower().endswith(".png"):
                files.append(os.path.join(root, f))
    files.sort()

    for p in files:
        if len(out) >= 16:
            break
        img = Image.open(p).convert("RGBA")
        if img.size != (16, 16):
            continue
        out.append((os.path.basename(p), img))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="HoloCube 16x16 icon pack demo")
    parser.add_argument("--ip", default="192.168.7.80", help="HoloCube IP address")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--zip", help="Path to a 16x16 icon pack zip")
    src.add_argument("--dir", help="Path to a directory containing 16x16 PNG icons")
    parser.add_argument("--scale", type=int, default=2, help="Scale factor for icons (1-4 recommended)")
    parser.add_argument("--bg", default=Color.BLACK, help="Background color")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout seconds")
    args = parser.parse_args()

    cube = HoloCube(args.ip, timeout=args.timeout)
    if args.zip:
        icons = load_first_16_icons(args.zip)
    else:
        icons = load_first_16_icons_from_dir(args.dir)
    if len(icons) < 16:
        raise SystemExit(f"Need 16 icons; found {len(icons)} 16x16 PNGs in source")

    spec = GridSpec(scale=max(1, min(4, args.scale)))

    # Center the grid
    x0 = (cube.SCREEN_WIDTH - spec.grid_w()) // 2
    y0 = (cube.SCREEN_HEIGHT - spec.grid_h()) // 2

    # Clear once (keep subsequent batches small)
    resp = cube.clear(args.bg)
    print("clear:", resp)

    def send_batch(cmds: list[dict]) -> None:
        if not cmds:
            return
        r = cube.batch(cmds)
        print(f"batch: commands={len(cmds)} resp={r}")
        time.sleep(0.05)

    commands: list[dict] = []
    # Keep JSON small for ESP8266 (large batches can exceed request/JSON limits)
    max_commands_per_batch = 60

    # Render icons as run-length rectangles
    for idx, (_name, img) in enumerate(icons[:16]):
        col = idx % spec.cols
        row = idx // spec.cols
        ox = x0 + col * (spec.icon_size * spec.scale + spec.gap)
        oy = y0 + row * (spec.icon_size * spec.scale + spec.gap)

        for py in range(16):
            for (rx0, rx1, color) in iter_runs_row(img, py):
                w = (rx1 - rx0) * spec.scale
                if w <= 0:
                    continue
                commands.append(
                    {
                        "type": "rect",
                        "x": ox + rx0 * spec.scale,
                        "y": oy + py * spec.scale,
                        "w": w,
                        "h": spec.scale,
                        "color": color,
                        "fill": True,
                    }
                )
                if len(commands) >= max_commands_per_batch:
                    send_batch(commands)
                    commands = []

    send_batch(commands)


if __name__ == "__main__":
    main()

