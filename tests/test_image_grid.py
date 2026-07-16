"""Regression tests for the main image grid's cards.

The reflow and packing live in ``CardGrid`` and are pinned by
``tests/test_card_grid.py``. What is left here is ImageGrid's own end of the
bargain: CardGrid never resizes a card, so the cards it is handed must already
be a fixed ``theme.card_size``. An ImageWidget that went back to sizing itself
would stretch again and no CardGrid test would notice.
"""

from types import SimpleNamespace

import pytest

from src.models.image_item import ImageItem
from src.ui.theme import (
    card_size, lighten_color, CARD_BORDER, CARD_UNTAGGED_BG,
    CARD_RING_CURRENT, CARD_RING_DELETE, CARD_RING_DATESTAMP)
from src.ui.widgets.image_grid import ImageGrid, ImageWidget

THUMBNAIL_SIZE = 200


class StubConfig:
    """ImageGrid reads ``thumbnail_size``; ImageWidget asks it for tag colors."""

    def __init__(self, colors=None):
        self.colors = colors or {}

    def get_setting(self, key, default=None):
        return {"thumbnail_size": THUMBNAIL_SIZE}.get(key, default)

    def get_size_color(self, size_tag):
        return self.colors.get(size_tag, "")


@pytest.fixture
def grid(qapp, tmp_path):
    """A 4-photo grid -- the case that first showed the stretching.

    The image files do not exist, so the background thumbnail loaders find
    nothing and every card keeps its placeholder. Layout does not care.
    """
    grid = ImageGrid(StubConfig())
    images = [ImageItem(str(tmp_path / f"photo_{i}.jpg")) for i in range(4)]
    grid.set_project(SimpleNamespace(images=images))
    grid.show()
    qapp.processEvents()
    yield grid
    grid.clear_grid()  # Joins the loader threads before the test process moves on.
    grid.deleteLater()


class TestImageWidgetSize:
    def test_card_is_the_shared_card_size(self, qapp, tmp_path):
        widget = ImageWidget(ImageItem(str(tmp_path / "photo.jpg")),
                             THUMBNAIL_SIZE, load_immediately=False,
                             config=StubConfig())

        assert (widget.width(), widget.height()) == card_size(THUMBNAIL_SIZE)

    def test_card_size_does_not_move_when_the_tag_text_grows(self, qapp, tmp_path):
        """The tag row is fixed height, so a two-line tag must not make one
        card taller than its neighbours."""
        item = ImageItem(str(tmp_path / "photo.jpg"))
        widget = ImageWidget(item, THUMBNAIL_SIZE, load_immediately=False,
                             config=StubConfig())
        untagged = widget.size()

        item.set_tags(album="A5", size="9x6")
        item.add_date_stamp = True
        widget.update_border()

        assert widget.size() == untagged


class TestGridPopulation:
    def test_every_photo_becomes_a_card(self, grid):
        assert len(grid.card_grid.cards) == 4
        assert len(grid.image_widgets) == 4

    def test_cards_handed_to_the_grid_are_fixed_size(self, grid):
        for card in grid.card_grid.cards:
            assert (card.width(), card.height()) == card_size(THUMBNAIL_SIZE)

    def test_reloading_a_project_replaces_the_cards(self, grid, tmp_path, qapp):
        grid.set_project(SimpleNamespace(
            images=[ImageItem(str(tmp_path / "only.jpg"))]))
        qapp.processEvents()

        assert len(grid.card_grid.cards) == 1
        assert len(grid.image_widgets) == 1

    def test_clearing_the_grid_empties_it(self, grid, qapp):
        grid.clear_grid()
        qapp.processEvents()

        assert grid.card_grid.cards == []
        assert grid.image_widgets == {}


TAG_COLOR = "#00e9e2"  # the real stored color for 9x6


class TestSelectionRing:
    """Tag state fills the card; selection rings it — the two must compose.

    The old ``update_border`` let selection repaint the whole card, so a
    selected card and a tagged card were near-identical pale washes, and
    selecting (or batch-marking) a tagged card hid which tag it carried.
    """

    @pytest.fixture
    def tagged_widget(self, qapp, tmp_path):
        item = ImageItem(str(tmp_path / "photo.jpg"))
        item.set_tags(album="A5", size="9x6")
        widget = ImageWidget(item, THUMBNAIL_SIZE, load_immediately=False,
                             config=StubConfig(colors={"9x6": TAG_COLOR}))
        yield widget
        widget.deleteLater()

    def test_selecting_a_tagged_card_keeps_its_tag_wash(self, tagged_widget):
        tagged_widget.set_current_selected(True)

        style = tagged_widget.styleSheet()
        assert lighten_color(TAG_COLOR, 0.82) in style   # fill survives
        assert f"border: {CARD_BORDER}px solid {CARD_RING_CURRENT}" in style

    def test_selecting_keeps_the_tag_text_and_its_color(self, tagged_widget):
        tagged_widget.set_current_selected(True)

        assert "A5" in tagged_widget.tag_label.text()
        assert TAG_COLOR in tagged_widget.tag_label.styleSheet()

    def test_deselecting_restores_the_tag_border(self, tagged_widget):
        tagged_widget.set_current_selected(True)
        tagged_widget.set_current_selected(False)

        style = tagged_widget.styleSheet()
        assert CARD_RING_CURRENT not in style
        assert lighten_color(TAG_COLOR, 0.45) in style

    def test_browse_selection_is_ring_only(self, tagged_widget):
        """The ✕/✓ badges carry a batch mode; browse selection has nothing
        for a glyph to say, so it must not grow a dot."""
        tagged_widget.set_current_selected(True)
        assert tagged_widget.badge.isHidden()

    def test_badge_shows_only_while_batch_selected(self, tagged_widget):
        assert tagged_widget.badge.isHidden()

        tagged_widget.set_selected(True, 'delete')
        assert not tagged_widget.badge.isHidden()

        tagged_widget.set_selected(False, None)
        assert tagged_widget.badge.isHidden()

    def test_delete_mode_rings_red_and_keeps_the_tag_visible(self, tagged_widget):
        tagged_widget.set_selected(True, 'delete')

        assert CARD_RING_DELETE in tagged_widget.styleSheet()
        assert "A5" in tagged_widget.tag_label.text()  # old code replaced this
        assert tagged_widget.badge.text() == '✕'

    def test_date_stamp_mode_rings_green(self, tagged_widget):
        tagged_widget.set_selected(True, 'date_stamp')

        assert CARD_RING_DATESTAMP in tagged_widget.styleSheet()
        assert tagged_widget.badge.text() == '✓'

    def test_badge_sits_inside_the_fixed_card(self, tagged_widget):
        """The badge is a raw child widget, so anything hanging past the card
        rect would be silently clipped rather than drawn."""
        assert tagged_widget.rect().contains(tagged_widget.badge.geometry())

    def test_untagged_selected_card_rings_over_the_neutral_fill(self, qapp, tmp_path):
        widget = ImageWidget(ImageItem(str(tmp_path / "p.jpg")), THUMBNAIL_SIZE,
                             load_immediately=False, config=StubConfig())

        widget.set_current_selected(True)

        style = widget.styleSheet()
        assert CARD_UNTAGGED_BG in style
        assert CARD_RING_CURRENT in style
