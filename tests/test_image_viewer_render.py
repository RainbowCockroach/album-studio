"""Tests for the image viewer's off-thread render path.

The third place the suite reaches into ``src/ui``, for the usual reason: these
are Qt-only rules no service test can see. Opening a 12MP photo used to block
the UI thread for ~11s (a full-resolution smartcrop plus a PNG encode/decode
roundtrip), so rendering moved to a QThreadPool with a small frame cache.

That buys two failure modes worth pinning:

- a render that lands **after** the user has already arrowed on must not be
  painted over the photo they are now looking at, and
- the cache must be keyed by everything that changes pixels, or toggling a date
  stamp would serve the pre-stamp frame back.

Renders are dispatched by key and delivered on the UI thread, so both are
testable without touching the pool's timing.
"""

import pytest
from PyQt6.QtGui import QImage

from src.models.image_item import ImageItem
from src.ui.dialogs.image_viewer_dialog import (ImageViewerDialog,
                                                _RENDER_CACHE_MAX,
                                                _render_image, _render_key)


def _image(width=8, height=6, value=200):
    q = QImage(width, height, QImage.Format.Format_RGB888)
    q.fill(value)
    return q


@pytest.fixture
def images(make_image):
    return [ImageItem(make_image()) for _ in range(3)]


@pytest.fixture
def viewer(qapp, images):
    """A viewer on the middle of three images.

    ``config=None`` keeps CropService out of it: these tests are about the
    cache and dispatch, not about cropping.
    """
    dialog = ImageViewerDialog(images[1].file_path, image_item=images[1],
                               images=images)
    yield dialog
    dialog.close()
    dialog.deleteLater()


# ------------------------------------------------------------------ cache keys

class TestRenderKey:
    def test_same_state_gives_same_key(self, images):
        item = images[0]
        assert _render_key(item, item.file_path) == _render_key(item, item.file_path)

    def test_key_tracks_the_date_stamp_toggle(self, images):
        """Stamped and unstamped frames are different pixels."""
        item = images[0]
        before = _render_key(item, item.file_path)
        item.add_date_stamp = True
        assert _render_key(item, item.file_path) != before

    def test_key_tracks_the_size_tag(self, images):
        """The size tag drives the crop ratio."""
        item = images[0]
        item.set_tags(album="A4", size="9x6")
        before = _render_key(item, item.file_path)
        item.set_tags(size="6x6")
        assert _render_key(item, item.file_path) != before

    def test_key_tracks_the_crop_box(self, images):
        item = images[0]
        item.crop_box = {"x": 0, "y": 0, "width": 10, "height": 10}
        before = _render_key(item, item.file_path)
        item.crop_box = {"x": 5, "y": 5, "width": 10, "height": 10}
        assert _render_key(item, item.file_path) != before

    def test_distinct_images_have_distinct_keys(self, images):
        assert (_render_key(images[0], images[0].file_path) !=
                _render_key(images[1], images[1].file_path))

    def test_key_survives_a_missing_item(self):
        """The viewer can be opened on a bare path, with no ImageItem."""
        assert _render_key(None, "/x/a.jpg") == _render_key(None, "/x/a.jpg")


# ---------------------------------------------------------------- render logic

class TestRenderImage:
    def test_untagged_render_returns_the_photo(self, make_image):
        path = make_image(size=(120, 90))
        image = _render_image(path, ImageItem(path), None, 2000)
        assert not image.isNull()
        assert (image.width(), image.height()) == (120, 90)

    def test_render_respects_max_size(self, make_image):
        path = make_image(size=(400, 200))
        image = _render_image(path, ImageItem(path), None, 100)
        assert max(image.width(), image.height()) <= 100

    def test_broken_file_does_not_raise(self, tmp_path):
        """A worker exception would otherwise surface as a bare thread crash."""
        bad = tmp_path / "broken.jpg"
        bad.write_bytes(b"not a jpeg")
        image = _render_image(str(bad), ImageItem(str(bad)), None, 500)
        assert image is None or image.isNull()


# ---------------------------------------------------------- cache and dispatch

class TestRenderCache:
    def test_put_then_hit(self, viewer):
        viewer._render_cache.clear()
        viewer._cache_put("k", _image())
        assert viewer._render_cache["k"] is not None

    def test_cache_is_bounded(self, viewer):
        viewer._render_cache.clear()
        for i in range(_RENDER_CACHE_MAX + 4):
            viewer._cache_put(f"k{i}", _image())
        assert len(viewer._render_cache) <= _RENDER_CACHE_MAX

    def test_oldest_entry_is_evicted_first(self, viewer):
        viewer._render_cache.clear()
        for i in range(_RENDER_CACHE_MAX + 1):
            viewer._cache_put(f"k{i}", _image())
        assert "k0" not in viewer._render_cache
        assert f"k{_RENDER_CACHE_MAX}" in viewer._render_cache

    def test_reinserting_does_not_duplicate(self, viewer):
        viewer._render_cache.clear()
        first = _image(value=10)
        viewer._cache_put("k", first)
        viewer._cache_put("k", _image(value=99))
        assert len(viewer._render_cache) == 1
        assert viewer._render_cache["k"] is first


class TestStaleRenders:
    """A render for a photo the user has already left must not be painted."""

    def test_stale_result_does_not_replace_the_shown_photo(self, viewer):
        viewer._pending_key = "wanted"
        shown = viewer.loaded_pixmap

        viewer._on_render_done("something-else", _image())

        assert viewer.loaded_pixmap is shown, "a stale frame was painted"
        assert viewer._pending_key == "wanted", "a stale frame cleared the wait"

    def test_stale_result_is_still_cached(self, viewer):
        """It was paid for — a prefetch lands this way and must be kept."""
        viewer._render_cache.clear()
        viewer._pending_key = "wanted"

        viewer._on_render_done("prefetched", _image())

        assert "prefetched" in viewer._render_cache

    def test_awaited_result_is_displayed(self, viewer):
        viewer._pending_key = "wanted"
        viewer._loading = True

        viewer._on_render_done("wanted", _image(40, 30))

        assert viewer._pending_key is None
        assert viewer._loading is False
        assert viewer.loaded_pixmap is not None
        assert (viewer.loaded_pixmap.width(),
                viewer.loaded_pixmap.height()) == (40, 30)

    def test_failed_render_clears_the_wait_without_painting(self, viewer):
        """A None result must not leave the viewer stuck saying 'Loading…'."""
        viewer._pending_key = "wanted"
        viewer._loading = True
        shown = viewer.loaded_pixmap

        viewer._on_render_done("wanted", None)

        assert viewer._pending_key is None
        assert viewer._loading is False
        assert viewer.loaded_pixmap is shown

    def test_cached_navigation_paints_without_waiting(self, viewer, images):
        """A cache hit must be synchronous — no 'Loading…' flash when arrowing back."""
        target = images[2]
        key = _render_key(target, target.file_path)
        viewer._cache_put(key, _image(50, 40))

        viewer._show_index(2)

        assert viewer._pending_key is None
        assert viewer._loading is False
        assert (viewer.loaded_pixmap.width(),
                viewer.loaded_pixmap.height()) == (50, 40)
