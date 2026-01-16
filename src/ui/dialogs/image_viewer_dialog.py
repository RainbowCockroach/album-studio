"""Dialog for viewing an image in detail with zoom support."""
from typing import Optional
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea, QApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPixmap, QWheelEvent, QMouseEvent, QKeyEvent
from src.utils.image_loader import ImageLoader


class ZoomableImageLabel(QLabel):
    """A QLabel that supports zooming and panning for an image."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.original_pixmap = None
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0

        # For panning
        self.panning = False
        self.pan_start = QPoint()
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_image(self, pixmap: QPixmap, initial_zoom: Optional[float] = None):
        """Set the image to display."""
        self.original_pixmap = pixmap
        if initial_zoom is not None:
            self.zoom_factor = initial_zoom
        else:
            self.zoom_factor = 1.0
        self.update_display()

    def update_display(self):
        """Update the displayed image based on current zoom level."""
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled_width = int(self.original_pixmap.width() * self.zoom_factor)
            scaled_height = int(self.original_pixmap.height() * self.zoom_factor)

            scaled_pixmap = self.original_pixmap.scaled(
                scaled_width, scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
            self.adjustSize()

    def wheelEvent(self, event: Optional[QWheelEvent]):
        """Handle mouse wheel for zooming."""
        if event:
            if event.angleDelta().y() > 0:
                # Zoom in
                self.zoom_factor = min(self.zoom_factor * 1.15, self.max_zoom)
            else:
                # Zoom out
                self.zoom_factor = max(self.zoom_factor / 1.15, self.min_zoom)

            self.update_display()
            event.accept()

    def mousePressEvent(self, event: Optional[QMouseEvent]):
        """Start panning on mouse press."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            self.pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]):
        """Stop panning on mouse release."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            self.panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: Optional[QMouseEvent]):
        """Handle panning when dragging."""
        if event and self.panning:
            delta = event.pos() - self.pan_start
            self.pan_start = event.pos()

            # Get the scroll area parent
            scroll_area = self.parent()
            if scroll_area and isinstance(scroll_area.parent(), QScrollArea):
                scroll_area = scroll_area.parent()
            elif isinstance(scroll_area, QScrollArea):
                pass
            else:
                # Try to find scroll area in ancestors
                widget = self.parent()
                while widget:
                    if isinstance(widget, QScrollArea):
                        scroll_area = widget
                        break
                    widget = widget.parent()

            if isinstance(scroll_area, QScrollArea):
                h_bar = scroll_area.horizontalScrollBar()
                v_bar = scroll_area.verticalScrollBar()
                if h_bar:
                    h_bar.setValue(h_bar.value() - delta.x())
                if v_bar:
                    v_bar.setValue(v_bar.value() - delta.y())

        super().mouseMoveEvent(event)


class ImageViewerDialog(QDialog):
    """Dialog for viewing an image in detail with zoom support."""

    def __init__(self, image_path: str, parent=None, image_item=None, config=None):
        super().__init__(parent)
        self.image_path = image_path
        self.image_item = image_item
        self.config = config

        self.setWindowTitle("Image Viewer")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Semi-transparent dark background
        self.setStyleSheet("QDialog { background-color: rgba(0, 0, 0, 200); }")

        self.init_ui()
        self.load_image()

        # Size to 90% of screen
        primary_screen = QApplication.primaryScreen()
        if primary_screen:
            screen = primary_screen.geometry()
            self.resize(int(screen.width() * 0.9), int(screen.height() * 0.9))

            # Center on screen
            self.move(
                (screen.width() - self.width()) // 2,
                (screen.height() - self.height()) // 2
            )

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        # Scroll area for the image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
        """)

        # Zoomable image label
        self.image_label = ZoomableImageLabel()
        self.image_label.setStyleSheet("background-color: transparent;")
        self.scroll_area.setWidget(self.image_label)

        layout.addWidget(self.scroll_area)

        # Hint label
        hint_label = QLabel("Scroll to zoom | Drag to pan | Click outside or press ESC to close")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setStyleSheet("color: white; font-size: 12px; padding: 10px;")
        layout.addWidget(hint_label)

        self.setLayout(layout)

    def load_image(self):
        """Load the image at full resolution, cropped if tagged."""
        # Check if we should display cropped version
        should_crop = (self.image_item is not None and
                      self.image_item.is_fully_tagged() and
                      self.config is not None)

        if should_crop:
            # Load cropped version using CropService
            try:
                from PIL import Image
                from src.services.crop_service import CropService

                crop_service = CropService(self.config)
                crop_box = crop_service.get_crop_box(
                    self.image_path,
                    self.image_item.size_tag,
                    manual_crop_box=self.image_item.crop_box
                )

                if crop_box:
                    # Load image with Pillow and crop it
                    img = Image.open(self.image_path)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    x, y, width, height = crop_box
                    cropped_img = img.crop((x, y, x + width, y + height))

                    # Convert PIL Image to QPixmap
                    import io

                    # Save PIL image to bytes
                    img_bytes = io.BytesIO()
                    cropped_img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)

                    # Load bytes into QPixmap
                    pixmap = QPixmap()
                    pixmap.loadFromData(img_bytes.read())
                else:
                    # Fallback to full image if crop calculation failed
                    pixmap = ImageLoader.load_pixmap(self.image_path)

            except Exception as e:
                print(f"Error loading cropped image: {e}")
                # Fallback to full image on error
                pixmap = ImageLoader.load_pixmap(self.image_path)
        else:
            # Load full image
            pixmap = ImageLoader.load_pixmap(self.image_path)

        if not pixmap.isNull():
            # Calculate zoom to fit image inside window
            screen = QApplication.primaryScreen().geometry()
            # Account for margins (20px each side) and hint label (~40px)
            max_width = int(screen.width() * 0.9) - 40
            max_height = int(screen.height() * 0.9) - 80

            # Always calculate fit-to-window zoom
            width_ratio = max_width / pixmap.width()
            height_ratio = max_height / pixmap.height()
            initial_zoom = min(width_ratio, height_ratio, 1.0)  # Don't upscale small images

            self.image_label.set_image(pixmap, initial_zoom)

    def keyPressEvent(self, event: Optional[QKeyEvent]):
        """Close dialog on ESC key."""
        if event and event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: Optional[QMouseEvent]):
        """Close dialog when clicking outside the image area."""
        # Check if click is on the dialog background (not on the scroll area content)
        if event and event.button() == Qt.MouseButton.LeftButton:
            # Get the scroll area geometry in dialog coordinates
            scroll_rect = self.scroll_area.geometry()
            click_pos = event.pos()

            # If click is outside scroll area, close
            if not scroll_rect.contains(click_pos):
                self.close()
                return

        super().mousePressEvent(event)
