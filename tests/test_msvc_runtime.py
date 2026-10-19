"""The C++ runtime must be loaded before PyQt6, or torch breaks on Windows.

See src/utils/msvc_runtime.py for the mechanism. The ordering test is the one
that matters: moving the preload below a PyQt6 import compiles, runs and passes
every other test, and only "Find similar" on Windows notices.
"""

import ast
import os
import sys
from pathlib import Path

import pytest

from src.utils import msvc_runtime

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_does_nothing_off_windows(monkeypatch):
    monkeypatch.setattr(msvc_runtime.sys, "platform", "darwin")
    assert msvc_runtime.preload_msvc_runtime() is None


def test_does_nothing_in_the_packaged_app(monkeypatch):
    # The bundle is fixed at build time (build.py upgrade_bundled_msvc_runtime);
    # a preload there does not stop Qt loading its own copy anyway.
    monkeypatch.setattr(msvc_runtime.sys, "platform", "win32")
    monkeypatch.setattr(msvc_runtime.sys, "frozen", True, raising=False)
    assert msvc_runtime.preload_msvc_runtime() is None


def test_preload_runs_before_any_pyqt6_import():
    tree = ast.parse((REPO_ROOT / "src" / "main.py").read_text(encoding="utf-8"))
    preload_line = pyqt_line = None
    for node in tree.body:
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and getattr(node.value.func, "id", None) == "preload_msvc_runtime"):
            preload_line = preload_line or node.lineno
        names = ([node.module or ""] if isinstance(node, ast.ImportFrom)
                 else [a.name for a in node.names] if isinstance(node, ast.Import)
                 else [])
        if any(n.startswith("PyQt6") or n.startswith("ui") for n in names):
            pyqt_line = pyqt_line or node.lineno
    assert preload_line is not None, "src/main.py no longer preloads the runtime"
    assert pyqt_line is not None
    assert preload_line < pyqt_line, "the runtime preload must come before PyQt6"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DLL behaviour")
def test_torch_loads_after_qt_once_preloaded():
    """The real thing, in a fresh process: app start, then torch."""
    import importlib.util
    import subprocess
    # find_spec, not importorskip: importing torch here, in a process where
    # other tests already loaded PyQt6, hits the very failure under test.
    if importlib.util.find_spec("torch") is None:
        pytest.skip("torch not installed")
    result = subprocess.run(
        [sys.executable, "-c", "import src.main, torch"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-500:]
