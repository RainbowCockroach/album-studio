"""Regression tests for the similar-images result cards.

The results grid stretched exactly like the main grid once did, for the same
reason, and was fixed the same way: fixed-size cards handed to a ``CardGrid``.
``CardGrid`` never resizes a card, so this pins the dialog's end of that deal.

Only the card is built here, not the dialog -- ``FindSimilarDialog.__init__``
wants a project, a similarity service and a config, and none of that has any
bearing on how a result card is laid out.
"""

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame

from src.ui.dialogs.find_similar_dialog import (
    RESULT_THUMBNAIL_SIZE, ImageThumbnail)
from src.ui.theme import CARD_OBJECT_NAME, card_size


class StubImage:
    """Stands in for ComparisonImage/ImageItem: a path and a thumbnail."""

    def __init__(self, file_path="/photos/some_photo.jpg", thumbnail=True):
        self.file_path = file_path
        self._thumbnail = thumbnail

    def get_thumbnail(self, size=150):
        if not self._thumbnail:
            return None
        pixmap = QPixmap(size, size // 2)  # Landscape: letterboxed in the square.
        pixmap.fill()
        return pixmap


class TestResultCard:
    def test_card_is_the_shared_card_size(self, qapp):
        card = ImageThumbnail(StubImage(), 0.595)

        assert (card.width(), card.height()) == card_size(RESULT_THUMBNAIL_SIZE)

    def test_card_is_a_styleable_frame(self, qapp):
        """A stylesheet background/border does not paint on a bare QWidget
        subclass -- the old card set one and silently drew nothing."""
        card = ImageThumbnail(StubImage(), 0.5)

        assert isinstance(card, QFrame)
        assert card.objectName() == CARD_OBJECT_NAME

    def test_a_card_with_no_thumbnail_keeps_the_image_row(self, qapp):
        """The image label used to be added only when the thumbnail loaded, so
        a broken image shunted the score and filename up into its place. Assert
        the row is there rather than that the card is the right size: the card
        is a fixed size either way, which would make that check vacuous."""
        broken = ImageThumbnail(StubImage(thumbnail=False), 0.5)

        layout = broken.layout()
        assert layout.count() == 3  # image, score, filename
        image_label = layout.itemAt(0).widget()
        assert (image_label.width(), image_label.height()) == \
            (RESULT_THUMBNAIL_SIZE, RESULT_THUMBNAIL_SIZE)

    def test_the_image_row_is_the_same_whether_or_not_the_photo_loads(self, qapp):
        # Both cards are bound to names deliberately: let one be a temporary
        # and Python collects it mid-test, taking its Qt children with it.
        good = ImageThumbnail(StubImage(), 0.5)
        broken = ImageThumbnail(StubImage(thumbnail=False), 0.5)

        assert good.layout().itemAt(0).widget().size() == \
            broken.layout().itemAt(0).widget().size()

    def test_clicking_emits_the_image(self, qapp):
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtGui import QMouseEvent

        image = StubImage()
        card = ImageThumbnail(image, 0.5)
        received = []
        card.clicked.connect(received.append)

        card.mousePressEvent(QMouseEvent(
            QMouseEvent.Type.MouseButtonPress, QPointF(5, 5),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier))

        assert received == [image]
