from PyQt6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QPushButton, QLabel
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QPalette


class ToolbarBottom(QWidget):
    """Bottom panel with tag selectors and action buttons."""

    crop_requested = pyqtSignal()  # Enter preview mode
    save_requested = pyqtSignal()  # Save and crop images
    cancel_requested = pyqtSignal()  # Cancel preview mode
    config_requested = pyqtSignal()  # Config button clicked
    detail_toggled = pyqtSignal(bool)  # Show/hide detail panel
    tags_changed = pyqtSignal(str, str)  # Emits album, size
    find_similar_requested = pyqtSignal()  # Find similar images
    rotate_requested = pyqtSignal()  # Rotate selected image

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Config button
        self.config_btn = QPushButton("Config")
        self.config_btn.setToolTip("Configure size groups and sizes")
        self.config_btn.clicked.connect(self.on_config_clicked)
        layout.addWidget(self.config_btn)
        
        # Detail toggle button
        self.detail_btn = QPushButton("Show detail")
        self.detail_btn.setCheckable(True)
        self.detail_btn.toggled.connect(self.on_detail_toggled)
        layout.addWidget(self.detail_btn)

        # Find similar button
        self.find_similar_btn = QPushButton("Find similar")
        self.find_similar_btn.setToolTip("Find visually similar images")
        self.find_similar_btn.clicked.connect(self.on_find_similar_clicked)
        layout.addWidget(self.find_similar_btn)

        # Rotate button
        self.rotate_btn = QPushButton("Rotate")
        self.rotate_btn.setToolTip("Rotate selected image 90° clockwise")
        self.rotate_btn.clicked.connect(self.on_rotate_clicked)
        layout.addWidget(self.rotate_btn)

        # ***************** Spacer *****************
        layout.addStretch()
        # ***************** Spacer *****************

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
        self.size_combo.currentTextChanged.connect(self.on_size_changed)
        layout.addWidget(self.size_combo)

        # Crop button (shows preview mode)
        self.crop_btn = QPushButton("Crop")
        self.crop_btn.clicked.connect(self.on_crop_clicked)
        layout.addWidget(self.crop_btn)

        # Cancel button (hidden initially)
        self.cancel_btn = QPushButton("Cancel")
        pal = self.cancel_btn.palette()
        pal.setColor(QPalette.ColorRole.Button, QColor("yellow"))
        self.cancel_btn.setPalette(pal)
        self.cancel_btn.setAutoFillBackground(True) 
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)
        self.cancel_btn.hide()
        layout.addWidget(self.cancel_btn)

        # Save button (hidden initially)
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.on_save_clicked)
        self.save_btn.hide()
        layout.addWidget(self.save_btn)

        self.setLayout(layout)

        # Initialize album list
        self.load_size_group()

    def set_enabled(self, enabled: bool):
        """Enable or disable all controls."""
        self.size_group_combo.setEnabled(enabled)
        self.size_combo.setEnabled(enabled)
        self.config_btn.setEnabled(enabled)
        self.crop_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)
        self.rotate_btn.setEnabled(enabled)

    #region | Group + size dropdowns
    def load_size_group(self):
        """Load size group list from config."""
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

        self.on_size_changed()
    
    def on_size_changed(self):
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
    #endregion

    #region | Crop buttons
    def on_crop_clicked(self):
        """Handle crop button click - enter preview mode."""
        self.crop_requested.emit()
        self.show_preview_mode_buttons()

    def on_cancel_clicked(self):
        """Handle cancel button click - exit preview without saving."""
        self.cancel_requested.emit()
        self.show_normal_mode_buttons()

    def on_save_clicked(self):
        """Handle save button click - crop and save images."""
        self.save_requested.emit()
        self.show_normal_mode_buttons()

    def show_preview_mode_buttons(self):
        """Show Cancel and Save buttons, hide Crop button."""
        self.crop_btn.hide()
        self.cancel_btn.show()
        self.save_btn.show()

    def show_normal_mode_buttons(self):
        """Show Crop button, hide Cancel and Save buttons."""
        self.cancel_btn.hide()
        self.save_btn.hide()
        self.crop_btn.show()
    #endregion

    #region | Config button
    def on_config_clicked(self):
        """Handle config button click."""
        self.config_requested.emit()
    #endregion
    
    #region | Detail button
    def on_detail_toggled(self, checked: bool):
        """Handle detail button toggle."""
        self.detail_btn.setText("Hide detail" if checked else "Show detail")
        self.detail_toggled.emit(checked)
    #endregion

    #region | Find Similar button
    def on_find_similar_clicked(self):
        """Handle find similar button click."""
        self.find_similar_requested.emit()
    #endregion

    #region | Rotate button
    def on_rotate_clicked(self):
        """Handle rotate button click."""
        self.rotate_requested.emit()
    #endregion
