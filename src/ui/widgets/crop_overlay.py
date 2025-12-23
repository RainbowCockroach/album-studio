from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen


class CropOverlay(QWidget):
    """Draggable crop rectangle overlay for image previews."""

    crop_changed = pyqtSignal(dict)  # Emits {x, y, width, height} in widget coordinates

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)

        # Crop rectangle in widget coordinates
        self.crop_rect = QRect(0, 0, 100, 100)
        self.aspect_ratio = 1.0  # Will be set based on size tag

        # Image bounds (actual displayable area within widget)
        self.image_bounds = QRect(0, 0, 100, 100)

        # Dragging state
        self.dragging = False
        self.drag_start_pos = QPoint()
        self.rect_start_pos = QRect()

        # Minimum crop size
        self.min_size = 50

    def set_aspect_ratio(self, ratio: float):
        """Set the aspect ratio for the crop rectangle (width/height)."""
        self.aspect_ratio = ratio

    def set_image_bounds(self, bounds: QRect):
        """Set the actual image bounds within the widget (for constraining the crop area)."""
        self.image_bounds = bounds
        self.update()

    def set_crop_rect(self, x: int, y: int, width: int, height: int):
        """Set the crop rectangle position and size."""
        self.crop_rect = QRect(x, y, width, height)
        self.update()

    def get_crop_rect(self) -> QRect:
        """Get the current crop rectangle."""
        return self.crop_rect

    def get_crop_dict(self) -> dict:
        """Get crop rectangle as dictionary."""
        return {
            'x': self.crop_rect.x(),
            'y': self.crop_rect.y(),
            'width': self.crop_rect.width(),
            'height': self.crop_rect.height()
        }

    def paintEvent(self, event):
        """Draw the crop overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw darkened areas outside crop
        dark_color = QColor(0, 0, 0, 120)
        full_rect = self.rect()

        # Top
        if self.crop_rect.top() > 0:
            painter.fillRect(0, 0, full_rect.width(), self.crop_rect.top(), dark_color)

        # Bottom
        if self.crop_rect.bottom() < full_rect.height():
            painter.fillRect(0, self.crop_rect.bottom(),
                           full_rect.width(), full_rect.height() - self.crop_rect.bottom(),
                           dark_color)

        # Left
        painter.fillRect(0, self.crop_rect.top(),
                        self.crop_rect.left(), self.crop_rect.height(),
                        dark_color)

        # Right
        painter.fillRect(self.crop_rect.right(), self.crop_rect.top(),
                        full_rect.width() - self.crop_rect.right(), self.crop_rect.height(),
                        dark_color)

        # Draw crop rectangle border
        pen = QPen(QColor(255, 255, 255), 2)
        painter.setPen(pen)
        painter.drawRect(self.crop_rect)

        # Draw corner handles
        handle_size = 8
        handle_color = QColor(255, 255, 255)
        painter.setBrush(handle_color)

        corners = [
            self.crop_rect.topLeft(),
            self.crop_rect.topRight(),
            self.crop_rect.bottomLeft(),
            self.crop_rect.bottomRight()
        ]

        for corner in corners:
            handle_rect = QRect(
                corner.x() - handle_size // 2,
                corner.y() - handle_size // 2,
                handle_size,
                handle_size
            )
            painter.fillRect(handle_rect, handle_color)

    def mousePressEvent(self, event):
        """Start dragging the crop rectangle."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.crop_rect.contains(event.pos()):
                self.dragging = True
                self.drag_start_pos = event.pos()
                self.rect_start_pos = QRect(self.crop_rect)

    def mouseMoveEvent(self, event):
        """Drag the crop rectangle."""
        if self.dragging:
            delta = event.pos() - self.drag_start_pos

            # Calculate new position
            new_rect = QRect(self.rect_start_pos)
            new_rect.translate(delta)

            # Constrain to image bounds - ensure rectangle stays fully within image area
            # Check left edge
            if new_rect.left() < self.image_bounds.left():
                new_rect.moveLeft(self.image_bounds.left())
            # Check top edge
            if new_rect.top() < self.image_bounds.top():
                new_rect.moveTop(self.image_bounds.top())
            # Check right edge - ensure right side doesn't exceed image right
            if new_rect.right() > self.image_bounds.right():
                new_rect.moveLeft(self.image_bounds.right() - new_rect.width())
            # Check bottom edge - ensure bottom doesn't exceed image bottom
            if new_rect.bottom() > self.image_bounds.bottom():
                new_rect.moveTop(self.image_bounds.bottom() - new_rect.height())

            self.crop_rect = new_rect
            self.update()
        else:
            # Change cursor if over crop rect
            if self.crop_rect.contains(event.pos()):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        """Stop dragging and emit signal."""
        if event.button() == Qt.MouseButton.LeftButton and self.dragging:
            self.dragging = False
            self.crop_changed.emit(self.get_crop_dict())

    def resizeEvent(self, event):
        """Handle widget resize - maintain crop rectangle within image bounds."""
        super().resizeEvent(event)

        # Ensure crop rectangle is within image bounds
        # Constrain width and height if larger than image bounds
        if self.crop_rect.width() > self.image_bounds.width():
            self.crop_rect.setWidth(self.image_bounds.width())
        if self.crop_rect.height() > self.image_bounds.height():
            self.crop_rect.setHeight(self.image_bounds.height())

        # Constrain position to keep rectangle fully within image bounds
        if self.crop_rect.left() < self.image_bounds.left():
            self.crop_rect.moveLeft(self.image_bounds.left())
        if self.crop_rect.top() < self.image_bounds.top():
            self.crop_rect.moveTop(self.image_bounds.top())
        if self.crop_rect.right() > self.image_bounds.right():
            self.crop_rect.moveLeft(self.image_bounds.right() - self.crop_rect.width())
        if self.crop_rect.bottom() > self.image_bounds.bottom():
            self.crop_rect.moveTop(self.image_bounds.bottom() - self.crop_rect.height())

        self.update()
