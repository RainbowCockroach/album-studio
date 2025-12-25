from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QLabel, QHeaderView)
from PyQt6.QtCore import Qt

class DetailPanel(QWidget):
    """Sidebar widget to display detailed information about the selected image."""

    def __init__(self):
        super().__init__()
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

        self.setLayout(layout)
        self.setMinimumWidth(250)
        self.setMaximumWidth(350)
        
        # Initially hidden
        self.hide()

    def set_data(self, data: dict):
        """Update the panel with new data."""
        self.tree.clear()
        
        if not data:
            return

        for key, value in data.items():
            item = QTreeWidgetItem(self.tree)
            item.setText(0, str(key))
            item.setText(1, str(value))
    
    def clear(self):
        """Clear the panel."""
        self.tree.clear()
