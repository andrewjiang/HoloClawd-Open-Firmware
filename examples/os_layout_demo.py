#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "pillow"]
# ///
"""
OS layout demo for HoloCube.

Demonstrates the 3-region template:
- status bar (icons/state)
- body (app content)
- footer (mascot)

Usage:
    uv run --script os_layout_demo.py --ip 192.168.7.80
"""

import argparse
import time

from holocube_client import HoloCube, Color, Layout, draw_lobster

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ICONS_DIR = os.path.join(REPO_ROOT, "assets", "icons")

POTION_ICON = os.path.join(ICONS_DIR, "kyrise_16x16_rpg", "Kyrise's 16x16 RPG Icon Pack - V1.3", "icons", "16x16", "potion_03b.png")
SWORD_ICON = os.path.join(ICONS_DIR, "kyrise_16x16_rpg", "Kyrise's 16x16 RPG Icon Pack - V1.3", "icons", "16x16", "sword_02c.png")
BOOK_ICON = os.path.join(ICONS_DIR, "kyrise_16x16_rpg", "Kyrise's 16x16 RPG Icon Pack - V1.3", "icons", "16x16", "book_05g.png")
CANDY_ICON = os.path.join(ICONS_DIR, "kyrise_16x16_rpg", "Kyrise's 16x16 RPG Icon Pack - V1.3", "icons", "16x16", "candy_02g.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="HoloCube OS layout demo")
    parser.add_argument("--ip", default="192.168.7.80", help="HoloCube IP address")
    args = parser.parse_args()

    cube = HoloCube(args.ip, timeout=15.0)
    layout = Layout(screen_w=cube.SCREEN_WIDTH, screen_h=cube.SCREEN_HEIGHT)

    # Draw static UI shell once
    cube.clear(Color.BLACK)
    cube.draw_tracker_bar(
        layout,
        water=3,
        exercise=15,
        focus=2,
        supplements_done=False,
        water_icon_path=POTION_ICON,
        exercise_icon_path=SWORD_ICON,
        focus_icon_path=BOOK_ICON,
        supplements_icon_path=CANDY_ICON,
    )

    mx, my = layout.mascot_anchor()
    draw_lobster(cube, mx, my, happy=False, frame=0)

    # Update only the dynamic body region
    for i in range(10, -1, -1):
        cube.show_timer(i, color=Color.CYAN, bg=Color.BLACK, clear_screen=False, y=layout.timer_y(size=5))
        time.sleep(1)

    cube.draw_tracker_bar(
        layout,
        water=4,
        exercise=20,
        focus=3,
        supplements_done=True,
        water_icon_path=POTION_ICON,
        exercise_icon_path=SWORD_ICON,
        focus_icon_path=BOOK_ICON,
        supplements_icon_path=CANDY_ICON,
    )
    draw_lobster(cube, mx, my, happy=True, frame=0)


if __name__ == "__main__":
    main()

