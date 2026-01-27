#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "pillow"]
# ///
"""
HoloCube Client Library - Control your HoloCube display programmatically

Example usage:
    from holocube_client import HoloCube

    cube = HoloCube("192.168.7.80")
    cube.clear("#000000")
    cube.text(60, 100, "Hello!", size=4, color="#00ffff")
    cube.circle(120, 120, 50, color="#ff0000", fill=True)

This module also includes a lightweight "OS template" layout helper (`Layout`) that
splits the 240x240 screen into:
- a top status bar (icons/states)
- a middle app body
- a bottom footer region (mascot/creature)
"""

import requests
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class Color:
    """Common colors for convenience"""
    BLACK = "#000000"
    WHITE = "#ffffff"
    RED = "#ff0000"
    GREEN = "#00ff00"
    BLUE = "#0000ff"
    CYAN = "#00ffff"
    MAGENTA = "#ff00ff"
    YELLOW = "#ffff00"
    ORANGE = "#ff6600"
    PURPLE = "#9900ff"


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Layout:
    """
    Simple 3-region UI layout for HoloCube (240x240 by default).

    Designed for constrained hardware: keep static areas stable and update only
    dynamic regions (text/progress) with small redraws.
    """

    screen_w: int = 240
    screen_h: int = 240
    padding: int = 10
    gap: int = 6
    status_h: int = 64
    footer_h: int = 70

    def status_rect(self) -> Rect:
        return Rect(0, 0, self.screen_w, min(self.status_h, self.screen_h))

    def footer_rect(self) -> Rect:
        h = min(self.footer_h, self.screen_h)
        return Rect(0, self.screen_h - h, self.screen_w, h)

    def body_rect(self) -> Rect:
        top = min(self.status_h, self.screen_h)
        bottom_h = min(self.footer_h, self.screen_h)
        h = max(0, self.screen_h - top - bottom_h)
        return Rect(0, top, self.screen_w, h)

    def status_text_y(self, size: int = 1) -> int:
        bar = self.status_rect()
        char_h = 8 * size
        return bar.y + max(0, (bar.h - char_h) // 2)

    def mascot_anchor(self) -> tuple[int, int]:
        """
        Anchor point for mascot drawing. For the lobster, this maps well to the
        existing art scale.
        """
        footer = self.footer_rect()
        return (self.screen_w // 2, footer.y + 20)

    def timer_y(self, size: int = 5) -> int:
        """Top y for a big timer string, vertically centered in the body."""
        body = self.body_rect()
        char_h = 8 * size
        return body.y + max(0, (body.h - char_h) // 2)


class HoloCube:
    """Client for controlling HoloCube display"""

    SCREEN_WIDTH = 240
    SCREEN_HEIGHT = 240
    CHAR_WIDTH = 6  # Base character width in pixels
    CHAR_HEIGHT = 8  # Base character height in pixels

    def __init__(self, ip: str = "192.168.7.80", timeout: float = 5.0):
        self.base_url = f"http://{ip}"
        self.timeout = timeout

    def _post(self, endpoint: str, data: dict) -> dict:
        """Make POST request to API"""
        try:
            resp = requests.post(
                f"{self.base_url}{endpoint}",
                json=data,
                timeout=self.timeout
            )
            return resp.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}

    def _get(self, endpoint: str) -> dict:
        """Make GET request to API"""
        try:
            resp = requests.get(f"{self.base_url}{endpoint}", timeout=self.timeout)
            return resp.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}

    def batch(self, commands: list[dict]) -> dict:
        """Send multiple draw commands in one request (reduces HTTP overhead)."""
        return self._post("/api/v1/draw/batch", {"commands": commands})

    # =========================================================================
    # Low-level drawing primitives
    # =========================================================================

    def clear(self, color: str = Color.BLACK) -> dict:
        """Clear screen with a color"""
        return self._post("/api/v1/draw/clear", {"color": color})

    def pixel(self, x: int, y: int, color: str = Color.WHITE) -> dict:
        """Draw a single pixel"""
        return self._post("/api/v1/draw/pixel", {"x": x, "y": y, "color": color})

    def line(self, x0: int, y0: int, x1: int, y1: int, color: str = Color.WHITE) -> dict:
        """Draw a line"""
        return self._post("/api/v1/draw/line", {
            "x0": x0, "y0": y0, "x1": x1, "y1": y1, "color": color
        })

    def rect(self, x: int, y: int, w: int, h: int,
             color: str = Color.WHITE, fill: bool = True) -> dict:
        """Draw a rectangle"""
        return self._post("/api/v1/draw/rect", {
            "x": x, "y": y, "w": w, "h": h, "color": color, "fill": fill
        })

    def circle(self, x: int, y: int, r: int,
               color: str = Color.WHITE, fill: bool = True) -> dict:
        """Draw a circle"""
        return self._post("/api/v1/draw/circle", {
            "x": x, "y": y, "r": r, "color": color, "fill": fill
        })

    def triangle(self, x0: int, y0: int, x1: int, y1: int, x2: int, y2: int,
                 color: str = Color.WHITE, fill: bool = True) -> dict:
        """Draw a triangle with three vertices"""
        return self._post("/api/v1/draw/triangle", {
            "x0": x0, "y0": y0, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "color": color, "fill": fill
        })

    def ellipse(self, x: int, y: int, rx: int, ry: int,
                color: str = Color.WHITE, fill: bool = True) -> dict:
        """Draw an ellipse with center (x,y) and radii rx, ry"""
        return self._post("/api/v1/draw/ellipse", {
            "x": x, "y": y, "rx": rx, "ry": ry, "color": color, "fill": fill
        })

    def roundrect(self, x: int, y: int, w: int, h: int, r: int,
                  color: str = Color.WHITE, fill: bool = True) -> dict:
        """Draw a rounded rectangle"""
        return self._post("/api/v1/draw/roundrect", {
            "x": x, "y": y, "w": w, "h": h, "r": r, "color": color, "fill": fill
        })

    def text(self, x: int, y: int, text: str,
             size: int = 2, color: str = Color.WHITE, bg: str = None,
             clear_bg: bool = False) -> dict:
        """Draw text at position. If bg is set, text overwrites old content."""
        data = {"x": x, "y": y, "text": text, "size": size, "color": color}
        if bg:
            data["bg"] = bg
            data["clear"] = clear_bg  # Clear background rect before drawing
        return self._post("/api/v1/draw/text", data)

    # =========================================================================
    # Helper methods
    # =========================================================================

    def text_width(self, text: str, size: int = 2) -> int:
        """Calculate pixel width of text"""
        return len(text) * self.CHAR_WIDTH * size

    def text_height(self, size: int = 2) -> int:
        """Calculate pixel height of text"""
        return self.CHAR_HEIGHT * size

    def center_x(self, text: str, size: int = 2) -> int:
        """Calculate x position to center text horizontally"""
        return (self.SCREEN_WIDTH - self.text_width(text, size)) // 2

    def center_y(self, size: int = 2) -> int:
        """Calculate y position to center text vertically"""
        return (self.SCREEN_HEIGHT - self.text_height(size)) // 2

    def centered_text(self, y: int, text: str,
                      size: int = 2, color: str = Color.WHITE) -> dict:
        """Draw horizontally centered text"""
        x = self.center_x(text, size)
        return self.text(x, y, text, size, color)

    # =========================================================================
    # High-level display functions
    # =========================================================================

    def show_message(self, lines: list[str], colors: list[str] = None,
                     size: int = 3, bg: str = Color.BLACK) -> None:
        """Display multiple lines of centered text"""
        self.clear(bg)

        if colors is None:
            colors = [Color.WHITE] * len(lines)

        line_height = self.text_height(size) + 10
        total_height = line_height * len(lines)
        start_y = (self.SCREEN_HEIGHT - total_height) // 2

        for i, line in enumerate(lines):
            y = start_y + i * line_height
            self.centered_text(y, line, size, colors[i] if i < len(colors) else Color.WHITE)

    def show_big_number(self, number: str, label: str = None,
                        color: str = Color.WHITE, bg: str = Color.BLACK) -> None:
        """Display a large number with optional label"""
        self.clear(bg)
        self.centered_text(80, number, size=5, color=color)
        if label:
            self.centered_text(180, label, size=2, color=Color.WHITE)

    def show_progress(self, progress: float, label: str = None,
                      fg: str = Color.GREEN, bg: str = Color.BLACK) -> None:
        """Display a progress bar (0.0 to 1.0)"""
        self.clear(bg)

        bar_width = 200
        bar_height = 30
        bar_x = (self.SCREEN_WIDTH - bar_width) // 2
        bar_y = 100

        # Background bar
        self.rect(bar_x, bar_y, bar_width, bar_height, color="#333333", fill=True)

        # Progress fill
        fill_width = int(bar_width * min(1.0, max(0.0, progress)))
        if fill_width > 0:
            self.rect(bar_x, bar_y, fill_width, bar_height, color=fg, fill=True)

        # Border
        self.rect(bar_x, bar_y, bar_width, bar_height, color=Color.WHITE, fill=False)

        # Percentage text
        pct_text = f"{int(progress * 100)}"
        self.centered_text(bar_y + bar_height + 20, pct_text, size=3, color=Color.WHITE)

        if label:
            self.centered_text(60, label, size=2, color=Color.WHITE)

    def alert(self, message: str, color: str = Color.RED) -> None:
        """Flash an alert message"""
        self.clear(color)
        time.sleep(0.1)
        self.show_message([message], colors=[Color.WHITE], size=3, bg=color)

    # =========================================================================
    # Timer/Clock helpers
    # =========================================================================

    def format_time(self, seconds: int) -> str:
        """Format seconds as MM:SS or HH:MM:SS"""
        if seconds >= 3600:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h}:{m:02d}:{s:02d}"
        else:
            m = seconds // 60
            s = seconds % 60
            return f"{m:02d}:{s:02d}"

    def show_timer(self, seconds: int, label: str = None,
                   color: str = Color.CYAN, bg: str = Color.BLACK,
                   clear_screen: bool = False, y: Optional[int] = None, size: int = 5) -> None:
        """Display a timer value. Set clear_screen=True only on first call."""
        time_str = self.format_time(seconds)
        if clear_screen:
            self.clear(bg)
            if label:
                self.centered_text(40, label, size=2, color=Color.WHITE)
        # Draw time with background color to overwrite previous text (clear_bg ensures clean overwrite)
        draw_y = 90 if y is None else y
        self.text(self.center_x(time_str, size), draw_y, time_str, size=size, color=color, bg=bg, clear_bg=True)

    # =========================================================================
    # OS-template helpers (status bar / body / footer)
    # =========================================================================

    def draw_status_bar(
        self,
        layout: Layout,
        left_text: str = "",
        right_text: str = "",
        *,
        wifi_connected: bool = True,
        wifi_bars: int = 4,
        battery_pct: int = 100,
        charging: bool = False,
        fg: str = Color.WHITE,
        bg: str = Color.BLACK,
        clear_bg: bool = True,
    ) -> dict:
        """
        Draw a lightweight status bar with simple WiFi+battery icons.

        This intentionally redraws just the bar region (small) instead of the full screen.
        """
        bar = layout.status_rect()
        y_text = layout.status_text_y(size=1)

        # Right-side icons: wifi (14x10) + gap + battery (20x10)
        icon_h = 10
        icon_y = bar.y + max(0, (bar.h - icon_h) // 2)
        pad = layout.padding
        wifi_w = 14
        batt_w = 20
        icons_w = wifi_w + layout.gap + batt_w

        commands: list[dict] = []
        if clear_bg:
            commands.append({"type": "rect", "x": bar.x, "y": bar.y, "w": bar.w, "h": bar.h, "color": bg, "fill": True})

        # Separator line at bottom of status bar (subtle)
        commands.append({"type": "rect", "x": bar.x, "y": bar.y + bar.h - 1, "w": bar.w, "h": 1, "color": "#333333", "fill": True})

        # Battery icon
        x_right = bar.x + bar.w - pad
        batt_x0 = x_right - batt_w
        body_w = 16
        body_h = 10
        nub_w = 3
        nub_h = 4
        nub_x = batt_x0 + body_w
        nub_y = icon_y + (icon_h - nub_h) // 2

        commands.append({"type": "rect", "x": batt_x0, "y": icon_y, "w": body_w, "h": body_h, "color": fg, "fill": False})
        commands.append({"type": "rect", "x": nub_x, "y": nub_y, "w": nub_w, "h": nub_h, "color": fg, "fill": True})
        p = max(0, min(100, int(battery_pct)))
        fill_w = (body_w - 2) * p // 100
        if fill_w > 0:
            commands.append({"type": "rect", "x": batt_x0 + 1, "y": icon_y + 1, "w": fill_w, "h": body_h - 2, "color": fg, "fill": True})
        if charging:
            cx = batt_x0 + body_w // 2
            cy = icon_y + body_h // 2
            commands.append({"type": "line", "x0": cx - 2, "y0": cy - 3, "x1": cx, "y1": cy, "color": bg})
            commands.append({"type": "line", "x0": cx, "y0": cy, "x1": cx - 1, "y1": cy + 3, "color": bg})
            commands.append({"type": "line", "x0": cx + 2, "y0": cy - 3, "x1": cx, "y1": cy, "color": bg})

        # WiFi icon
        x_right = batt_x0 - layout.gap
        wifi_x0 = x_right - wifi_w
        commands.append({"type": "rect", "x": wifi_x0, "y": icon_y, "w": wifi_w, "h": icon_h, "color": bg, "fill": True})
        if not wifi_connected:
            commands.append({"type": "rect", "x": wifi_x0, "y": icon_y, "w": wifi_w, "h": icon_h, "color": "#777777", "fill": False})
        bars = max(0, min(4, int(wifi_bars)))
        for i in range(4):
            bw = 2
            gap = 1
            bx = wifi_x0 + 1 + i * (bw + gap)
            bh = 2 + i * 2
            by = icon_y + icon_h - bh
            on = fg if (wifi_connected and i < bars) else "#777777"
            commands.append({"type": "rect", "x": bx, "y": by, "w": bw, "h": bh, "color": on, "fill": True})

        # Right text (left of icons)
        if right_text:
            tw = self.text_width(right_text, size=1)
            tx = bar.x + bar.w - pad - icons_w - layout.gap - tw
            commands.append({"type": "text", "x": tx, "y": y_text, "text": right_text, "size": 1, "color": fg, "bg": bg})

        # Left text
        if left_text:
            commands.append({"type": "text", "x": bar.x + pad, "y": y_text, "text": left_text, "size": 1, "color": fg, "bg": bg})

        return self.batch(commands)

    def draw_tracker_bar(
        self,
        layout: Layout,
        *,
        water: int,
        exercise: int,
        focus: int,
        supplements_done: bool,
        water_icon_path: str,
        exercise_icon_path: str,
        focus_icon_path: str,
        supplements_icon_path: str,
        icon_scale: int = 2,
        content_inset: int = 6,
        count_offset_y: int = -6,
        x_shift: int = 0,
        value_gap: int = 6,
        border: bool = False,
        border_color: str = "#777777",
        fg: str = Color.WHITE,
        bg: str = Color.BLACK,
        clear_bg: bool = True,
    ) -> dict:
        """
        Option A: big tracker row. Four evenly spaced widgets:
        - water (droplet) + count
        - tomato + count
        - pushups + count
        - supplements (pill) + (0 or green check)
        """
        bar = layout.status_rect()
        pad = layout.padding
        y_mid = bar.y + bar.h // 2

        # The icon-to-rect conversion can generate hundreds of rects; sending one huge
        # batch often fails on ESP8266. We chunk into smaller batches.
        commands: list[dict] = []
        max_commands_per_batch = 60

        def send_batch(cmds: list[dict]) -> dict:
            if not cmds:
                return {"status": "ok", "processed": 0}
            resp = self.batch(cmds)
            # Small breather helps avoid back-to-back HTTP saturation on ESP8266
            time.sleep(0.02)
            return resp
        if clear_bg:
            commands.append({"type": "rect", "x": bar.x, "y": bar.y, "w": bar.w, "h": bar.h, "color": bg, "fill": True})

        if border:
            # Simple pixel-ish double border (2 strokes) around header area.
            commands.append({"type": "rect", "x": bar.x, "y": bar.y, "w": bar.w, "h": bar.h, "color": border_color, "fill": False})
            commands.append({"type": "rect", "x": bar.x + 1, "y": bar.y + 1, "w": bar.w - 2, "h": bar.h - 2, "color": "#333333", "fill": False})
            # Thicker bottom edge to feel like a HUD base
            commands.append({"type": "rect", "x": bar.x + 1, "y": bar.y + bar.h - 3, "w": bar.w - 2, "h": 2, "color": border_color, "fill": True})

        # Subtle separator
        commands.append({"type": "rect", "x": bar.x, "y": bar.y + bar.h - 1, "w": bar.w, "h": 1, "color": "#333333", "fill": True})

        trackers = [
            ("water", int(water), water_icon_path),
            ("exercise", int(exercise), exercise_icon_path),
            ("focus", int(focus), focus_icon_path),
            ("supplements", 0, supplements_icon_path),
        ]
        n = len(trackers)
        cell_w = (bar.w - 2 * pad) // n if n else bar.w
        icon_r = 10
        icon_cy = y_mid - 4  # icons higher, counts lower
        text_size = 2  # smaller counts
        text_y = bar.y + bar.h - (8 * text_size) - content_inset + count_offset_y
        if text_y < bar.y + 6:
            text_y = bar.y + 6

        def load_icon(path: str):
            # Cache decoded RGBA icons (most calls redraw frequently).
            try:
                from PIL import Image  # type: ignore
            except Exception as e:  # pragma: no cover
                raise RuntimeError(
                    "PNG icon rendering requires Pillow. "
                    "Run with `uv run --script ...` and include `pillow` in the script dependencies."
                ) from e

            cache = getattr(self, "_icon_cache", None)
            if cache is None:
                cache = {}
                setattr(self, "_icon_cache", cache)
            if path in cache:
                return cache[path]
            img = Image.open(path).convert("RGBA")
            cache[path] = img
            return img

        def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
            r, g, b = rgb
            return f"#{r:02x}{g:02x}{b:02x}"

        def iter_runs_row(img, y: int):
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

        def draw_icon(img, ox: int, oy: int, scale: int = 2):
            # Draw as run-length horizontal rectangles.
            for py in range(16):
                for (rx0, rx1, color) in iter_runs_row(img, py):
                    w = (rx1 - rx0) * scale
                    if w <= 0:
                        continue
                    commands.append(
                        {
                            "type": "rect",
                            "x": ox + rx0 * scale,
                            "y": oy + py * scale,
                            "w": w,
                            "h": scale,
                            "color": color,
                            "fill": True,
                        }
                    )
                    if len(commands) >= max_commands_per_batch:
                        send_batch(commands)
                        commands.clear()

        for i, (kind, count, icon_path) in enumerate(trackers):
            cell_x0 = bar.x + pad + i * cell_w
            # Place icon at left of widget
            icon_x = cell_x0 + content_inset + x_shift
            icon_y = bar.y + content_inset
            draw_icon(load_icon(icon_path), icon_x, icon_y, scale=icon_scale)

            # Place value / state to the right of icon
            tx = icon_x + 16 * icon_scale + value_gap
            if kind == "water":
                commands.append({"type": "text", "x": tx, "y": text_y, "text": str(count), "size": text_size, "color": fg, "bg": bg, "clear": True})
            elif kind in ("exercise", "focus"):
                commands.append({"type": "text", "x": tx, "y": text_y, "text": str(count), "size": text_size, "color": fg, "bg": bg, "clear": True})
            else:
                if supplements_done:
                    # green checkmark
                    x0 = tx
                    y0 = text_y + 10
                    commands.append({"type": "line", "x0": x0, "y0": y0, "x1": x0 + 4, "y1": y0 + 4, "color": Color.GREEN})
                    commands.append({"type": "line", "x0": x0 + 4, "y0": y0 + 4, "x1": x0 + 12, "y1": y0 - 4, "color": Color.GREEN})
                else:
                    commands.append({"type": "text", "x": tx, "y": text_y, "text": "0", "size": text_size, "color": "#777777", "bg": bg, "clear": True})

            if len(commands) >= max_commands_per_batch:
                send_batch(commands)
                commands.clear()

        # Flush remaining
        return send_batch(commands)

    def draw_os_header(
        self,
        layout: Layout,
        *,
        water: int,
        exercise: int,
        focus: int,
        supplements_done: bool,
        water_icon_path: str,
        exercise_icon_path: str,
        focus_icon_path: str,
        supplements_icon_path: str,
        title_left: str,
        clock_right: str,
        active_tab: str = "focus",
        fg: str = Color.WHITE,
        bg: str = Color.BLACK,
        clear_bg: bool = True,
    ) -> dict:
        """
        OS template header:
        - row 1: 4 small icons + counts (16x16 icons, scale=1)
        - row 2: left title + right clock
        """
        bar = layout.status_rect()

        # Chunked batches (same reason as tracker bar)
        commands: list[dict] = []
        max_commands_per_batch = 60

        def send_batch(cmds: list[dict]) -> dict:
            if not cmds:
                return {"status": "ok", "processed": 0}
            resp = self.batch(cmds)
            time.sleep(0.02)
            return resp

        if clear_bg:
            commands.append({"type": "rect", "x": bar.x, "y": bar.y, "w": bar.w, "h": bar.h, "color": bg, "fill": True})

        # separator
        commands.append({"type": "rect", "x": bar.x, "y": bar.y + bar.h - 1, "w": bar.w, "h": 1, "color": "#333333", "fill": True})

        def load_icon(path: str):
            try:
                from PIL import Image  # type: ignore
            except Exception as e:  # pragma: no cover
                raise RuntimeError(
                    "PNG icon rendering requires Pillow. "
                    "Run with `uv run --script ...` and include `pillow` in the script dependencies."
                ) from e

            cache = getattr(self, "_icon_cache", None)
            if cache is None:
                cache = {}
                setattr(self, "_icon_cache", cache)
            if path in cache:
                return cache[path]
            img = Image.open(path).convert("RGBA")
            cache[path] = img
            return img

        def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
            r, g, b = rgb
            return f"#{r:02x}{g:02x}{b:02x}"

        def iter_runs_row(img, y: int):
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

        def draw_icon(img, ox: int, oy: int, scale: int = 1):
            for py in range(16):
                for (rx0, rx1, color) in iter_runs_row(img, py):
                    w = (rx1 - rx0) * scale
                    if w <= 0:
                        continue
                    commands.append(
                        {"type": "rect", "x": ox + rx0 * scale, "y": oy + py * scale, "w": w, "h": scale, "color": color, "fill": True}
                    )
                    if len(commands) >= max_commands_per_batch:
                        send_batch(commands)
                        commands.clear()

        # Layout: row1 icons
        pad = layout.padding
        row1_y = bar.y + 4
        row2_y = bar.y + 24
        icon_scale = 1
        count_size = 1
        icon_w = 16 * icon_scale

        items = [
            ("water", water, water_icon_path),
            ("exercise", exercise, exercise_icon_path),
            ("focus", focus, focus_icon_path),
            ("supplements", 0, supplements_icon_path),
        ]
        # spread across width
        cell_w = (bar.w - 2 * pad) // 4

        for i, (kind, count, icon_path) in enumerate(items):
            cell_x0 = bar.x + pad + i * cell_w
            ix = cell_x0
            iy = row1_y
            draw_icon(load_icon(icon_path), ix, iy, scale=icon_scale)

            # optional underline for active tab
            if kind == active_tab:
                commands.append({"type": "rect", "x": ix, "y": iy + 16 + 1, "w": icon_w, "h": 2, "color": "#00ffff", "fill": True})

            tx = ix + icon_w + 3
            if kind == "supplements":
                if supplements_done:
                    # checkmark
                    x0 = tx
                    y0 = iy + 12
                    commands.append({"type": "line", "x0": x0, "y0": y0, "x1": x0 + 3, "y1": y0 + 3, "color": Color.GREEN})
                    commands.append({"type": "line", "x0": x0 + 3, "y0": y0 + 3, "x1": x0 + 9, "y1": y0 - 3, "color": Color.GREEN})
                else:
                    commands.append({"type": "text", "x": tx, "y": iy + 6, "text": "0", "size": count_size, "color": "#777777", "bg": bg, "clear": True})
            else:
                commands.append({"type": "text", "x": tx, "y": iy + 6, "text": str(count), "size": count_size, "color": fg, "bg": bg, "clear": True})

            if len(commands) >= max_commands_per_batch:
                send_batch(commands)
                commands.clear()

        # Row2: title + clock
        commands.append({"type": "text", "x": bar.x + pad, "y": row2_y, "text": title_left, "size": 2, "color": fg, "bg": bg, "clear": True})
        clock_w = self.text_width(clock_right, size=2)
        commands.append({"type": "text", "x": bar.x + bar.w - pad - clock_w, "y": row2_y, "text": clock_right, "size": 2, "color": fg, "bg": bg, "clear": True})

        return send_batch(commands)

    # =========================================================================
    # GIF control
    # =========================================================================

    def list_gifs(self) -> dict:
        """List available GIFs"""
        return self._get("/api/v1/gif")

    def play_gif(self, name: str) -> dict:
        """Play a GIF by name"""
        return self._post("/api/v1/gif/play", {"name": name})

    def stop_gif(self) -> dict:
        """Stop GIF playback"""
        return self._post("/api/v1/gif/stop", {})

    # =========================================================================
    # System
    # =========================================================================

    def wifi_status(self) -> dict:
        """Get WiFi connection status"""
        return self._get("/api/v1/wifi/status")

    def reboot(self) -> dict:
        """Reboot the device"""
        return self._post("/api/v1/reboot", {})


# =============================================================================
# Lobster Mascot - Cute buddy for the HoloCube
# =============================================================================

# Confetti configuration for party mode
CONFETTI_COLORS = ["#ffff00", "#00ffff", "#ff00ff", "#00ff00", "#ff8800", "#88ff00"]
CONFETTI_POSITIONS = [
    (-45, -30), (40, -25), (-30, 20), (35, 15),
    (-20, -35), (25, -20), (-40, 5), (45, 0),
    (-15, 25), (20, 30), (-35, -10), (30, -5)
]


def draw_confetti(cube: HoloCube, cx: int, cy: int, frame: int = 0, clear_first: bool = False):
    """Draw animated confetti - twinkle effect"""
    for i, (dx, dy) in enumerate(CONFETTI_POSITIONS):
        confetti_x = cx + dx
        confetti_y = cy + dy
        visible = (i + frame) % 2 == 0

        if clear_first:
            if i % 3 == 0:
                cube.circle(confetti_x, confetti_y, 3, "#000000", fill=True)
            elif i % 3 == 1:
                cube.rect(confetti_x, confetti_y, 5, 5, "#000000", fill=True)
            else:
                cube.triangle(confetti_x, confetti_y, confetti_x + 5, confetti_y,
                             confetti_x + 2, confetti_y - 5, color="#000000", fill=True)

        if visible:
            color = CONFETTI_COLORS[(i + frame) % len(CONFETTI_COLORS)]
            if i % 3 == 0:
                cube.circle(confetti_x, confetti_y, 3, color, fill=True)
            elif i % 3 == 1:
                cube.rect(confetti_x, confetti_y, 5, 5, color, fill=True)
            else:
                cube.triangle(confetti_x, confetti_y, confetti_x + 5, confetti_y,
                             confetti_x + 2, confetti_y - 5, color=color, fill=True)


def draw_lobster(cube: HoloCube, cx: int, cy: int, happy: bool = False, frame: int = 0, scale: float = 1.0):
    """
    Draw cute lobster mascot at position (cx, cy).

    Args:
        cube: HoloCube instance
        cx, cy: Center position for the lobster
        happy: If True, show party mode with confetti and happy eyes
        frame: Animation frame number for confetti twinkle effect
    """
    def off(v: int) -> int:
        """Scale signed offsets (can be negative)."""
        return int(round(v * scale))

    def sz(v: int) -> int:
        """Scale sizes/radii (always positive at least 1)."""
        return max(1, int(round(v * scale)))

    body = "#ff6b6b"
    body_light = "#ff9999"
    body_dark = "#cc4444"
    eye_white = "#ffffff"
    eye_black = "#111111"
    cheek = "#ffaaaa"

    # Draw confetti first (behind lobster) if happy
    if happy:
        draw_confetti(cube, cx, cy, frame)

    # Claws - raised higher if happy (celebrating!)
    claw_raise = off(-5) if happy else 0
    cube.line(cx - off(10), cy - off(5) + claw_raise, cx - off(18), cy - off(13) + claw_raise, body)
    cube.circle(cx - off(21), cy - off(16) + claw_raise, sz(4), body, fill=True)
    cube.triangle(cx - off(23), cy - off(19) + claw_raise, cx - off(20), cy - off(20) + claw_raise,
                  cx - off(27), cy - off(27) + claw_raise, color=body, fill=True)
    cube.triangle(cx - off(24), cy - off(14) + claw_raise, cx - off(23), cy - off(17) + claw_raise,
                  cx - off(32), cy - off(17) + claw_raise, color=body, fill=True)

    cube.line(cx + off(10), cy - off(5) + claw_raise, cx + off(18), cy - off(13) + claw_raise, body)
    cube.circle(cx + off(21), cy - off(16) + claw_raise, sz(4), body, fill=True)
    cube.triangle(cx + off(23), cy - off(19) + claw_raise, cx + off(20), cy - off(20) + claw_raise,
                  cx + off(27), cy - off(27) + claw_raise, color=body, fill=True)
    cube.triangle(cx + off(24), cy - off(14) + claw_raise, cx + off(23), cy - off(17) + claw_raise,
                  cx + off(32), cy - off(17) + claw_raise, color=body, fill=True)

    # Body
    cube.ellipse(cx, cy, sz(14), sz(12), body, fill=True)
    cube.ellipse(cx - off(2), cy - off(2), sz(7), sz(5), body_light, fill=True)

    # Eyes - happy curved eyes (^_^) or normal round eyes
    if happy:
        cube.circle(cx - off(5), cy - off(3), sz(5), eye_white, fill=True)
        cube.circle(cx + off(5), cy - off(3), sz(5), eye_white, fill=True)
        cube.line(cx - off(8), cy - off(2), cx - off(5), cy - off(5), eye_black)
        cube.line(cx - off(5), cy - off(5), cx - off(2), cy - off(2), eye_black)
        cube.line(cx + off(2), cy - off(2), cx + off(5), cy - off(5), eye_black)
        cube.line(cx + off(5), cy - off(5), cx + off(8), cy - off(2), eye_black)
    else:
        cube.circle(cx - off(5), cy - off(3), sz(5), eye_white, fill=True)
        cube.circle(cx + off(5), cy - off(3), sz(5), eye_white, fill=True)
        cube.circle(cx - off(4), cy - off(4), sz(2), eye_black, fill=True)
        cube.circle(cx + off(6), cy - off(4), sz(2), eye_black, fill=True)
        cube.pixel(cx - off(6), cy - off(5), eye_white)
        cube.pixel(cx + off(4), cy - off(5), eye_white)

    # Blush - bigger when happy
    blush_size = (sz(4), sz(3)) if happy else (sz(3), sz(2))
    cube.ellipse(cx - off(8), cy + off(3), blush_size[0], blush_size[1], cheek, fill=True)
    cube.ellipse(cx + off(8), cy + off(3), blush_size[0], blush_size[1], cheek, fill=True)

    # Antennae
    cube.line(cx - off(2), cy - off(14), cx - off(6), cy - off(24), body)
    cube.line(cx + off(2), cy - off(14), cx + off(6), cy - off(24), body)
    cube.circle(cx - off(6), cy - off(24), sz(2), body_light, fill=True)
    cube.circle(cx + off(6), cy - off(24), sz(2), body_light, fill=True)

    # Legs
    for offset in [-5, 1, 7]:
        cube.line(cx - off(12), cy + off(offset), cx - off(18), cy + off(offset + 3), body_dark)
        cube.line(cx + off(12), cy + off(offset), cx + off(18), cy + off(offset + 3), body_dark)

    # Tail
    cube.ellipse(cx, cy + off(14), sz(5), sz(3), body, fill=True)
    cube.ellipse(cx, cy + off(19), sz(4), sz(2), body, fill=True)
    cube.ellipse(cx, cy + off(23), sz(3), sz(2), body_dark, fill=True)
    cube.circle(cx - off(4), cy + off(27), sz(3), body, fill=True)
    cube.circle(cx + off(4), cy + off(27), sz(3), body, fill=True)
    cube.circle(cx, cy + off(29), sz(3), body, fill=True)


# =============================================================================
# Example usage / demo
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HoloCube Client Demo")
    parser.add_argument("--ip", default="192.168.7.80", help="HoloCube IP address")
    parser.add_argument("demo", choices=["message", "timer", "progress", "alert", "os"],
                        help="Demo to run")
    args = parser.parse_args()

    cube = HoloCube(args.ip)

    if args.demo == "message":
        cube.show_message(
            ["Hello", "From", "Python"],
            colors=[Color.CYAN, Color.WHITE, Color.ORANGE]
        )

    elif args.demo == "timer":
        cube.show_timer(1500, label="FOCUS")  # 25 minutes

    elif args.demo == "progress":
        for i in range(101):
            cube.show_progress(i / 100, label="Loading")
            time.sleep(0.05)

    elif args.demo == "alert":
        cube.alert("BREAK TIME")

    elif args.demo == "os":
        layout = Layout()
        cube.clear(Color.BLACK)
        cube.draw_tracker_bar(layout, water=3, tomato=2, pushups=15, supplements_done=False)
        cube.show_big_number("42", label="STATUS", color=Color.CYAN, bg=Color.BLACK)
        mx, my = layout.mascot_anchor()
        draw_lobster(cube, mx, my, happy=True, frame=0)
