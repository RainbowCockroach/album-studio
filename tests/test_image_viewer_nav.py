"""Tests for Left/Right browsing in the image viewer.

The second place the suite reaches into ``src/ui``, for the same reason as
``test_main_window_pull.py``: a Qt-only rule that no service test can see.
``QScrollArea`` inherits ``QAbstractScrollArea``, which accepts focus *and*
consumes arrow keys to scroll itself — so with its default focus policy the
viewer's Left/Right would be eaten before ``keyPressEvent`` ever ran, and the
arrows would silently do nothing. ``test_arrow_keys_*`` below pin that fix by
routing keys through the focus chain, exactly as the window system does; send
them straight to the dialog instead and they pass even with the bug present.

The index arithmetic is pure, so those tests skip Qt entirely.
"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.models.image_item import ImageItem
from src.ui.dialogs.image_viewer_dialog import ImageViewerDialog


def _bare_viewer(count, index=0):
    """A viewer with no Qt behind it — enough for the pure index arithmetic."""
    viewer = ImageViewerDialog.__new__(ImageViewerDialog)
    viewer.images = [object() for _ in range(count)]
    viewer.index = index
    return viewer


@pytest.fixture
def images(make_image):
    """Three real on-disk photos, as ImageItems in grid order."""
    return [ImageItem(make_image()) for _ in range(3)]


@pytest.fixture
def viewer(qapp, images):
    """A shown viewer opened on the middle of three images.

    Shown because focus is only assigned to a visible window, and focus is the
    whole point of the arrow-key tests. config is None, which keeps
    ``_check_real_size_available`` false and the CropService out of the picture.
    """
    dialog = ImageViewerDialog(images[1].file_path, image_item=images[1],
                               images=images)
    dialog.show()
    QTest.qWaitForWindowExposed(dialog)
    yield dialog
    dialog.deleteLater()


def _press(dialog, key):
    """Send a key the way the window system does — to whatever holds focus."""
    QTest.keyClick(dialog.focusWidget() or dialog, key)


# ---------------------------------------------------------------- index maths

def test_target_index_steps_to_neighbours():
    viewer = _bare_viewer(3, index=1)
    assert viewer._target_index(-1) == 0
    assert viewer._target_index(+1) == 2


def test_target_index_stops_at_the_ends():
    assert _bare_viewer(3, index=0)._target_index(-1) is None
    assert _bare_viewer(3, index=2)._target_index(+1) is None


def test_target_index_handles_single_and_empty_lists():
    assert _bare_viewer(1, index=0)._target_index(+1) is None
    assert _bare_viewer(1, index=0)._target_index(-1) is None
    assert _bare_viewer(0)._target_index(+1) is None


# ------------------------------------------------------------------ key input

def test_scroll_area_refuses_focus(viewer):
    """The fix itself: anything else and the scroll area swallows the arrows."""
    assert viewer.scroll_area.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_arrow_keys_browse(viewer, images):
    _press(viewer, Qt.Key.Key_Right)
    assert viewer.index == 2
    assert viewer.image_item is images[2]
    assert viewer.image_path == images[2].file_path

    _press(viewer, Qt.Key.Key_Left)
    assert viewer.index == 1
    assert viewer.image_item is images[1]


def test_arrow_keys_stop_at_the_ends(viewer):
    _press(viewer, Qt.Key.Key_Left)
    _press(viewer, Qt.Key.Key_Left)  # already at the first image
    assert viewer.index == 0

    for _ in range(4):
        _press(viewer, Qt.Key.Key_Right)
    assert viewer.index == 2


def test_escape_and_r_still_reach_the_dialog(viewer):
    """The focus change must not cost the keys that worked before."""
    _press(viewer, Qt.Key.Key_R)  # no size tag, so this is a no-op, not a crash
    assert viewer.real_size_mode is False

    _press(viewer, Qt.Key.Key_Escape)
    assert viewer.isVisible() is False


# -------------------------------------------------------------- chevrons & UI

def test_chevrons_hide_at_the_ends(viewer):
    assert viewer.prev_btn.isVisible()
    assert viewer.next_btn.isVisible()

    viewer.navigate(-1)
    assert not viewer.prev_btn.isVisible()  # first image
    assert viewer.next_btn.isVisible()

    viewer.navigate(+1)
    viewer.navigate(+1)
    assert viewer.prev_btn.isVisible()
    assert not viewer.next_btn.isVisible()  # last image


def test_chevrons_do_not_take_focus_from_the_arrows(viewer):
    """A focusable chevron would grab the arrow keys and re-fire the button."""
    assert viewer.prev_btn.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert viewer.next_btn.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_chevron_click_navigates(viewer, images):
    QTest.mouseClick(viewer.next_btn, Qt.MouseButton.LeftButton)
    assert viewer.image_item is images[2]


def test_hint_shows_position(viewer):
    assert "2 / 3" in viewer.hint_label.text()
    viewer.navigate(-1)
    assert "1 / 3" in viewer.hint_label.text()


def test_navigating_emits_image_changed(viewer, images):
    seen = []
    viewer.image_changed.connect(seen.append)

    viewer.navigate(+1)
    assert seen == [images[2]]

    viewer.navigate(+1)  # at the end — nothing happened, so nothing is emitted
    assert seen == [images[2]]


# ------------------------------------------------------- single-image viewers

def test_viewer_without_a_list_has_no_navigation(qapp, images):
    """The date-stamp preview opens this way; it must not grow arrows."""
    dialog = ImageViewerDialog(images[0].file_path, image_item=images[0])
    try:
        assert dialog.images == [images[0]]
        assert dialog._target_index(+1) is None
        assert not dialog.prev_btn.isVisible()
        assert not dialog.next_btn.isVisible()
        assert "1 / 1" not in dialog.hint_label.text()
    finally:
        dialog.deleteLater()
