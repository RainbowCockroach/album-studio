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
            # readlink, not realpath: realpath resolves against the local
            # drive on Windows ("C:\\Applications"), and would also pass a
            # plain folder named Applications that is not a link at all.
            staged["drop_link"] = os.readlink(f"{srcfolder}/Applications")
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



class TestWindowsInstaller:
    """The Setup.exe must actually be built, and carry the real version."""

    @pytest.fixture
    def built_app(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dist" / "AlbumStudio").mkdir(parents=True)
        (tmp_path / "dist" / "AlbumStudio" / "AlbumStudio.exe").write_text("")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "version.py").write_text(
            '__version_base__ = "1.4"\n__version__ = "1.4.87"\n')

    @pytest.fixture
    def bundle(self, tmp_path, build):
        """A bundle shaped like PyInstaller's: a top-level runtime, Qt's own
        2020 copy in Qt6/bin, and numpy's private hashed copy."""
        b = tmp_path / "_internal"
        qt = b / "PyQt6" / "Qt6" / "bin"
        qt.mkdir(parents=True)
        (b / "numpy.libs").mkdir()
        for path, ver in [(b / "msvcp140.dll", "14.16"), (qt / "MSVCP140.dll", "14.26"),
                          (qt / "VCRUNTIME140.dll", "14.26"),
                          (b / "numpy.libs" / "msvcp140-abc123.dll", "14.40")]:
            path.write_text(ver)
        sys32 = tmp_path / "System32"
        sys32.mkdir()
        for name in build.APP_LOCAL_MSVC_RUNTIME:
            (sys32 / name).write_text("14.50")
        return b, sys32

    def test_runtime_missing_from_the_bundle_is_added(self, build, bundle):
        # torch_cpu.dll imports vcruntime140_threads.dll, which PyInstaller
        # never collected; the build PC had it, a clean PC would not.
        b, sys32 = bundle
        build.upgrade_bundled_msvc_runtime(str(b), str(sys32), self._read)
        assert (b / "vcruntime140_threads.dll").read_text() == "14.50"

    def test_build_machine_without_the_runtime_aborts(self, build, bundle):
        b, sys32 = bundle
        (sys32 / "vcruntime140_threads.dll").unlink()
        with pytest.raises(SystemExit):
            build.upgrade_bundled_msvc_runtime(str(b), str(sys32), self._read)

    @staticmethod
    def _read(path):
        return tuple(int(x) for x in Path(path).read_text().split("."))

    def test_every_old_runtime_copy_is_upgraded(self, build, bundle):
        # Qt's own copy is the one that matters: a preload at startup did not
        # stop Qt loading it, and torch's c10.dll then failed (WinError 1114).
        b, sys32 = bundle
        build.upgrade_bundled_msvc_runtime(str(b), str(sys32), self._read)
        assert (b / "msvcp140.dll").read_text() == "14.50"
        assert (b / "PyQt6" / "Qt6" / "bin" / "MSVCP140.dll").read_text() == "14.50"
        assert (b / "PyQt6" / "Qt6" / "bin" / "VCRUNTIME140.dll").read_text() == "14.50"
        assert (b / "numpy.libs" / "msvcp140-abc123.dll").read_text() == "14.40"

    def test_old_qt_runtime_aborts_the_build(self, build, bundle):
        # The top-level copy alone being current is not enough.
        b, _ = bundle
        (b / "msvcp140.dll").write_text("14.50")
        with pytest.raises(SystemExit):
            build.check_bundled_msvc_runtime(str(b), self._read)

    def test_upgraded_bundle_passes(self, build, bundle):
        b, sys32 = bundle
        build.upgrade_bundled_msvc_runtime(str(b), str(sys32), self._read)
        build.check_bundled_msvc_runtime(str(b), self._read)

    def test_bundle_without_a_runtime_aborts(self, build, tmp_path):
        with pytest.raises(SystemExit):
            build.check_bundled_msvc_runtime(str(tmp_path), self._read)

    @pytest.mark.parametrize("builder", ["build_macos", "build_windows"])
    def test_torchvision_extension_is_collected(self, build, monkeypatch, builder):
        # PyInstaller's hook asks for the pre-0.29 name torchvision._C, so
        # _C_stable was left out: "operator torchvision::nms does not exist".
        monkeypatch.chdir(REPO_ROOT)
        assert "--hidden-import=torchvision._C_stable" in _capture_cmd(
            build, monkeypatch, builder)

    def test_missing_ca_certs_abort(self, build, tmp_path):
        with pytest.raises(SystemExit):
            build.check_bundled_ca_certs(str(tmp_path))
        (tmp_path / "certifi").mkdir()
        (tmp_path / "certifi" / "cacert.pem").write_text("")
        build.check_bundled_ca_certs(str(tmp_path))

    def test_missing_torchvision_extension_aborts(self, build, tmp_path):
        with pytest.raises(SystemExit):
            build.check_bundled_torchvision_ops(str(tmp_path))
        (tmp_path / "_C_stable.pyd").write_text("")
        build.check_bundled_torchvision_ops(str(tmp_path))

    def test_pyinstaller_sees_system32_first(self, build, monkeypatch):
        monkeypatch.setenv("SystemRoot", r"C:\WINDOWS")
        monkeypatch.setenv("PATH", os.pathsep.join(
            [r"C:\jdk\bin", r"C:\WINDOWS\system32", r"C:\tools"]))
        parts = build.system32_first_env()["PATH"].split(os.pathsep)
        assert parts[0] == os.path.join(r"C:\WINDOWS", "System32")
        assert parts[1:] == [r"C:\jdk\bin", r"C:\tools"]

    def test_finds_a_per_user_inno_setup(self, build, monkeypatch, tmp_path):
        # winget --scope user installs here and does not touch PATH.
        iscc = tmp_path / "Programs" / "Inno Setup 6" / "ISCC.exe"
        iscc.parent.mkdir(parents=True)
        iscc.write_text("")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(build.os.path, "exists",
                            lambda p: os.path.normcase(p) == os.path.normcase(str(iscc)))
        monkeypatch.setattr(build.shutil, "which", lambda _: None)
        assert build.find_iscc() == str(iscc)

    def test_missing_inno_setup_aborts(self, build, monkeypatch, built_app):
        # It used to print [SKIP] and exit 0, so CI would publish a release
        # with no installer in it.
        monkeypatch.setattr(build, "find_iscc", lambda: None)
        with pytest.raises(SystemExit):
            build.build_installer()

    def test_aborts_when_the_app_was_never_built(self, build, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(build, "find_iscc", lambda: "ISCC.exe")
        with pytest.raises(SystemExit):
            build.build_installer()

    def test_passes_the_app_version_to_inno(self, build, monkeypatch, built_app):
        # Without it every install registers as installer.iss's placeholder.
        monkeypatch.setattr(build, "find_iscc", lambda: "ISCC.exe")
        calls = []
        monkeypatch.setattr(build.subprocess, "run", lambda cmd, **_kw: calls.append(cmd))
        build.build_installer()
        assert calls == [["ISCC.exe", "/DMyAppVersion=1.4.87", "installer.iss"]]

    def test_iss_lets_the_version_be_overridden(self):
        iss = (REPO_ROOT / "installer.iss").read_text()
        assert "#ifndef MyAppVersion" in iss, (
            "a plain #define in installer.iss overrides nothing: /DMyAppVersion "
            "is ignored and every build ships as the hardcoded version"
        )

    def test_iss_output_name_is_what_build_py_reports(self, build):
        iss = (REPO_ROOT / "installer.iss").read_text()
        assert "OutputBaseFilename=AlbumStudio-Windows-Setup\n" in iss
        assert build.INSTALLER_PATH == "installer_output/AlbumStudio-Windows-Setup.exe"

    def test_iss_refuses_windows_older_than_qt_supports(self):
        iss = (REPO_ROOT / "installer.iss").read_text()
        assert "MinVersion=10.0.17763" in iss

    def test_iss_clears_old_libraries_on_upgrade(self):
        # Setup copies over the old install; without this, DLLs from dropped
        # dependencies linger in _internal/ forever.
        iss = (REPO_ROOT / "installer.iss").read_text()
        assert 'Type: filesandordirs; Name: "{app}\\_internal"' in iss


class TestPinnedRequirements:
    """Every build must install the same versions.

    Unpinned torch/torchvision meant each build took whatever was newest that
    day; torch 2.9+ beside PyQt6 and torchvision 0.29's renamed extension both
    broke "Find similar" on Windows while every test stayed green.
    """

    @pytest.mark.parametrize("name", ["requirements.txt", "requirements-dev.txt"])
    def test_every_requirement_is_an_exact_pin(self, name):
        lines = [l.split("#")[0].strip()
                 for l in (REPO_ROOT / name).read_text().splitlines()]
        reqs = [l for l in lines if l and not l.startswith("-r")]
        loose = [r for r in reqs if "==" not in r]
        assert reqs and not loose, f"{name} has unpinned requirements: {loose}"

    def test_ci_installs_the_pinned_build_tools(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "build-release.yml").read_text()
        assert "pip install -r requirements-dev.txt" in workflow
        assert "pip install pyinstaller" not in workflow, (
            "an unpinned PyInstaller in CI undoes the pin in requirements-dev.txt")


class TestWindowsReleaseWorkflow:
    """CI must ship both the installer and the portable zip."""

    @pytest.fixture
    def release_files(self):
        """The release step's `files:` entries, in order."""
        path = REPO_ROOT / ".github" / "workflows" / "build-release.yml"
        return [line.strip() for line in path.read_text().splitlines()
                if line.strip().startswith("artifacts/")]

    def test_both_windows_downloads_are_published(self, release_files):
        assert "artifacts/AlbumStudio-Windows-Setup.exe" in release_files
        assert "artifacts/AlbumStudio-Windows-Portable.zip" in release_files

    def test_zip_is_listed_before_the_installer(self, release_files):
        # Copies released before the installer existed take the first asset
        # whose name contains "windows" and can only unzip it.
        assert (release_files.index("artifacts/AlbumStudio-Windows-Portable.zip")
                < release_files.index("artifacts/AlbumStudio-Windows-Setup.exe"))

    def test_workflow_installs_inno_setup(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "build-release.yml").read_text()
        assert "choco install innosetup" in workflow


def _capture_cmd_allowing_none(build, monkeypatch):
    captured = {}

    def fake_run(cmd, *_args, **_kwargs):
        captured["cmd"] = cmd
        return None

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    build.build_dmg()
    return captured["cmd"]
