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

        self.size_groups: Dict[str, dict] = {}
        # Per-size metadata keyed by size ratio (e.g. "9x6"): {"cost": float, "color": str}.
        # A "9x6" used in multiple groups shares one cost and color.
        self.size_metadata: Dict[str, dict] = {}
        self.settings: dict = {}
        self.load_all()

    def load_all(self):
        """Load all configuration files."""
        self.load_settings()  # Load first — legacy size_costs/size_colors may live here
        self.load_size_groups()  # Migrates legacy fields out of settings into size_metadata

    def load_size_groups(self):
        """Load groups + per-size metadata from size_group.json.

        Format:
            {"groups": {<group>: {"sizes": [{"ratio", "alias"}, ...]}},
             "sizes":  {<ratio>: {"cost": float, "color": str}}}

        Legacy formats are migrated automatically. Legacy size_costs/size_colors
        in settings.json are pulled into size_metadata.
        """
        user_path = os.path.join(self.user_config_dir, "size_group.json")
        bundled_path = os.path.join(self.bundled_config_dir, "size_group.json")
        path = user_path if os.path.exists(user_path) else bundled_path

        data = self._read_json(path) or {}
        self.size_groups, self.size_metadata = self._migrate_size_group_data(data)


    def load_settings(self):
        """Load settings.json by merging bundled defaults with user overrides.

        New keys added to bundled settings reach existing users on upgrade,
        while user-modified values still take precedence.
        """
        bundled_path = os.path.join(self.bundled_config_dir, "settings.json")
        user_path = os.path.join(self.user_config_dir, "settings.json")

        bundled = self._read_json(bundled_path) or self._get_default_settings()
        user = self._read_json(user_path) or {}

        self.settings = {**bundled, **user}

    def _read_json(self, path: str) -> Optional[dict]:
        """Read a JSON file, returning None if missing or invalid."""
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error loading {os.path.basename(path)}: {e}")
            return None

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

    def get_size_info(self, size_name: str) -> dict:
        """Get ratio for a specific size, parsed from its name (e.g. '9x6' -> 1.5)."""
        try:
            return {"ratio": self.parse_size_ratio(size_name)}
        except ValueError:
            return {}

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
        """Save groups + size_metadata to user config directory (persists across updates)."""
        size_group_path = os.path.join(self.user_config_dir, "size_group.json")
        payload = {"groups": self.size_groups, "sizes": self.size_metadata}
        try:
            os.makedirs(self.user_config_dir, exist_ok=True)
            with open(size_group_path, 'w') as f:
                json.dump(payload, f, indent=2)
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
        return self.size_metadata.get(size_ratio, {}).get("color", "")

    def set_size_color(self, size_ratio: str, color: str):
        """Set the color for a size ratio."""
        self.size_metadata.setdefault(size_ratio, {})["color"] = color

    def get_all_size_colors(self) -> Dict[str, str]:
        """Get all size colors as a {ratio: color} dictionary."""
        return {r: m["color"] for r, m in self.size_metadata.items() if m.get("color")}

    def _migrate_size_group_data(self, data: dict) -> tuple:
        """Parse size_group.json into (groups, size_metadata).

        Handles three input formats:
          1. New: {"groups": {...}, "sizes": {...}}
          2. Legacy v2: top-level group names with "sizes" lists
          3. Legacy v1: top-level group names mapping to plain ratio lists

        Also pulls legacy size_costs/size_colors from self.settings into size_metadata
        (one-time migration; the keys are removed from settings).
        """
        # Detect new format vs legacy
        if "groups" in data or "sizes" in data:
            raw_groups = data.get("groups", {})
            metadata = dict(data.get("sizes", {}))
        else:
            raw_groups = data
            metadata = {}

        groups: Dict[str, dict] = {}
        seen_ratios = set()

        for group_name, group_data in raw_groups.items():
            sizes_list = []

            if isinstance(group_data, list):
                # Legacy v1: ["9x6", "5x7", ...]
                raw_sizes = [{"ratio": s, "alias": s} for s in group_data]
            elif isinstance(group_data, dict) and "sizes" in group_data:
                raw_sizes = group_data["sizes"]
            else:
                groups[group_name] = {"sizes": []}
                continue

            for size in raw_sizes:
                if isinstance(size, dict):
                    ratio = size.get("ratio") or size.get("id")
                    if not ratio:
                        continue
                    sizes_list.append({"ratio": ratio, "alias": size.get("alias", ratio)})
                    # Pull color from legacy per-size entry
                    if "color" in size:
                        metadata.setdefault(ratio, {}).setdefault("color", size["color"])
                else:
                    ratio = size
                    sizes_list.append({"ratio": ratio, "alias": ratio})
                seen_ratios.add(ratio)

            groups[group_name] = {"sizes": sizes_list}

        # Pull legacy size_costs / size_colors out of settings, then drop them
        legacy_costs = self.settings.pop("size_costs", None)
        legacy_colors = self.settings.pop("size_colors", None)
        if isinstance(legacy_costs, dict):
            for ratio, cost in legacy_costs.items():
                metadata.setdefault(ratio, {}).setdefault("cost", cost)
        if isinstance(legacy_colors, dict):
            for ratio, color in legacy_colors.items():
                metadata.setdefault(ratio, {}).setdefault("color", color)

        # Auto-assign a color for any size that doesn't have one
        for ratio in seen_ratios:
            entry = metadata.setdefault(ratio, {})
            if not entry.get("color"):
                entry["color"] = generate_random_color()

        return groups, metadata

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
        return self.size_metadata.get(size_ratio, {}).get("cost", 0)

    def set_size_cost(self, size_ratio: str, cost: float):
        """Set the cost for a specific size."""
        self.size_metadata.setdefault(size_ratio, {})["cost"] = cost

    def get_all_size_costs(self) -> Dict[str, float]:
        """Get all size costs as a {ratio: cost} dictionary."""
        return {r: m["cost"] for r, m in self.size_metadata.items() if "cost" in m}

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
            "last_project": "",  # Reopened on next launch; see MainWindow.load_projects
            "thumbnail_size": 200,
            "date_format": "%Y%m%d_%H%M%S",
            "supported_formats": [".jpg", ".jpeg", ".png", ".heic", ".JPG", ".JPEG", ".PNG", ".HEIC"],
            "pixels_per_unit": 100,  # Pixels per unit for real-size preview (calibrated by user)
            # Date stamp settings
            "date_stamp_format": "YY.MM.DD",
            "date_stamp_physical_height": 0.2,  # units (same as size tag units)
            "date_stamp_target_dpi": 300,  # pixels per unit (resolution)
            "date_stamp_position": "bottom-right",  # bottom-right, bottom-left, top-right, top-left
            "date_stamp_temp_outer": 1800,  # Outer glow temperature in Kelvin (warmer, 1000-4000)
            "date_stamp_temp_core": 6500,  # Core text temperature in Kelvin (hotter, 4000-10000)
            "date_stamp_glow_intensity": 80,  # 0-100
            "date_stamp_opacity": 90,  # 0-100
            # Server sync (Pull from server) — see docs/SERVER_SYNC.md
            "server_url": "",
            "server_token": ""
        }

    # ========== Config Export/Import ==========

    def export_config(self, filepath: str) -> bool:
        """Export all configuration to a single JSON file.

        Args:
            filepath: Path to save the exported config file.

        Returns:
            True if export succeeded, False otherwise.
        """
        try:
            # Build export data with version for future compatibility
            export_data = {
                "version": 2,
                "size_groups": self.size_groups,
                "size_metadata": self.size_metadata,
                "settings": self.settings
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            print(f"Error exporting config: {e}")
            return False

    def import_config(self, filepath: str) -> tuple[bool, str]:
        """Import configuration from a single JSON file.

        Args:
            filepath: Path to the config file to import.

        Returns:
            Tuple of (success: bool, message: str).
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            # Validate version
            version = import_data.get("version", 0)
            if version < 1:
                return False, "Invalid config file format (missing version)."

            # Import size_groups (+ size_metadata for v2+). _migrate handles all formats.
            if "size_groups" in import_data:
                payload = {
                    "groups": import_data["size_groups"],
                    "sizes": import_data.get("size_metadata", {}),
                }
                self.size_groups, self.size_metadata = self._migrate_size_group_data(payload)
                self.save_size_groups()

            # Import settings (merge with existing to preserve machine-specific settings)
            if "settings" in import_data:
                imported_settings = import_data["settings"]

                # Preserve machine-specific settings that shouldn't be overwritten
                machine_specific_keys = ["workspace_directory", "pixels_per_unit"]
                for key in machine_specific_keys:
                    if key in self.settings:
                        imported_settings[key] = self.settings[key]

                self.settings = imported_settings
                self.save_settings()

            return True, "Configuration imported successfully."
        except json.JSONDecodeError:
            return False, "Invalid JSON file. Please select a valid config file."
        except Exception as e:
            return False, f"Error importing config: {e}"
