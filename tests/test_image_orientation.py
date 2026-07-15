"""Tests for EXIF-orientation handling (``src/utils/image_loader.open_oriented``).

Phone cameras store the raw sensor buffer and record the rotation needed for
display in EXIF tag 274 rather than re-encoding the pixels. Server-pulled JPEGs
keep that tag (``ServerSyncService.download`` writes hash-verified bytes
verbatim and must not rewrite them), so every path that touches pixels has to
apply the tag itself or the photo renders sideways — and, worse, exports that
way permanently, since the crop is saved without an EXIF block to correct it.

Expected geometry is computed with ``numpy.rot90`` rather than Pillow's
``exif_transpose``, so these tests pin the real orientation semantics instead of
agreeing with the implementation's own helper.
"""

from datetime import datetime

import numpy as np
import piexif
import pytest
from PIL import Image

from src.utils.image_loader import ImageLoader, open_oriented


def _asymmetric(width=60, height=40):
    """An image no rotation maps onto itself: each quadrant a distinct color."""
    a = np.zeros((height, width, 3), dtype=np.uint8)
    h, w = height // 2, width // 2
    a[:h, :w] = (255, 0, 0)      # top-left     red
    a[:h, w:] = (0, 255, 0)      # top-right    green
    a[h:, :w] = (0, 0, 255)      # bottom-left  blue
    a[h:, w:] = (255, 255, 0)    # bottom-right yellow
    return a


def _write_jpeg(path, array, orientation=None):
    """Save `array` as a JPEG, optionally tagging it with an EXIF orientation."""
    img = Image.fromarray(array)
    exif = (
        piexif.dump({"0th": {piexif.ImageIFD.Orientation: orientation}})
        if orientation is not None
        else b""
    )
    img.save(str(path), "JPEG", quality=100, subsampling=0, exif=exif)
    return str(path)


def assert_same_image(actual, expected, message=""):
    """Compare pixels with a tolerance for JPEG's lossy round-trip.

    JPEG perturbs values by a few units even at quality=100, so exact equality
    is not available. The quadrant colors are 255 apart, so any real rotation
    slip dwarfs the tolerance and is still caught.

    Only for paths that encode once — use assert_same_orientation for anything
    that re-saves.
    """
    assert actual.shape == expected.shape, (
        f"{message}shape {actual.shape} != expected {expected.shape}"
    )
    assert np.allclose(actual, expected, atol=20), f"{message}pixels differ"


def _quadrant_means(a):
    """Mean color of each quadrant's inner core, keyed by position."""
    h, w = a.shape[0], a.shape[1]
    qh, qw = h // 4, w // 4
    return {
        (row, col): a[
            slice(0, qh) if row == "top" else slice(-qh, None),
            slice(0, qw) if col == "left" else slice(-qw, None),
        ].reshape(-1, 3).mean(axis=0)
        for row in ("top", "bottom")
        for col in ("left", "right")
    }


def assert_same_orientation(actual, expected, message=""):
    """Compare which quadrant sits where, tolerating a JPEG re-encode.

    Paths that re-save (rotate_image, crop_image) put the image through a second
    lossy pass, and these synthetic hard quadrant edges ring badly enough to
    break a per-pixel tolerance while the geometry is perfectly fine. Quadrant
    means sample away from those edges and still pin the orientation exactly:
    the four colors are 255 apart, so any rotation slip swaps them outright.
    """
    assert actual.shape == expected.shape, (
        f"{message}shape {actual.shape} != expected {expected.shape}"
    )
    actual_q, expected_q = _quadrant_means(actual), _quadrant_means(expected)
    for key in expected_q:
        assert np.allclose(actual_q[key], expected_q[key], atol=12), (
            f"{message}{key[0]}-{key[1]} quadrant is "
            f"{actual_q[key].round()}, expected {expected_q[key].round()}"
        )


class TestOpenOriented:
    def test_orientation_3_is_rotated_180(self, tmp_path):
        """The real-world bug: a 180° photo pulled from the server."""
        stored = _asymmetric()
        path = _write_jpeg(tmp_path / "o3.jpg", stored, orientation=3)

        result = np.asarray(open_oriented(path).convert("RGB"))

        assert_same_image(result, np.rot90(stored, 2))

    def test_orientation_6_is_rotated_90_clockwise(self, tmp_path):
        """Orientation 6: 0th row is the visual right side → rotate 90° CW."""
        stored = _asymmetric()
        path = _write_jpeg(tmp_path / "o6.jpg", stored, orientation=6)

        result = np.asarray(open_oriented(path).convert("RGB"))

        # np.rot90 with k=-1 rotates clockwise; axes swap, so 60x40 → 40x60
        assert_same_image(result, np.rot90(stored, -1))
        assert open_oriented(path).size == (40, 60)

    def test_orientation_8_is_rotated_90_counter_clockwise(self, tmp_path):
        stored = _asymmetric()
        path = _write_jpeg(tmp_path / "o8.jpg", stored, orientation=8)

        result = np.asarray(open_oriented(path).convert("RGB"))

        assert_same_image(result, np.rot90(stored, 1))

    def test_orientation_1_is_left_alone(self, tmp_path):
        stored = _asymmetric()
        path = _write_jpeg(tmp_path / "o1.jpg", stored, orientation=1)

        result = np.asarray(open_oriented(path).convert("RGB"))

        assert_same_image(result, stored)

    def test_image_without_exif_is_left_alone(self, tmp_path):
        stored = _asymmetric()
        path = _write_jpeg(tmp_path / "none.jpg", stored, orientation=None)

        result = np.asarray(open_oriented(path).convert("RGB"))

        assert_same_image(result, stored)

    def test_orientation_tag_is_cleared_so_rotation_is_not_applied_twice(self, tmp_path):
        """The returned image is already upright; a stale tag would re-rotate it."""
        path = _write_jpeg(tmp_path / "o3.jpg", _asymmetric(), orientation=3)

        result = open_oriented(path)

        assert (result.getexif() or {}).get(274) in (None, 1)


class TestGetImageDimensions:
    def test_axes_swap_for_quarter_turns(self, tmp_path):
        """A 90°-rotated photo is displayed with its axes swapped."""
        path = _write_jpeg(tmp_path / "o6.jpg", _asymmetric(60, 40), orientation=6)

        assert ImageLoader.get_image_dimensions(path) == (40, 60)

    @pytest.mark.parametrize("orientation", [None, 1, 3])
    def test_axes_kept_for_half_turns_and_upright(self, tmp_path, orientation):
        path = _write_jpeg(
            tmp_path / f"o{orientation}.jpg", _asymmetric(60, 40), orientation
        )

        assert ImageLoader.get_image_dimensions(path) == (60, 40)


class TestRotateRespectsOrientation:
    """User rotation must turn the photo the user sees, not the raw buffer.

    ``rotate_image`` bakes the rotation in and saves without an orientation tag.
    Rotating the raw buffer of a tagged photo would land 180° (or 90°) away from
    where the user asked, since the display applies the tag but the rotation
    did not.
    """

    def test_rotate_of_tagged_photo_turns_the_displayed_image(self, tmp_path):
        from src.services.image_processor import ImageProcessor

        stored = _asymmetric(60, 40)
        path = _write_jpeg(tmp_path / "o3.jpg", stored, orientation=3)
        displayed = np.rot90(stored, 2)  # what the user sees before rotating

        assert ImageProcessor.rotate_image(path, degrees=-90)

        # -90 in Pillow is a clockwise quarter turn == np.rot90(..., -1)
        result = np.asarray(open_oriented(path).convert("RGB"))
        assert_same_orientation(result, np.rot90(displayed, -1))

    def test_rotate_leaves_no_orientation_tag_to_reapply(self, tmp_path):
        from src.services.image_processor import ImageProcessor

        path = _write_jpeg(tmp_path / "o3.jpg", _asymmetric(60, 40), orientation=3)

        ImageProcessor.rotate_image(path)

        assert (Image.open(path).getexif() or {}).get(274) in (None, 1)

    def test_format_is_preserved_so_rotation_does_not_change_encoding(self, tmp_path):
        """open_oriented() must keep .format, which rotate_image saves by."""
        path = _write_jpeg(tmp_path / "o3.jpg", _asymmetric(60, 40), orientation=3)

        assert open_oriented(path).format == "JPEG"


class TestRotatePreservesMetadata:
    """Rotating must not cost the photo its EXIF.

    Pillow writes no EXIF on save unless handed it explicitly, so rotating used
    to silently drop the capture date. That hid behind the ``YYYYMMDD_HHMMSS``
    filename fallback in ``get_display_date()`` — date stamps kept working, so
    the loss was invisible until a photo arrived without a dated filename.

    Re-attaching EXIF is only safe because ``open_oriented()`` has already
    stripped the orientation tag from those bytes; the tag must stay gone, or
    the next load re-rotates an image whose rotation is already baked in.
    """

    def _write_tagged(self, path, orientation=3):
        exif = piexif.dump({
            "0th": {
                piexif.ImageIFD.Orientation: orientation,
                piexif.ImageIFD.Make: b"TestPhone",
            },
            "Exif": {piexif.ExifIFD.DateTimeOriginal: b"2026:07:06 14:44:46"},
        })
        Image.fromarray(_asymmetric(60, 40)).save(
            str(path), "JPEG", quality=100, exif=exif
        )
        return str(path)

    def test_capture_date_survives_rotation(self, tmp_path):
        from src.services.image_processor import ImageProcessor

        path = self._write_tagged(tmp_path / "dated.jpg")

        assert ImageProcessor.rotate_image(path)

        assert ImageProcessor.read_exif_date(path) == datetime(2026, 7, 6, 14, 44, 46)

    def test_other_exif_survives_rotation(self, tmp_path):
        from src.services.image_processor import ImageProcessor

        path = self._write_tagged(tmp_path / "make.jpg")

        ImageProcessor.rotate_image(path)

        assert (Image.open(path).getexif() or {}).get(271) == "TestPhone"

    def test_reattached_exif_does_not_smuggle_the_orientation_tag_back(self, tmp_path):
        """The tag must not ride along, or the next load double-rotates."""
        from src.services.image_processor import ImageProcessor

        path = self._write_tagged(tmp_path / "o3.jpg", orientation=3)

        ImageProcessor.rotate_image(path, degrees=-90)

        assert (Image.open(path).getexif() or {}).get(274) in (None, 1)

        # Belt and braces: a second rotation must land 90° on from the first,
        # which it cannot do if a surviving tag is re-rotating on every load.
        after_first = np.asarray(open_oriented(path).convert("RGB"))
        ImageProcessor.rotate_image(path, degrees=-90)
        after_second = np.asarray(open_oriented(path).convert("RGB"))
        assert_same_orientation(after_second, np.rot90(after_first, -1))

    def test_rotation_of_photo_without_exif_still_works(self, tmp_path):
        from src.services.image_processor import ImageProcessor

        stored = _asymmetric(60, 40)
        path = _write_jpeg(tmp_path / "bare.jpg", stored, orientation=None)

        assert ImageProcessor.rotate_image(path, degrees=-90)

        result = np.asarray(open_oriented(path).convert("RGB"))
        assert_same_orientation(result, np.rot90(stored, -1))


class TestCropExportRespectsOrientation:
    """The export path is where a missed rotation becomes permanent.

    ``crop_image`` saves without an EXIF block, so the output carries no
    orientation tag: whatever pixels it writes are final. Cropping from the raw
    buffer would bake the rotation in and print the photo upside down.
    """

    def test_export_of_rotated_photo_has_upright_pixels(self, tmp_path):
        from src.services.crop_service import CropService
        from tests.test_crop_service import StubConfig

        stored = _asymmetric(600, 400)
        path = _write_jpeg(tmp_path / "o3.jpg", stored, orientation=3)
        out = tmp_path / "out" / "cropped.jpg"

        # Full-frame manual crop box in upright coords, so the export should be
        # the upright image itself — any orientation slip shows up as a rotation.
        ok = CropService(StubConfig()).crop_image(
            path, "9x6", str(out),
            manual_crop_box={"x": 0, "y": 0, "width": 600, "height": 400},
        )

        assert ok
        result = np.asarray(Image.open(str(out)).convert("RGB"))
        assert_same_orientation(result, np.rot90(stored, 2))

    def test_export_carries_no_stale_orientation_tag(self, tmp_path):
        from src.services.crop_service import CropService
        from tests.test_crop_service import StubConfig

        path = _write_jpeg(tmp_path / "o3.jpg", _asymmetric(600, 400), orientation=3)
        out = tmp_path / "out" / "cropped.jpg"

        CropService(StubConfig()).crop_image(
            path, "9x6", str(out),
            manual_crop_box={"x": 0, "y": 0, "width": 600, "height": 400},
        )

        assert (Image.open(str(out)).getexif() or {}).get(274) in (None, 1)
