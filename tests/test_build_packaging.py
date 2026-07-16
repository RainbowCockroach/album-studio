"""Packaging tests for build.py — app icon and the installer disk image.

Both defects these pin were invisible from inside the app: a missing icon file
made PyInstaller quietly substitute its own Python logo, and a DMG built
straight from the .app opened as a single icon in an empty window with nowhere
to drop it. Neither fails a build, so only a test or a human notices.

PyInstaller and hdiutil are never actually run — subprocess is stubbed and the
command line inspected.
"""
import importlib.util
import os
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


@pytest.fixture
def build():
    return _load_build_module()


def _capture_cmd(build, monkeypatch, builder_name):
    """Run a builder with subprocess stubbed; return the command line it built."""
    captured = {}

    def fake_run(cmd, *_args, **_kwargs):
        captured["cmd"] = cmd
        raise AssertionError("unreachable: the real tool must not run")

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    with pytest.raises(AssertionError):
        getattr(build, builder_name)()
    return captured["cmd"]


class TestAppIcon:
    """The icon must be passed explicitly, and never silently skipped."""

    @pytest.mark.parametrize(
        "builder,flag",
        [
            ("build_macos", "--icon=assets/icon.icns"),
            ("build_windows", "--icon=assets/icon.ico"),
        ],
    )
    def test_builder_passes_icon(self, build, monkeypatch, builder, flag):
        monkeypatch.chdir(REPO_ROOT)
        assert flag in _capture_cmd(build, monkeypatch, builder)

    def test_missing_icon_aborts_the_build(self, build, tmp_path, monkeypatch):
        # Previously the flag was dropped on a missing file and the build
        # "succeeded" wearing PyInstaller's default icon.
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            build.require_icon("assets/icon.icns")

    @pytest.mark.parametrize("name", ["icon.icns", "icon.ico", "app_icon.png"])
    def test_icon_assets_are_committed(self, name):
        assert (REPO_ROOT / "assets" / name).exists(), (
            f"assets/{name} is missing — the build now refuses to run without it."
        )

    def test_icns_is_a_real_multi_size_icon(self):
        """A stub or a renamed PNG would build fine and look wrong in Finder."""
        data = (REPO_ROOT / "assets" / "icon.icns").read_bytes()
        assert data[:4] == b"icns"
        # Retina Dock/Finder sizes; without these macOS upscales a small one.
        assert b"ic09" in data or b"ic10" in data


class TestBundledData:
    """Everything the app reads at runtime has to be handed to --add-data."""

    @pytest.mark.parametrize(
        "builder,flag",
        [
            ("build_macos", "--add-data=assets:assets"),
            ("build_windows", "--add-data=assets;assets"),
        ],
    )
    def test_builder_bundles_assets(self, build, monkeypatch, builder, flag):
        monkeypatch.chdir(REPO_ROOT)
        assert flag in _capture_cmd(build, monkeypatch, builder), (
            "assets/ is not bundled, so the DSEG7 font is absent from the app "
            "and date stamps silently render in Pillow's default bitmap font."
        )


class TestDmg:
    """A DMG without an /Applications symlink cannot be dragged into."""

    @pytest.fixture
    def fake_app(self, tmp_path, build, monkeypatch):
        """A stand-in .app so build_dmg has something to package.

        Also pins `ismount` to False. Without it these tests read the real
        machine: a DMG left mounted from testing makes build_dmg try to detach
        it for real and hands every stub an unexpected `hdiutil detach`. Tests
        that want the stale-volume path opt back in explicitly.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(build.os.path, "ismount", lambda _p: False)
        app = tmp_path / "dist" / "AlbumStudio.app"
        (app / "Contents" / "MacOS").mkdir(parents=True)
        (app / "Contents" / "MacOS" / "AlbumStudio").write_text("#!/bin/sh\n")
        return app

    def test_plain_image_gets_an_applications_drop_link(
        self, build, monkeypatch, fake_app
    ):
        monkeypatch.setattr(build.shutil, "which", lambda _: None)  # no create-dmg
        staged = {}

        def fake_run(cmd, *_args, **_kwargs):
            # Inspect the staging dir now: build_dmg deletes it afterwards.
            srcfolder = cmd[cmd.index("-srcfolder") + 1]
            staged["has_app"] = os.path.isdir(f"{srcfolder}/AlbumStudio.app")
            staged["drop_link"] = os.path.realpath(f"{srcfolder}/Applications")
            return None

        monkeypatch.setattr(build.subprocess, "run", fake_run)
        build.build_dmg()

        assert staged["has_app"]
        assert staged["drop_link"] == "/Applications"

    def test_create_dmg_is_preferred_and_gets_a_drop_link(
        self, build, monkeypatch, fake_app
    ):
        monkeypatch.setattr(build.shutil, "which", lambda _: "/opt/homebrew/bin/create-dmg")
        cmd = _capture_cmd_allowing_none(build, monkeypatch)
        assert cmd[0] == "create-dmg"
        assert "--app-drop-link" in cmd

    def test_aborts_when_the_app_was_never_built(self, build, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            build.build_dmg()

    def test_stale_volume_is_unmounted_first(self, build, monkeypatch, fake_app):
        """A DMG left mounted from testing forces create-dmg into a '<name> 1'
        volume, whose window its AppleScript cannot find (exit 64)."""
        monkeypatch.setattr(build.os.path, "ismount", lambda p: p == "/Volumes/Album Studio")
        calls = []
        monkeypatch.setattr(build.shutil, "which", lambda _: "/usr/local/bin/create-dmg")
        monkeypatch.setattr(build.subprocess, "run", lambda cmd, **_kw: calls.append(cmd))

        build.build_dmg()

        assert calls[0] == ["hdiutil", "detach", "/Volumes/Album Studio", "-quiet"], (
            "the stale volume must be detached before create-dmg runs"
        )
        assert calls[1][0] == "create-dmg"

    def test_abandoned_temp_images_are_removed(self, build, monkeypatch, fake_app):
        """An interrupted create-dmg leaves a ~640MB rw.*.dmg in dist/."""
        leftover = Path("dist/rw.4760.AlbumStudio.dmg")
        leftover.write_text("stale scratch image")

        monkeypatch.setattr(build.shutil, "which", lambda _: "/usr/local/bin/create-dmg")
        monkeypatch.setattr(build.subprocess, "run", lambda cmd, **_kw: None)
        build.build_dmg()

        assert not leftover.exists()


class TestReleaseWorkflow:
    """CI must build the DMG through build.py, not by hand.

    Every fix in TestDmg was dead code for months of releases: the workflow
    called `python build.py macos` and then rolled its own `hdiutil create
    -srcfolder dist/AlbumStudio.app`, so build_dmg() and its /Applications
    symlink never ran. Local DMGs were correct and every published one opened
    as a lone icon with nowhere to drop it.
    """

    @pytest.fixture
    def workflow(self):
        path = REPO_ROOT / ".github" / "workflows" / "build-release.yml"
        assert path.exists(), "the release workflow moved — update this test"
        return path.read_text()

    def test_dmg_is_built_through_build_py(self, workflow):
        assert "python build.py dmg" in workflow, (
            "the release workflow does not call `build.py dmg`, so build_dmg() "
            "and the /Applications drop link never run in CI — published DMGs "
            "cannot be dragged to Applications."
        )

    def test_workflow_does_not_roll_its_own_hdiutil(self, workflow):
        # Comments are excluded on purpose: the step is documented by naming the
        # very command it must not run.
        commands = "\n".join(
            line for line in workflow.splitlines() if not line.strip().startswith("#")
        )
        assert "hdiutil" not in commands, (
            "the release workflow calls hdiutil directly. A bare `hdiutil "
            "create -srcfolder <app>` omits the /Applications symlink. Package "
            "via `python build.py dmg` instead."
        )

    def test_uploaded_dmg_is_the_one_build_py_produces(self, build, workflow):
        # build.py names the image dist/AlbumStudio.dmg; the release asset is
        # AlbumStudio-macOS.dmg. A rename bridges them — if either name drifts,
        # the upload step silently ships a stale or missing file.
        assert build.DMG_PATH == "dist/AlbumStudio.dmg"
        assert f"mv {build.DMG_PATH} dist/AlbumStudio-macOS.dmg" in workflow


def _capture_cmd_allowing_none(build, monkeypatch):
    captured = {}

    def fake_run(cmd, *_args, **_kwargs):
        captured["cmd"] = cmd
        return None

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    build.build_dmg()
    return captured["cmd"]
