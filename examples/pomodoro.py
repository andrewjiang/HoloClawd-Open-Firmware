#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
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
from holocube_client import HoloCube, Color, draw_lobster, draw_confetti

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
                 spotify_work: str = "",
                 spotify_break: str = ""):
        self.cube = cube
        self.work_secs = work_mins * 60
        self.short_break_secs = short_break_mins * 60
        self.long_break_secs = long_break_mins * 60
        self.sessions_before_long = sessions_before_long
        self.completed_sessions = 0
        self.task = task[:MAX_TASK_LENGTH].upper()  # Truncate and uppercase
        self.spotify_work = spotify_work
        self.spotify_break = spotify_break

    def draw_timer_screen(self, label: str, color: str, is_break: bool = False, frame: int = 0):
        """Draw the full timer screen with lobster buddy"""
        self.cube.clear(Color.BLACK)
        self.cube.centered_text(30, label, size=2, color=Color.WHITE)
        draw_lobster(self.cube, 120, 190, happy=is_break, frame=frame)

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
                    draw_confetti(self.cube, 120, 190, frame=frame, clear_first=True)

                self.cube.show_timer(remaining, label=None, color=color, clear_screen=False)
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
        return self.countdown(self.work_secs, self.task, Color.RED)

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
        print("-" * 30)

        try:
            while True:
                if not self.work_session():
                    break

                self.completed_sessions += 1
                print(f"Completed session {self.completed_sessions}")

                if self.completed_sessions % self.sessions_before_long == 0:
                    if not self.long_break():
                        break
                else:
                    if not self.short_break():
                        break

                self.flash_alert("WORK", Color.RED, times=3)

        except KeyboardInterrupt:
            pass

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
    parser.add_argument("--spotify-work", default="", help="Spotify URI to play during work (e.g., spotify:playlist:xxx)")
    parser.add_argument("--spotify-break", default="", help="Spotify URI to play during breaks")
    args = parser.parse_args()

    cube = HoloCube(args.ip)

    # Check connection
    status = cube.wifi_status()
    if "error" in status.get("status", ""):
        print(f"Cannot connect to HoloCube at {args.ip}")
        sys.exit(1)

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
        spotify_work=args.spotify_work,
        spotify_break=args.spotify_break
    )

    timer.run()


if __name__ == "__main__":
    main()
