"""Tests for src/services/project_manager.py — CRUD, discovery, imports."""

import os

from src.services.project_manager import ProjectManager


def workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    return str(ws)


class TestCrud:
    def test_create_project_builds_folders(self, tmp_path):
        ws = workspace(tmp_path)
        pm = ProjectManager(workspace_directory=ws)
        proj = pm.create_project("2026-06", ws)
        assert proj is not None
        assert os.path.isdir(os.path.join(ws, "2026-06", "input"))
        assert os.path.isdir(os.path.join(ws, "2026-06", "output"))
        assert pm.get_project_names() == ["2026-06"]

    def test_create_duplicate_returns_none(self, tmp_path):
        ws = workspace(tmp_path)
        pm = ProjectManager(workspace_directory=ws)
        pm.create_project("dup", ws)
        assert pm.create_project("dup", ws) is None

    def test_create_in_missing_workspace_returns_none(self, tmp_path):
        pm = ProjectManager(workspace_directory=str(tmp_path))
        assert pm.create_project("x", str(tmp_path / "nonexistent")) is None

    def test_delete_project(self, tmp_path):
        ws = workspace(tmp_path)
        pm = ProjectManager(workspace_directory=ws)
        pm.create_project("gone", ws)
        assert pm.delete_project("gone") is True
        assert pm.get_project_names() == []
        assert pm.delete_project("gone") is False

    def test_save_load_round_trip(self, tmp_path):
        ws = workspace(tmp_path)
        pm = ProjectManager(workspace_directory=ws)
        pm.create_project("2026-06", ws)

        pm2 = ProjectManager(workspace_directory=ws)
        loaded = pm2.load_projects()
        assert isinstance(loaded, list)
        assert pm2.get_project_names() == ["2026-06"]


class TestDiscovery:
    # NOTE: load_projects() returns early when projects.json is absent, so
    # discovery only runs once that file exists. We seed it via save_projects()
    # to exercise the discovery path — mirroring a workspace already in use.

    def test_discovers_dropped_project_folder(self, tmp_path):
        ws = workspace(tmp_path)
        pm = ProjectManager(workspace_directory=ws)
        pm.save_projects()  # create projects.json so load() proceeds to discovery

        # a month folder with an input/ subfolder, never registered
        os.makedirs(os.path.join(ws, "2026-07", "input"))
        pm.load_projects()

        assert "2026-07" in pm.get_project_names()
        # output folder is created for discovered projects
        assert os.path.isdir(os.path.join(ws, "2026-07", "output"))

    def test_skips_reserved_and_dot_folders(self, tmp_path):
        ws = workspace(tmp_path)
        for reserved in ("_past_printed", "printed", ".album-studio-settings"):
            os.makedirs(os.path.join(ws, reserved, "input"), exist_ok=True)
        os.makedirs(os.path.join(ws, ".hidden", "input"))

        pm = ProjectManager(workspace_directory=ws)
        pm.save_projects()
        pm.load_projects()
        assert pm.get_project_names() == []

    def test_folder_without_input_is_not_a_project(self, tmp_path):
        ws = workspace(tmp_path)
        os.makedirs(os.path.join(ws, "random", "notinput"))
        pm = ProjectManager(workspace_directory=ws)
        pm.save_projects()
        pm.load_projects()
        assert pm.get_project_names() == []


class TestImportPrinted:
    def test_import_creates_thumbnails(self, tmp_path):
        ws = workspace(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        from PIL import Image
        Image.new("RGB", (300, 200), (10, 20, 30)).save(str(src / "one.jpg"))
        Image.new("RGB", (300, 200), (40, 50, 60)).save(str(src / "two.png"))

        pm = ProjectManager(workspace_directory=ws)
        stats = pm.import_printed_images(str(src), ws, thumbnail_size=64)

        assert stats["imported"] == 2
        printed = os.path.join(ws, "_past_printed")
        # both saved as .jpg thumbnails, downscaled
        assert set(os.listdir(printed)) == {"one.jpg", "two.jpg"}
        w, h = Image.open(os.path.join(printed, "one.jpg")).size
        assert max(w, h) <= 64

    def test_import_dedupes_colliding_names(self, tmp_path):
        from PIL import Image
        ws = workspace(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        # same base name, different extensions → both map to same .jpg target
        Image.new("RGB", (50, 50), (1, 2, 3)).save(str(src / "pic.jpg"))
        Image.new("RGB", (50, 50), (4, 5, 6)).save(str(src / "pic.png"))

        pm = ProjectManager(workspace_directory=ws)
        stats = pm.import_printed_images(str(src), ws)
        assert stats["imported"] == 2
        printed = os.path.join(ws, "_past_printed")
        assert set(os.listdir(printed)) == {"pic.jpg", "pic_1.jpg"}
