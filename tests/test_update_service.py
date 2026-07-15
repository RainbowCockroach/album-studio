"""Tests for the pure logic in src/services/update_service.py.

Version comparison and platform-asset selection are deterministic; the network
and installer paths are out of scope.
"""

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

    def test_windows_picks_zip(self, svc, monkeypatch):
        monkeypatch.setattr("src.services.update_service.platform.system",
                            lambda: "Windows")
        assets = [self._asset("AlbumStudio-macos.dmg"),
                  self._asset("AlbumStudio-windows.zip")]
        assert svc._find_platform_asset(assets)["name"] == "AlbumStudio-windows.zip"

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


class TestSimpleAccessors:
    def test_get_current_version(self, svc):
        assert svc.get_current_version() == "1.2.3"

    def test_get_release_url_is_github(self, svc):
        url = svc.get_release_url()
        assert url.startswith("https://github.com/")
        assert "releases" in url
