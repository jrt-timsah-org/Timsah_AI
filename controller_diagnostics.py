"""Compatibility entry point for the USB controller diagnostic tool."""

import runpy
from pathlib import Path


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "tools/controller_diagnostics/main.py"),
        run_name="__main__",
    )
