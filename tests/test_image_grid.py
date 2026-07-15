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
from src.ui.theme import card_size
from src.ui.widgets.image_grid import ImageGrid, ImageWidget

THUMBNAIL_SIZE = 200


class StubConfig:
    """ImageGrid only ever reads ``thumbnail_size`` off the config."""

    def get_setting(self, key, default=None):
        return {"thumbnail_size": THUMBNAIL_SIZE}.get(key, default)

    def get_size_color(self, size_tag):
        return None


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
