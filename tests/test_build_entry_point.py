"""Guards the fix for BUG-5 — the PyInstaller entry point must not use relative imports.

See `docs/KNOWN_BUGS.md` (BUG-5, fixed). Pointing PyInstaller at `src/main.py`
crashed the bundled app on launch with "attempted relative import with no known
parent package", and PyInstaller's analysis silently discovered none of `src/`,
so torch/numpy never made it into the bundle either — a build that looked
healthy (exit 0, no warnings) and was dead on arrival. `run.py` is the shim that
keeps `src` a package; this pins both builders to it.

This pins the invariant without running a real multi-minute PyInstaller build:
the script handed to PyInstaller becomes `__main__`, so it must not rely on
relative imports.
"""
import ast
import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_build_module():
    """Import repo-root build.py under a private name (it is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "_build_under_test", REPO_ROOT / "build.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entry_script(monkeypatch, builder_name: str) -> str:
    """Return the entry script build.py would hand PyInstaller, without building."""
    build = _load_build_module()
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, *_args, **_kwargs):
        captured["cmd"] = cmd
        raise AssertionError("unreachable: PyInstaller must not actually run")

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    with pytest.raises(AssertionError):
        getattr(build, builder_name)()

    # The entry script is the trailing positional arg, after all --flags.
    return captured["cmd"][-1]


def _uses_relative_imports(path: Path) -> bool:
    tree = ast.parse(path.read_text())
    return any(
        isinstance(node, ast.ImportFrom) and (node.level or 0) > 0
        for node in ast.walk(tree)
    )


@pytest.mark.parametrize("builder", ["build_macos", "build_windows"])
def test_pyinstaller_entry_point_runs_as_a_script(monkeypatch, builder):
    entry = Path(_entry_script(monkeypatch, builder))

    assert not _uses_relative_imports(REPO_ROOT / entry), (
        f"build.py hands PyInstaller '{entry}', which uses relative imports. "
        "PyInstaller executes it as __main__ with no parent package, so the "
        "bundled app dies with ImportError at line 1 and none of src/ is "
        "discovered. Point the build at a root-level shim that does "
        "`from src.main import main`."
    )
