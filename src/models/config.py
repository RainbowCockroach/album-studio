import json
import os
import re
from typing import Dict, List


class Config:
    """Global configuration manager for albums, sizes, and settings."""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.size_groups: Dict[str, dict] = {}  # Changed from List[str] to dict
        self.sizes: Dict[str, dict] = {}  # Deprecated, kept for backward compatibility
        self.settings: dict = {}
        self.load_all()

    def load_all(self):
        """Load all configuration files."""
        self.load_size_groups()
        self.load_sizes()  # Kept for backward compatibility
        self.load_settings()

    def load_size_groups(self):
        """Load size group definitions from size_group.json with migration support."""
        size_group_path = os.path.join(self.config_dir, "size_group.json")
        try:
            with open(size_group_path, 'r') as f:
                data = json.load(f)
                # Migrate old format to new format
                self.size_groups = self._migrate_size_group_data(data)
        except FileNotFoundError:
            print(f"Warning: {size_group_path} not found. Using empty size groups.")
            self.size_groups = {}
        except json.JSONDecodeError as e:
            print(f"Error loading size_group.json: {e}")
            self.size_groups = {}

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

    def get_size_group_names(self) -> List[str]:
        """Get list of all size group names."""
        return list(self.size_groups.keys())

    def get_sizes_for_size_groups(self, album_name: str) -> List[str]:
        """Get available sizes for a specific album (returns size ratios only)."""
        group_data = self.size_groups.get(album_name, {})
        if isinstance(group_data, dict) and "sizes" in group_data:
            # New format: extract ratios from list of dicts
            return [size["ratio"] for size in group_data["sizes"]]
        return []  # Empty if group doesn't exist or invalid format

    def get_all_sizes(self) -> List[str]:
        """Get list of all defined sizes."""
        return list(self.sizes.keys())

    def get_size_info(self, size_name: str) -> dict:
        """Get dimensions and ratio for a specific size (parsed from size_name)."""
        try:
            ratio = self.parse_size_ratio(size_name)
            return {"ratio": ratio}
        except ValueError:
            # Fall back to sizes.json if it exists (backward compatibility)
            return self.sizes.get(size_name, {})

    def get_setting(self, key: str, default=None):
        """Get a specific setting value."""
        return self.settings.get(key, default)

    def set_setting(self, key: str, value):
        """Set a specific setting value."""
        self.settings[key] = value

    # ========== New methods for size group management ==========

    @staticmethod
    def parse_size_ratio(size_id: str) -> float:
        """Parse ratio from size ID (e.g., '9x6' -> 1.5).
        Returns first/second always.
        Raises ValueError if format is invalid.
        """
        match = re.match(r'(\d+)x(\d+)', size_id, re.IGNORECASE)
        if not match:
            raise ValueError(f"Invalid size ID format: {size_id}. Must be 'NxM' (e.g., '9x6')")
        width = int(match.group(1))
        height = int(match.group(2))
        if height == 0:
            raise ValueError(f"Invalid size ID: {size_id}. Height cannot be zero.")
        return width / height

    @staticmethod
    def validate_size_id(size_id: str) -> bool:
        """Validate size ID follows NxM pattern."""
        return bool(re.match(r'^\d+x\d+$', size_id, re.IGNORECASE))

    def get_sizes_with_aliases_for_group(self, size_group_name: str) -> List[Dict]:
        """Returns list of {"ratio": str, "alias": str} for a size group."""
        group_data = self.size_groups.get(size_group_name, {})
        if isinstance(group_data, dict) and "sizes" in group_data:
            return group_data["sizes"]
        return []

    def get_size_alias(self, size_group_name: str, size_ratio: str) -> str:
        """Returns the alias for a size within a specific group."""
        sizes = self.get_sizes_with_aliases_for_group(size_group_name)
        for size in sizes:
            if size["ratio"] == size_ratio:
                return size["alias"]
        return size_ratio  # Default to ratio if not found

    def save_size_groups(self):
        """Save size_groups back to config/size_group.json."""
        size_group_path = os.path.join(self.config_dir, "size_group.json")
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(size_group_path, 'w') as f:
                json.dump(self.size_groups, f, indent=2)
        except Exception as e:
            print(f"Error saving size_group.json: {e}")

    def add_size_group(self, name: str):
        """Add new size group with empty sizes list."""
        if name and name not in self.size_groups:
            self.size_groups[name] = {"sizes": []}

    def remove_size_group(self, name: str):
        """Remove a size group."""
        if name in self.size_groups:
            del self.size_groups[name]

    def rename_size_group(self, old_name: str, new_name: str):
        """Rename a size group."""
        if old_name in self.size_groups and new_name and new_name not in self.size_groups:
            self.size_groups[new_name] = self.size_groups.pop(old_name)

    def add_size_to_group(self, size_group_name: str, size_ratio: str, alias: str):
        """Add size to a specific group with an alias.
        Validates size_ratio format before adding."""
        if not self.validate_size_id(size_ratio):
            raise ValueError(f"Invalid size ratio format: {size_ratio}. Must be 'NxM' (e.g., '9x6')")

        if size_group_name not in self.size_groups:
            return

        group_data = self.size_groups[size_group_name]
        if "sizes" not in group_data:
            group_data["sizes"] = []

        # Check if size already exists in group
        for size in group_data["sizes"]:
            if size["ratio"] == size_ratio:
                return  # Size already exists, don't add duplicate

        # Add the size
        group_data["sizes"].append({"ratio": size_ratio, "alias": alias or size_ratio})

    def remove_size_from_group(self, size_group_name: str, size_ratio: str):
        """Remove size from a specific group."""
        if size_group_name not in self.size_groups:
            return

        group_data = self.size_groups[size_group_name]
        if "sizes" in group_data:
            group_data["sizes"] = [s for s in group_data["sizes"] if s["ratio"] != size_ratio]

    def update_size_alias(self, size_group_name: str, size_ratio: str, new_alias: str):
        """Update the alias for a size in a specific group."""
        if size_group_name not in self.size_groups:
            return

        group_data = self.size_groups[size_group_name]
        if "sizes" in group_data:
            for size in group_data["sizes"]:
                if size["ratio"] == size_ratio:
                    size["alias"] = new_alias or size_ratio
                    break

    def _migrate_size_group_data(self, data: dict) -> dict:
        """Migrate old format to new format with 'ratio' field."""
        migrated = {}
        for group_name, sizes in data.items():
            if isinstance(sizes, list):
                # Old format: list of size ratios (strings)
                migrated[group_name] = {
                    "sizes": [{"ratio": size, "alias": size} for size in sizes]
                }
            elif isinstance(sizes, dict) and "sizes" in sizes:
                # Migrate from "id" to "ratio" if needed
                migrated_sizes = []
                for size in sizes["sizes"]:
                    if isinstance(size, dict):
                        # If using old "id" field, convert to "ratio"
                        if "id" in size and "ratio" not in size:
                            migrated_sizes.append({
                                "ratio": size["id"],
                                "alias": size.get("alias", size["id"])
                            })
                        else:
                            # Already using "ratio" field
                            migrated_sizes.append(size)
                    else:
                        # String format
                        migrated_sizes.append({"ratio": size, "alias": size})
                migrated[group_name] = {"sizes": migrated_sizes}
            else:
                # Unknown format: default to empty
                migrated[group_name] = {"sizes": []}
        return migrated

    def get_comparison_directory(self) -> str:
        """
        Get the comparison directory for similarity search.
        Defaults to {workspace_directory}/printed if not set.
        """
        comparison_dir = self.settings.get("comparison_directory", "")

        # If not set, default to workspace/printed
        if not comparison_dir:
            workspace = self.settings.get("workspace_directory", "")
            if workspace:
                comparison_dir = os.path.join(workspace, "printed")

        return comparison_dir

    @staticmethod
    def _get_default_settings() -> dict:
        """Get default settings if settings.json doesn't exist."""
        return {
            "workspace_directory": "",
            "default_input_folder": "",
            "default_output_folder": "",
            "thumbnail_size": 200,
            "grid_columns": 5,
            "date_format": "%Y%m%d_%H%M%S",
            "supported_formats": [".jpg", ".jpeg", ".png", ".heic", ".JPG", ".JPEG", ".PNG", ".HEIC"],
            "comparison_directory": ""  # Empty means use {workspace}/printed
        }
