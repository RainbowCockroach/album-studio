"""Dialog for viewing an image in detail with zoom support."""
from typing import Optional
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea, QApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPixmap, QWheelEvent, QMouseEvent, QKeyEvent
from src.utils.image_loader import ImageLoader
from src.models.config import Config


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

        # Real-size preview mode
        self.real_size_mode = False
        self.can_use_real_size = self._check_real_size_available()
        self.loaded_pixmap = None  # Store the loaded pixmap for mode switching

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

        # Hint label (will be updated based on mode)
        self.hint_label = QLabel()
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: white; font-size: 12px; padding: 10px;")
        self._update_hint_label()
        layout.addWidget(self.hint_label)

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

                    # Apply date stamp preview if enabled
                    if self.image_item.add_date_stamp:
                        cropped_img = self._apply_date_stamp_preview(cropped_img)

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
            # Store pixmap for mode switching
            self.loaded_pixmap = pixmap

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

    def _apply_date_stamp_preview(self, img):
        """
        Apply date stamp preview to the PIL Image.

        Args:
            img: PIL Image to apply date stamp to

        Returns:
            PIL Image with date stamp applied
        """
        if not self.image_item or not self.config:
            return img

        try:
            from src.services.date_stamp_service import DateStampService

            # Get display date
            display_date = self.image_item.get_display_date()
            if not display_date:
                return img

            # Apply date stamp using the service
            date_stamp_service = DateStampService(self.config)
            stamped_img = date_stamp_service.apply_date_stamp(
                img,
                display_date,
                self.image_item.size_tag
            )

            return stamped_img

        except Exception as e:
            print(f"Error applying date stamp preview: {e}")
            return img  # Return original image on error

    def _check_real_size_available(self) -> bool:
        """Check if real-size preview is available for this image."""
        # Must have image_item, config, and a valid size tag
        if self.image_item is None or self.config is None:
            return False
        if not self.image_item.is_fully_tagged():
            return False
        # Verify size_tag can be parsed
        try:
            Config.parse_size_dimensions(self.image_item.size_tag)
            return True
        except ValueError:
            return False

    def _update_hint_label(self):
        """Update the hint label based on current mode."""
        base_hint = "Scroll to zoom | Drag to pan | Click outside or ESC to close"

        # Check if date stamp preview is shown
        date_stamp_indicator = ""
        if self.image_item and self.image_item.add_date_stamp:
            date_stamp_indicator = "[DATE STAMP PREVIEW] | "

        if self.can_use_real_size:
            if self.real_size_mode:
                # Get dimensions for display
                try:
                    width, height = Config.parse_size_dimensions(self.image_item.size_tag)
                    ppu = self.config.get_setting("pixels_per_unit", 100)
                    real_width = width * ppu
                    real_height = height * ppu
                    mode_info = f"[REAL SIZE: {width}x{height} units = {real_width}x{real_height}px]"
                except ValueError:
                    mode_info = "[REAL SIZE MODE]"
                self.hint_label.setText(f"{date_stamp_indicator}{mode_info} | Press R for normal view | {base_hint}")
            else:
                self.hint_label.setText(
                    f"{date_stamp_indicator}[Normal View] | Press R for real-size preview | {base_hint}")
        else:
            self.hint_label.setText(f"{date_stamp_indicator}{base_hint}")

    def toggle_real_size_mode(self):
        """Toggle between normal and real-size preview modes."""
        if not self.can_use_real_size:
            return

        self.real_size_mode = not self.real_size_mode
        self._update_hint_label()

        if self.loaded_pixmap and not self.loaded_pixmap.isNull():
            if self.real_size_mode:
                self._apply_real_size_zoom()
            else:
                # Restore fit-to-window zoom
                screen = QApplication.primaryScreen().geometry()
                max_width = int(screen.width() * 0.9) - 40
                max_height = int(screen.height() * 0.9) - 80

                width_ratio = max_width / self.loaded_pixmap.width()
                height_ratio = max_height / self.loaded_pixmap.height()
                initial_zoom = min(width_ratio, height_ratio, 1.0)

                self.image_label.set_image(self.loaded_pixmap, initial_zoom)

    def _apply_real_size_zoom(self):
        """Apply zoom level for real-size preview."""
        if not self.loaded_pixmap or self.loaded_pixmap.isNull():
            return
        if not self.image_item or not self.config:
            return

        try:
            # Get size dimensions from tag (e.g., "9x6" -> (9, 6))
            width_units, _height_units = Config.parse_size_dimensions(self.image_item.size_tag)

            # Get pixels per unit from config
            ppu = self.config.get_setting("pixels_per_unit", 100)

            # Calculate target display size in pixels
            target_width = width_units * ppu

            # Calculate zoom factor based on the loaded pixmap dimensions
            # The pixmap is already cropped to the correct aspect ratio
            zoom_factor = target_width / self.loaded_pixmap.width()

            # Apply the zoom
            self.image_label.set_image(self.loaded_pixmap, zoom_factor)

        except (ValueError, ZeroDivisionError) as e:
            print(f"Error applying real-size zoom: {e}")
            # Fall back to normal view
            self.real_size_mode = False
            self._update_hint_label()

    def keyPressEvent(self, event: Optional[QKeyEvent]):
        """Handle keyboard shortcuts: ESC to close, R to toggle real-size mode."""
        if event:
            if event.key() == Qt.Key.Key_Escape:
                self.close()
            elif event.key() == Qt.Key.Key_R:
                self.toggle_real_size_mode()
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
