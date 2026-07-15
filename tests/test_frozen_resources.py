"""Guards the fixes for BUG-6 and BUG-8 — resource lookup inside the packaged app.

See `docs/KNOWN_BUGS.md` (BUG-6 and BUG-8, both fixed). Neither bug was visible
from source: every path here resolves when running `python3 -m src.main` from the
repo root, and both only broke once frozen, where nothing raises — the app
silently fell back to defaults and started with no size groups at all.

`sys.frozen` / `sys._MEIPASS` are faked against a directory laid out like a real
PyInstaller 6 .app bundle, so no build is needed.
"""
import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def frozen_bundle(tmp_path, monkeypatch):
    """A directory shaped like a PyInstaller 6 macOS .app, marked as frozen.

    PyInstaller puts data files in Contents/Frameworks (which is what _MEIPASS
    points at) and leaves only the executable in Contents/MacOS.
    """
    contents = tmp_path / "AlbumStudio.app" / "Contents"
    meipass = contents / "Frameworks"
    macos = contents / "MacOS"
    (meipass / "config").mkdir(parents=True)
    (meipass / "assets" / "fonts").mkdir(parents=True)
    macos.mkdir(parents=True)

    (meipass / "config" / "settings.json").write_text("{}")
    (meipass / "config" / "size_group.json").write_text("{}")
    (meipass / "assets" / "fonts" / "DSEG7ClassicMini-Bold.ttf").write_bytes(b"stub")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(macos / "AlbumStudio"))
    return meipass


def test_frozen_config_dir_finds_the_bundled_config(frozen_bundle):
    from src.utils.paths import get_config_dir

    assert (Path(get_config_dir()) / "settings.json").exists(), (
        "The packaged app cannot see its own bundled config, so it silently "
        "falls back to defaults and ships with no size groups at all."
    )


def test_frozen_assets_dir_finds_the_bundled_font(frozen_bundle):
    from src.utils.paths import get_assets_dir

    assert (Path(get_assets_dir()) / "fonts" / "DSEG7ClassicMini-Bold.ttf").exists(), (
        "The packaged app cannot see the DSEG7 font, so date stamps silently "
        "fall back to Pillow's default bitmap font."
    )


def _qicon_arguments(path: Path):
    """Every argument passed to a QIcon(...) call in the given module."""
    tree = ast.parse(path.read_text())
    return [
        node.args[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "QIcon"
        and node.args
    ]


def test_window_icon_is_not_a_relative_path():
    args = _qicon_arguments(REPO_ROOT / "src" / "main.py")
    assert args, "expected main.py to set a window icon"

    for arg in args:
        assert not isinstance(arg, ast.Constant), (
            "main.py passes QIcon a bare string literal, which resolves against "
            "the working directory — '/' when launched from Finder — so the icon "
            "silently never loads. Build the path from get_assets_dir()."
        )
