#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
3D Wireframe Demo for HoloCube

Demonstrates the on-device 3D rendering capabilities:
- Rotating wireframe primitives (cube, pyramid, icosahedron, etc.)
- Color cycling
- Various rotation speeds

Usage:
    uv run --script demo_3d.py [--ip 192.168.7.80]
"""

import argparse
import time
from holocube_client import HoloCube, Color


# Available 3D primitives
PRIMITIVES = ["cube", "pyramid", "octahedron", "diamond", "tetrahedron", "icosahedron"]

# Colors optimized for holographic display (bright, high contrast)
HOLO_COLORS = [
    "#00ffff",  # Cyan
    "#ff00ff",  # Magenta
    "#00ff00",  # Green
    "#ffff00",  # Yellow
    "#ff6600",  # Orange
    "#00ff88",  # Teal
    "#ff0088",  # Pink
    "#8800ff",  # Purple
]


def demo_primitives(cube: HoloCube, duration_each: float = 5.0):
    """Cycle through all primitives with rotation"""
    print("Demo: Cycling through all 3D primitives...")

    for i, primitive in enumerate(PRIMITIVES):
        color = HOLO_COLORS[i % len(HOLO_COLORS)]
        print(f"  Showing: {primitive} in {color}")

        # Start animation with this primitive
        cube.animate_3d(
            speed_x=1,
            speed_y=2,
            speed_z=0,
            primitive_type=primitive,
            color=color,
            scale=1.2
        )

        time.sleep(duration_each)

    cube.stop_3d()


def demo_rotation_speeds(cube: HoloCube, duration: float = 10.0):
    """Show different rotation patterns"""
    print("Demo: Different rotation patterns...")

    patterns = [
        {"name": "Slow Y-axis", "x": 0, "y": 1, "z": 0},
        {"name": "Fast spin", "x": 2, "y": 3, "z": 1},
        {"name": "Tumble", "x": 2, "y": 1, "z": 2},
        {"name": "X-axis only", "x": 2, "y": 0, "z": 0},
    ]

    for pattern in patterns:
        print(f"  Pattern: {pattern['name']}")
        cube.animate_3d(
            speed_x=pattern["x"],
            speed_y=pattern["y"],
            speed_z=pattern["z"],
            primitive_type="icosahedron",
            color=Color.CYAN
        )
        time.sleep(duration / len(patterns))

    cube.stop_3d()


def demo_color_cycle(cube: HoloCube, duration: float = 15.0):
    """Cycle colors while rotating"""
    print("Demo: Color cycling...")

    # Start with cube
    cube.animate_3d(
        speed_x=1,
        speed_y=2,
        speed_z=0,
        primitive_type="cube",
        color=HOLO_COLORS[0]
    )

    interval = duration / len(HOLO_COLORS)
    for color in HOLO_COLORS:
        print(f"  Color: {color}")
        cube.transform_3d(color=color)
        time.sleep(interval)

    cube.stop_3d()


def demo_scale(cube: HoloCube, duration: float = 10.0):
    """Animate scale changes"""
    print("Demo: Scale animation...")

    cube.animate_3d(
        speed_x=0,
        speed_y=2,
        speed_z=1,
        primitive_type="diamond",
        color=Color.MAGENTA,
        scale=0.5
    )

    # Gradually increase scale
    scales = [0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.3, 1.1, 0.9, 0.7]
    interval = duration / len(scales)

    for scale in scales:
        print(f"  Scale: {scale:.1f}")
        cube.transform_3d(scale=scale)
        time.sleep(interval)

    cube.stop_3d()


def interactive_mode(cube: HoloCube):
    """Interactive control of 3D renderer"""
    print("\n3D Interactive Mode")
    print("=" * 40)
    print("Commands:")
    print("  p <type>  - Set primitive (cube, pyramid, octahedron, diamond, tetrahedron, icosahedron)")
    print("  c <hex>   - Set color (e.g., #00ffff)")
    print("  s <val>   - Set scale (e.g., 1.5)")
    print("  r <x> <y> <z> - Set rotation speed")
    print("  a         - Start animation with current settings")
    print("  x         - Stop animation")
    print("  q         - Quit")
    print()

    current_primitive = "cube"
    current_color = Color.CYAN
    current_scale = 1.0
    speeds = [0, 2, 0]

    while True:
        try:
            cmd = input("> ").strip().lower()
            if not cmd:
                continue

            parts = cmd.split()
            action = parts[0]

            if action == "q":
                cube.stop_3d()
                print("Goodbye!")
                break
            elif action == "p" and len(parts) > 1:
                current_primitive = parts[1]
                print(f"Primitive: {current_primitive}")
                cube.primitive_3d(current_primitive, current_color, current_scale)
            elif action == "c" and len(parts) > 1:
                current_color = parts[1]
                print(f"Color: {current_color}")
                cube.transform_3d(color=current_color)
            elif action == "s" and len(parts) > 1:
                current_scale = float(parts[1])
                print(f"Scale: {current_scale}")
                cube.transform_3d(scale=current_scale)
            elif action == "r" and len(parts) > 3:
                speeds = [int(parts[1]), int(parts[2]), int(parts[3])]
                print(f"Rotation speeds: X={speeds[0]}, Y={speeds[1]}, Z={speeds[2]}")
            elif action == "a":
                print("Starting animation...")
                cube.animate_3d(
                    speed_x=speeds[0],
                    speed_y=speeds[1],
                    speed_z=speeds[2],
                    primitive_type=current_primitive,
                    color=current_color,
                    scale=current_scale
                )
            elif action == "x":
                print("Stopping animation...")
                cube.stop_3d()
            else:
                print("Unknown command. Type 'q' to quit.")

        except KeyboardInterrupt:
            cube.stop_3d()
            print("\nInterrupted. Goodbye!")
            break
        except (ValueError, IndexError) as e:
            print(f"Invalid input: {e}")


def main():
    parser = argparse.ArgumentParser(description="3D Wireframe Demo for HoloCube")
    parser.add_argument("--ip", default="192.168.7.80", help="HoloCube IP address")
    parser.add_argument("--demo", choices=["all", "primitives", "rotation", "color", "scale", "interactive"],
                        default="all", help="Which demo to run")
    args = parser.parse_args()

    cube = HoloCube(args.ip)

    # Check connection
    status = cube.wifi_status()
    if status.get("status") == "error":
        print(f"Error connecting to HoloCube at {args.ip}")
        print(f"Details: {status.get('message', 'Unknown error')}")
        return

    print(f"Connected to HoloCube at {args.ip}")
    print()

    try:
        if args.demo == "interactive":
            interactive_mode(cube)
        elif args.demo == "primitives":
            demo_primitives(cube)
        elif args.demo == "rotation":
            demo_rotation_speeds(cube)
        elif args.demo == "color":
            demo_color_cycle(cube)
        elif args.demo == "scale":
            demo_scale(cube)
        else:  # all
            demo_primitives(cube, duration_each=3.0)
            time.sleep(1)
            demo_rotation_speeds(cube, duration=8.0)
            time.sleep(1)
            demo_color_cycle(cube, duration=10.0)
            time.sleep(1)
            demo_scale(cube, duration=8.0)

        print("\nDemo complete!")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        cube.stop_3d()


if __name__ == "__main__":
    main()
