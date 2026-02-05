"""
Auto-update service for Album Studio.
Checks GitHub releases and handles downloading/installing updates.
"""

import json
import os
import sys
import tempfile
import platform
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Optional, Callable
from dataclasses import dataclass

from ..version import __version__, GITHUB_OWNER, GITHUB_REPO


@dataclass
class ReleaseInfo:
    """Information about a GitHub release."""
    version: str
    download_url: str
    release_notes: str
    published_at: str
    asset_name: str
    asset_size: int  # bytes


class UpdateService:
    """Service to check for updates and download new versions."""

    GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

    def __init__(self):
        self.current_version = __version__
        self._latest_release: Optional[ReleaseInfo] = None

    def check_for_updates(self) -> Optional[ReleaseInfo]:
        """
        Check GitHub for the latest release.

        Returns:
            ReleaseInfo if a newer version is available, None otherwise.
        """
        try:
            # Create request with User-Agent header (GitHub API requires it)
            request = Request(
                self.GITHUB_API_URL,
                headers={
                    "User-Agent": f"AlbumStudio/{self.current_version}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )

            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

            # Parse version from tag (remove 'v' prefix if present)
            latest_version = data.get("tag_name", "").lstrip("v")

            if not latest_version:
                print("[UpdateService] No version tag found in release")
                return None

            # Compare versions
            if not self._is_newer_version(latest_version):
                print(f"[UpdateService] Current version {self.current_version} is up to date")
                return None

            # Find the appropriate asset for this platform
            asset = self._find_platform_asset(data.get("assets", []))

            if not asset:
                print(f"[UpdateService] No suitable asset found for {platform.system()}")
                return None

            self._latest_release = ReleaseInfo(
                version=latest_version,
                download_url=asset["browser_download_url"],
                release_notes=data.get("body", ""),
                published_at=data.get("published_at", ""),
                asset_name=asset["name"],
                asset_size=asset.get("size", 0)
            )

            print(f"[UpdateService] New version available: {latest_version}")
            return self._latest_release

        except HTTPError as e:
            print(f"[UpdateService] HTTP error checking for updates: {e.code} {e.reason}")
            return None
        except URLError as e:
            print(f"[UpdateService] Network error checking for updates: {e.reason}")
            return None
        except Exception as e:
            print(f"[UpdateService] Error checking for updates: {e}")
            return None

    def _is_newer_version(self, latest: str) -> bool:
        """Compare version strings to determine if latest is newer."""
        try:
            current_parts = [int(x) for x in self.current_version.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]

            # Pad with zeros to make same length
            max_len = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            latest_parts.extend([0] * (max_len - len(latest_parts)))

            return latest_parts > current_parts
        except ValueError:
            # If parsing fails, assume no update needed
            return False

    def _find_platform_asset(self, assets: list) -> Optional[dict]:
        """Find the download asset for the current platform."""
        system = platform.system().lower()

        # Define patterns for each platform
        if system == "darwin":
            patterns = [".dmg", "macos", "mac", "osx"]
        elif system == "windows":
            patterns = [".zip", "windows", "win"]
        else:
            # Linux or other - try generic patterns
            patterns = [".tar.gz", "linux", system]

        # First try to find exact platform match
        for asset in assets:
            name = asset["name"].lower()
            for pattern in patterns:
                if pattern in name:
                    return asset

        # Fallback: return first asset if only one exists
        if len(assets) == 1:
            return assets[0]

        return None

    def download_update(
        self,
        release: ReleaseInfo,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[str]:
        """
        Download the update to a temporary location.

        Args:
            release: The release info to download
            progress_callback: Optional callback(downloaded_bytes, total_bytes)

        Returns:
            Path to downloaded file, or None if failed
        """
        try:
            # Create temp directory that persists after app closes
            temp_dir = os.path.join(tempfile.gettempdir(), "AlbumStudio_Update")
            os.makedirs(temp_dir, exist_ok=True)

            download_path = os.path.join(temp_dir, release.asset_name)

            print(f"[UpdateService] Downloading {release.asset_name} to {download_path}")

            request = Request(
                release.download_url,
                headers={"User-Agent": f"AlbumStudio/{self.current_version}"}
            )

            with urlopen(request, timeout=300) as response:
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 8192

                with open(download_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)

            print(f"[UpdateService] Download complete: {download_path}")
            return download_path

        except Exception as e:
            print(f"[UpdateService] Error downloading update: {e}")
            return None

    def install_update(self, download_path: str) -> bool:
        """
        Install the downloaded update.

        This creates a script that will:
        1. Wait for current app to close
        2. Replace the app with the new version
        3. Restart the app

        Args:
            download_path: Path to downloaded update file

        Returns:
            True if installation script was created and launched
        """
        system = platform.system().lower()

        try:
            if system == "darwin":
                return self._install_macos(download_path)
            elif system == "windows":
                return self._install_windows(download_path)
            else:
                print(f"[UpdateService] Unsupported platform: {system}")
                return False
        except Exception as e:
            print(f"[UpdateService] Error installing update: {e}")
            return False

    def _install_macos(self, dmg_path: str) -> bool:
        """Install update on macOS."""
        # Get current app location
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle
            app_path = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
            if not app_path.endswith(".app"):
                # Find the .app bundle
                parts = app_path.split(os.sep)
                for i, part in enumerate(parts):
                    if part.endswith(".app"):
                        app_path = os.sep.join(parts[:i + 1])
                        break
        else:
            # Running from source - can't auto-update
            print("[UpdateService] Cannot auto-update when running from source")
            return False

        # Create update script
        script_path = os.path.join(tempfile.gettempdir(), "album_studio_update.sh")

        script_content = f'''#!/bin/bash
# Album Studio Update Script

APP_PATH="{app_path}"
DMG_PATH="{dmg_path}"
APP_NAME="AlbumStudio"

echo "Waiting for Album Studio to close..."
sleep 2

# Mount DMG
echo "Mounting disk image..."
MOUNT_POINT=$(hdiutil attach "$DMG_PATH" -nobrowse -noverify | grep -o '/Volumes/.*' | head -1)

if [ -z "$MOUNT_POINT" ]; then
    echo "Failed to mount DMG"
    exit 1
fi

echo "Mounted at: $MOUNT_POINT"

# Find the .app in the mounted volume
NEW_APP=$(find "$MOUNT_POINT" -maxdepth 1 -name "*.app" | head -1)

if [ -z "$NEW_APP" ]; then
    echo "No .app found in DMG"
    hdiutil detach "$MOUNT_POINT" -quiet
    exit 1
fi

echo "Found app: $NEW_APP"

# Remove old app
echo "Removing old version..."
rm -rf "$APP_PATH"

# Copy new app
echo "Installing new version..."
cp -R "$NEW_APP" "$APP_PATH"

# Unmount DMG
echo "Cleaning up..."
hdiutil detach "$MOUNT_POINT" -quiet

# Remove DMG
rm -f "$DMG_PATH"

# Launch new app
echo "Launching Album Studio..."
open "$APP_PATH"

# Self-destruct this script
rm -f "$0"
'''

        with open(script_path, "w") as f:
            f.write(script_content)

        # Make executable
        os.chmod(script_path, 0o755)

        # Launch script in background
        subprocess.Popen(
            ["bash", script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        print(f"[UpdateService] Update script launched: {script_path}")
        return True

    def _install_windows(self, zip_path: str) -> bool:
        """Install update on Windows."""

        # Get current app location
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
            app_exe = sys.executable
        else:
            print("[UpdateService] Cannot auto-update when running from source")
            return False

        # Create update script (batch file)
        script_path = os.path.join(tempfile.gettempdir(), "album_studio_update.bat")

        # Extract to temp first
        extract_dir = os.path.join(tempfile.gettempdir(), "AlbumStudio_Update_Extract")

        script_content = f'''@echo off
echo Album Studio Update Script
echo.

echo Waiting for Album Studio to close...
timeout /t 3 /nobreak > nul

echo Extracting update...
powershell -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '{extract_dir}' -Force"

echo Installing update...
xcopy /E /Y /Q "{extract_dir}\\AlbumStudio\\*" "{app_dir}\\"

echo Cleaning up...
rmdir /S /Q "{extract_dir}"
del "{zip_path}"

echo Launching Album Studio...
start "" "{app_exe}"

echo Update complete!
del "%~f0"
'''

        with open(script_path, "w") as f:
            f.write(script_content)

        # Launch script
        subprocess.Popen(
            ["cmd", "/c", script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # type: ignore[attr-defined]
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )

        print(f"[UpdateService] Update script launched: {script_path}")
        return True

    def get_current_version(self) -> str:
        """Get the current application version."""
        return self.current_version

    def get_release_url(self) -> str:
        """Get the URL to the GitHub releases page."""
        return f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
