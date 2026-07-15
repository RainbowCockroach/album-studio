"""Tests for src/utils/image_loader.py's QImage/QPixmap conversion layer.

``load_qimage`` is the thread-safe core the image viewer's background renderer
calls; ``load_pixmap`` is a GUI-thread wrapper over it. Both are covered here
because the viewer's speed fix moved real work into the former — including the
EXIF orientation that ``QImageReader`` does *not* apply by default, which has
bitten this app before (see tests/test_image_orientation.py).

QImage needs no QApplication, so most of this runs without the ``qapp`` fixture;
the QPixmap tests take it because QPixmap is a QPaintDevice.
"""

import numpy as np
import piexif
import pytest
from PIL import Image
from PyQt6.QtGui import QImage

from src.utils.image_loader import ImageLoader, pil_to_qimage


def _qimage_to_array(image: QImage) -> np.ndarray:
    """Copy a QImage's visible pixels into an (h, w, 3) uint8 array."""
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    width, height = image.width(), image.height()
    ptr = image.constBits()
    assert ptr is not None
    ptr.setsize(image.sizeInBytes())
    # Rows are padded to a 4-byte boundary, so index by bytesPerLine and trim.
    raw = np.frombuffer(bytes(ptr), dtype=np.uint8)
    raw = raw.reshape(height, image.bytesPerLine())
    return raw[:, : width * 3].reshape(height, width, 3)


def _write_jpeg(path, array, orientation=None):
    """Save `array` as a JPEG, optionally tagging an EXIF orientation."""
    img = Image.fromarray(array)
    exif = (
        piexif.dump({"0th": {piexif.ImageIFD.Orientation: orientation}})
        if orientation is not None
        else None
    )
    kwargs = {"exif": exif} if exif else {}
    img.save(str(path), "JPEG", quality=95, **kwargs)
    return str(path)


def _two_tone(width=64, height=48):
    """Top half red, bottom half blue — distinguishable under a 180° turn."""
    a = np.zeros((height, width, 3), dtype=np.uint8)
    a[: height // 2] = (255, 0, 0)
    a[height // 2 :] = (0, 0, 255)
    return a


class TestPilToQImage:
    """Replaces a PNG encode+decode roundtrip that cost 2.8s on a 12MP frame."""

    def test_dimensions_and_pixels_survive(self):
        img = Image.fromarray(_two_tone(64, 48))
        q = pil_to_qimage(img)

        assert (q.width(), q.height()) == (64, 48)
        arr = _qimage_to_array(q)
        assert tuple(arr[5, 5]) == (255, 0, 0)
        assert tuple(arr[40, 5]) == (0, 0, 255)

    def test_non_rgb_is_converted(self):
        q = pil_to_qimage(Image.new("L", (10, 8), 128))
        assert (q.width(), q.height()) == (10, 8)
        assert tuple(_qimage_to_array(q)[0, 0]) == (128, 128, 128)

    def test_result_owns_its_pixels(self):
        """The QImage must not alias PIL's buffer, which Python may free."""
        img = Image.fromarray(_two_tone(32, 32))
        q = pil_to_qimage(img)
        del img
        import gc

        gc.collect()
        assert tuple(_qimage_to_array(q)[2, 2]) == (255, 0, 0)


class TestLoadQImage:
    def test_missing_file_returns_null(self, tmp_path):
        assert ImageLoader.load_qimage(str(tmp_path / "nope.jpg")).isNull()

    def test_loads_full_size_when_no_max(self, tmp_path):
        path = _write_jpeg(tmp_path / "a.jpg", _two_tone(120, 90))
        q = ImageLoader.load_qimage(path)
        assert (q.width(), q.height()) == (120, 90)

    def test_max_size_scales_down_preserving_aspect(self, tmp_path):
        path = _write_jpeg(tmp_path / "a.jpg", _two_tone(400, 200))
        q = ImageLoader.load_qimage(path, max_size=100)
        assert max(q.width(), q.height()) <= 100
        assert q.width() == 100 and q.height() == 50

    @pytest.mark.parametrize("fmt,name", [("JPEG", "a.jpg"), ("PNG", "a.png")])
    def test_small_image_is_not_upscaled(self, tmp_path, fmt, name):
        """max_size is a ceiling, not a target.

        The JPEG branch used to upscale here (QSize.scaled grows too) while the
        Pillow branch never did, so this asserts both agree. Upscaling wasted
        memory and made the viewer render a blur above 1:1.
        """
        path = tmp_path / name
        Image.fromarray(_two_tone(40, 30)).save(str(path), fmt)

        q = ImageLoader.load_qimage(str(path), max_size=500)
        assert (q.width(), q.height()) == (40, 30)


class TestLoadQImageOrientation:
    """QImageReader.setAutoTransform is OFF by default; both paths must set it.

    The scaled path (max_size, JPEG) and the full-size path are separate
    branches, so a regression can hide in either one.
    """

    @pytest.mark.parametrize("max_size", [None, 32])
    def test_orientation_3_is_applied(self, tmp_path, max_size):
        # Stored upside-down with a tag saying "rotate 180 to display":
        # top half is blue on disk, must read back red on top.
        stored = np.rot90(_two_tone(64, 48), 2)
        path = _write_jpeg(tmp_path / "o3.jpg", stored, orientation=3)

        q = ImageLoader.load_qimage(path, max_size=max_size)
        arr = _qimage_to_array(q)

        top = arr[: q.height() // 4].reshape(-1, 3).mean(axis=0)
        bottom = arr[3 * q.height() // 4 :].reshape(-1, 3).mean(axis=0)
        assert top[0] > 200 and top[2] < 60, f"top should be red, got {top}"
        assert bottom[2] > 200 and bottom[0] < 60, f"bottom should be blue, got {bottom}"

    def test_quarter_turn_swaps_axes(self, tmp_path):
        # 6 = rotate 90° CW to display, so a stored 90x60 shows as 60x90.
        stored = np.rot90(_two_tone(60, 90), 1)
        path = _write_jpeg(tmp_path / "o6.jpg", stored, orientation=6)

        q = ImageLoader.load_qimage(path)
        assert (q.width(), q.height()) == (60, 90)


class TestLoadPixmapWrapper:
    def test_returns_pixmap_matching_qimage(self, qapp, tmp_path):
        path = _write_jpeg(tmp_path / "a.jpg", _two_tone(80, 60))
        pixmap = ImageLoader.load_pixmap(path)
        assert not pixmap.isNull()
        assert (pixmap.width(), pixmap.height()) == (80, 60)

    def test_missing_file_returns_null_pixmap(self, qapp, tmp_path):
        assert ImageLoader.load_pixmap(str(tmp_path / "nope.jpg")).isNull()

    def test_max_size_is_honoured(self, qapp, tmp_path):
        path = _write_jpeg(tmp_path / "a.jpg", _two_tone(400, 200))
        pixmap = ImageLoader.load_pixmap(path, max_size=100)
        assert (pixmap.width(), pixmap.height()) == (100, 50)
