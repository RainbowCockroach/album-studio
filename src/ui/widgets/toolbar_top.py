from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QComboBox, QPushButton,
                             QLabel, QDialog, QVBoxLayout, QLineEdit,
                             QFileDialog, QDialogButtonBox, QFormLayout)
from PyQt6.QtCore import pyqtSignal


class ProjectToolbar(QWidget):
    """Top toolbar with project selector and new project button."""

    project_changed = pyqtSignal(str)  # Emits project name
    new_project_created = pyqtSignal(str, str, str)  # Emits name, input_folder, output_folder
    add_photo_requested = pyqtSignal()
    delete_mode_toggled = pyqtSignal(bool)
    delete_confirmed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Project label
        label = QLabel("Project:")
        layout.addWidget(label)

        # Project selector dropdown
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(200)
        self.project_combo.currentTextChanged.connect(self.on_project_changed)
        layout.addWidget(self.project_combo)

        # New project button
        self.new_project_btn = QPushButton("New Project")
        self.new_project_btn.clicked.connect(self.on_new_project_clicked)
        layout.addWidget(self.new_project_btn)

        # Add Photo button
        self.add_photo_btn = QPushButton("Add Photo")
        self.add_photo_btn.clicked.connect(self.add_photo_requested.emit)
        layout.addWidget(self.add_photo_btn)

        # Delete Photo button (Normal mode)
        self.delete_photo_btn = QPushButton("Delete Photo")
        self.delete_photo_btn.clicked.connect(lambda: self.toggle_delete_mode(True))
        layout.addWidget(self.delete_photo_btn)

        # Delete mode buttons (Hidden by default)
        self.delete_confirm_btn = QPushButton("Delete")
        self.delete_confirm_btn.setStyleSheet("background-color: #ffcccc; color: red; font-weight: bold;")
        self.delete_confirm_btn.clicked.connect(self.delete_confirmed.emit)
        self.delete_confirm_btn.hide()
        layout.addWidget(self.delete_confirm_btn)

        self.delete_cancel_btn = QPushButton("Cancel")
        self.delete_cancel_btn.clicked.connect(lambda: self.toggle_delete_mode(False))
        self.delete_cancel_btn.hide()
        layout.addWidget(self.delete_cancel_btn)

        layout.addStretch()

        self.setLayout(layout)

    def toggle_delete_mode(self, enabled: bool):
        """Toggle between normal and delete mode."""
        self.delete_mode_toggled.emit(enabled)
        
        self.new_project_btn.setVisible(not enabled)
        self.project_combo.setEnabled(not enabled)
        self.add_photo_btn.setVisible(not enabled)
        self.delete_photo_btn.setVisible(not enabled)
        
        self.delete_confirm_btn.setVisible(enabled)
        self.delete_cancel_btn.setVisible(enabled)

    def set_projects(self, project_names: list):
        """Update the project dropdown with available projects."""
        current = self.project_combo.currentText()
        self.project_combo.clear()
        self.project_combo.addItems(project_names)

        # Try to restore previous selection
        if current and current in project_names:
            self.project_combo.setCurrentText(current)

    def get_current_project(self) -> str:
        """Get the currently selected project name."""
        return self.project_combo.currentText()

    def set_current_project(self, name: str):
        """Set the current project by name."""
        index = self.project_combo.findText(name)
        if index >= 0:
            self.project_combo.setCurrentIndex(index)

    def on_project_changed(self, project_name: str):
        """Handle project selection change."""
        if project_name:
            self.project_changed.emit(project_name)

    def on_new_project_clicked(self):
        """Show dialog to create new project."""
        dialog = NewProjectDialog(self)
        if dialog.exec():
            name, input_folder, output_folder = dialog.get_values()
            self.new_project_created.emit(name, input_folder, output_folder)


class NewProjectDialog(QDialog):
    """Dialog for creating a new project."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setMinimumWidth(500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Form layout for inputs
        form_layout = QFormLayout()

        # Project name
        self.name_input = QLineEdit()
        form_layout.addRow("Project Name:", self.name_input)

        # Input folder
        input_layout = QHBoxLayout()
        self.input_folder_input = QLineEdit()
        input_browse_btn = QPushButton("Browse...")
        input_browse_btn.clicked.connect(self.browse_input_folder)
        input_layout.addWidget(self.input_folder_input)
        input_layout.addWidget(input_browse_btn)
        form_layout.addRow("Input Folder:", input_layout)

        # Output folder
        output_layout = QHBoxLayout()
        self.output_folder_input = QLineEdit()
        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self.browse_output_folder)
        output_layout.addWidget(self.output_folder_input)
        output_layout.addWidget(output_browse_btn)
        form_layout.addRow("Output Folder:", output_layout)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def browse_input_folder(self):
        """Browse for input folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.input_folder_input.setText(folder)

    def browse_output_folder(self):
        """Browse for output folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder_input.setText(folder)

    def get_values(self) -> tuple:
        """Get the entered values."""
        return (
            self.name_input.text().strip(),
            self.input_folder_input.text().strip(),
            self.output_folder_input.text().strip()
        )
