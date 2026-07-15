"""Tests for reopening the last-used project on launch.

The selection logic lives in ``MainWindow.load_projects``, so — as in
``test_main_window_pull.py`` — these bypass the real ``__init__`` (it reads the
user config, scans the workspace and hits the network) and drive the method
against a stub ProjectManager and an in-memory Config.

The awkward part being pinned: ``ProjectToolbar.set_projects`` fills a combo
wired to ``currentTextChanged``, so populating it auto-selects entry 0 and
fires ``project_changed`` -> ``load_project`` -> last_project is overwritten
before the remembered name is ever read. ``load_projects`` therefore has to
read the setting *first*; ``test_remembered_project_survives_combo_autoselect``
is what fails if that read ever slides below ``set_projects``.
"""

import pytest
from PyQt6.QtWidgets import QMainWindow

from src.models.config import Config
from src.models.project import Project
from src.ui.main_window import MainWindow
from src.ui.widgets.image_grid import ImageGrid
from src.ui.widgets.toolbar_bottom import ToolbarBottom
from src.ui.widgets.toolbar_top import ProjectToolbar


class StubProjectManager:
    """Serves a fixed list of projects; no disk, no discovery."""

    def __init__(self, names):
        self.projects = [Project(n, f"/ws/{n}/input", f"/ws/{n}/output")
                         for n in names]
        self.data_dir = "/ws/.album-studio-settings"

    def load_projects(self):
        return self.projects

    def get_project_names(self):
        return [p.name for p in self.projects]

    def get_project_by_name(self, name):
        return next((p for p in self.projects if p.name == name), None)


@pytest.fixture
def config(tmp_path, monkeypatch):
    """A Config that reads and writes settings.json under tmp_path."""
    user_config_dir = tmp_path / "config"
    user_config_dir.mkdir()
    monkeypatch.setattr("src.models.config.get_user_config_dir",
                        lambda: str(user_config_dir))
    return Config()


@pytest.fixture
def window(qapp, config):
    """A MainWindow with a live Qt object and real widgets, but no __init__.

    Real widgets are used deliberately: the project combo's auto-select on
    populate is the behaviour these tests exist to guard, and a stub would not
    reproduce it. ``load_project`` drives the grid and tag panel too, so they
    are real for the same reason — a wrong call should fail here, not pass.
    """
    w = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(w)
    w.config = config
    w.project_toolbar = ProjectToolbar()
    w.image_grid = ImageGrid(config)
    w.tag_panel = ToolbarBottom(config)
    w.current_project = None
    w.update_total_cost = lambda: None  # reads tag state that __init__ would build
    # The one wire connect_signals() would make that matters here: without it
    # the combo's auto-select never reaches load_project and these tests would
    # pass even with the clobbering bug present.
    w.project_toolbar.project_changed.connect(w.on_project_changed)
    yield w
    w.deleteLater()


def load(window, names, monkeypatch):
    """Run load_projects over `names`, with image loading stubbed out."""
    monkeypatch.setattr(Project, "load_images", lambda self, formats: None)
    monkeypatch.setattr(Project, "load_project_data", lambda self, data_dir: None)
    window.project_manager = StubProjectManager(names)
    window.load_projects()


def test_last_project_is_reopened(window, monkeypatch):
    window.config.set_setting("last_project", "2026-05")

    load(window, ["2026-04", "2026-05", "2026-06"], monkeypatch)

    assert window.current_project is not None
    assert window.current_project.name == "2026-05"
    assert window.project_toolbar.get_current_project() == "2026-05", \
        "the dropdown must agree with the loaded project"


def test_remembered_project_survives_combo_autoselect(window, monkeypatch):
    """Filling the combo loads entry 0 first; the remembered pick must still win."""
    window.config.set_setting("last_project", "2026-06")

    load(window, ["2026-04", "2026-05", "2026-06"], monkeypatch)

    assert window.current_project.name == "2026-06"
    assert window.config.get_setting("last_project") == "2026-06", \
        "the autoselected first project clobbered the remembered one"


def test_missing_project_falls_back_to_first(window, monkeypatch):
    """Archived, deleted or renamed away: open the first project instead."""
    window.config.set_setting("last_project", "2026-05")

    load(window, ["2026-04", "2026-06"], monkeypatch)

    assert window.current_project.name == "2026-04"


def test_never_opened_falls_back_to_first(window, monkeypatch):
    """A fresh install has no remembered project."""
    load(window, ["2026-04", "2026-06"], monkeypatch)

    assert window.current_project.name == "2026-04"


def test_no_projects_opens_nothing(window, monkeypatch):
    window.config.set_setting("last_project", "2026-05")

    load(window, [], monkeypatch)

    assert window.current_project is None


def test_opening_a_project_is_remembered(window, monkeypatch, tmp_path):
    load(window, ["2026-04", "2026-06"], monkeypatch)

    window.on_project_changed("2026-06")

    assert window.config.get_setting("last_project") == "2026-06"
    # And it must reach disk, not just the in-memory dict — set_setting alone
    # does not persist.
    assert Config().get_setting("last_project") == "2026-06"


def test_fallback_replaces_the_stale_name(window, monkeypatch):
    """Falling back must not leave the vanished project queued for next launch."""
    window.config.set_setting("last_project", "2026-05")

    load(window, ["2026-04"], monkeypatch)

    assert window.config.get_setting("last_project") == "2026-04"
