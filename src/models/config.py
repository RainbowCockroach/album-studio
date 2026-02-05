import colorsys
import json
import os
import random
import re
from typing import Dict, List, Optional
from ..utils.paths import get_config_dir, get_user_config_dir


def generate_random_color() -> str:
    """Generate a random saturated color as hex string."""
    h = random.random()
    s = 0.6 + random.random() * 0.4  # 60-100% saturation
    v = 0.7 + random.random() * 0.2  # 70-90% brightness
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


class Config:
    """Global configuration manager for albums, sizes, and settings."""

    def __init__(self, config_dir: Optional[str] = None):
        # Bundled config directory (ships with app, read-only)
        self.bundled_config_dir = config_dir if config_dir else get_config_dir()
        # User config directory (for modifications, persists across updates)
        self.user_config_dir = get_user_config_dir()

        self.size_groups: Dict[str, dict] = {}  # Changed from List[str] to dict
        self.sizes: Dict[str, dict] = {}  # Deprecated, kept for backward compatibility
        self.settings: dict = {}
        self.load_all()

    def load_all(self):
        """Load all configuration files."""
        self.load_settings()  # Load settings first (colors are stored here)
        self.load_size_groups()  # Migration may add colors to settings
        self.load_sizes()  # Kept for backward compatibility

    def load_size_groups(self):
        """Load size group definitions from size_group.json with migration support."""
        # Check user config first, then fall back to bundled config
        user_path = os.path.join(self.user_config_dir, "size_group.json")
        bundled_path = os.path.join(self.bundled_config_dir, "size_group.json")

        size_group_path = user_path if os.path.exists(user_path) else bundled_path

        try:
            with open(size_group_path, 'r') as f:
                data = json.load(f)
                # Migrate old format to new format
                self.size_groups = self._migrate_size_group_data(data)
        except FileNotFoundError:
            print("Warning: size_group.json not found. Using empty size groups.")
            self.size_groups = {}
        except json.JSONDecodeError as e:
            print(f"Error loading size_group.json: {e}")
            self.size_groups = {}

    def load_sizes(self):
        """Load size definitions from sizes.json."""
        # Check user config first, then fall back to bundled config
        user_path = os.path.join(self.user_config_dir, "sizes.json")
        bundled_path = os.path.join(self.bundled_config_dir, "sizes.json")

        sizes_path = user_path if os.path.exists(user_path) else bundled_path

        try:
            with open(sizes_path, 'r') as f:
                self.sizes = json.load(f)
        except FileNotFoundError:
            print("Warning: sizes.json not found. Using empty sizes.")
            self.sizes = {}
        except json.JSONDecodeError as e:
            print(f"Error loading sizes.json: {e}")
            self.sizes = {}

    def load_settings(self):
        """Load user settings from settings.json."""
        # Check user config first, then fall back to bundled config
        user_path = os.path.join(self.user_config_dir, "settings.json")
        bundled_path = os.path.join(self.bundled_config_dir, "settings.json")

        settings_path = user_path if os.path.exists(user_path) else bundled_path

        try:
            with open(settings_path, 'r') as f:
                self.settings = json.load(f)
        except FileNotFoundError:
            print("Warning: settings.json not found. Using default settings.")
            self.settings = self._get_default_settings()
        except json.JSONDecodeError as e:
            print(f"Error loading settings.json: {e}")
            self.settings = self._get_default_settings()

    def save_settings(self):
        """Save current settings to user config directory (persists across updates)."""
        settings_path = os.path.join(self.user_config_dir, "settings.json")
        try:
            os.makedirs(self.user_config_dir, exist_ok=True)
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
    def parse_size_dimensions(size_id: str) -> tuple:
        """Parse dimensions from size ID (e.g., '9x6' -> (9, 6)).
        Returns (width, height) as integers.
        Raises ValueError if format is invalid.
        """
        match = re.match(r'(\d+)x(\d+)', size_id, re.IGNORECASE)
        if not match:
            raise ValueError(f"Invalid size ID format: {size_id}. Must be 'NxM' (e.g., '9x6')")
        width = int(match.group(1))
        height = int(match.group(2))
        return (width, height)

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
        """Save size_groups to user config directory (persists across updates)."""
        size_group_path = os.path.join(self.user_config_dir, "size_group.json")
        try:
            os.makedirs(self.user_config_dir, exist_ok=True)
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
        Validates size_ratio format before adding.
        Auto-assigns a color if this is a new size ratio."""
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

        # Auto-assign color if this is a new size ratio (not seen before)
        if not self.get_size_color(size_ratio):
            self.set_size_color(size_ratio, generate_random_color())

        # Add the size (color is stored globally in settings, not here)
        group_data["sizes"].append({
            "ratio": size_ratio,
            "alias": alias or size_ratio
        })

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

    def get_size_color(self, size_ratio: str) -> str:
        """Get the color for a size ratio. Returns empty string if not set."""
        colors = self.settings.get("size_colors", {})
        return colors.get(size_ratio, "")

    def set_size_color(self, size_ratio: str, color: str):
        """Set the color for a size ratio."""
        if "size_colors" not in self.settings:
            self.settings["size_colors"] = {}
        self.settings["size_colors"][size_ratio] = color

    def get_all_size_colors(self) -> Dict[str, str]:
        """Get all size colors as a dictionary."""
        return self.settings.get("size_colors", {})

    def _migrate_size_group_data(self, data: dict) -> dict:
        """Migrate old format to new format with 'ratio' field.
        Also migrates colors from size entries to settings (global per ratio)."""
        migrated = {}
        colors_to_migrate = {}  # Collect colors to migrate to settings

        for group_name, sizes in data.items():
            if isinstance(sizes, list):
                # Old format: list of size ratios (strings)
                migrated_sizes = []
                for size in sizes:
                    migrated_sizes.append({"ratio": size, "alias": size})
                    # Assign color if not already set
                    if size not in colors_to_migrate:
                        colors_to_migrate[size] = generate_random_color()
                migrated[group_name] = {"sizes": migrated_sizes}
            elif isinstance(sizes, dict) and "sizes" in sizes:
                # Migrate from "id" to "ratio" if needed
                migrated_sizes = []
                for size in sizes["sizes"]:
                    if isinstance(size, dict):
                        # If using old "id" field, convert to "ratio"
                        if "id" in size and "ratio" not in size:
                            ratio = size["id"]
                            migrated_sizes.append({
                                "ratio": ratio,
                                "alias": size.get("alias", ratio)
                            })
                        else:
                            ratio = size["ratio"]
                            migrated_sizes.append({
                                "ratio": ratio,
                                "alias": size.get("alias", ratio)
                            })
                        # Migrate color from size entry to global colors
                        if "color" in size and ratio not in colors_to_migrate:
                            colors_to_migrate[ratio] = size["color"]
                        elif ratio not in colors_to_migrate:
                            colors_to_migrate[ratio] = generate_random_color()
                    else:
                        # String format
                        migrated_sizes.append({"ratio": size, "alias": size})
                        if size not in colors_to_migrate:
                            colors_to_migrate[size] = generate_random_color()
                migrated[group_name] = {"sizes": migrated_sizes}
            else:
                # Unknown format: default to empty
                migrated[group_name] = {"sizes": []}

        # Migrate colors to settings (only if not already set)
        if colors_to_migrate:
            if "size_colors" not in self.settings:
                self.settings["size_colors"] = {}
            for ratio, color in colors_to_migrate.items():
                if ratio not in self.settings["size_colors"]:
                    self.settings["size_colors"][ratio] = color

        return migrated

    def get_comparison_directory(self) -> str:
        """
        Get the comparison directory for similarity search.
        Fixed to {workspace_directory}/_past_printed.
        """
        workspace = self.settings.get("workspace_directory", "")
        if workspace:
            return os.path.join(workspace, "_past_printed")
        return ""

    # ========== Size Cost Management ==========

    def get_size_cost(self, size_ratio: str) -> float:
        """Get the cost for a specific size. Returns 0 if not set."""
        costs = self.settings.get("size_costs", {})
        return costs.get(size_ratio, 0)

    def set_size_cost(self, size_ratio: str, cost: float):
        """Set the cost for a specific size."""
        if "size_costs" not in self.settings:
            self.settings["size_costs"] = {}
        self.settings["size_costs"][size_ratio] = cost

    def get_all_size_costs(self) -> Dict[str, float]:
        """Get all size costs as a dictionary."""
        return self.settings.get("size_costs", {})

    def get_all_unique_sizes(self) -> List[str]:
        """Get all unique size ratios from all size groups."""
        unique_sizes = set()
        for group_data in self.size_groups.values():
            if isinstance(group_data, dict) and "sizes" in group_data:
                for size in group_data["sizes"]:
                    unique_sizes.add(size["ratio"])
        return sorted(unique_sizes)

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
            "size_costs": {},  # Maps size ratio (e.g., "5x7") to cost (number)
            "size_colors": {},  # Maps size ratio (e.g., "5x7") to color (hex string)
            "pixels_per_unit": 100,  # Pixels per unit for real-size preview (calibrated by user)
            # Date stamp settings
            "date_stamp_format": "YY.MM.DD",
            "date_stamp_physical_height": 0.2,  # units (same as size tag units)
            "date_stamp_target_dpi": 300,  # pixels per unit (resolution)
            "date_stamp_position": "bottom-right",  # bottom-right, bottom-left, top-right, top-left
            "date_stamp_temp_outer": 1800,  # Outer glow temperature in Kelvin (warmer, 1000-4000)
            "date_stamp_temp_core": 6500,  # Core text temperature in Kelvin (hotter, 4000-10000)
            "date_stamp_glow_intensity": 80,  # 0-100
            "date_stamp_margin": 30,  # pixels from edge
            "date_stamp_opacity": 90  # 0-100
        }
