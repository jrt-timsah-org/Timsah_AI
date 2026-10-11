"""Compatibility entry point for the Robot Control Monitor."""

import runpy
from pathlib import Path


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "apps/robot_control_monitor/app.py"),
        run_name="__main__",
    )
