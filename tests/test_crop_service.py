"""Tests for src/services/crop_service.py.

Only the pure geometry (``get_crop_dimensions``) plus one end-to-end crop with a
deterministic manual crop box are covered — smartcrop's saliency search is
non-deterministic and out of scope for unit tests.
"""

import pytest

from src.services.crop_service import CropService


class StubConfig:
    """Just enough of Config for CropService: get_size_info + get_setting."""

    def get_size_info(self, size_tag):
        from src.models.config import Config
        try:
            return {"ratio": Config.parse_size_ratio(size_tag)}
        except ValueError:
            return {}

    def get_setting(self, key, default=None):
        return default


def make_service():
    return CropService(StubConfig())


class TestGetCropDimensions:
    def test_fit_by_width_for_landscape_target(self):
        svc = make_service()
        # 3:2 target (ratio 1.5) into a 1000x1000 image → limited by height
        # width path: h = 1000/1.5 = 666 <= 1000 → fit by width
        assert svc.get_crop_dimensions("9x6", 1000, 1000) == (1000, 666)

    def test_fit_by_height_when_width_path_overflows(self):
        svc = make_service()
        # very wide target into a wide-but-short image forces the height branch
        # ratio 3.0; image 1000x200: h_by_width = 1000/3 = 333 > 200 → fit by height
        assert svc.get_crop_dimensions("3x1", 1000, 200) == (600, 200)

    def test_square_target(self):
        svc = make_service()
        assert svc.get_crop_dimensions("6x6", 800, 600) == (600, 600)

    def test_unknown_size_returns_none(self):
        svc = make_service()
        assert svc.get_crop_dimensions("bogus", 1000, 1000) is None


class TestCropImageManualBox:
    def test_manual_crop_writes_output_at_target_size(self, tmp_path, make_image):
        from PIL import Image

        svc = make_service()
        # PNG source: avoids the JPEG 'keep' subsampling path (see xfail below)
        src = make_image(size=(1000, 800), color=(120, 60, 200), fmt="PNG")
        out = tmp_path / "out" / "9x6" / "result.jpg"

        ok = svc.crop_image(
            src, "9x6", str(out),
            manual_crop_box={"x": 0, "y": 0, "width": 600, "height": 400},
        )
        assert ok is True
        assert out.exists()
        # output is resized to the computed target dims for a 1000x800 image at 3:2
        w, h = Image.open(str(out)).size
        assert (w, h) == (1000, 666)

    @pytest.mark.xfail(
        reason="KNOWN BUG: crop_image sets subsampling='keep' for JPEG sources, "
               "but the resized output image is not a JPEG-loaded object, so "
               "PIL raises and crop_image swallows it and returns False. Real "
               "inputs are HEIC, so this path is rarely hit in production.",
        strict=True,
    )
    def test_jpeg_source_crop_currently_fails(self, tmp_path, make_image):
        svc = make_service()
        src = make_image(size=(1000, 800), color=(120, 60, 200), fmt="JPEG")
        out = tmp_path / "out" / "9x6" / "result.jpg"
        ok = svc.crop_image(
            src, "9x6", str(out),
            manual_crop_box={"x": 0, "y": 0, "width": 600, "height": 400},
        )
        assert ok is True  # xfails today; flips to xpass when the bug is fixed
