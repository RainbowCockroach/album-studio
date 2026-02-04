from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QComboBox, QPushButton,
                             QLabel, QDialog, QVBoxLayout, QLineEdit,
                             QDialogButtonBox, QFormLayout)
from PyQt6.QtCore import pyqtSignal

from ...version import __version__


class ProjectToolbar(QWidget):
    """Top toolbar with project selector and new project button."""

    project_changed = pyqtSignal(str)  # Emits project name
    new_project_created = pyqtSignal(str)  # Emits project name only
    archive_requested = pyqtSignal(str)  # Emits project name to archive
    refresh_requested = pyqtSignal()
    add_photo_requested = pyqtSignal()
    delete_mode_toggled = pyqtSignal(bool)
    delete_confirmed = pyqtSignal()
    date_stamp_mode_toggled = pyqtSignal(bool)
    date_stamp_confirmed = pyqtSignal()
    update_requested = pyqtSignal()  # Emitted when user clicks update button

    def __init__(self):
        super().__init__()
        self._update_available = False
        self._update_version = ""
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

        # Refresh button
        self.refresh_btn = QPushButton("Reload project")
        self.refresh_btn.clicked.connect(self.on_refresh_clicked)
        layout.addWidget(self.refresh_btn)

        # New project button
        self.new_project_btn = QPushButton("New Project")
        self.new_project_btn.clicked.connect(self.on_new_project_clicked)
        layout.addWidget(self.new_project_btn)

        # Archive project button
        self.archive_project_btn = QPushButton("Archive")
        self.archive_project_btn.clicked.connect(self.on_archive_project_clicked)
        layout.addWidget(self.archive_project_btn)

        # ***************** Spacer *****************
        layout.addStretch()
        # ***************** Spacer *****************

        # Total cost display
        self.total_cost_label = QLabel("Total: 0")
        self.total_cost_label.setStyleSheet("font-weight: bold; padding: 0 10px;")
        layout.addWidget(self.total_cost_label)

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

        # Add Date Stamp button (Normal mode)
        self.date_stamp_btn = QPushButton("Add Date Stamp")
        self.date_stamp_btn.clicked.connect(lambda: self.toggle_date_stamp_mode(True))
        layout.addWidget(self.date_stamp_btn)

        # Date Stamp mode buttons (Hidden by default)
        self.date_stamp_confirm_btn = QPushButton("Mark to set date stamp")
        self.date_stamp_confirm_btn.setStyleSheet("background-color: #ccf0cc; color: green; font-weight: bold;")
        self.date_stamp_confirm_btn.clicked.connect(self.date_stamp_confirmed.emit)
        self.date_stamp_confirm_btn.hide()
        layout.addWidget(self.date_stamp_confirm_btn)

        self.date_stamp_cancel_btn = QPushButton("Cancel")
        self.date_stamp_cancel_btn.clicked.connect(lambda: self.toggle_date_stamp_mode(False))
        self.date_stamp_cancel_btn.hide()
        layout.addWidget(self.date_stamp_cancel_btn)

        layout.addStretch()

        # Update button (hidden by default, shown when update available)
        self.update_btn = QPushButton()
        self.update_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; "
            "padding: 5px 15px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.update_btn.clicked.connect(self.update_requested.emit)
        self.update_btn.hide()
        layout.addWidget(self.update_btn)

        # Version label
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setStyleSheet("color: #888; font-size: 11px; padding: 0 5px;")
        layout.addWidget(self.version_label)

        self.setLayout(layout)

    def toggle_delete_mode(self, enabled: bool):
        """Toggle between normal and delete mode."""
        self.delete_mode_toggled.emit(enabled)

        self.new_project_btn.setVisible(not enabled)
        self.archive_project_btn.setVisible(not enabled)
        self.refresh_btn.setVisible(not enabled)
        self.project_combo.setEnabled(not enabled)
        self.add_photo_btn.setVisible(not enabled)
        self.delete_photo_btn.setVisible(not enabled)
        self.date_stamp_btn.setVisible(not enabled)

        self.delete_confirm_btn.setVisible(enabled)
        self.delete_cancel_btn.setVisible(enabled)

    def toggle_date_stamp_mode(self, enabled: bool):
        """Toggle between normal and date stamp selection mode."""
        self.date_stamp_mode_toggled.emit(enabled)

        self.new_project_btn.setVisible(not enabled)
        self.archive_project_btn.setVisible(not enabled)
        self.refresh_btn.setVisible(not enabled)
        self.project_combo.setEnabled(not enabled)
        self.add_photo_btn.setVisible(not enabled)
        self.delete_photo_btn.setVisible(not enabled)
        self.date_stamp_btn.setVisible(not enabled)

        self.date_stamp_confirm_btn.setVisible(enabled)
        self.date_stamp_cancel_btn.setVisible(enabled)

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
            name = dialog.get_values()
            self.new_project_created.emit(name)

    def on_archive_project_clicked(self):
        """Handle archive button click."""
        project_name = self.get_current_project()
        if project_name:
            self.archive_requested.emit(project_name)

    def on_refresh_clicked(self):
        """Handle refresh button click."""
        self.refresh_requested.emit()

    def set_total_cost(self, cost: float):
        """Update the total cost display."""
        self.total_cost_label.setText(f"Total: {cost:.2f}")

    def show_update_available(self, version: str):
        """Show the update available button."""
        self._update_available = True
        self._update_version = version
        self.update_btn.setText(f"Update Available (v{version})")
        self.update_btn.show()

    def hide_update_button(self):
        """Hide the update button."""
        self._update_available = False
        self.update_btn.hide()

    def set_update_button_downloading(self):
        """Show downloading state on update button."""
        self.update_btn.setText("Downloading...")
        self.update_btn.setEnabled(False)

    def set_update_button_installing(self):
        """Show installing state on update button."""
        self.update_btn.setText("Installing...")
        self.update_btn.setEnabled(False)


class NewProjectDialog(QDialog):
    """Dialog for creating a new project."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Form layout for inputs
        form_layout = QFormLayout()

        # Project name
        self.name_input = QLineEdit()
        form_layout.addRow("Project Name:", self.name_input)

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

    def get_values(self) -> str:
        """Get the entered project name."""
        return self.name_input.text().strip()
