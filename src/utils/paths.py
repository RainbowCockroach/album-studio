"""
Platform-specific path utilities for Album Studio.
Ensures data persists across app updates by using proper user directories.
"""

import os
import sys
import shutil
import platform
from pathlib import Path


def get_user_data_dir() -> str:
    """
    Get the platform-specific user data directory for Album Studio.

    Data stored here persists across app updates.

    Returns:
        Path to user data directory (e.g., ~/Library/Application Support/AlbumStudio on macOS)
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:  # Linux and others
        base = Path.home() / ".local" / "share"

    app_data_dir = base / "AlbumStudio"

    # Create directory if it doesn't exist
    app_data_dir.mkdir(parents=True, exist_ok=True)

    return str(app_data_dir)


def get_app_bundle_dir() -> str:
    """
    Get the directory where the application is installed.

    This is where the old 'data/' folder was stored (inside the app bundle).
    Used for migration only.

    Returns:
        Path to app bundle directory
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return os.path.dirname(sys.executable)
    else:
        # Running from source - use project root
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def migrate_old_data():
    """
    Migrate data from old location (inside app bundle) to new user data directory.

    This runs once on first launch after update to preserve existing user data.
    Only copies if:
    1. Old data exists in app bundle
    2. New location doesn't have the data yet
    """
    user_data_dir = get_user_data_dir()
    old_data_dir = os.path.join(get_app_bundle_dir(), "data")

    # Check if old data exists
    if not os.path.exists(old_data_dir):
        return

    # Migration targets
    migrations = [
        ("projects.json", "projects.json"),
        ("projects", "projects"),  # Entire projects folder
    ]

    migrated_any = False

    for old_name, new_name in migrations:
        old_path = os.path.join(old_data_dir, old_name)
        new_path = os.path.join(user_data_dir, new_name)

        # Skip if old doesn't exist
        if not os.path.exists(old_path):
            continue

        # Skip if new already exists (don't overwrite)
        if os.path.exists(new_path):
            continue

        # Perform migration
        try:
            if os.path.isdir(old_path):
                shutil.copytree(old_path, new_path)
                print(f"[Migration] Copied directory {old_name} to user data directory")
            else:
                shutil.copy2(old_path, new_path)
                print(f"[Migration] Copied {old_name} to user data directory")

            migrated_any = True
        except Exception as e:
            print(f"[Migration] Warning: Failed to migrate {old_name}: {e}")

    if migrated_any:
        print(f"[Migration] Data migrated to: {user_data_dir}")
        print("[Migration] Your projects, tags, and settings have been preserved!")


def get_config_dir() -> str:
    """
    Get the directory where config files are stored.

    Config files (size_group.json, settings.json, sizes.json) are shipped with the app
    and should remain in the app bundle. However, user modifications should be saved
    to the user data directory.

    Returns:
        Path to config directory (inside app bundle)
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - config bundled with app
        return os.path.join(os.path.dirname(sys.executable), "config")
    else:
        # Running from source
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config"
        )


def get_user_config_dir() -> str:
    """
    Get directory for user-modified config files.

    When users modify config through the UI, changes are saved here
    instead of modifying the bundled config files.

    Returns:
        Path to user config directory
    """
    user_config = os.path.join(get_user_data_dir(), "config")
    os.makedirs(user_config, exist_ok=True)
    return user_config
