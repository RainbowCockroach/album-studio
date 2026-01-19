"""Dialog for renaming images using a date picker."""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QDateEdit)
from PyQt6.QtCore import QDate
from datetime import datetime


class DateRenameDialog(QDialog):
    """Dialog for selecting a date to rename an image."""

    def __init__(self, current_filename, exif_date=None, parent=None):
        """
        Initialize the date rename dialog.

        Args:
            current_filename: Current filename to display
            exif_date: Optional datetime object from EXIF data to pre-populate
            parent: Parent widget
        """
        super().__init__(parent)
        self.selected_date = None
        self.init_ui(current_filename, exif_date)

    def init_ui(self, current_filename, exif_date):
        """Initialize the user interface."""
        self.setWindowTitle("Rename Image")
        self.setModal(True)

        layout = QVBoxLayout()

        # Info label
        info_label = QLabel(f"Current filename: {current_filename}")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Instruction label
        instruction = QLabel("Select a date for the new filename:")
        layout.addWidget(instruction)

        # Date picker with calendar popup
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")

        # Set initial date (from EXIF or current date)
        if exif_date:
            qdate = QDate(exif_date.year, exif_date.month, exif_date.day)
            self.date_edit.setDate(qdate)
        else:
            self.date_edit.setDate(QDate.currentDate())

        layout.addWidget(self.date_edit)

        # Preview label showing the generated filename
        self.preview_label = QLabel()
        self.update_preview()
        self.date_edit.dateChanged.connect(self.update_preview)
        layout.addWidget(self.preview_label)

        # Buttons
        button_layout = QHBoxLayout()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)
        button_layout.addWidget(ok_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setMinimumWidth(350)

    def update_preview(self):
        """Update the filename preview based on selected date."""
        date = self.date_edit.date()
        # Convert QDate to datetime and format like auto-rename (YYYYMMDD_000000)
        dt = datetime(date.year(), date.month(), date.day(), 0, 0, 0)
        preview_name = dt.strftime("%Y%m%d_000000")
        self.preview_label.setText(f"New filename will be: {preview_name}")
        self.preview_label.setStyleSheet("color: #666; font-style: italic; margin-top: 10px;")

    def get_selected_datetime(self):
        """
        Get the selected date as a datetime object with time set to 00:00:00.

        Returns:
            datetime object with the selected date
        """
        date = self.date_edit.date()
        return datetime(date.year(), date.month(), date.day(), 0, 0, 0)
