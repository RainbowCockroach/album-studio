from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QLabel, QHeaderView, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal

class DetailPanel(QWidget):
    """Sidebar widget to display detailed information about the selected image."""

    rename_requested = pyqtSignal(object)  # Emits the current image item

    def __init__(self):
        super().__init__()
        self.current_image_item = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QLabel("Image Details")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-weight: bold; padding: 10px; background-color: #333; color: white;")
        layout.addWidget(header)

        # Tree widget for properties
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tree)

        # Rename button
        self.rename_btn = QPushButton("Rename")
        self.rename_btn.clicked.connect(self.on_rename_clicked)
        self.rename_btn.setEnabled(False)
        layout.addWidget(self.rename_btn)

        self.setLayout(layout)
        self.setMinimumWidth(250)
        self.setMaximumWidth(350)
        
        # Initially hidden
        self.hide()

    def set_data(self, data: dict, image_item=None):
        """Update the panel with new data."""
        self.tree.clear()
        self.current_image_item = image_item
        
        if not data:
            self.rename_btn.setEnabled(False)
            return

        for key, value in data.items():
            item = QTreeWidgetItem(self.tree)
            item.setText(0, str(key))
            item.setText(1, str(value))
        
        # Enable rename button if we have an image item
        self.rename_btn.setEnabled(image_item is not None)
    
    def clear(self):
        """Clear the panel."""
        self.tree.clear()
        self.current_image_item = None
        self.rename_btn.setEnabled(False)
    
    def on_rename_clicked(self):
        """Handle rename button click."""
        if self.current_image_item:
            self.rename_requested.emit(self.current_image_item)
