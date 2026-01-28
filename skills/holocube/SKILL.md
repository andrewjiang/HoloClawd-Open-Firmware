---
name: HoloCube (Pomodoro + Trackers)
slug: holocube
version: 0.2.1
description: Run the HoloCube Pomodoro “OS” UI (tracker bar + centered label + lobster) and control water/exercise/focus/pills live.
metadata:
  clawdbot:
    requires:
      - python>=3.10
      - uv
---

## What this skill does

This repo includes a template “OS” layout for the HoloCube:

- **Top**: a tracker bar (icons + counts + pixel border)
- **Middle**: centered app label + smaller timer
- **Bottom**: lobster mascot (animated / confetti on breaks)

The Pomodoro app uses this layout and supports live tracker updates.

## Run Pomodoro

From this repo root:

```bash
uv run --script examples/pomodoro.py --ip <HOLOCUBE_IP> --task "DEEP WORK"
```

Useful flags:

- `--work 25 --short 5 --long 15 --sessions 4`
- `--focus-text "BUILD"`
- **Trackers (starting values)**:
  - `--water 0` (water count)
  - `--exercise 0` (exercise count)
  - `--focus 0` (focus count)
  - `--pills` (mark supplements as done)

## Live tracker commands (while Pomodoro is running)

Type these into the terminal running Pomodoro (press Enter after each):

- **Increment**:
  - `w` or `water` → +1 water
  - `e` or `exercise` → +1 exercise
  - `f` or `focus` → +1 focus
- **Toggle pills**:
  - `p` or `pills` → toggle “supplements done”
- **Set an exact value**:
  - `set water 3`
  - `set exercise 1`
  - `set focus 10`
  - `set focus 0` (reset focus back to 0)
- **Help / quit**:
  - `help`
  - `q`

### Auto focus increment

Each time a **work session completes**, Pomodoro automatically increments the **focus** tracker by +1.

## Notes

- The tracker icons are PNGs stored in-repo under `assets/icons/...` and rendered efficiently via run-length encoded draw commands.
- HoloCube communication uses the REST draw API (batch mode + chunking for ESP8266 stability).

