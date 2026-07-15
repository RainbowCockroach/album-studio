"""A scroll area that lays fixed-size cards out in a reflowing grid.

Shared by the main image grid and the similar-images results. Both grew the
same layout bug independently — cards taking whatever space ``QGridLayout`` had
spare, so a handful of photos rendered as a few enormous cards smeared across
the window — which is reason enough for one implementation rather than two.

The invariant: cards keep the size they ask for and the *column count* follows
the viewport. Callers supply cards that are already a fixed size (see
``theme.card_size``); this class never resizes them.
"""

from typing import Optional

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QGridLayout, QScrollArea, QWidget

from ..theme import GRID_MARGIN, GRID_SPACING, grid_columns_for_width


class CardGrid(QScrollArea):
    """Scrollable grid of fixed-size cards, packed top-left."""

    def __init__(self, thumbnail_size: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbnail_size = thumbnail_size
        self.cards: list[QWidget] = []
        # Placeholder: the column count is derived from the viewport width, and
        # the viewport has no meaningful width until the grid is first laid out.
        self.columns = 1

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.container = QWidget()
        self.container.setObjectName("imageGridContainer")
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(GRID_SPACING)
        self.grid_layout.setContentsMargins(
            GRID_MARGIN, GRID_MARGIN, GRID_MARGIN, GRID_MARGIN)
        self.container.setLayout(self.grid_layout)
        self.setWidget(self.container)

        # The viewport, not this widget, is what the cards have to fit inside —
        # a vertical scrollbar appearing narrows it without resizing the grid.
        viewport = self.viewport()
        if viewport:
            viewport.installEventFilter(self)

    def eventFilter(self, a0: Optional[QObject], a1: Optional[QEvent]) -> bool:
        """Reflow the columns whenever the scroll viewport changes width."""
        if a1 and a1.type() == QEvent.Type.Resize and a0 is self.viewport():
            self._update_columns()
        return super().eventFilter(a0, a1)

    def set_cards(self, cards):
        """Show ``cards``, replacing any already there, and take ownership."""
        self.clear_cards()
        self.cards = list(cards)
        self.columns = self._viewport_columns()
        self._rebuild_layout()

    def clear_cards(self):
        """Remove and destroy every card."""
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)
        for card in self.cards:
            card.deleteLater()
        self.cards = []

    def _viewport_columns(self) -> int:
        """Column count that fits the current viewport width."""
        viewport = self.viewport()
        if not viewport or viewport.width() <= 0:
            return self.columns
        return grid_columns_for_width(viewport.width(), self.thumbnail_size)

    def _update_columns(self):
        """Re-derive the column count and reflow if it changed."""
        columns = self._viewport_columns()
        if columns != self.columns:
            self.columns = columns
            self._rebuild_layout()

    def _rebuild_layout(self):
        """Place the cards into ``self.columns`` columns, packed top-left.

        Cards are a fixed size, so the leftover width and height have to go
        somewhere: a stretch column and row past the last card absorb it.
        Without them QGridLayout hands the slack to the card cells instead —
        the cards keep their size but drift apart across the empty space, which
        looks exactly like the stretching this is meant to prevent.
        """
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)  # Detaches the item; the card survives.
        for col in range(self.grid_layout.columnCount()):
            self.grid_layout.setColumnStretch(col, 0)
        for row in range(self.grid_layout.rowCount()):
            self.grid_layout.setRowStretch(row, 0)

        if not self.cards:
            return

        align = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        for index, card in enumerate(self.cards):
            self.grid_layout.addWidget(
                card, index // self.columns, index % self.columns, align)

        rows = -(-len(self.cards) // self.columns)
        self.grid_layout.setColumnStretch(self.columns, 1)
        self.grid_layout.setRowStretch(rows, 1)
