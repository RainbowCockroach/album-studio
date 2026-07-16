"""Dialog for finding and displaying similar images."""
import os

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QFrame, QSizePolicy, QMessageBox,
                             QProgressDialog, QSlider, QSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal
from ...services.image_similarity_service import SimilaritySearchWorker
from ..theme import (
    card_size, card_style, CARD_CAPTION_HEIGHT, CARD_OBJECT_NAME,
    CARD_PADDING, CARD_SPACING, CARD_TEXT_HEIGHT,
    CARD_HOVER_BG, CARD_HOVER_BORDER,
    CARD_UNTAGGED_BG, CARD_UNTAGGED_BORDER,
    STYLE_FILENAME_LABEL, STYLE_READONLY_FIELD, STYLE_STATUS_LABEL, TEXT_MUTED)
from ..widgets.card_grid import CardGrid

# Results use a smaller thumbnail than the main grid: this dialog is a picker,
# and more results on screen matters more than detail.
RESULT_THUMBNAIL_SIZE = 150


class ComparisonImage:
    """Simple wrapper for images from comparison directory."""

    def __init__(self, file_path, features=None):
        self.file_path = file_path
        self.feature_vector = features
        self._thumbnail = None

    def get_thumbnail(self, size=150):
        """Generate thumbnail for display."""
        if self._thumbnail is None:
            try:
                from ...utils.image_loader import ImageLoader
                self._thumbnail = ImageLoader.load_pixmap(self.file_path, max_size=size * 2)
                if not self._thumbnail.isNull() and (self._thumbnail.width() > size or self._thumbnail.height() > size):
                    self._thumbnail = self._thumbnail.scaled(
                        size, size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
            except Exception as e:
                print(f"Error creating thumbnail for {self.file_path}: {e}")
                return None
        return self._thumbnail


class ImageThumbnail(QFrame):
    """A result card: thumbnail, similarity score, filename.

    A QFrame rather than a plain QWidget because a stylesheet background and
    border simply do not paint on a bare QWidget subclass — it has no styled
    paintEvent, so the old ``ImageThumbnail { … }`` rule here silently drew
    nothing and the results floated on the dialog with no card behind them.
    """

    clicked = pyqtSignal(object)  # Emits ImageItem when clicked

    def __init__(self, image_item, similarity_score, parent=None):
        super().__init__(parent)
        self.image_item = image_item
        self.similarity_score = similarity_score
        self.init_ui()

    def init_ui(self):
        # Same object name, size and chrome as the cards in the main grid — the
        # two grids should look like one app. See theme.card_size().
        self.setObjectName(CARD_OBJECT_NAME)
        self.setFixedSize(*card_size(RESULT_THUMBNAIL_SIZE))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout()
        layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        layout.setSpacing(CARD_SPACING)

        # Image thumbnail. The label is added even when the thumbnail fails to
        # load, so a broken image leaves a gap rather than shunting the score
        # and filename up into its place.
        image_label = QLabel()
        image_label.setFixedSize(RESULT_THUMBNAIL_SIZE, RESULT_THUMBNAIL_SIZE)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumbnail = self.image_item.get_thumbnail(RESULT_THUMBNAIL_SIZE)
        if thumbnail and not thumbnail.isNull():
            image_label.setPixmap(thumbnail)
        else:
            image_label.setText("No image")
            image_label.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Similarity score
        score_label = QLabel(f"Similarity: {self.similarity_score:.1%}")
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_label.setFixedHeight(CARD_TEXT_HEIGHT)
        layout.addWidget(score_label)

        # File name
        filename_label = QLabel(os.path.basename(self.image_item.file_path))
        filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        filename_label.setWordWrap(True)
        filename_label.setStyleSheet(STYLE_FILENAME_LABEL)
        filename_label.setFixedHeight(CARD_CAPTION_HEIGHT)
        layout.addWidget(filename_label)

        self.setLayout(layout)

        # Make it look clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(card_style(
            CARD_UNTAGGED_BG, CARD_UNTAGGED_BORDER,
            hover_bg=CARD_HOVER_BG, hover_border=CARD_HOVER_BORDER))

    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.image_item)
        super().mousePressEvent(event)


class FindSimilarDialog(QDialog):
    """Dialog for finding similar images using deep learning."""

    image_selected = pyqtSignal(object)  # Emits ImageItem when user clicks on a similar image

    def __init__(self, current_project, similarity_service, config, parent=None):
        super().__init__(parent)
        self.current_project = current_project
        self.similarity_service = similarity_service
        self.config = config
        self.target_image = None
        self.similar_images = []
        self.comparison_images = []  # Images loaded from comparison directory

        self.setWindowTitle("Find Similar Images")
        self.resize(900, 700)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Instructions
        instructions = QLabel(
            "Click on an image in the main window, then click 'Find Similar' to see similar images.\n"
            "Or select an image from the current project below."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Target image section
        target_layout = QHBoxLayout()
        target_label = QLabel("Target image:")
        target_layout.addWidget(target_label)

        self.target_image_label = QLabel("No image selected")
        self.target_image_label.setStyleSheet(STYLE_READONLY_FIELD)
        target_layout.addWidget(self.target_image_label, stretch=1)

        layout.addLayout(target_layout)

        # Settings panel
        settings_layout = QHBoxLayout()

        # Number of results
        settings_layout.addWidget(QLabel("Max results:"))
        self.num_results_spin = QSpinBox()
        self.num_results_spin.setMinimum(5)
        self.num_results_spin.setMaximum(100)
        self.num_results_spin.setValue(20)
        settings_layout.addWidget(self.num_results_spin)

        settings_layout.addSpacing(20)

        # Minimum similarity threshold
        settings_layout.addWidget(QLabel("Min similarity:"))
        self.min_similarity_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_similarity_slider.setMinimum(0)
        self.min_similarity_slider.setMaximum(100)
        self.min_similarity_slider.setValue(50)
        self.min_similarity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.min_similarity_slider.setTickInterval(10)
        settings_layout.addWidget(self.min_similarity_slider)

        self.min_similarity_label = QLabel("50%")
        self.min_similarity_slider.valueChanged.connect(
            lambda v: self.min_similarity_label.setText(f"{v}%")
        )
        settings_layout.addWidget(self.min_similarity_label)

        settings_layout.addStretch()
        layout.addLayout(settings_layout)

        # Search button
        self.search_btn = QPushButton("Find Similar Images")
        self.search_btn.clicked.connect(self.find_similar)
        self.search_btn.setEnabled(False)
        layout.addWidget(self.search_btn)

        # Results grid — fixed-size cards, columns reflowed to the dialog width.
        self.results_grid = CardGrid(RESULT_THUMBNAIL_SIZE)
        layout.addWidget(self.results_grid, stretch=1)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(STYLE_STATUS_LABEL)
        layout.addWidget(self.status_label)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def set_target_image(self, image_item):
        """Set the target image to find similar images for."""
        self.target_image = image_item

        import os
        filename = os.path.basename(image_item.file_path)
        self.target_image_label.setText(filename)

        self.search_btn.setEnabled(True)
        self.status_label.setText("")

        # Clear previous results (both UI and data)
        self.clear_results()
        self.similar_images = []

    def clear_results(self):
        """Clear the results grid UI widgets only."""
        self.results_grid.clear_cards()

        # Note: Do NOT clear self.similar_images here - that's data, not UI

    def find_similar(self):
        """Find similar images to the target using background worker."""

        if not self.target_image:
            return

        # Get comparison directory
        comparison_dir = self.config.get_comparison_directory()

        if not comparison_dir:
            QMessageBox.warning(
                self,
                "No Comparison Directory",
                "Comparison directory not configured.\n\n"
                "Please set it in the Config dialog."
            )
            return

        # Get parameters
        top_k = self.num_results_spin.value()
        min_similarity = self.min_similarity_slider.value() / 100.0
        supported_formats = self.config.get_setting("supported_formats", [])

        # Create progress dialog
        progress = QProgressDialog("Preparing similarity search...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Finding Similar Images")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        # Create and start worker
        worker = SimilaritySearchWorker(
            self.similarity_service,
            self.target_image,
            comparison_dir,
            supported_formats,
            top_k=top_k,
            min_similarity=min_similarity
        )

        # Connect signals
        def on_progress(current, total, message):
            if total > 0:
                progress.setMaximum(total)
                progress.setValue(current)
            progress.setLabelText(message)

        def on_complete(results):
            progress.close()

            self.similar_images = results

            # Display results
            self.display_results()

            if not self.similar_images:
                msg = "No similar images found. Try lowering the minimum similarity threshold."
                self.status_label.setText(msg)
            else:
                msg = f"Found {len(self.similar_images)} similar images in comparison directory"
                self.status_label.setText(msg)

            # Clean up worker
            worker.deleteLater()

        def on_cancel():
            worker.cancel()
            self.status_label.setText("Search cancelled")

        worker.progress_updated.connect(on_progress)
        worker.search_complete.connect(on_complete)
        progress.canceled.connect(on_cancel)

        # Start the worker
        worker.start()

    def display_results(self):
        """Display similar images in a grid."""
        cards = []
        for image_item, similarity in self.similar_images:
            thumbnail = ImageThumbnail(image_item, similarity)
            thumbnail.clicked.connect(self.on_thumbnail_clicked)
            cards.append(thumbnail)

        self.results_grid.set_cards(cards)

    def on_thumbnail_clicked(self, image_item):
        """Handle clicking on a similar image."""
        # Emit signal so MainWindow can handle it (e.g., scroll to that image)
        self.image_selected.emit(image_item)

        # Show info
        filename = os.path.basename(image_item.file_path)
        self.status_label.setText(f"Selected: {filename}")
