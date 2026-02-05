from typing import Optional
from PyQt6.QtWidgets import (QWidget, QScrollArea, QGridLayout, QLabel,
                             QVBoxLayout, QFrame, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect, QThread
from PyQt6.QtGui import QPixmap, QColor
from .crop_overlay import CropOverlay
from .date_stamp_preview_overlay import DateStampPreviewOverlay
from src.utils.image_loader import ImageLoader


class ThumbnailLoaderWorker(QThread):
    """Background worker thread for loading thumbnails asynchronously."""

    thumbnail_loaded = pyqtSignal(object, QPixmap)  # Emits (ImageItem, QPixmap)

    def __init__(self, image_item, thumbnail_size):
        super().__init__()
        self.image_item = image_item
        self.thumbnail_size = thumbnail_size

    def run(self):
        """Load thumbnail in background thread."""
        try:
            pixmap = self.image_item.get_thumbnail(self.thumbnail_size)
            if pixmap and not pixmap.isNull():
                self.thumbnail_loaded.emit(self.image_item, pixmap)
        except Exception as e:
            print(f"Error loading thumbnail in background: {e}")


class ImageGrid(QWidget):
    """Grid view for displaying images with thumbnails."""

    image_clicked = pyqtSignal(object)  # Emits ImageItem
    image_double_clicked = pyqtSignal(object)  # Emits ImageItem
    image_selected = pyqtSignal(object)  # Emits ImageItem when right-clicked for selection
    image_preview_requested = pyqtSignal(object)  # Emits ImageItem for right double-click

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_project = None
        self.thumbnail_size = config.get_setting("thumbnail_size", 200)
        self.columns = config.get_setting("grid_columns", 5)
        self.image_widgets = {}  # Map ImageItem to ImageWidget
        self.preview_mode = False
        self.date_stamp_preview_mode = False
        self.selection_mode = False
        self.selection_mode_type = None  # 'delete' or 'date_stamp'
        self.selected_items = set()
        self.current_selected_item = None  # Single image selection via right-click
        self.thumbnail_workers = []  # Track active thumbnail loading threads
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
        """Load images from current project into grid with background thumbnail loading."""
        self.clear_grid()
        self.selected_items.clear()  # Clear selection on reload
        self.current_selected_item = None  # Clear current selection

        if not self.current_project:
            return

        row = 0
        col = 0

        for image_item in self.current_project.images:
            # Create image widget with placeholder (no immediate thumbnail loading)
            image_widget = ImageWidget(image_item, self.thumbnail_size, load_immediately=False, config=self.config)
            image_widget.clicked.connect(lambda item=image_item: self.on_image_clicked(item))
            image_widget.double_clicked.connect(lambda item=image_item: self.on_image_double_clicked(item))
            image_widget.right_clicked.connect(lambda item=image_item: self.on_image_right_clicked(item))
            image_widget.right_double_clicked.connect(self.on_image_right_double_clicked)

            # Add to grid
            self.grid_layout.addWidget(image_widget, row, col)
            self.image_widgets[image_item] = image_widget

            # Start background thumbnail loading
            worker = ThumbnailLoaderWorker(image_item, self.thumbnail_size)
            worker.thumbnail_loaded.connect(self._on_thumbnail_loaded)
            worker.finished.connect(lambda w=worker: self._on_worker_finished(w))
            self.thumbnail_workers.append(worker)
            worker.start()

            # Update position
            col += 1
            if col >= self.columns:
                col = 0
                row += 1

    def _on_thumbnail_loaded(self, image_item, pixmap):
        """Handle thumbnail loaded in background thread."""
        if image_item in self.image_widgets:
            self.image_widgets[image_item].set_thumbnail(pixmap)

    def _on_worker_finished(self, worker):
        """Clean up finished thumbnail loading worker."""
        if worker in self.thumbnail_workers:
            self.thumbnail_workers.remove(worker)
            worker.deleteLater()

    def clear_grid(self):
        """Clear all images from the grid."""
        # Stop all running thumbnail workers
        for worker in self.thumbnail_workers:
            worker.quit()
            worker.wait()
        self.thumbnail_workers.clear()

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
            is_current = image_item == self.current_selected_item
            widget.set_selected(is_selected, self.selection_mode_type)
            widget.set_current_selected(is_current)
            widget.update_border()

    def refresh_image(self, image_item):
        """Refresh the thumbnail for a specific image."""
        if image_item in self.image_widgets:
            self.image_widgets[image_item].refresh_thumbnail()

    def toggle_selection_mode(self, enabled: bool, mode: str = 'delete'):
        """
        Enable or disable selection mode.

        Args:
            enabled: Whether to enable selection mode
            mode: Type of selection mode - 'delete' or 'date_stamp'
        """
        self.selection_mode = enabled
        self.selection_mode_type = mode if enabled else None
        if not enabled:
            self.selected_items.clear()
        else:
            # For date stamp mode, pre-select images that already have the flag
            if mode == 'date_stamp' and self.current_project:
                self.selected_items.clear()
                for image_item in self.current_project.images:
                    if image_item.add_date_stamp:
                        self.selected_items.add(image_item)
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
            self.image_widgets[image_item].set_selected(
                image_item in self.selected_items,
                self.selection_mode_type
            )

    def on_image_double_clicked(self, image_item):
        """Handle double click on image."""
        if not self.preview_mode and not self.selection_mode:
            self.image_double_clicked.emit(image_item)

    def on_image_right_clicked(self, image_item):
        """Handle right click on image - select the image."""
        # Clear previous selection
        if self.current_selected_item and self.current_selected_item in self.image_widgets:
            self.image_widgets[self.current_selected_item].set_current_selected(False)

        # Set new selection
        self.current_selected_item = image_item
        if image_item in self.image_widgets:
            self.image_widgets[image_item].set_current_selected(True)

        # Emit signal for main window
        self.image_selected.emit(image_item)

    def on_image_right_double_clicked(self, image_item):
        """Handle right double click on image - open image viewer dialog."""
        self.image_preview_requested.emit(image_item)

    def get_current_selected_item(self):
        """Get the currently selected image (via right-click)."""
        return self.current_selected_item

    def clear_current_selection(self):
        """Clear the current image selection."""
        if self.current_selected_item and self.current_selected_item in self.image_widgets:
            self.image_widgets[self.current_selected_item].set_current_selected(False)
        self.current_selected_item = None

    def select_all(self):
        """Select all images."""
        if not self.current_project:
            return False

        self.selected_items = set(self.current_project.images)
        for _image_item, widget in self.image_widgets.items():
            widget.set_selected(True, self.selection_mode_type)
        return True

    def deselect_all(self):
        """Deselect all images."""
        self.selected_items.clear()
        for _, widget in self.image_widgets.items():
            widget.set_selected(False, None)

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
        for _, widget in self.image_widgets.items():
            widget.exit_preview_mode()

    def enter_date_stamp_preview_mode(self):
        """Enter date stamp preview mode for all images marked for date stamping."""
        if self.selection_mode or self.preview_mode:
            return  # Don't enter if in selection or crop preview mode

        self.date_stamp_preview_mode = True
        for image_item, widget in self.image_widgets.items():
            if image_item.add_date_stamp:
                widget.enter_date_stamp_preview_mode(self.config)

    def exit_date_stamp_preview_mode(self):
        """Exit date stamp preview mode."""
        self.date_stamp_preview_mode = False
        for _, widget in self.image_widgets.items():
            widget.exit_date_stamp_preview_mode()


class ImageWidget(QFrame):
    """Widget representing a single image in the grid."""

    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    right_clicked = pyqtSignal()  # Emits when right-clicked for selection
    right_double_clicked = pyqtSignal(object)  # Emits ImageItem for image viewer

    def __init__(self, image_item, thumbnail_size, load_immediately=True, config=None):
        super().__init__()
        self.image_item = image_item
        self.thumbnail_size = thumbnail_size
        self.load_immediately = load_immediately
        self.config = config
        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self._handle_single_click)
        self.double_click_flag = False
        # Right-click timer for distinguishing single vs double right-click
        self.right_click_timer = QTimer()
        self.right_click_timer.setSingleShot(True)
        self.right_click_timer.timeout.connect(self._handle_single_right_click)
        self.right_double_click_flag = False
        self.crop_overlay = None  # Will be created in preview mode
        self.date_stamp_overlay = None  # Will be created in date stamp preview mode
        self.in_preview_mode = False
        self.in_date_stamp_preview_mode = False
        self.is_selected = False  # For batch selection mode
        self.selection_mode_type = None  # 'delete' or 'date_stamp'
        self.is_current_selected = False  # For single right-click selection
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

        # Load thumbnail or show placeholder
        if self.load_immediately:
            pixmap = self.image_item.get_thumbnail(self.thumbnail_size)
            if pixmap:
                self.thumbnail_label.setPixmap(pixmap)
            else:
                self.thumbnail_label.setText("No Image")
        else:
            # Show placeholder while loading in background
            self._show_placeholder()

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

    def _show_placeholder(self):
        """Show a placeholder while thumbnail is loading."""
        # Create a simple gray placeholder pixmap
        placeholder = QPixmap(self.thumbnail_size, self.thumbnail_size)
        placeholder.fill(QColor(220, 220, 220))  # Light gray
        self.thumbnail_label.setPixmap(placeholder)
        self.thumbnail_label.setText("")  # Clear any text

    def set_thumbnail(self, pixmap: QPixmap):
        """Set the thumbnail pixmap (called when loaded in background)."""
        if pixmap and not pixmap.isNull():
            self.thumbnail_label.setPixmap(pixmap)

    def set_selected(self, selected: bool, mode: Optional[str] = None):
        """
        Set visual selection state for batch selection mode.

        Args:
            selected: Whether this image is selected
            mode: Selection mode type - 'delete' or 'date_stamp'
        """
        self.is_selected = selected
        self.selection_mode_type = mode
        self.update_border()

    def set_current_selected(self, selected: bool):
        """Set visual current selection state (right-click selection)."""
        self.is_current_selected = selected
        self.update_border()

    def refresh_thumbnail(self):
        """Reload the thumbnail from the image item."""
        pixmap = self.image_item.get_thumbnail(self.thumbnail_size)
        if pixmap:
            self.thumbnail_label.setPixmap(pixmap)
        else:
            self.thumbnail_label.setText("No Image")

    def update_border(self):
        """Update border color based on tag status or selection."""
        if self.is_selected:
            # Different colors for different selection modes
            if self.selection_mode_type == 'delete':
                # Red border for delete mode
                self.setStyleSheet("QFrame { border: 4px solid red; background-color: #ffeeee; }")
                self.tag_label.setText("Selected for Deletion")
            elif self.selection_mode_type == 'date_stamp':
                # Green border for date stamp mode
                self.setStyleSheet("QFrame { border: 4px solid green; background-color: #eeffee; }")
                self.tag_label.setText("Selected for Date Stamp")
            else:
                # Fallback for unknown mode
                self.setStyleSheet("QFrame { border: 4px solid blue; background-color: #eeeeff; }")
                self.tag_label.setText("Selected")
            return

        # Determine background color based on current selection
        bg_style = "background-color: #e6f0ff;" if self.is_current_selected else ""

        # Date stamp indicator
        date_stamp_indicator = " 📅" if self.image_item.add_date_stamp else ""

        if self.image_item.is_fully_tagged():
            # Get color from config for fully tagged images (color is global per size ratio)
            if self.config and self.image_item.size_tag:
                size_color = self.config.get_size_color(self.image_item.size_tag)
                if not size_color:
                    size_color = "#4CAF50"  # Default green if not set
            else:
                size_color = "#4CAF50"  # Default green

            border_color = "#0066cc" if self.is_current_selected else size_color
            self.setStyleSheet(f"QFrame {{ border: 3px solid {border_color}; {bg_style} }}")
            tag_text = f"{self.image_item.album_tag}\n{self.image_item.size_tag}{date_stamp_indicator}"
            self.tag_label.setText(tag_text)
        elif self.image_item.has_tags():
            # Yellow/orange border for partially tagged
            border_color = "#0066cc" if self.is_current_selected else "orange"
            self.setStyleSheet(f"QFrame {{ border: 3px solid {border_color}; {bg_style} }}")
            tag_text = f"{self.image_item.album_tag or ''}\n{self.image_item.size_tag or ''}{date_stamp_indicator}"
            self.tag_label.setText(tag_text)
        else:
            # Default border for untagged
            border_color = "#0066cc" if self.is_current_selected else "lightgray"
            self.setStyleSheet(f"QFrame {{ border: 3px solid {border_color}; {bg_style} }}")
            tag_text = "No tags" + date_stamp_indicator
            self.tag_label.setText(tag_text)

    def _handle_single_click(self):
        """Handle single click after delay (if not double-clicked)."""
        if self.double_click_flag:
            # Reset flag and ignore this single click
            self.double_click_flag = False
            return
        self.clicked.emit()

    def _handle_single_right_click(self):
        """Handle single right click after delay (if not double-clicked)."""
        if self.right_double_click_flag:
            # Reset flag and ignore this single right click
            self.right_double_click_flag = False
            return
        self.right_clicked.emit()

    def mousePressEvent(self, a0):
        """Handle mouse press events."""
        if a0:
            if a0.button() == Qt.MouseButton.LeftButton:
                self.click_pos = a0.pos()
            elif a0.button() == Qt.MouseButton.RightButton:
                self.right_click_pos = a0.pos()

    def mouseReleaseEvent(self, a0):
        """Handle mouse release events."""
        if a0:
            # Use system's double-click interval
            interval = QApplication.doubleClickInterval()
            if a0.button() == Qt.MouseButton.LeftButton:
                self.click_timer.start(interval + 50)  # Add 50ms buffer
            elif a0.button() == Qt.MouseButton.RightButton:
                self.right_click_timer.start(interval + 50)

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
            elif a0.button() == Qt.MouseButton.RightButton:
                # Stop any pending single right click timers
                self.right_click_timer.stop()
                # Set flag to ignore next single right click
                self.right_double_click_flag = True
                # Emit right double click signal with ImageItem
                self.right_double_clicked.emit(self.image_item)

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

    def enter_date_stamp_preview_mode(self, config):
        """Enter date stamp preview mode - show date stamp overlay."""
        self.in_date_stamp_preview_mode = True

        # Create date stamp overlay if not exists
        if not self.date_stamp_overlay:
            self.date_stamp_overlay = DateStampPreviewOverlay(self.thumbnail_label)
            self.date_stamp_overlay.setGeometry(self.thumbnail_label.rect())

        # Get display date for this image
        display_date = self.image_item.get_display_date()
        if display_date and self.image_item.size_tag:
            self.date_stamp_overlay.set_preview_data(
                display_date,
                config,
                self.thumbnail_size,
                self.image_item.size_tag
            )
            self.date_stamp_overlay.show()
        else:
            # Hide if no date or size tag
            self.date_stamp_overlay.hide()

    def exit_date_stamp_preview_mode(self):
        """Exit date stamp preview mode - hide date stamp overlay."""
        self.in_date_stamp_preview_mode = False
        if self.date_stamp_overlay:
            self.date_stamp_overlay.hide()

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
