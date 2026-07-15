"""Shared pytest fixtures for the Album Studio test suite.

These tests exercise the pure-logic layers (``src/models`` and
``src/services``). Qt's ``offscreen`` platform plugin is forced so nothing ever
tries to reach a display on a headless machine.

The one deliberate exception is ``test_main_window_pull.py``: the 'Pull from
Server' dialog handlers hid a bug that no service-level test could catch, so
they get the ``qapp`` fixture below. Widgets remain untested otherwise.
"""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    """The process-wide QApplication required to construct any widget.

    Session-scoped because Qt allows only one per process; it is intentionally
    never torn down, as destroying it mid-session breaks later widget tests.
    """
    from PyQt6.QtWidgets import QApplication

    yield QApplication.instance() or QApplication([])


@pytest.fixture
def bundled_config_dir(tmp_path):
    """An empty bundled-config directory (ships-with-app, read-only in prod)."""
    d = tmp_path / "bundled_config"
    d.mkdir()
    return str(d)


@pytest.fixture
def user_config_dir(tmp_path, monkeypatch):
    """Redirect Config's user-config directory to a temp dir.

    ``Config`` imports ``get_user_config_dir`` into its own module namespace,
    so we patch it there. Returns the temp path for the test to inspect.
    """
    d = tmp_path / "user_config"
    d.mkdir()
    monkeypatch.setattr(
        "src.models.config.get_user_config_dir", lambda: str(d)
    )
    return str(d)


@pytest.fixture
def make_config(bundled_config_dir, user_config_dir):
    """Factory that builds a Config against isolated temp dirs.

    Optionally seed bundled/user ``settings.json`` and ``size_group.json``
    before construction so migration/merge paths can be exercised.
    """
    from src.models.config import Config

    def _write(directory, name, data):
        if data is not None:
            with open(os.path.join(directory, name), "w") as f:
                json.dump(data, f)

    def _build(bundled_settings=None, user_settings=None,
               bundled_size_group=None, user_size_group=None):
        _write(bundled_config_dir, "settings.json", bundled_settings)
        _write(user_config_dir, "settings.json", user_settings)
        _write(bundled_config_dir, "size_group.json", bundled_size_group)
        _write(user_config_dir, "size_group.json", user_size_group)
        return Config(config_dir=bundled_config_dir)

    return _build


@pytest.fixture
def make_image(tmp_path):
    """Factory that writes a small solid-color JPEG and returns its path."""
    from PIL import Image

    counter = {"n": 0}

    def _make(name=None, size=(120, 80), color=(200, 100, 50), fmt="JPEG"):
        counter["n"] += 1
        if name is None:
            ext = "jpg" if fmt == "JPEG" else fmt.lower()
            name = f"img_{counter['n']}.{ext}"
        path = tmp_path / name
        Image.new("RGB", size, color).save(str(path), fmt)
        return str(path)

    return _make
