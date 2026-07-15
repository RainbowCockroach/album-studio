"""Tests for src/services/crop_service.py.

Only the pure geometry (``get_crop_dimensions``) plus one end-to-end crop with a
deterministic manual crop box are covered — smartcrop's saliency search is
non-deterministic and out of scope for unit tests.

The smartcrop *plumbing* is tested, though, without asserting which crop it
picks: that it analyses a downscaled copy (the fix for a 9s stall on a 12MP
photo) and that the result is memoised. Both are asserted through a stub
smartcrop, so they pin the contract rather than the saliency heuristic.
"""

import pytest

from src.services.crop_service import (CropService, SMARTCROP_ANALYSIS_SIZE,
                                       clear_smart_crop_memo)


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


@pytest.fixture(autouse=True)
def _clear_memo():
    """The smartcrop memo is module-level, so it would leak between tests."""
    clear_smart_crop_memo()
    yield
    clear_smart_crop_memo()


class SpySmartCrop:
    """Records every image smartcrop is asked to analyse.

    Returns a fixed top-left box so tests stay deterministic; the real
    saliency search is not what is under test here.
    """

    def __init__(self):
        self.calls = []

    def crop(self, image, width, height):
        self.calls.append({"size": image.size, "width": width,
                           "height": height})
        return {"top_crop": {"x": 0, "y": 0, "width": width, "height": height}}


class TestSmartCropPrescale:
    """The 9s-per-photo fix: analyse a downscaled copy, not the full image.

    Smartcrop's own prescale never fires here — get_crop_dimensions asks for the
    largest crop that fits, so its internal scale is 1.0 and it would chew
    through every pixel of a 12MP photo.
    """

    def test_analysis_image_is_downscaled(self, make_image):
        svc = make_service()
        spy = SpySmartCrop()
        svc.smartcrop = spy

        src = make_image(size=(4000, 3000), fmt="JPEG")
        svc.get_crop_box(src, "9x6")

        assert len(spy.calls) == 1
        assert max(spy.calls[0]["size"]) == SMARTCROP_ANALYSIS_SIZE

    def test_small_image_is_not_upscaled_for_analysis(self, make_image):
        svc = make_service()
        spy = SpySmartCrop()
        svc.smartcrop = spy

        src = make_image(size=(600, 400), fmt="JPEG")
        svc.get_crop_box(src, "9x6")

        assert spy.calls[0]["size"] == (600, 400)

    def test_returned_box_is_in_full_resolution_coords(self, make_image):
        """Coordinates must come back in the source's space, not the analysis copy's."""
        svc = make_service()
        svc.smartcrop = SpySmartCrop()

        src = make_image(size=(4000, 3000), fmt="JPEG")
        x, y, width, height = svc.get_crop_box(src, "9x6")

        # 3:2 into 4000x3000 fits by width: 4000 x 2666
        assert (width, height) == (4000, 2666)
        assert 0 <= x <= 4000 - width
        assert 0 <= y <= 3000 - height

    def test_box_stays_inside_image(self, make_image):
        """A box mapped back up must never overhang the source edge."""
        svc = make_service()

        class BottomRightCrop(SpySmartCrop):
            def crop(self, image, width, height):
                self.calls.append({"size": image.size})
                # Hug the far corner, where rounding error would push it over.
                return {"top_crop": {"x": image.size[0] - width,
                                     "y": image.size[1] - height,
                                     "width": width, "height": height}}

        svc.smartcrop = BottomRightCrop()
        src = make_image(size=(4001, 3001), fmt="JPEG")
        x, y, width, height = svc.get_crop_box(src, "9x6")

        assert x + width <= 4001
        assert y + height <= 3001
        assert x >= 0 and y >= 0


class TestSmartCropMemo:
    """Recomputing cost 9s per arrow-key press in the viewer."""

    def test_second_call_reuses_result(self, make_image):
        svc = make_service()
        spy = SpySmartCrop()
        svc.smartcrop = spy

        src = make_image(size=(2000, 1500), fmt="JPEG")
        first = svc.get_crop_box(src, "9x6")
        second = svc.get_crop_box(src, "9x6")

        assert first == second
        assert len(spy.calls) == 1, "smartcrop ran twice for the same image"

    def test_export_reuses_the_box_the_viewer_previewed(self, tmp_path, make_image):
        """crop_image must not re-derive a box get_crop_box already chose."""
        svc = make_service()
        spy = SpySmartCrop()
        svc.smartcrop = spy

        src = make_image(size=(2000, 1500), fmt="JPEG")
        svc.get_crop_box(src, "9x6")  # the viewer's preview
        ok = svc.crop_image(src, "9x6", str(tmp_path / "out.jpg"))  # the export

        assert ok is True
        assert len(spy.calls) == 1

    def test_different_size_tag_recomputes(self, make_image):
        svc = make_service()
        spy = SpySmartCrop()
        svc.smartcrop = spy

        src = make_image(size=(2000, 1500), fmt="JPEG")
        svc.get_crop_box(src, "9x6")
        svc.get_crop_box(src, "6x6")

        assert len(spy.calls) == 2

    def test_modified_file_recomputes(self, make_image, tmp_path):
        """Keyed by mtime: a rotated file's old box points at pixels that moved."""
        import os
        from PIL import Image

        svc = make_service()
        spy = SpySmartCrop()
        svc.smartcrop = spy

        src = make_image(size=(2000, 1500), fmt="JPEG")
        svc.get_crop_box(src, "9x6")

        Image.new("RGB", (1500, 2000), (10, 20, 30)).save(src, "JPEG")
        os.utime(src, (0, 0))  # force a distinct mtime regardless of clock
        svc.get_crop_box(src, "9x6")

        assert len(spy.calls) == 2

    def test_manual_box_never_calls_smartcrop(self, make_image):
        svc = make_service()
        spy = SpySmartCrop()
        svc.smartcrop = spy

        src = make_image(size=(2000, 1500), fmt="JPEG")
        box = svc.get_crop_box(
            src, "9x6", manual_crop_box={"x": 5, "y": 6, "width": 60, "height": 40})

        assert box == (5, 6, 60, 40)
        assert spy.calls == []


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

    def test_jpeg_source_crop(self, tmp_path, make_image):
        from PIL import Image

        svc = make_service()
        src = make_image(size=(1000, 800), color=(120, 60, 200), fmt="JPEG")
        out = tmp_path / "out" / "9x6" / "result.jpg"
        ok = svc.crop_image(
            src, "9x6", str(out),
            manual_crop_box={"x": 0, "y": 0, "width": 600, "height": 400},
        )
        assert ok is True
        assert out.exists()
        w, h = Image.open(str(out)).size
        assert (w, h) == (1000, 666)
