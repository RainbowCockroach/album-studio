"""Tests for the pure helpers in src/services/date_stamp_service.py.

The actual glow/font rendering is image work and isn't unit-tested here; the
deterministic string/number helpers are.
"""

from datetime import datetime

import pytest

from src.services.date_stamp_service import DateStampService, kelvin_to_rgb


class StubConfig:
    def get_setting(self, key, default=None):
        return default


def service():
    return DateStampService(StubConfig())


class TestKelvinToRgb:
    def test_low_temp_is_warm(self):
        r, g, b = kelvin_to_rgb(1800)
        assert r == 255  # red saturated at low temps
        assert b < r     # little blue

    def test_high_temp_has_full_blue(self):
        # blue saturates at 255 once temp/100 >= 66 (i.e. >= 6600K)
        assert kelvin_to_rgb(10000)[2] == 255

    def test_clamps_below_and_above_range(self):
        assert kelvin_to_rgb(500) == kelvin_to_rgb(1000)
        assert kelvin_to_rgb(99999) == kelvin_to_rgb(40000)

    def test_channels_in_byte_range(self):
        for temp in (1000, 3000, 6500, 10000, 40000):
            for channel in kelvin_to_rgb(temp):
                assert 0 <= channel <= 255


class TestFormatDate:
    def test_yy_mm_dd(self):
        svc = service()
        d = datetime(2023, 12, 25)
        assert svc._format_date(d, "YY.MM.DD") == "23.12.25"

    def test_mm_dd_yy_with_leading_quote(self):
        svc = service()
        d = datetime(2023, 1, 5)
        assert svc._format_date(d, "MM.DD.'YY") == "01.05.'23"

    def test_dd_mm_yy(self):
        svc = service()
        d = datetime(2023, 1, 5)
        assert svc._format_date(d, "DD.MM.'YY") == "05.01.'23"


class TestParsePrintHeight:
    @pytest.mark.parametrize("tag,expected", [
        ("9x6", 6.0),
        ("10x15", 15.0),
        ("4x6", 6.0),
    ])
    def test_parses_height(self, tag, expected):
        assert service()._parse_print_height(tag) == expected

    def test_bad_tag_falls_back_to_default(self):
        assert service()._parse_print_height("garbage") == 6.0


class TestHexToRgb:
    def test_with_hash(self):
        assert DateStampService._hex_to_rgb("#FF7700") == (255, 119, 0)

    def test_without_hash(self):
        assert DateStampService._hex_to_rgb("00ff00") == (0, 255, 0)
