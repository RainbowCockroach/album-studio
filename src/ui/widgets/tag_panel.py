from PyQt6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QPushButton, QLabel
from PyQt6.QtCore import pyqtSignal


class TagPanel(QWidget):
    """Bottom panel with tag selectors and action buttons."""

    crop_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    preview_requested = pyqtSignal()  # Preview & adjust crops
    config_requested = pyqtSignal()  # Config button clicked
    tags_changed = pyqtSignal(str, str)  # Emits album, size

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Album selector
        size_group_label = QLabel("Size group:")
        layout.addWidget(size_group_label)

        self.size_group_combo = QComboBox()
        self.size_group_combo.setMinimumWidth(150)
        self.size_group_combo.currentTextChanged.connect(self.on_size_group_changed)
        layout.addWidget(self.size_group_combo)

        # Size selector
        size_label = QLabel("Size:")
        layout.addWidget(size_label)

        self.size_combo = QComboBox()
        self.size_combo.setMinimumWidth(100)
        self.size_combo.currentTextChanged.connect(self.on_tags_changed)
        layout.addWidget(self.size_combo)

        # Config button
        self.config_btn = QPushButton("Config")
        self.config_btn.setToolTip("Configure size groups and sizes")
        self.config_btn.clicked.connect(self.on_config_clicked)
        layout.addWidget(self.config_btn)

        layout.addStretch()

        # Refresh button
        self.refresh_btn = QPushButton("Refresh & Rename Images")
        self.refresh_btn.clicked.connect(self.on_refresh_clicked)
        layout.addWidget(self.refresh_btn)

        # Preview button
        self.preview_btn = QPushButton("Preview & Adjust Crops")
        self.preview_btn.clicked.connect(self.on_preview_clicked)
        layout.addWidget(self.preview_btn)

        # Crop button
        self.crop_btn = QPushButton("Crop All Tagged Images")
        self.crop_btn.clicked.connect(self.on_crop_clicked)
        layout.addWidget(self.crop_btn)

        self.setLayout(layout)

        # Initialize album list
        self.load_size_group()

    def load_size_group(self):
        """Load album list from config."""
        size_group_names = self.config.get_size_group_names()
        self.size_group_combo.clear()
        self.size_group_combo.addItems(size_group_names)

    def on_size_group_changed(self, size_group_name: str):
        """Handle size group selection change - update size dropdown with aliases."""
        if not size_group_name:
            self.size_combo.clear()
            return

        # Get sizes with aliases from config
        sizes_with_aliases = self.config.get_sizes_with_aliases_for_group(size_group_name)

        self.size_combo.clear()
        for size_data in sizes_with_aliases:
            size_ratio = size_data["ratio"]
            alias = size_data["alias"]
            # Add item with alias as display text, size_ratio as user data
            self.size_combo.addItem(alias, userData=size_ratio)

        self.on_tags_changed()

    def on_tags_changed(self):
        """Emit signal when tags change."""
        album = self.size_group_combo.currentText()
        size = self.size_combo.currentText()
        self.tags_changed.emit(album, size)

    def get_selected_tags(self) -> tuple:
        """Get currently selected album and size ratio."""
        album = self.size_group_combo.currentText()
        # Get the size ratio from user data, not the display text (alias)
        size_ratio = self.size_combo.currentData()
        return (album, size_ratio if size_ratio else "")

    def on_crop_clicked(self):
        """Handle crop button click."""
        self.crop_requested.emit()

    def on_preview_clicked(self):
        """Handle preview button click."""
        self.preview_requested.emit()

    def on_refresh_clicked(self):
        """Handle refresh button click."""
        self.refresh_requested.emit()

    def on_config_clicked(self):
        """Handle config button click."""
        self.config_requested.emit()

    def set_enabled(self, enabled: bool):
        """Enable or disable all controls."""
        self.size_group_combo.setEnabled(enabled)
        self.size_combo.setEnabled(enabled)
        self.config_btn.setEnabled(enabled)
        self.crop_btn.setEnabled(enabled)
        self.preview_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
