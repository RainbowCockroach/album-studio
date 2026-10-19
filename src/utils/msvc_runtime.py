"""Load a current Microsoft C++ runtime before PyQt6 does (Windows, from source).

PyQt6 ships its own msvcp140.dll (14.26, from 2020). Once that old copy is in
the process, torch's c10.dll gets it and fails its init with WinError 1114 —
and torch is imported lazily on "Find similar", always after Qt.

Running from source, loading System32's newer copy first is enough: Qt's
dependencies then resolve to it. In the packaged app it is not — Qt still
loads its own copy beside it — so build.py instead replaces every old runtime
DLL in the bundle, and this does nothing when frozen.

Must run before the first PyQt6 import.
"""

import ctypes
import os
import sys
from typing import Optional


def preload_msvc_runtime() -> Optional[str]:
    """Load System32's msvcp140.dll ahead of Qt. Returns the path, or None."""
    if sys.platform != "win32" or getattr(sys, "frozen", False):
        return None
    path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                        "System32", "msvcp140.dll")
    if not os.path.exists(path):
        return None
    try:
        ctypes.WinDLL(path)  # type: ignore[attr-defined]
    except OSError as e:
        print(f"[msvc_runtime] Could not load {path}: {e}")
        return None
    return path
