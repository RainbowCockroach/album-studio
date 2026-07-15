#!/usr/bin/env python3
"""Frozen-app entry point.

PyInstaller executes its entry script as `__main__`, with no parent package, so
it cannot be `src/main.py` — that module's relative imports (`from .ui...`) raise
ImportError on the first line, and PyInstaller's analysis fails to follow them,
silently leaving all of `src/` out of the bundle. Importing `src.main` from the
repo root instead keeps `src` a real package for both.

Running from source still uses `python3 -m src.main`; this file exists for the
build.
"""

from src.main import main

if __name__ == "__main__":
    main()
