#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
HoloCube Client Library - Control your HoloCube display programmatically

Example usage:
    from holocube_client import HoloCube

    cube = HoloCube("192.168.7.80")
    cube.clear("#000000")
    cube.text(60, 100, "Hello!", size=4, color="#00ffff")
    cube.circle(120, 120, 50, color="#ff0000", fill=True)
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
                   clear_screen: bool = False) -> None:
        """Display a timer value. Set clear_screen=True only on first call."""
        time_str = self.format_time(seconds)
        if clear_screen:
            self.clear(bg)
            if label:
                self.centered_text(40, label, size=2, color=Color.WHITE)
        # Draw time with background color to overwrite previous text (clear_bg ensures clean overwrite)
        self.text(self.center_x(time_str, 5), 90, time_str, size=5, color=color, bg=bg, clear_bg=True)

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


def draw_lobster(cube: HoloCube, cx: int, cy: int, happy: bool = False, frame: int = 0):
    """
    Draw cute lobster mascot at position (cx, cy).

    Args:
        cube: HoloCube instance
        cx, cy: Center position for the lobster
        happy: If True, show party mode with confetti and happy eyes
        frame: Animation frame number for confetti twinkle effect
    """
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
    claw_raise = -5 if happy else 0
    cube.line(cx - 10, cy - 5 + claw_raise, cx - 18, cy - 13 + claw_raise, body)
    cube.circle(cx - 21, cy - 16 + claw_raise, 4, body, fill=True)
    cube.triangle(cx - 23, cy - 19 + claw_raise, cx - 20, cy - 20 + claw_raise,
                  cx - 27, cy - 27 + claw_raise, color=body, fill=True)
    cube.triangle(cx - 24, cy - 14 + claw_raise, cx - 23, cy - 17 + claw_raise,
                  cx - 32, cy - 17 + claw_raise, color=body, fill=True)

    cube.line(cx + 10, cy - 5 + claw_raise, cx + 18, cy - 13 + claw_raise, body)
    cube.circle(cx + 21, cy - 16 + claw_raise, 4, body, fill=True)
    cube.triangle(cx + 23, cy - 19 + claw_raise, cx + 20, cy - 20 + claw_raise,
                  cx + 27, cy - 27 + claw_raise, color=body, fill=True)
    cube.triangle(cx + 24, cy - 14 + claw_raise, cx + 23, cy - 17 + claw_raise,
                  cx + 32, cy - 17 + claw_raise, color=body, fill=True)

    # Body
    cube.ellipse(cx, cy, 14, 12, body, fill=True)
    cube.ellipse(cx - 2, cy - 2, 7, 5, body_light, fill=True)

    # Eyes - happy curved eyes (^_^) or normal round eyes
    if happy:
        cube.circle(cx - 5, cy - 3, 5, eye_white, fill=True)
        cube.circle(cx + 5, cy - 3, 5, eye_white, fill=True)
        cube.line(cx - 8, cy - 2, cx - 5, cy - 5, eye_black)
        cube.line(cx - 5, cy - 5, cx - 2, cy - 2, eye_black)
        cube.line(cx + 2, cy - 2, cx + 5, cy - 5, eye_black)
        cube.line(cx + 5, cy - 5, cx + 8, cy - 2, eye_black)
    else:
        cube.circle(cx - 5, cy - 3, 5, eye_white, fill=True)
        cube.circle(cx + 5, cy - 3, 5, eye_white, fill=True)
        cube.circle(cx - 4, cy - 4, 2, eye_black, fill=True)
        cube.circle(cx + 6, cy - 4, 2, eye_black, fill=True)
        cube.pixel(cx - 6, cy - 5, eye_white)
        cube.pixel(cx + 4, cy - 5, eye_white)

    # Blush - bigger when happy
    blush_size = (4, 3) if happy else (3, 2)
    cube.ellipse(cx - 8, cy + 3, blush_size[0], blush_size[1], cheek, fill=True)
    cube.ellipse(cx + 8, cy + 3, blush_size[0], blush_size[1], cheek, fill=True)

    # Antennae
    cube.line(cx - 2, cy - 14, cx - 6, cy - 24, body)
    cube.line(cx + 2, cy - 14, cx + 6, cy - 24, body)
    cube.circle(cx - 6, cy - 24, 2, body_light, fill=True)
    cube.circle(cx + 6, cy - 24, 2, body_light, fill=True)

    # Legs
    for offset in [-5, 1, 7]:
        cube.line(cx - 12, cy + offset, cx - 18, cy + offset + 3, body_dark)
        cube.line(cx + 12, cy + offset, cx + 18, cy + offset + 3, body_dark)

    # Tail
    cube.ellipse(cx, cy + 14, 5, 3, body, fill=True)
    cube.ellipse(cx, cy + 19, 4, 2, body, fill=True)
    cube.ellipse(cx, cy + 23, 3, 2, body_dark, fill=True)
    cube.circle(cx - 4, cy + 27, 3, body, fill=True)
    cube.circle(cx + 4, cy + 27, 3, body, fill=True)
    cube.circle(cx, cy + 29, 3, body, fill=True)


# =============================================================================
# Example usage / demo
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HoloCube Client Demo")
    parser.add_argument("--ip", default="192.168.7.80", help="HoloCube IP address")
    parser.add_argument("demo", choices=["message", "timer", "progress", "alert"],
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
