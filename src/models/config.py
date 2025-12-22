import json
import os
from typing import Dict, List


class Config:
    """Global configuration manager for albums, sizes, and settings."""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.albums: Dict[str, List[str]] = {}
        self.sizes: Dict[str, dict] = {}
        self.settings: dict = {}
        self.load_all()

    def load_all(self):
        """Load all configuration files."""
        self.load_albums()
        self.load_sizes()
        self.load_settings()

    def load_albums(self):
        """Load album definitions from albums.json."""
        albums_path = os.path.join(self.config_dir, "albums.json")
        try:
            with open(albums_path, 'r') as f:
                self.albums = json.load(f)
        except FileNotFoundError:
            print(f"Warning: {albums_path} not found. Using empty albums.")
            self.albums = {}
        except json.JSONDecodeError as e:
            print(f"Error loading albums.json: {e}")
            self.albums = {}

    def load_sizes(self):
        """Load size definitions from sizes.json."""
        sizes_path = os.path.join(self.config_dir, "sizes.json")
        try:
            with open(sizes_path, 'r') as f:
                self.sizes = json.load(f)
        except FileNotFoundError:
            print(f"Warning: {sizes_path} not found. Using empty sizes.")
            self.sizes = {}
        except json.JSONDecodeError as e:
            print(f"Error loading sizes.json: {e}")
            self.sizes = {}

    def load_settings(self):
        """Load user settings from settings.json."""
        settings_path = os.path.join(self.config_dir, "settings.json")
        try:
            with open(settings_path, 'r') as f:
                self.settings = json.load(f)
        except FileNotFoundError:
            print(f"Warning: {settings_path} not found. Using default settings.")
            self.settings = self._get_default_settings()
        except json.JSONDecodeError as e:
            print(f"Error loading settings.json: {e}")
            self.settings = self._get_default_settings()

    def save_settings(self):
        """Save current settings to settings.json."""
        settings_path = os.path.join(self.config_dir, "settings.json")
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(settings_path, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings.json: {e}")

    def get_album_names(self) -> List[str]:
        """Get list of all album names."""
        return list(self.albums.keys())

    def get_sizes_for_album(self, album_name: str) -> List[str]:
        """Get available sizes for a specific album."""
        return self.albums.get(album_name, [])

    def get_all_sizes(self) -> List[str]:
        """Get list of all defined sizes."""
        return list(self.sizes.keys())

    def get_size_info(self, size_name: str) -> dict:
        """Get dimensions and ratio for a specific size."""
        return self.sizes.get(size_name, {})

    def get_setting(self, key: str, default=None):
        """Get a specific setting value."""
        return self.settings.get(key, default)

    def set_setting(self, key: str, value):
        """Set a specific setting value."""
        self.settings[key] = value

    @staticmethod
    def _get_default_settings() -> dict:
        """Get default settings if settings.json doesn't exist."""
        return {
            "default_input_folder": "",
            "default_output_folder": "",
            "thumbnail_size": 200,
            "grid_columns": 5,
            "date_format": "%Y%m%d_%H%M%S",
            "supported_formats": [".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]
        }
