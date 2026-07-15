"""Tests for src/models/config.py — the config parsing/migration layer."""

import pytest

from src.models.config import Config, generate_random_color


# --------------------------------------------------------------- size parsing

class TestSizeParsing:
    def test_parse_ratio_basic(self):
        assert Config.parse_size_ratio("9x6") == 1.5
        assert Config.parse_size_ratio("10x15") == pytest.approx(10 / 15)
        assert Config.parse_size_ratio("6x6") == 1.0

    def test_parse_ratio_case_insensitive(self):
        assert Config.parse_size_ratio("9X6") == 1.5

    def test_parse_ratio_invalid_format_raises(self):
        with pytest.raises(ValueError):
            Config.parse_size_ratio("banana")

    def test_parse_ratio_zero_height_raises(self):
        with pytest.raises(ValueError):
            Config.parse_size_ratio("9x0")

    def test_parse_dimensions(self):
        assert Config.parse_size_dimensions("9x6") == (9, 6)

    def test_parse_dimensions_invalid_raises(self):
        with pytest.raises(ValueError):
            Config.parse_size_dimensions("nope")

    def test_validate_size_id(self):
        assert Config.validate_size_id("9x6") is True
        assert Config.validate_size_id("10X15") is True
        # validate is anchored (^...$), so trailing junk is rejected
        assert Config.validate_size_id("9x6cm") is False
        assert Config.validate_size_id("9-6") is False


# ---------------------------------------------------------------- color util

def test_generate_random_color_is_hex():
    color = generate_random_color()
    assert color.startswith("#")
    assert len(color) == 7
    int(color[1:], 16)  # parses as hex → no exception


# --------------------------------------------------------------- settings merge

class TestSettingsMerge:
    def test_user_overrides_bundled_but_new_keys_survive(self, make_config):
        cfg = make_config(
            bundled_settings={"thumbnail_size": 200, "new_key": "present"},
            user_settings={"thumbnail_size": 320},
        )
        # user value wins
        assert cfg.get_setting("thumbnail_size") == 320
        # bundled-only key still reaches an existing user
        assert cfg.get_setting("new_key") == "present"

    def test_defaults_used_when_no_bundled_file(self, make_config):
        cfg = make_config()  # no files written at all
        # falls back to _get_default_settings()
        assert cfg.get_setting("thumbnail_size") == 200
        assert cfg.get_setting("server_url") == ""

    def test_get_setting_default(self, make_config):
        cfg = make_config()
        assert cfg.get_setting("does_not_exist", "fallback") == "fallback"

    def test_set_setting(self, make_config):
        cfg = make_config()
        cfg.set_setting("thumbnail_size", 320)
        assert cfg.get_setting("thumbnail_size") == 320


# ------------------------------------------------------------------ migration

class TestSizeGroupMigration:
    def test_new_format(self, make_config):
        cfg = make_config(user_size_group={
            "groups": {"A4": {"sizes": [{"ratio": "9x6", "alias": "postcard"}]}},
            "sizes": {"9x6": {"cost": 1.5, "color": "#abcdef"}},
        })
        assert cfg.get_size_group_names() == ["A4"]
        assert cfg.get_sizes_for_size_groups("A4") == ["9x6"]
        assert cfg.get_size_alias("A4", "9x6") == "postcard"
        assert cfg.get_size_cost("9x6") == 1.5
        assert cfg.get_size_color("9x6") == "#abcdef"

    def test_legacy_v2_top_level_groups_with_sizes(self, make_config):
        cfg = make_config(user_size_group={
            "A4": {"sizes": [{"ratio": "9x6", "alias": "pc"}]},
        })
        assert cfg.get_size_group_names() == ["A4"]
        assert cfg.get_sizes_for_size_groups("A4") == ["9x6"]
        # missing color is auto-assigned during migration
        assert cfg.get_size_color("9x6") != ""

    def test_legacy_v1_plain_ratio_lists(self, make_config):
        cfg = make_config(user_size_group={"A4": ["9x6", "5x7"]})
        assert cfg.get_sizes_for_size_groups("A4") == ["9x6", "5x7"]
        # alias defaults to the ratio itself
        assert cfg.get_size_alias("A4", "9x6") == "9x6"

    def test_legacy_per_size_color_pulled_into_metadata(self, make_config):
        cfg = make_config(user_size_group={
            "A4": {"sizes": [{"ratio": "9x6", "alias": "pc", "color": "#123456"}]},
        })
        assert cfg.get_size_color("9x6") == "#123456"

    def test_legacy_costs_colors_pulled_from_settings(self, make_config):
        cfg = make_config(
            user_settings={
                "size_costs": {"9x6": 2.0},
                "size_colors": {"9x6": "#0f0f0f"},
            },
            user_size_group={"A4": ["9x6"]},
        )
        assert cfg.get_size_cost("9x6") == 2.0
        assert cfg.get_size_color("9x6") == "#0f0f0f"
        # legacy keys are removed from settings after migration
        assert "size_costs" not in cfg.settings
        assert "size_colors" not in cfg.settings

    def test_empty_data_yields_no_groups(self, make_config):
        cfg = make_config()
        assert cfg.get_size_group_names() == []

    def test_malformed_group_value_becomes_empty_sizes(self, make_config):
        # a group mapping to a bare string is neither list nor {"sizes": ...}
        cfg = make_config(user_size_group={"Weird": "garbage"})
        assert cfg.get_sizes_for_size_groups("Weird") == []


# --------------------------------------------------------------- cost / color

class TestCostColorApi:
    def test_cost_defaults_to_zero(self, make_config):
        cfg = make_config()
        assert cfg.get_size_cost("9x6") == 0

    def test_set_and_get_cost_color(self, make_config):
        cfg = make_config()
        cfg.set_size_cost("9x6", 3.25)
        cfg.set_size_color("9x6", "#ff0000")
        assert cfg.get_size_cost("9x6") == 3.25
        assert cfg.get_size_color("9x6") == "#ff0000"

    def test_cost_color_shared_across_groups_by_ratio(self, make_config):
        cfg = make_config(user_size_group={
            "A4": {"sizes": [{"ratio": "9x6", "alias": "big"}]},
            "A5": {"sizes": [{"ratio": "9x6", "alias": "small"}]},
        })
        cfg.set_size_cost("9x6", 5.0)
        # same ratio in a different group sees the same cost
        assert cfg.get_size_cost("9x6") == 5.0
        # but aliases remain per-group
        assert cfg.get_size_alias("A4", "9x6") == "big"
        assert cfg.get_size_alias("A5", "9x6") == "small"

    def test_all_size_costs_and_colors(self, make_config):
        cfg = make_config()
        cfg.set_size_cost("9x6", 1.0)
        cfg.set_size_color("9x6", "#111111")
        assert cfg.get_all_size_costs() == {"9x6": 1.0}
        assert cfg.get_all_size_colors() == {"9x6": "#111111"}


# ---------------------------------------------------------- group mutation ops

class TestGroupMutation:
    def test_add_remove_rename_group(self, make_config):
        cfg = make_config()
        cfg.add_size_group("A4")
        assert "A4" in cfg.get_size_group_names()
        cfg.rename_size_group("A4", "A5")
        assert cfg.get_size_group_names() == ["A5"]
        cfg.remove_size_group("A5")
        assert cfg.get_size_group_names() == []

    def test_add_size_validates_format(self, make_config):
        cfg = make_config()
        cfg.add_size_group("A4")
        with pytest.raises(ValueError):
            cfg.add_size_to_group("A4", "not-a-size", "alias")

    def test_add_size_auto_assigns_color_and_dedupes(self, make_config):
        cfg = make_config()
        cfg.add_size_group("A4")
        cfg.add_size_to_group("A4", "9x6", "pc")
        assert cfg.get_size_color("9x6") != ""  # auto color
        # adding the same ratio again is a no-op
        cfg.add_size_to_group("A4", "9x6", "duplicate")
        assert cfg.get_sizes_for_size_groups("A4") == ["9x6"]

    def test_get_all_unique_sizes_sorted(self, make_config):
        cfg = make_config(user_size_group={
            "A4": ["9x6", "5x7"],
            "A5": ["5x7", "4x6"],
        })
        assert cfg.get_all_unique_sizes() == ["4x6", "5x7", "9x6"]


# ------------------------------------------------------------ derived helpers

def test_get_comparison_directory(make_config):
    cfg = make_config(user_settings={"workspace_directory": "/ws"})
    assert cfg.get_comparison_directory().replace("\\", "/") == "/ws/_past_printed"


def test_get_comparison_directory_empty_when_no_workspace(make_config):
    cfg = make_config()
    assert cfg.get_comparison_directory() == ""


def test_get_size_info(make_config):
    cfg = make_config()
    assert cfg.get_size_info("9x6") == {"ratio": 1.5}
    assert cfg.get_size_info("bogus") == {}


# ---------------------------------------------------------- export / import

class TestExportImport:
    def test_round_trip_preserves_groups_and_costs(self, make_config, tmp_path):
        cfg = make_config(user_size_group={
            "A4": {"sizes": [{"ratio": "9x6", "alias": "pc"}]},
        })
        cfg.set_size_cost("9x6", 4.0)
        out = tmp_path / "export.json"
        assert cfg.export_config(str(out)) is True

        cfg2 = make_config()  # fresh, empty
        ok, _ = cfg2.import_config(str(out))
        assert ok is True
        assert cfg2.get_sizes_for_size_groups("A4") == ["9x6"]
        assert cfg2.get_size_cost("9x6") == 4.0

    def test_import_rejects_missing_version(self, make_config, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text('{"size_groups": {}}')
        cfg = make_config()
        ok, msg = cfg.import_config(str(bad))
        assert ok is False
        assert "version" in msg.lower()

    def test_import_rejects_invalid_json(self, make_config, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        cfg = make_config()
        ok, msg = cfg.import_config(str(bad))
        assert ok is False
        assert "json" in msg.lower()

    def test_import_preserves_machine_specific_settings(self, make_config, tmp_path):
        cfg = make_config(user_settings={
            "workspace_directory": "/my/machine",
            "pixels_per_unit": 137,
        })
        out = tmp_path / "export.json"
        cfg.export_config(str(out))

        # a config on a *different* machine
        other = make_config(user_settings={
            "workspace_directory": "/other/machine",
            "pixels_per_unit": 999,
        })
        other.import_config(str(out))
        # imported settings must not clobber this machine's workspace/calibration
        assert other.get_setting("workspace_directory") == "/other/machine"
        assert other.get_setting("pixels_per_unit") == 999
