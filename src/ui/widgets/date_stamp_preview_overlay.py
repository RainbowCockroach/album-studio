"""Preview overlay for date stamp visualization on thumbnails."""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QFont
from datetime import datetime


# Simple preview color - just for showing stamp position and size
PREVIEW_COLOR = "#FF9933"


class DateStampPreviewOverlay(QLabel):
    """
    Overlay widget that shows a preview of the date stamp on thumbnail.

    This is a simplified preview showing only the text position and size.
    The actual rendering with full glow effects happens during export.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.date_text = ""
        self.position = "bottom-right"
        self.stamp_margin = 5  # Scaled down margin for thumbnail
        self.font_size = 10  # Scaled down font size for thumbnail

        # Make overlay transparent to mouse events so clicks pass through
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # Set transparent background
        self.setStyleSheet("background-color: transparent;")

    def set_preview_data(self, date: datetime, config, thumbnail_size: int, image_size_tag: str):
        """
        Set the date and configuration for preview.

        Args:
            date: Date to display
            config: Configuration object
            thumbnail_size: Size of the thumbnail in pixels
            image_size_tag: Size tag of the image (e.g., "9x6")
        """
        # Format date
        date_format = config.get_setting("date_stamp_format", "YY.MM.DD")
        self.date_text = self._format_date(date, date_format)

        # Get position setting
        self.position = config.get_setting("date_stamp_position", "bottom-right")

        # Calculate font size for thumbnail
        physical_height = config.get_setting("date_stamp_physical_height", 0.2)

        # Parse size tag to get dimensions
        try:
            parts = image_size_tag.lower().split('x')
            if len(parts) == 2:
                width_units = float(parts[0])
                height_units = float(parts[1])
                # Assume image is oriented with larger dimension horizontal
                larger_dim = max(width_units, height_units)

                # Scale font size based on thumbnail vs actual print size
                self.font_size = int(physical_height * thumbnail_size / larger_dim)
                self.font_size = max(8, min(16, self.font_size))  # Clamp to readable range
            else:
                self.font_size = 10  # Default
        except Exception:
            self.font_size = 10  # Default fallback

        # Auto-calculate margin based on font size (50% of font height)
        self.stamp_margin = max(2, int(self.font_size * 0.5))

        self.update()

    def _format_date(self, date: datetime, format_str: str) -> str:
        """Format date according to the specified format string."""
        result = format_str
        result = result.replace("YY", date.strftime("%y"))
        result = result.replace("MM", date.strftime("%m"))
        result = result.replace("DD", date.strftime("%d"))
        return result

    def paintEvent(self, event):
        """Paint the date stamp preview with simple solid color."""
        if not self.date_text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Set font
        font = QFont("Courier", self.font_size, QFont.Weight.Bold)
        painter.setFont(font)

        # Get text size
        metrics = painter.fontMetrics()
        text_rect = metrics.boundingRect(self.date_text)
        text_width = text_rect.width()
        text_height = text_rect.height()

        # Calculate position
        widget_width = self.width()
        widget_height = self.height()

        if self.position == "bottom-right":
            x = widget_width - text_width - self.stamp_margin
            y = widget_height - self.stamp_margin
        elif self.position == "bottom-left":
            x = self.stamp_margin
            y = widget_height - self.stamp_margin
        elif self.position == "top-right":
            x = widget_width - text_width - self.stamp_margin
            y = text_height + self.stamp_margin
        elif self.position == "top-left":
            x = self.stamp_margin
            y = text_height + self.stamp_margin
        else:
            # Default to bottom-right
            x = widget_width - text_width - self.stamp_margin
            y = widget_height - self.stamp_margin

        # Draw simple solid color text (no glow/outline - just for size preview)
        painter.setPen(QColor(PREVIEW_COLOR))
        painter.drawText(int(x), int(y), self.date_text)
