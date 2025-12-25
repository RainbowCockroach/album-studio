from PyQt6.QtWidgets import (QWidget, QScrollArea, QGridLayout, QLabel,
                             QVBoxLayout, QFrame, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect
from PyQt6.QtGui import QPixmap, QPalette
from .crop_overlay import CropOverlay
from src.utils.image_loader import ImageLoader


class ImageGrid(QWidget):
    """Grid view for displaying images with thumbnails."""

    image_clicked = pyqtSignal(object)  # Emits ImageItem
    image_double_clicked = pyqtSignal(object)  # Emits ImageItem

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_project = None
        self.thumbnail_size = config.get_setting("thumbnail_size", 200)
        self.columns = config.get_setting("grid_columns", 5)
        self.image_widgets = {}  # Map ImageItem to ImageWidget
        self.preview_mode = False
        self.selection_mode = False
        self.selected_items = set()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create grid container
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)
        self.grid_container.setLayout(self.grid_layout)

        scroll_area.setWidget(self.grid_container)
        layout.addWidget(scroll_area)

        self.setLayout(layout)

    def set_project(self, project):
        """Set the current project and load its images."""
        self.current_project = project
        self.load_images()

    def load_images(self):
        """Load images from current project into grid."""
        self.clear_grid()
        self.selected_items.clear()  # Clear selection on reload

        if not self.current_project:
            return

        row = 0
        col = 0

        for image_item in self.current_project.images:
            # Create image widget
            image_widget = ImageWidget(image_item, self.thumbnail_size)
            image_widget.clicked.connect(lambda item=image_item: self.on_image_clicked(item))
            image_widget.double_clicked.connect(lambda item=image_item: self.on_image_double_clicked(item))

            # Add to grid
            self.grid_layout.addWidget(image_widget, row, col)
            self.image_widgets[image_item] = image_widget

            # Update position
            col += 1
            if col >= self.columns:
                col = 0
                row += 1

    def clear_grid(self):
        """Clear all images from the grid."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        self.image_widgets.clear()

    def refresh_display(self):
        """Refresh the display of all images (update borders based on tags/selection)."""
        for image_item, widget in self.image_widgets.items():
            is_selected = image_item in self.selected_items
            widget.set_selected(is_selected)
            widget.update_border()

    def toggle_selection_mode(self, enabled: bool):
        """Enable or disable selection mode."""
        self.selection_mode = enabled
        if not enabled:
            self.selected_items.clear()
        self.refresh_display()

    def get_selected_items(self):
        """Get list of currently selected items."""
        return list(self.selected_items)

    def on_image_clicked(self, image_item):
        """Handle single click on image."""
        if self.selection_mode:
            self.toggle_selection(image_item)
        elif not self.preview_mode:
            self.image_clicked.emit(image_item)

    def toggle_selection(self, image_item):
        """Toggle selection state for an image."""
        if image_item in self.selected_items:
            self.selected_items.remove(image_item)
        else:
            self.selected_items.add(image_item)
        
        # Update specific widget
        if image_item in self.image_widgets:
            self.image_widgets[image_item].set_selected(image_item in self.selected_items)

    def on_image_double_clicked(self, image_item):
        """Handle double click on image."""
        if not self.preview_mode and not self.selection_mode:
            self.image_double_clicked.emit(image_item)

    def enter_preview_mode(self):
        """Enter crop preview mode for all fully tagged images."""
        if self.selection_mode:
            return # Don't enter preview if in selection mode

        self.preview_mode = True
        for image_item, widget in self.image_widgets.items():
            if image_item.is_fully_tagged():
                widget.enter_preview_mode(self.config)

    def exit_preview_mode(self):
        """Exit crop preview mode."""
        self.preview_mode = False
        for image_item, widget in self.image_widgets.items():
            widget.exit_preview_mode()


class ImageWidget(QFrame):
    """Widget representing a single image in the grid."""

    clicked = pyqtSignal()
    double_clicked = pyqtSignal()

    def __init__(self, image_item, thumbnail_size):
        super().__init__()
        self.image_item = image_item
        self.thumbnail_size = thumbnail_size
        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self._handle_single_click)
        self.double_click_flag = False
        self.crop_overlay = None  # Will be created in preview mode
        self.in_preview_mode = False
        self.is_selected = False
        self.init_ui()

    def init_ui(self):
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(3)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Load thumbnail
        pixmap = self.image_item.get_thumbnail(self.thumbnail_size)
        if pixmap:
            self.thumbnail_label.setPixmap(pixmap)
        else:
            self.thumbnail_label.setText("No Image")

        layout.addWidget(self.thumbnail_label)

        # Filename label
        filename = self.image_item.file_path.split('/')[-1]
        filename_label = QLabel(filename)
        filename_label.setWordWrap(True)
        filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(filename_label)

        # Tag info label
        self.tag_label = QLabel()
        self.tag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tag_label.setWordWrap(True)
        layout.addWidget(self.tag_label)

        self.setLayout(layout)
        self.update_border()

    def set_selected(self, selected: bool):
        """Set visual selection state."""
        self.is_selected = selected
        self.update_border()

    def update_border(self):
        """Update border color based on tag status or selection."""
        if self.is_selected:
            # Red border for selection (delete mode)
            self.setStyleSheet("QFrame { border: 4px solid red; background-color: #ffeeee; }")
            self.tag_label.setText("Selected for Deletion")
            return

        if self.image_item.is_fully_tagged():
            # Green border for fully tagged
            self.setStyleSheet("QFrame { border: 3px solid green; }")
            tag_text = f"{self.image_item.album_tag}\n{self.image_item.size_tag}"
            self.tag_label.setText(tag_text)
        elif self.image_item.has_tags():
            # Yellow border for partially tagged
            self.setStyleSheet("QFrame { border: 3px solid orange; }")
            tag_text = f"{self.image_item.album_tag or ''}\n{self.image_item.size_tag or ''}"
            self.tag_label.setText(tag_text)
        else:
            # Default border for untagged
            self.setStyleSheet("QFrame { border: 3px solid lightgray; }")
            self.tag_label.setText("No tags")

    def _handle_single_click(self):
        """Handle single click after delay (if not double-clicked)."""
        if self.double_click_flag:
            # Reset flag and ignore this single click
            self.double_click_flag = False
            return
        self.clicked.emit()

    def mousePressEvent(self, a0):
        """Handle mouse press events."""
        if a0:
            if a0.button() == Qt.MouseButton.LeftButton:
                self.click_pos = a0.pos()

    def mouseReleaseEvent(self, a0):
        """Handle mouse release events."""
        if a0:
            if a0.button() == Qt.MouseButton.LeftButton:
                # Use system's double-click interval
                interval = QApplication.doubleClickInterval()
                self.click_timer.start(interval + 50)  # Add 50ms buffer

    def mouseDoubleClickEvent(self, a0):
        """Handle double click events."""
        if a0:
            if a0.button() == Qt.MouseButton.LeftButton and not self.in_preview_mode:
                # Stop any pending single click timers
                self.click_timer.stop()
                # Set flag to ignore next single click
                self.double_click_flag = True
                # Emit double click signal
                self.double_clicked.emit()

    def enter_preview_mode(self, config):
        """Enter crop preview mode - show crop overlay."""
        self.in_preview_mode = True

        # Create crop overlay if not exists
        if not self.crop_overlay:
            self.crop_overlay = CropOverlay(self.thumbnail_label)
            self.crop_overlay.setGeometry(self.thumbnail_label.rect())
            self.crop_overlay.crop_changed.connect(self._on_crop_changed)

        # Get aspect ratio from size tag
        size_info = config.get_size_info(self.image_item.size_tag)
        if size_info and 'ratio' in size_info:
            aspect_ratio = size_info['ratio']
        else:
            aspect_ratio = 1.0

        self.crop_overlay.set_aspect_ratio(aspect_ratio)

        # Set the actual pixmap bounds for the overlay
        pixmap_rect = self._get_pixmap_rect()
        self.crop_overlay.set_image_bounds(pixmap_rect)

        # Calculate initial crop position
        self._calculate_initial_crop(config)

        self.crop_overlay.show()
        self.crop_overlay.raise_()

    def exit_preview_mode(self):
        """Exit crop preview mode - hide crop overlay."""
        self.in_preview_mode = False
        if self.crop_overlay:
            self.crop_overlay.hide()

    def _get_pixmap_rect(self) -> QRect:
        """Calculate the actual rectangle where the pixmap is displayed within the label."""
        pixmap = self.thumbnail_label.pixmap()
        if not pixmap or pixmap.isNull():
            # Return full label rect if no pixmap
            return self.thumbnail_label.rect()

        label_width = self.thumbnail_label.width()
        label_height = self.thumbnail_label.height()
        pixmap_width = pixmap.width()
        pixmap_height = pixmap.height()

        # Calculate offset due to centering (AlignCenter)
        x_offset = (label_width - pixmap_width) // 2
        y_offset = (label_height - pixmap_height) // 2

        return QRect(x_offset, y_offset, pixmap_width, pixmap_height)

    def _calculate_initial_crop(self, config):
        """Calculate initial crop position using smart crop or saved position."""
        # ImageLoader is now imported globally
        from PIL import Image
        import smartcrop

        # If we already have a saved crop position, use it
        if self.image_item.crop_box:
            self._apply_crop_box_to_overlay(self.image_item.crop_box)
            return

        # Otherwise, use smart crop to suggest initial position
        try:
            # Get size ratio
            size_info = config.get_size_info(self.image_item.size_tag)
            if not size_info:
                self._set_centered_crop()
                return

            ratio = size_info.get('ratio')
            if not ratio:
                self._set_centered_crop()
                return

            # Load image with PIL
            img = Image.open(self.image_item.file_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Get image dimensions
            image_width, image_height = img.size

            # Optimization: Downscale image for smart crop analysis if it's too large
            # This massively speeds up HEIC/large image processing
            analysis_img = img
            scale_factor = 1.0
            MAX_ANALYSIS_SIZE = 600
            
            if image_width > MAX_ANALYSIS_SIZE or image_height > MAX_ANALYSIS_SIZE:
                analysis_img = img.copy()
                analysis_img.thumbnail((MAX_ANALYSIS_SIZE, MAX_ANALYSIS_SIZE), Image.Resampling.LANCZOS)
                scale_factor = image_width / analysis_img.width

            # Calculate the largest possible crop dimensions based on ratio
            # Try fitting by width
            crop_width_by_width = image_width
            crop_height_by_width = int(image_width / ratio)

            # Try fitting by height
            crop_height_by_height = image_height
            crop_width_by_height = int(image_height * ratio)

            # Choose the option that fits within the image bounds
            if crop_height_by_width <= image_height:
                target_width = crop_width_by_width
                target_height = crop_height_by_width
            else:
                target_width = crop_width_by_height
                target_height = crop_height_by_height

            # Use smartcrop to find best crop
            # We must scale target dimensions down for the analysis image
            analysis_target_width = int(target_width / scale_factor)
            analysis_target_height = int(target_height / scale_factor)
            
            # Smart crop on smaller image
            sc = smartcrop.SmartCrop()
            result = sc.crop(analysis_img, analysis_target_width, analysis_target_height)

            # Get crop coordinates from smartcrop result and scale back up
            crop = result['top_crop']
            crop_box = {
                'x': int(crop['x'] * scale_factor),
                'y': int(crop['y'] * scale_factor),
                'width': int(crop['width'] * scale_factor),
                'height': int(crop['height'] * scale_factor)
            }

            # Save to image item
            self.image_item.crop_box = crop_box

            # Apply to overlay
            self._apply_crop_box_to_overlay(crop_box)

        except Exception as e:
            print(f"Error calculating smart crop: {e}")
            self._set_centered_crop()

    def _apply_crop_box_to_overlay(self, crop_box: dict):
        """Convert image coordinates to thumbnail coordinates and apply to overlay."""
        try:
            # Optimize: Get dimensions without loading full pixmap
            # This is much faster for HEIC support
            img_width, img_height = ImageLoader.get_image_dimensions(self.image_item.file_path)
            
            if img_width == 0 or img_height == 0:
                self._set_centered_crop()
                return

            # Get thumbnail pixmap to find scale factor
            thumbnail = self.image_item.get_thumbnail(self.thumbnail_size)
            if not thumbnail:
                self._set_centered_crop()
                return

            thumb_width = thumbnail.width()
            thumb_height = thumbnail.height()

            # Get pixmap offset within label
            pixmap_rect = self._get_pixmap_rect()

            # Calculate scale factors
            scale_x = thumb_width / img_width
            scale_y = thumb_height / img_height

            # Convert crop box to thumbnail coordinates and add offset
            overlay_x = int(crop_box['x'] * scale_x) + pixmap_rect.x()
            overlay_y = int(crop_box['y'] * scale_y) + pixmap_rect.y()
            overlay_width = int(crop_box['width'] * scale_x)
            overlay_height = int(crop_box['height'] * scale_y)

            # Apply to overlay
            if self.crop_overlay:
                self.crop_overlay.set_crop_rect(overlay_x, overlay_y, overlay_width, overlay_height)

        except Exception as e:
            print(f"Error applying crop box: {e}")
            self._set_centered_crop()

    def _set_centered_crop(self):
        """Set a default centered crop rectangle."""
        # Get aspect ratio
        aspect_ratio = self.crop_overlay.aspect_ratio if self.crop_overlay else 1.0

        # Get actual pixmap bounds
        pixmap_rect = self._get_pixmap_rect()
        pixmap_width = pixmap_rect.width()
        pixmap_height = pixmap_rect.height()

        # Calculate centered crop size within the pixmap
        if pixmap_width / pixmap_height > aspect_ratio:
            # Fit by height
            crop_height = int(pixmap_height * 0.8)
            crop_width = int(crop_height * aspect_ratio)
        else:
            # Fit by width
            crop_width = int(pixmap_width * 0.8)
            crop_height = int(crop_width / aspect_ratio)

        # Center it within the pixmap area
        x = pixmap_rect.x() + (pixmap_width - crop_width) // 2
        y = pixmap_rect.y() + (pixmap_height - crop_height) // 2

        if self.crop_overlay:
            self.crop_overlay.set_crop_rect(x, y, crop_width, crop_height)

        # Save to image item (convert to full image coordinates)
        self._save_crop_from_overlay()

    def _on_crop_changed(self, crop_dict: dict):
        """Handle crop overlay position change."""
        self._save_crop_from_overlay()

    def _save_crop_from_overlay(self):
        """Save current overlay crop position to image item in full image coordinates."""
        try:
            if self.crop_overlay:
                # Get overlay crop in thumbnail coordinates
                overlay_crop = self.crop_overlay.get_crop_dict()

                # Optimize: Get dimensions without loading full pixmap
                img_width, img_height = ImageLoader.get_image_dimensions(self.image_item.file_path)
                
                if img_width == 0 or img_height == 0:
                    return

                # Get thumbnail dimensions
                thumbnail = self.image_item.get_thumbnail(self.thumbnail_size)
                if not thumbnail:
                    return

                thumb_width = thumbnail.width()
                thumb_height = thumbnail.height()

                # Get pixmap offset within label
                pixmap_rect = self._get_pixmap_rect()

                # Calculate scale factors (inverse)
                scale_x = img_width / thumb_width
                scale_y = img_height / thumb_height

                # Convert to full image coordinates (subtract offset first)
                self.image_item.crop_box = {
                    'x': int((overlay_crop['x'] - pixmap_rect.x()) * scale_x),
                    'y': int((overlay_crop['y'] - pixmap_rect.y()) * scale_y),
                    'width': int(overlay_crop['width'] * scale_x),
                    'height': int(overlay_crop['height'] * scale_y)
                }

        except Exception as e:
            print(f"Error saving crop position: {e}")
