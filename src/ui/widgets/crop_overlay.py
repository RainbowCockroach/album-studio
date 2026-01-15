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

        # Resizing state
        self.resizing = False
        self.resize_corner = None  # 'top_left', 'top_right', 'bottom_left', 'bottom_right'
        self.resize_start_pos = QPoint()
        self.resize_start_rect = QRect()

        # Minimum crop size
        self.min_size = 50

        # Handle size for corner detection
        self.handle_size = 8
        self.handle_hit_area = 16  # Larger hit area for easier grabbing

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

    def _get_corner_at_pos(self, pos: QPoint) -> str | None:
        """Check if position is near a corner handle. Returns corner name or None."""
        hit_area = self.handle_hit_area

        corners = {
            'top_left': self.crop_rect.topLeft(),
            'top_right': self.crop_rect.topRight(),
            'bottom_left': self.crop_rect.bottomLeft(),
            'bottom_right': self.crop_rect.bottomRight()
        }

        for corner_name, corner_pos in corners.items():
            # Check if mouse is within hit area of this corner
            if abs(pos.x() - corner_pos.x()) <= hit_area and abs(pos.y() - corner_pos.y()) <= hit_area:
                return corner_name

        return None

    def _resize_from_corner(self, corner: str, current_pos: QPoint) -> QRect:
        """Calculate new crop rectangle when resizing from a corner, maintaining aspect ratio."""
        delta = current_pos - self.resize_start_pos
        new_rect = QRect(self.resize_start_rect)

        # Calculate size change based on which corner is being dragged
        # We'll use the larger dimension change to maintain aspect ratio
        if corner == 'bottom_right':
            # Expanding: moving right and down increases size
            # Use the larger delta to maintain aspect ratio
            width_delta = delta.x()
            height_delta = delta.y()

            # Calculate what the new dimensions would be
            new_width = max(self.min_size, self.resize_start_rect.width() + width_delta)
            new_height = max(self.min_size, self.resize_start_rect.height() + height_delta)

            # Determine which dimension to prioritize based on aspect ratio
            # Calculate what height should be for the new width
            height_for_width = new_width / self.aspect_ratio
            # Calculate what width should be for the new height
            width_for_height = new_height * self.aspect_ratio

            # Use the smaller of the two to ensure we don't exceed bounds
            if height_for_width <= new_height:
                # Width is the limiting factor
                new_rect.setWidth(int(new_width))
                new_rect.setHeight(int(height_for_width))
            else:
                # Height is the limiting factor
                new_rect.setHeight(int(new_height))
                new_rect.setWidth(int(width_for_height))

        elif corner == 'bottom_left':
            # Moving left and down
            width_delta = -delta.x()  # Moving left increases width
            height_delta = delta.y()

            new_width = max(self.min_size, self.resize_start_rect.width() + width_delta)
            new_height = max(self.min_size, self.resize_start_rect.height() + height_delta)

            height_for_width = new_width / self.aspect_ratio
            width_for_height = new_height * self.aspect_ratio

            if height_for_width <= new_height:
                final_width = int(new_width)
                final_height = int(height_for_width)
            else:
                final_height = int(new_height)
                final_width = int(width_for_height)

            # Move left edge
            new_rect.setLeft(self.resize_start_rect.right() - final_width)
            new_rect.setWidth(final_width)
            new_rect.setHeight(final_height)

        elif corner == 'top_right':
            # Moving right and up
            width_delta = delta.x()
            height_delta = -delta.y()  # Moving up increases height

            new_width = max(self.min_size, self.resize_start_rect.width() + width_delta)
            new_height = max(self.min_size, self.resize_start_rect.height() + height_delta)

            height_for_width = new_width / self.aspect_ratio
            width_for_height = new_height * self.aspect_ratio

            if height_for_width <= new_height:
                final_width = int(new_width)
                final_height = int(height_for_width)
            else:
                final_height = int(new_height)
                final_width = int(width_for_height)

            # Move top edge
            new_rect.setTop(self.resize_start_rect.bottom() - final_height)
            new_rect.setWidth(final_width)
            new_rect.setHeight(final_height)

        elif corner == 'top_left':
            # Moving left and up
            width_delta = -delta.x()
            height_delta = -delta.y()

            new_width = max(self.min_size, self.resize_start_rect.width() + width_delta)
            new_height = max(self.min_size, self.resize_start_rect.height() + height_delta)

            height_for_width = new_width / self.aspect_ratio
            width_for_height = new_height * self.aspect_ratio

            if height_for_width <= new_height:
                final_width = int(new_width)
                final_height = int(height_for_width)
            else:
                final_height = int(new_height)
                final_width = int(width_for_height)

            # Move both top and left edges
            new_rect.setLeft(self.resize_start_rect.right() - final_width)
            new_rect.setTop(self.resize_start_rect.bottom() - final_height)
            new_rect.setWidth(final_width)
            new_rect.setHeight(final_height)

        # Constrain to image bounds
        new_rect = self._constrain_to_bounds(new_rect)

        return new_rect

    def _constrain_to_bounds(self, rect: QRect) -> QRect:
        """Constrain rectangle to stay within image bounds while maintaining aspect ratio."""
        constrained = QRect(rect)

        # Ensure minimum size while maintaining aspect ratio
        if constrained.width() < self.min_size or constrained.height() < self.min_size:
            # Calculate minimum dimensions that satisfy both min_size and aspect ratio
            min_width_for_height = self.min_size * self.aspect_ratio
            min_height_for_width = self.min_size / self.aspect_ratio

            if self.aspect_ratio >= 1.0:
                # Wider than tall: height is the limiting factor
                new_height = max(self.min_size, constrained.height())
                new_width = int(new_height * self.aspect_ratio)
                if new_width < self.min_size:
                    new_width = self.min_size
                    new_height = int(new_width / self.aspect_ratio)
            else:
                # Taller than wide: width is the limiting factor
                new_width = max(self.min_size, constrained.width())
                new_height = int(new_width / self.aspect_ratio)
                if new_height < self.min_size:
                    new_height = self.min_size
                    new_width = int(new_height * self.aspect_ratio)

            constrained.setWidth(new_width)
            constrained.setHeight(new_height)

        # Check if rect fits within image bounds, shrink proportionally if needed
        if constrained.width() > self.image_bounds.width() or constrained.height() > self.image_bounds.height():
            # Calculate max size that fits within bounds while maintaining aspect ratio
            max_width = self.image_bounds.width()
            max_height = self.image_bounds.height()

            # Try fitting by width
            fit_by_width_w = max_width
            fit_by_width_h = int(max_width / self.aspect_ratio)

            # Try fitting by height
            fit_by_height_h = max_height
            fit_by_height_w = int(max_height * self.aspect_ratio)

            # Choose the one that fits within bounds
            if fit_by_width_h <= max_height:
                constrained.setWidth(fit_by_width_w)
                constrained.setHeight(fit_by_width_h)
            else:
                constrained.setWidth(fit_by_height_w)
                constrained.setHeight(fit_by_height_h)

        # Now constrain position (just move, don't resize)
        if constrained.left() < self.image_bounds.left():
            constrained.moveLeft(self.image_bounds.left())
        if constrained.top() < self.image_bounds.top():
            constrained.moveTop(self.image_bounds.top())
        if constrained.right() > self.image_bounds.right():
            constrained.moveLeft(self.image_bounds.right() - constrained.width())
        if constrained.bottom() > self.image_bounds.bottom():
            constrained.moveTop(self.image_bounds.bottom() - constrained.height())

        return constrained

    def paintEvent(self, a0):
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
                corner.x() - self.handle_size // 2,
                corner.y() - self.handle_size // 2,
                self.handle_size,
                self.handle_size
            )
            painter.fillRect(handle_rect, handle_color)

    def mousePressEvent(self, a0):
        """Start dragging or resizing the crop rectangle."""
        if a0:
            if a0.button() == Qt.MouseButton.LeftButton:
                # Check if clicking on a corner handle (resize mode)
                corner = self._get_corner_at_pos(a0.pos())
                if corner:
                    self.resizing = True
                    self.resize_corner = corner
                    self.resize_start_pos = a0.pos()
                    self.resize_start_rect = QRect(self.crop_rect)
                # Check if clicking inside the crop rect (drag mode)
                elif self.crop_rect.contains(a0.pos()):
                    self.dragging = True
                    self.drag_start_pos = a0.pos()
                    self.rect_start_pos = QRect(self.crop_rect)

    def mouseMoveEvent(self, a0):
        """Handle dragging or resizing the crop rectangle."""
        if a0:
            if self.resizing:
                # Resize mode
                new_rect = self._resize_from_corner(self.resize_corner, a0.pos())
                self.crop_rect = new_rect
                self.update()
            elif self.dragging:
                # Drag mode
                delta = a0.pos() - self.drag_start_pos

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
                # Update cursor based on position
                corner = self._get_corner_at_pos(a0.pos())
                if corner:
                    # Show resize cursor based on corner
                    if corner in ['top_left', 'bottom_right']:
                        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                    else:  # top_right, bottom_left
                        self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                elif self.crop_rect.contains(a0.pos()):
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, a0):
        """Stop dragging or resizing and emit signal."""
        if a0:
            if a0.button() == Qt.MouseButton.LeftButton:
                if self.dragging:
                    self.dragging = False
                    self.crop_changed.emit(self.get_crop_dict())
                elif self.resizing:
                    self.resizing = False
                    self.resize_corner = None
                    self.crop_changed.emit(self.get_crop_dict())

    def resizeEvent(self, a0):
        """Handle widget resize - maintain crop rectangle within image bounds."""
        super().resizeEvent(a0)

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
