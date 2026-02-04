"""Preview overlay for date stamp visualization on thumbnails."""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QFont, QPen
from datetime import datetime


class DateStampPreviewOverlay(QLabel):
    """Overlay widget that shows a preview of the date stamp on thumbnail."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.date_text = ""
        self.position = "bottom-right"
        self.color = "#FF7700"
        self.margin = 5  # Scaled down margin for thumbnail
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

        # Get settings
        self.position = config.get_setting("date_stamp_position", "bottom-right")
        self.color = config.get_setting("date_stamp_color", "#FF7700")

        # Scale margin for thumbnail (original margin / typical image size * thumbnail size)
        original_margin = config.get_setting("date_stamp_margin", 30)
        self.margin = int(original_margin * thumbnail_size / 2000)  # Assume ~2000px typical image

        # Calculate font size for thumbnail
        # This is a simplified calculation - just scale based on thumbnail size
        physical_height = config.get_setting("date_stamp_physical_height", 0.2)
        pixels_per_unit = config.get_setting("date_stamp_target_dpi", 300)

        # Parse size tag to get dimensions
        try:
            parts = image_size_tag.lower().split('x')
            if len(parts) == 2:
                width_units = float(parts[0])
                height_units = float(parts[1])
                # Assume image is oriented with larger dimension horizontal
                larger_dim = max(width_units, height_units)

                # Scale font size based on thumbnail vs actual print size
                # Font size = physical_height * pixels_per_unit * (thumbnail_size / (larger_dim * pixels_per_unit))
                self.font_size = int(physical_height * thumbnail_size / larger_dim)
                self.font_size = max(8, min(16, self.font_size))  # Clamp to readable range
            else:
                self.font_size = 10  # Default
        except:
            self.font_size = 10  # Default fallback

        self.update()

    def _format_date(self, date: datetime, format_str: str) -> str:
        """Format date according to the specified format string."""
        result = format_str
        result = result.replace("YY", date.strftime("%y"))
        result = result.replace("MM", date.strftime("%m"))
        result = result.replace("DD", date.strftime("%d"))
        return result

    def paintEvent(self, event):
        """Paint the date stamp preview."""
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
            x = widget_width - text_width - self.margin
            y = widget_height - self.margin
        elif self.position == "bottom-left":
            x = self.margin
            y = widget_height - self.margin
        elif self.position == "top-right":
            x = widget_width - text_width - self.margin
            y = text_height + self.margin
        elif self.position == "top-left":
            x = self.margin
            y = text_height + self.margin
        else:
            # Default to bottom-right
            x = widget_width - text_width - self.margin
            y = widget_height - self.margin

        # Draw glow effect (simplified - just one layer)
        glow_color = QColor(self.color)
        glow_color.setAlpha(100)
        painter.setPen(QPen(glow_color, 3))
        painter.drawText(x, y, self.date_text)

        # Draw dark outline for visibility on light backgrounds
        painter.setPen(QPen(QColor(34, 17, 0, 100), 1))
        painter.drawText(x-1, y-1, self.date_text)
        painter.drawText(x+1, y-1, self.date_text)
        painter.drawText(x-1, y+1, self.date_text)
        painter.drawText(x+1, y+1, self.date_text)

        # Draw main text
        main_color = QColor(self.color)
        painter.setPen(main_color)
        painter.drawText(x, y, self.date_text)
