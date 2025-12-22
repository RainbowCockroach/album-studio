from PyQt6.QtWidgets import (QWidget, QScrollArea, QGridLayout, QLabel,
                             QVBoxLayout, QFrame, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QPalette


class ImageGrid(QWidget):
    """Grid view for displaying images with thumbnails."""

    image_clicked = pyqtSignal(object)  # Emits ImageItem
    image_double_clicked = pyqtSignal(object)  # Emits ImageItem

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_project = None
        self.thumbnail_size = config.get_setting("thumbnail_size", 200)
        self.columns = config.get_setting("grid_columns", 5)
        self.image_widgets = {}  # Map ImageItem to ImageWidget
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create grid container
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)
        self.grid_container.setLayout(self.grid_layout)

        scroll_area.setWidget(self.grid_container)
        layout.addWidget(scroll_area)

        self.setLayout(layout)

    def set_project(self, project):
        """Set the current project and load its images."""
        self.current_project = project
        self.load_images()

    def load_images(self):
        """Load images from current project into grid."""
        self.clear_grid()

        if not self.current_project:
            return

        row = 0
        col = 0

        for image_item in self.current_project.images:
            # Create image widget
            image_widget = ImageWidget(image_item, self.thumbnail_size)
            image_widget.clicked.connect(lambda item=image_item: self.on_image_clicked(item))
            image_widget.double_clicked.connect(lambda item=image_item: self.on_image_double_clicked(item))

            # Add to grid
            self.grid_layout.addWidget(image_widget, row, col)
            self.image_widgets[image_item] = image_widget

            # Update position
            col += 1
            if col >= self.columns:
                col = 0
                row += 1

    def clear_grid(self):
        """Clear all images from the grid."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.image_widgets.clear()

    def refresh_display(self):
        """Refresh the display of all images (update borders based on tags)."""
        for image_item, widget in self.image_widgets.items():
            widget.update_border()

    def on_image_clicked(self, image_item):
        """Handle single click on image."""
        self.image_clicked.emit(image_item)

    def on_image_double_clicked(self, image_item):
        """Handle double click on image."""
        self.image_double_clicked.emit(image_item)


class ImageWidget(QFrame):
    """Widget representing a single image in the grid."""

    clicked = pyqtSignal()
    double_clicked = pyqtSignal()

    def __init__(self, image_item, thumbnail_size):
        super().__init__()
        self.image_item = image_item
        self.thumbnail_size = thumbnail_size
        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self._handle_single_click)
        self.double_click_flag = False
        self.init_ui()

    def init_ui(self):
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(3)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Load thumbnail
        pixmap = self.image_item.get_thumbnail(self.thumbnail_size)
        if pixmap:
            self.thumbnail_label.setPixmap(pixmap)
        else:
            self.thumbnail_label.setText("No Image")

        layout.addWidget(self.thumbnail_label)

        # Filename label
        filename = self.image_item.file_path.split('/')[-1]
        filename_label = QLabel(filename)
        filename_label.setWordWrap(True)
        filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(filename_label)

        # Tag info label
        self.tag_label = QLabel()
        self.tag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tag_label.setWordWrap(True)
        layout.addWidget(self.tag_label)

        self.setLayout(layout)
        self.update_border()

    def update_border(self):
        """Update border color based on tag status."""
        if self.image_item.is_fully_tagged():
            # Green border for fully tagged
            self.setStyleSheet("QFrame { border: 3px solid green; }")
            tag_text = f"{self.image_item.album_tag}\n{self.image_item.size_tag}"
            self.tag_label.setText(tag_text)
        elif self.image_item.has_tags():
            # Yellow border for partially tagged
            self.setStyleSheet("QFrame { border: 3px solid orange; }")
            tag_text = f"{self.image_item.album_tag or ''}\n{self.image_item.size_tag or ''}"
            self.tag_label.setText(tag_text)
        else:
            # Default border for untagged
            self.setStyleSheet("QFrame { border: 3px solid lightgray; }")
            self.tag_label.setText("No tags")

    def _handle_single_click(self):
        """Handle single click after delay (if not double-clicked)."""
        if self.double_click_flag:
            # Reset flag and ignore this single click
            self.double_click_flag = False
            return
        self.clicked.emit()

    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_pos = event.pos()

    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Use system's double-click interval
            interval = QApplication.doubleClickInterval()
            self.click_timer.start(interval + 50)  # Add 50ms buffer

    def mouseDoubleClickEvent(self, event):
        """Handle double click events."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Stop any pending single click timers
            self.click_timer.stop()
            # Set flag to ignore next single click
            self.double_click_flag = True
            # Emit double click signal
            self.double_clicked.emit()
