#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "pillow"]
# ///
"""
Pomodoro Timer for HoloCube with Lobster Mascot

A productivity timer that displays on your HoloCube with a cute lobster buddy.
During work sessions, the lobster focuses with you. During breaks, it celebrates!

Features:
- Custom task labels
- Optional Spotify integration for focus/break music
- Configurable work/break durations

Usage:
    uv run --script pomodoro.py                        # 25min work, 5min break (default)
    uv run --script pomodoro.py --task "FINISH UPDATE" # Custom task label
    uv run --script pomodoro.py --work 50              # 50 minute work sessions
    uv run --script pomodoro.py --short 10             # 10 minute short breaks

Spotify integration (macOS only):
    uv run --script pomodoro.py --spotify-work "spotify:playlist:xxx" --spotify-break "spotify:playlist:yyy"
"""

MAX_TASK_LENGTH = 20

import argparse
import time
import sys
import subprocess
import os
import threading
import queue
from holocube_client import HoloCube, Color, draw_lobster, draw_confetti, Layout

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ICONS_DIR = os.path.join(REPO_ROOT, "assets", "icons", "kyrise_16x16_rpg", "Kyrise's 16x16 RPG Icon Pack - V1.3", "icons", "16x16")

# Tracker icons (Kyrise pack)
WATER_ICON = os.path.join(ICONS_DIR, "potion_03b.png")
EXERCISE_ICON = os.path.join(ICONS_DIR, "sword_02c.png")
FOCUS_ICON = os.path.join(ICONS_DIR, "book_05g.png")
PILLS_ICON = os.path.join(ICONS_DIR, "candy_02g.png")

# Default Spotify script location (relative to this file)
SPOTIFY_SCRIPT = os.path.join(os.path.dirname(__file__), "spotify.sh")


def play_spotify(uri: str, script_path: str = SPOTIFY_SCRIPT) -> None:
    """Play a Spotify URI using the spotify AppleScript wrapper (macOS only)"""
    if not uri:
        return
    if not os.path.exists(script_path):
        print(f"Spotify script not found at {script_path}")
        return
    try:
        subprocess.run([script_path, "play", uri], check=False, capture_output=True)
    except Exception as e:
        print(f"Spotify: {e}")


class PomodoroTimer:
    """Pomodoro timer with lobster mascot for HoloCube display"""

    def __init__(self, cube: HoloCube,
                 work_mins: int = 25,
                 short_break_mins: int = 5,
                 long_break_mins: int = 15,
                 sessions_before_long: int = 4,
                 task: str = "FOCUS",
                 focus_text: str = "",
                 spotify_work: str = "",
                 spotify_break: str = "",
                 water: int = 0,
                 exercise: int = 0,
                 focus: int = 0,
                 pills_done: bool = False):
        self.cube = cube
        self.layout = Layout(screen_w=cube.SCREEN_WIDTH, screen_h=cube.SCREEN_HEIGHT)
        self.work_secs = work_mins * 60
        self.short_break_secs = short_break_mins * 60
        self.long_break_secs = long_break_mins * 60
        self.sessions_before_long = sessions_before_long
        self.completed_sessions = 0
        self.task = task[:MAX_TASK_LENGTH].upper()  # Truncate and uppercase
        self.focus_text = (focus_text or self.task)[:MAX_TASK_LENGTH].upper()
        self.spotify_work = spotify_work
        self.spotify_break = spotify_break
        self.water = water
        self.exercise = exercise
        self.focus = focus
        self.pills_done = pills_done
        self._last_clock = ""
        self._cmd_q: "queue.Queue[str]" = queue.Queue()
        self._stop_cmd = threading.Event()
        self._cmd_thread: threading.Thread | None = None

    def start_command_listener(self) -> None:
        """
        Background stdin command listener.

        Commands (press Enter after each):
        - w / water: +1 water
        - e / ex: +1 exercise
        - f / focus: +1 focus
        - p / pills: toggle pills done
        - set water|exercise|focus <n>
        - help
        - q: quit
        """
        if self._cmd_thread is not None:
            return

        def run():
            while not self._stop_cmd.is_set():
                try:
                    line = sys.stdin.readline()
                except Exception:
                    break
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                self._cmd_q.put(line)

        self._cmd_thread = threading.Thread(target=run, name="pomodoro-cmd", daemon=True)
        self._cmd_thread.start()

    def stop_command_listener(self) -> None:
        self._stop_cmd.set()

    def draw_header_only(self) -> None:
        """Redraw just the top tracker bar (no full screen clear)."""
        self.cube.draw_tracker_bar(
            self.layout,
            water=self.water,
            exercise=self.exercise,
            focus=self.focus,
            supplements_done=self.pills_done,
            water_icon_path=WATER_ICON,
            exercise_icon_path=EXERCISE_ICON,
            focus_icon_path=FOCUS_ICON,
            supplements_icon_path=PILLS_ICON,
            icon_scale=2,
            content_inset=8,
            count_offset_y=-8,
            x_shift=-4,
            value_gap=4,
            border=True,
            fg=Color.WHITE,
            bg=Color.BLACK,
            clear_bg=True,
        )

    def apply_command(self, cmd: str) -> bool:
        """
        Apply a single command. Returns False if the app should quit.
        """
        parts = cmd.strip().split()
        if not parts:
            return True

        head = parts[0].lower()
        if head in ("q", "quit", "exit"):
            return False
        if head in ("help", "?"):
            print("Commands: w/e/f (increment), p (toggle pills), set water|exercise|focus N, q (quit)")
            return True

        if head in ("w", "water"):
            self.water += 1
            self.draw_header_only()
            return True
        if head in ("e", "ex", "exercise"):
            self.exercise += 1
            self.draw_header_only()
            return True
        if head in ("f", "focus"):
            self.focus += 1
            self.draw_header_only()
            return True
        if head in ("p", "pill", "pills"):
            self.pills_done = not self.pills_done
            self.draw_header_only()
            return True

        if head == "set" and len(parts) >= 3:
            key = parts[1].lower()
            try:
                val = int(parts[2])
            except ValueError:
                print("set: value must be an int")
                return True
            if key == "water":
                self.water = val
            elif key in ("exercise", "ex"):
                self.exercise = val
            elif key == "focus":
                self.focus = val
            else:
                print("set: key must be water|exercise|focus")
                return True
            self.draw_header_only()
            return True

        print(f"Unknown command: {cmd} (try 'help')")
        return True

    def draw_timer_screen(self, label: str, color: str, is_break: bool = False, frame: int = 0):
        """Draw the full timer screen with lobster buddy"""
        self.cube.clear(Color.BLACK)
        # Top row: big icons + counts (like before)
        self.cube.draw_tracker_bar(
            self.layout,
            water=self.water,
            exercise=self.exercise,
            focus=self.focus,
            supplements_done=self.pills_done,
            water_icon_path=WATER_ICON,
            exercise_icon_path=EXERCISE_ICON,
            focus_icon_path=FOCUS_ICON,
            supplements_icon_path=PILLS_ICON,
            icon_scale=2,
            content_inset=8,
            count_offset_y=-8,
            x_shift=-4,
            value_gap=4,
            border=True,
            fg=Color.WHITE,
            bg=Color.BLACK,
            clear_bg=True,
        )

        # Below icons: centered label
        body = self.layout.body_rect()
        # Center line should be exactly the focus/break label (no extra symbols/prefix).
        header_text = f"{label}"
        # Use background-clearing text to avoid ghosting and guarantee centering.
        self.cube.text(
            self.cube.center_x(header_text, size=2),
            body.y + 14,
            header_text,
            size=2,
            color=Color.WHITE,
            bg=Color.BLACK,
            clear_bg=True,
        )

        # Mascot footer
        footer = self.layout.footer_rect()
        mx = self.cube.SCREEN_WIDTH // 2
        my = footer.y + 22
        draw_lobster(self.cube, mx, my, happy=is_break, frame=frame, scale=0.85)

    def countdown(self, seconds: int, label: str, color: str, is_break: bool = False) -> bool:
        """Run countdown. Returns True if completed, False if interrupted."""
        remaining = seconds
        frame = 0
        try:
            while remaining >= 0:
                if frame == 0:
                    self.draw_timer_screen(label, color, is_break=is_break, frame=0)
                elif is_break:
                    # Animate confetti during breaks
                    mx, my = self.layout.mascot_anchor()
                    draw_confetti(self.cube, mx, my, frame=frame, clear_first=True)

                # Timer: slightly smaller
                body = self.layout.body_rect()
                self.cube.show_timer(
                    remaining,
                    label=None,
                    color=color,
                    clear_screen=False,
                    y=body.y + 52,
                    size=4,
                )

                # Apply any queued commands (updates trackers live)
                while True:
                    try:
                        cmd = self._cmd_q.get_nowait()
                    except queue.Empty:
                        break
                    if not self.apply_command(cmd):
                        return False

                frame += 1
                time.sleep(1)
                remaining -= 1
            return True
        except KeyboardInterrupt:
            return False

    def flash_alert(self, message: str, color: str, times: int = 3):
        """Flash an alert message"""
        for _ in range(times):
            self.cube.clear(color)
            time.sleep(0.3)
            self.cube.show_message([message], colors=[Color.WHITE], size=3, bg=color)
            time.sleep(0.3)

    def work_session(self) -> bool:
        """Run a work session"""
        print(f"Starting work session {self.completed_sessions + 1}: {self.task}")
        if self.spotify_work:
            play_spotify(self.spotify_work)
        return self.countdown(self.work_secs, self.focus_text, Color.RED)

    def short_break(self) -> bool:
        """Run a short break with happy lobster"""
        self.flash_alert("BREAK", Color.GREEN, times=3)
        print("Short break!")
        if self.spotify_break:
            play_spotify(self.spotify_break)
        return self.countdown(self.short_break_secs, "SHORT BREAK", Color.GREEN, is_break=True)

    def long_break(self) -> bool:
        """Run a long break with happy lobster"""
        self.flash_alert("LONG BREAK", Color.BLUE, times=5)
        print("Long break!")
        if self.spotify_break:
            play_spotify(self.spotify_break)
        return self.countdown(self.long_break_secs, "LONG BREAK", Color.BLUE, is_break=True)

    def run(self):
        """Main pomodoro loop"""
        print("Pomodoro Timer Started")
        print("Press Ctrl+C to stop")
        print("Commands: w/e/f (increment), p (toggle pills), set water|exercise|focus N, q (quit)")
        print("-" * 30)
        self.start_command_listener()

        try:
            while True:
                if not self.work_session():
                    break

                self.completed_sessions += 1
                # Auto-increment focus tracker when a work session completes
                self.focus += 1
                print(f"Completed session {self.completed_sessions}")
                self.draw_header_only()

                if self.completed_sessions % self.sessions_before_long == 0:
                    if not self.long_break():
                        break
                else:
                    if not self.short_break():
                        break

                self.flash_alert("WORK", Color.RED, times=3)

        except KeyboardInterrupt:
            pass
        finally:
            self.stop_command_listener()

        # Show final stats
        self.cube.show_message(
            ["Done!", f"{self.completed_sessions}", "sessions"],
            colors=[Color.WHITE, Color.CYAN, Color.WHITE],
            size=3
        )
        print(f"\nCompleted {self.completed_sessions} work sessions")


def main():
    parser = argparse.ArgumentParser(description="Pomodoro Timer for HoloCube")
    parser.add_argument("--ip", default="192.168.7.80", help="HoloCube IP")
    parser.add_argument("--work", type=int, default=25, help="Work duration (minutes)")
    parser.add_argument("--short", type=int, default=5, help="Short break (minutes)")
    parser.add_argument("--long", type=int, default=15, help="Long break (minutes)")
    parser.add_argument("--sessions", type=int, default=4, help="Sessions before long break")
    parser.add_argument("--task", "-t", default="FOCUS", help=f"Task label (max {MAX_TASK_LENGTH} chars)")
    parser.add_argument("--focus-text", default="", help="Centered focus text (defaults to --task)")
    parser.add_argument("--spotify-work", default="", help="Spotify URI to play during work (e.g., spotify:playlist:xxx)")
    parser.add_argument("--spotify-break", default="", help="Spotify URI to play during breaks")
    parser.add_argument("--water", type=int, default=0, help="Initial water count")
    parser.add_argument("--exercise", type=int, default=0, help="Initial exercise count")
    parser.add_argument("--focus", type=int, default=0, help="Initial focus count")
    parser.add_argument("--pills", action="store_true", help="Mark supplements as done")
    args = parser.parse_args()

    cube = HoloCube(args.ip, timeout=15.0)

    # Check connection
    status = cube.wifi_status()
    if "error" in status.get("status", ""):
        print(f"Cannot connect to HoloCube at {args.ip}")
        sys.exit(1)

    # Clear the display before starting (ensures a clean slate even if a previous
    # app left pixels on-screen).
    cube.clear(Color.BLACK)

    task = args.task[:MAX_TASK_LENGTH].upper()
    spotify_status = "on" if (args.spotify_work or args.spotify_break) else "off"
    print(f"Connected to HoloCube at {args.ip}")
    print(f"Task: {task} | Work: {args.work}min | Break: {args.short}min | Spotify: {spotify_status}")

    timer = PomodoroTimer(
        cube,
        work_mins=args.work,
        short_break_mins=args.short,
        long_break_mins=args.long,
        sessions_before_long=args.sessions,
        task=task,
        focus_text=args.focus_text,
        spotify_work=args.spotify_work,
        spotify_break=args.spotify_break,
        water=args.water,
        exercise=args.exercise,
        focus=args.focus,
        pills_done=args.pills,
    )

    timer.run()


if __name__ == "__main__":
    main()
