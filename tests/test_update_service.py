"""Tests for the pure logic in src/services/update_service.py.

Version comparison, platform-asset selection and the generated Windows update
scripts are deterministic; the network and actually running a script are out
of scope.
"""

import os

import pytest

from src.services.update_service import UpdateService


@pytest.fixture
def svc():
    s = UpdateService()
    s.current_version = "1.2.3"  # pin so tests don't depend on the real version
    return s


class TestIsNewerVersion:
    @pytest.mark.parametrize("latest", ["1.2.4", "1.3.0", "2.0.0", "1.2.3.1"])
    def test_newer_versions(self, svc, latest):
        assert svc._is_newer_version(latest) is True

    @pytest.mark.parametrize("latest", ["1.2.3", "1.2.2", "1.0.0", "0.9.9"])
    def test_same_or_older_versions(self, svc, latest):
        assert svc._is_newer_version(latest) is False

    def test_shorter_latest_padded_with_zeros(self, svc):
        # "1.2" == "1.2.0" < "1.2.3"
        assert svc._is_newer_version("1.2") is False

    def test_longer_current_than_latest(self, svc):
        svc.current_version = "1.2.3.4"
        assert svc._is_newer_version("1.2.3") is False
        assert svc._is_newer_version("1.2.4") is True

    def test_unparseable_version_returns_false(self, svc):
        assert svc._is_newer_version("v2.0-beta") is False


class TestFindPlatformAsset:
    def _asset(self, name):
        return {"name": name, "browser_download_url": f"https://x/{name}"}

    def test_macos_picks_dmg(self, svc, monkeypatch):
        monkeypatch.setattr("src.services.update_service.platform.system",
                            lambda: "Darwin")
        assets = [self._asset("AlbumStudio-win.zip"),
                  self._asset("AlbumStudio-macos.dmg")]
        assert svc._find_platform_asset(assets)["name"] == "AlbumStudio-macos.dmg"

    WINDOWS_RELEASE = ["AlbumStudio-macOS.dmg",
                       "AlbumStudio-Windows-Portable.zip",
                       "AlbumStudio-Windows-Setup.exe"]

    def _on_windows(self, svc, monkeypatch, installed):
        monkeypatch.setattr("src.services.update_service.platform.system",
                            lambda: "Windows")
        monkeypatch.setattr(svc, "_is_installed_windows", lambda: installed)

    @pytest.mark.parametrize("order", [WINDOWS_RELEASE, WINDOWS_RELEASE[::-1]])
    def test_portable_copy_picks_the_zip(self, svc, monkeypatch, order):
        # Running Setup from a portable folder would install a second copy.
        self._on_windows(svc, monkeypatch, installed=False)
        assets = [self._asset(n) for n in order]
        assert svc._find_platform_asset(assets)["name"] == "AlbumStudio-Windows-Portable.zip"

    @pytest.mark.parametrize("order", [WINDOWS_RELEASE, WINDOWS_RELEASE[::-1]])
    def test_installed_copy_picks_the_installer(self, svc, monkeypatch, order):
        # Unzipping over an installed copy leaves Settings > Apps on the old
        # version and skips the installer's cleanup of stale files.
        self._on_windows(svc, monkeypatch, installed=True)
        assets = [self._asset(n) for n in order]
        assert svc._find_platform_asset(assets)["name"] == "AlbumStudio-Windows-Setup.exe"

    def test_installed_copy_never_falls_back_to_a_zip(self, svc, monkeypatch):
        # A release with no installer must not hand an installed copy the zip,
        # not even through the single-asset fallback.
        self._on_windows(svc, monkeypatch, installed=True)
        assert svc._find_platform_asset(
            [self._asset("AlbumStudio-Windows-Portable.zip")]) is None

    def test_single_asset_fallback(self, svc, monkeypatch):
        monkeypatch.setattr("src.services.update_service.platform.system",
                            lambda: "Darwin")
        assets = [self._asset("only-one.bin")]
        assert svc._find_platform_asset(assets)["name"] == "only-one.bin"

    def test_no_match_multiple_assets_returns_none(self, svc, monkeypatch):
        monkeypatch.setattr("src.services.update_service.platform.system",
                            lambda: "Darwin")
        assets = [self._asset("a-win.zip"), self._asset("b-linux.tar.gz")]
        assert svc._find_platform_asset(assets) is None


class TestIsInstalledWindows:
    def test_folder_with_inno_uninstaller_is_installed(self, tmp_path):
        (tmp_path / "AlbumStudio.exe").write_text("")
        (tmp_path / "unins000.exe").write_text("")
        assert UpdateService._is_installed_windows(str(tmp_path)) is True

    def test_unzipped_folder_is_portable(self, tmp_path):
        (tmp_path / "AlbumStudio.exe").write_text("")
        assert UpdateService._is_installed_windows(str(tmp_path)) is False


class TestWindowsUpdateScripts:
    def test_setup_script_upgrades_silently_then_relaunches(self):
        script = UpdateService._windows_setup_script(
            r"C:\Temp\AlbumStudio-Windows-Setup.exe", r"C:\App\AlbumStudio.exe")
        install = next(l for l in script.splitlines() if "Setup.exe\" /VERYSILENT" in l)
        # /wait: relaunching before Setup finishes would start the old copy.
        assert install.startswith('start "" /wait ')
        assert "/SUPPRESSMSGBOXES" in install
        # A silent install skips Setup's own "Launch" step, so the script must.
        assert script.index(install) < script.index(r'start "" "C:\App\AlbumStudio.exe"')

    def test_zip_script_copies_from_the_extract_root(self, monkeypatch):
        # The release zip is built with `Compress-Archive dist/AlbumStudio/*`,
        # so AlbumStudio.exe sits at its top level. Copying from an
        # AlbumStudio\ subfolder found nothing and relaunched the old version.
        monkeypatch.setattr("src.services.update_service.tempfile.gettempdir",
                            lambda: r"C:\Temp")
        script = UpdateService._windows_zip_script(
            r"C:\Temp\AlbumStudio-Windows-Portable.zip", r"C:\App",
            r"C:\App\AlbumStudio.exe")
        copy = next(l for l in script.splitlines() if l.startswith("xcopy"))
        extract_dir = os.path.join(r"C:\Temp", "AlbumStudio_Update_Extract")
        assert copy == f'xcopy /E /Y /Q "{extract_dir}\\*" "C:\\App\\"'

    def test_install_windows_routes_by_download_type(self, svc, monkeypatch, tmp_path):
        monkeypatch.setattr("src.services.update_service.sys.frozen", True, raising=False)
        monkeypatch.setattr("src.services.update_service.sys.executable",
                            str(tmp_path / "AlbumStudio.exe"))
        monkeypatch.setattr("src.services.update_service.tempfile.gettempdir",
                            lambda: str(tmp_path))
        monkeypatch.setattr("src.services.update_service.subprocess.Popen",
                            lambda *a, **k: None)
        # Popen's Windows-only flags are absent on other platforms.
        monkeypatch.setattr("src.services.update_service.subprocess.CREATE_NEW_PROCESS_GROUP",
                            0, raising=False)
        monkeypatch.setattr("src.services.update_service.subprocess.DETACHED_PROCESS",
                            0, raising=False)
        script = tmp_path / "album_studio_update.bat"

        assert svc._install_windows(str(tmp_path / "AlbumStudio-Windows-Setup.exe"))
        assert "/VERYSILENT" in script.read_text()

        assert svc._install_windows(str(tmp_path / "AlbumStudio-Windows-Portable.zip"))
        assert "Expand-Archive" in script.read_text()


class TestSimpleAccessors:
    def test_get_current_version(self, svc):
        assert svc.get_current_version() == "1.2.3"

    def test_get_release_url_is_github(self, svc):
        url = svc.get_release_url()
        assert url.startswith("https://github.com/")
        assert "releases" in url
