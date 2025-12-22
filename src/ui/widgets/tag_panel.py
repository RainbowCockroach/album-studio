from PyQt6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QPushButton, QLabel
from PyQt6.QtCore import pyqtSignal


class TagPanel(QWidget):
    """Bottom panel with tag selectors and action buttons."""

    crop_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    tags_changed = pyqtSignal(str, str)  # Emits album, size

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Album selector
        album_label = QLabel("Album:")
        layout.addWidget(album_label)

        self.album_combo = QComboBox()
        self.album_combo.setMinimumWidth(150)
        self.album_combo.currentTextChanged.connect(self.on_album_changed)
        layout.addWidget(self.album_combo)

        # Size selector
        size_label = QLabel("Size:")
        layout.addWidget(size_label)

        self.size_combo = QComboBox()
        self.size_combo.setMinimumWidth(100)
        self.size_combo.currentTextChanged.connect(self.on_tags_changed)
        layout.addWidget(self.size_combo)

        layout.addStretch()

        # Refresh button
        self.refresh_btn = QPushButton("Refresh & Rename Images")
        self.refresh_btn.clicked.connect(self.on_refresh_clicked)
        layout.addWidget(self.refresh_btn)

        # Crop button
        self.crop_btn = QPushButton("Crop All Tagged Images")
        self.crop_btn.clicked.connect(self.on_crop_clicked)
        layout.addWidget(self.crop_btn)

        self.setLayout(layout)

        # Initialize album list
        self.load_albums()

    def load_albums(self):
        """Load album list from config."""
        album_names = self.config.get_album_names()
        self.album_combo.clear()
        self.album_combo.addItems(album_names)

    def on_album_changed(self, album_name: str):
        """Handle album selection change - update size dropdown."""
        if not album_name:
            self.size_combo.clear()
            return

        # Get available sizes for this album
        sizes = self.config.get_sizes_for_album(album_name)
        self.size_combo.clear()
        self.size_combo.addItems(sizes)

        self.on_tags_changed()

    def on_tags_changed(self):
        """Emit signal when tags change."""
        album = self.album_combo.currentText()
        size = self.size_combo.currentText()
        self.tags_changed.emit(album, size)

    def get_selected_tags(self) -> tuple:
        """Get currently selected album and size."""
        return (
            self.album_combo.currentText(),
            self.size_combo.currentText()
        )

    def on_crop_clicked(self):
        """Handle crop button click."""
        self.crop_requested.emit()

    def on_refresh_clicked(self):
        """Handle refresh button click."""
        self.refresh_requested.emit()

    def set_enabled(self, enabled: bool):
        """Enable or disable all controls."""
        self.album_combo.setEnabled(enabled)
        self.size_combo.setEnabled(enabled)
        self.crop_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
