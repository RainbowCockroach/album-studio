"""Layout regression tests for the shared card grid.

One of the few places the suite reaches into ``src/ui`` (see
``test_main_window_pull.py`` for the reasoning). Card layout is a pure-Qt
concern no service test can see: cards used to take whatever space
``QGridLayout`` had spare, so a four-photo project rendered as four ~490px-wide
cards stretched across the window while every test stayed green. The same bug
shipped a second time in the similar-images dialog, which is why the layout now
lives in one widget -- and why it is pinned here rather than per-caller.

``theme.py`` holds the geometry maths and ``tests/test_theme.py`` covers it
without Qt. What is pinned here is the wiring that maths depends on. The cards
are plain fixed-size QWidgets: CardGrid never inspects them, so nothing here
needs a real photo.
"""

import pytest
from PyQt6.QtWidgets import QWidget

from src.ui.theme import GRID_SPACING, card_size, grid_columns_for_width
from src.ui.widgets.card_grid import CardGrid

THUMBNAIL_SIZE = 200
CARD_WIDTH, CARD_HEIGHT = card_size(THUMBNAIL_SIZE)


def make_card():
    """A stand-in for a real card: fixed size is all CardGrid relies on."""
    card = QWidget()
    card.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
    return card


@pytest.fixture
def grid(qapp):
    """A shown 4-card grid -- the case that first showed the stretching."""
    grid = CardGrid(THUMBNAIL_SIZE)
    grid.set_cards([make_card() for _ in range(4)])
    grid.show()
    yield grid
    grid.deleteLater()


def _settle(grid, qapp, width, height=900):
    """Resize the grid and let Qt deliver the events the reflow hangs off."""
    grid.resize(width, height)
    qapp.processEvents()
    grid.container.layout().activate()
    qapp.processEvents()


class TestCardSizing:
    def test_cards_keep_their_size_in_a_wide_window(self, grid, qapp):
        """The original bug: four cards inflating to fill a 2000px window."""
        _settle(grid, qapp, 2000)

        for card in grid.cards:
            assert (card.width(), card.height()) == (CARD_WIDTH, CARD_HEIGHT)

    def test_a_full_row_is_the_same_size_as_a_lone_card(self, grid, qapp):
        """Card size must not depend on how many cards there are."""
        _settle(grid, qapp, 2000)
        four_up = grid.cards[0].size()

        grid.set_cards([make_card()])
        _settle(grid, qapp, 2000)

        assert grid.cards[0].size() == four_up


class TestColumnReflow:
    def test_columns_follow_the_viewport_width(self, grid, qapp):
        _settle(grid, qapp, 2000)

        assert grid.columns == grid_columns_for_width(
            grid.viewport().width(), THUMBNAIL_SIZE)
        assert grid.columns > 1  # Reflow ran at all; the initial value is 1.

    def test_narrowing_the_window_reflows(self, grid, qapp):
        _settle(grid, qapp, 2000)
        wide = grid.columns

        _settle(grid, qapp, 600)

        assert grid.columns < wide

    def test_cards_never_overflow_the_viewport(self, grid, qapp):
        """A card pushed past the right edge is the visible symptom of a stale
        column count -- it shows up as a horizontal scrollbar."""
        for width in (2000, 1200, 700, 500):
            _settle(grid, qapp, width)

            for card in grid.cards:
                assert card.geometry().right() <= grid.viewport().width()

    def test_cards_are_packed_top_left(self, grid, qapp):
        """The stretch row/column absorb the slack, so the first card sits at
        the grid's margin no matter how much space is left over."""
        _settle(grid, qapp, 2000)
        first = grid.cards[0].geometry()

        _settle(grid, qapp, 1200)

        assert grid.cards[0].geometry().topLeft() == first.topLeft()


class TestStretchSpacers:
    """Fixed-size cards alone are not enough. Without a stretch column and row
    past the last card, QGridLayout widens the card *cells* to fill the window
    instead; the cards keep their size but drift apart across the empty space,
    which reads as exactly the same 'stretched out' layout.
    """

    def test_cards_in_a_row_are_one_gap_apart(self, grid, qapp):
        _settle(grid, qapp, 2000)  # All four cards fit on one row.

        xs = [c.geometry().x() for c in grid.cards]

        assert len({c.geometry().y() for c in grid.cards}) == 1
        assert [b - a for a, b in zip(xs, xs[1:])] == \
            [CARD_WIDTH + GRID_SPACING] * 3

    def test_rows_are_one_gap_apart(self, grid, qapp):
        _settle(grid, qapp, 620)  # Narrow enough to wrap into two rows.

        ys = sorted({c.geometry().y() for c in grid.cards})

        assert len(ys) > 1, "expected the cards to wrap onto multiple rows"
        assert [b - a for a, b in zip(ys, ys[1:])] == \
            [CARD_HEIGHT + GRID_SPACING] * (len(ys) - 1)


class TestSetCards:
    def test_replacing_cards_drops_the_old_ones(self, grid, qapp):
        _settle(grid, qapp, 2000)

        grid.set_cards([make_card(), make_card()])
        _settle(grid, qapp, 2000)

        assert len(grid.cards) == 2
        assert grid.grid_layout.count() == 2

    def test_clearing_empties_the_grid(self, grid, qapp):
        grid.clear_cards()
        _settle(grid, qapp, 2000)

        assert grid.cards == []
        assert grid.grid_layout.count() == 0

    def test_an_empty_grid_survives_a_resize(self, grid, qapp):
        """_rebuild_layout divides by the column count; nothing to divide here."""
        grid.clear_cards()

        _settle(grid, qapp, 400)
        _settle(grid, qapp, 2000)

        assert grid.cards == []
