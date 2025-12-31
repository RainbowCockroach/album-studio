"""Dialog for finding and displaying similar images."""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QWidget, QGridLayout, QMessageBox,
                             QProgressDialog, QSlider, QSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PIL import Image as PILImage


class ComparisonImage:
    """Simple wrapper for images from comparison directory."""

    def __init__(self, file_path, features=None):
        self.file_path = file_path
        self.feature_vector = features
        self._thumbnail = None

    def get_thumbnail(self, size=150):
        """Generate thumbnail for display."""
        if self._thumbnail is None:
            try:
                from ...utils.image_loader import ImageLoader
                self._thumbnail = ImageLoader.load_pixmap(self.file_path, max_size=size * 2)
                if not self._thumbnail.isNull() and (self._thumbnail.width() > size or self._thumbnail.height() > size):
                    self._thumbnail = self._thumbnail.scaled(
                        size, size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
            except Exception as e:
                print(f"[DEBUG] Error creating thumbnail for {self.file_path}: {e}")
                return None
        return self._thumbnail


class ImageThumbnail(QWidget):
    """Widget for displaying a single thumbnail with similarity score."""

    clicked = pyqtSignal(object)  # Emits ImageItem when clicked

    def __init__(self, image_item, similarity_score, parent=None):
        super().__init__(parent)
        self.image_item = image_item
        self.similarity_score = similarity_score
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Image thumbnail
        thumbnail = self.image_item.get_thumbnail(150)
        if thumbnail:
            image_label = QLabel()
            image_label.setPixmap(thumbnail)
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(image_label)

        # Similarity score
        score_text = f"Similarity: {self.similarity_score:.1%}"
        score_label = QLabel(score_text)
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(score_label)

        # File name
        import os
        filename = os.path.basename(self.image_item.file_path)
        filename_label = QLabel(filename)
        filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        filename_label.setWordWrap(True)
        filename_label.setStyleSheet("font-size: 10px; color: gray;")
        layout.addWidget(filename_label)

        self.setLayout(layout)

        # Make it look clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            ImageThumbnail {
                border: 2px solid #ccc;
                border-radius: 5px;
                background: white;
            }
            ImageThumbnail:hover {
                border: 2px solid #0078d7;
                background: #f0f0f0;
            }
        """)

    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.image_item)
        super().mousePressEvent(event)


class FindSimilarDialog(QDialog):
    """Dialog for finding similar images using deep learning."""

    image_selected = pyqtSignal(object)  # Emits ImageItem when user clicks on a similar image

    def __init__(self, current_project, similarity_service, config, parent=None):
        super().__init__(parent)
        self.current_project = current_project
        self.similarity_service = similarity_service
        self.config = config
        self.target_image = None
        self.similar_images = []
        self.comparison_images = []  # Images loaded from comparison directory

        self.setWindowTitle("Find Similar Images")
        self.resize(900, 700)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Instructions
        instructions = QLabel(
            "Click on an image in the main window, then click 'Find Similar' to see similar images.\n"
            "Or select an image from the current project below."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Target image section
        target_layout = QHBoxLayout()
        target_label = QLabel("Target image:")
        target_layout.addWidget(target_label)

        self.target_image_label = QLabel("No image selected")
        self.target_image_label.setStyleSheet("padding: 5px; background: #f0f0f0; border: 1px solid #ccc;")
        target_layout.addWidget(self.target_image_label, stretch=1)

        layout.addLayout(target_layout)

        # Settings panel
        settings_layout = QHBoxLayout()

        # Number of results
        settings_layout.addWidget(QLabel("Max results:"))
        self.num_results_spin = QSpinBox()
        self.num_results_spin.setMinimum(5)
        self.num_results_spin.setMaximum(100)
        self.num_results_spin.setValue(20)
        settings_layout.addWidget(self.num_results_spin)

        settings_layout.addSpacing(20)

        # Minimum similarity threshold
        settings_layout.addWidget(QLabel("Min similarity:"))
        self.min_similarity_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_similarity_slider.setMinimum(0)
        self.min_similarity_slider.setMaximum(100)
        self.min_similarity_slider.setValue(50)
        self.min_similarity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.min_similarity_slider.setTickInterval(10)
        settings_layout.addWidget(self.min_similarity_slider)

        self.min_similarity_label = QLabel("50%")
        self.min_similarity_slider.valueChanged.connect(
            lambda v: self.min_similarity_label.setText(f"{v}%")
        )
        settings_layout.addWidget(self.min_similarity_label)

        settings_layout.addStretch()
        layout.addLayout(settings_layout)

        # Search button
        self.search_btn = QPushButton("Find Similar Images")
        self.search_btn.clicked.connect(self.find_similar)
        self.search_btn.setEnabled(False)
        layout.addWidget(self.search_btn)

        # Results scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.results_widget = QWidget()
        self.results_layout = QGridLayout()
        self.results_widget.setLayout(self.results_layout)
        scroll.setWidget(self.results_widget)

        layout.addWidget(scroll, stretch=1)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.status_label)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def set_target_image(self, image_item):
        """Set the target image to find similar images for."""
        print(f"[DEBUG] FindSimilarDialog: Setting target image: {image_item.file_path}")
        self.target_image = image_item

        import os
        filename = os.path.basename(image_item.file_path)
        self.target_image_label.setText(filename)

        self.search_btn.setEnabled(True)
        self.status_label.setText("")

        # Clear previous results (both UI and data)
        self.clear_results()
        self.similar_images = []
        print(f"[DEBUG] FindSimilarDialog: Target image set successfully")

    def clear_results(self):
        """Clear the results grid UI widgets only."""
        # Remove all widgets from grid
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Note: Do NOT clear self.similar_images here - that's data, not UI

    def find_similar(self):
        """Find similar images to the target."""
        print(f"[DEBUG] FindSimilarDialog: find_similar() called")

        if not self.target_image:
            print(f"[DEBUG] ERROR: Missing target_image")
            return

        # Get comparison directory
        comparison_dir = self.config.get_comparison_directory()
        print(f"[DEBUG] Comparison directory: {comparison_dir}")

        if not comparison_dir:
            QMessageBox.warning(
                self,
                "No Comparison Directory",
                "Comparison directory not configured.\n\n"
                "Please set it in the Config dialog."
            )
            return

        # Get parameters
        top_k = self.num_results_spin.value()
        min_similarity = self.min_similarity_slider.value() / 100.0

        print(f"[DEBUG] Search parameters:")
        print(f"[DEBUG]   - top_k: {top_k}")
        print(f"[DEBUG]   - min_similarity: {min_similarity}")

        # Show progress dialog
        progress = QProgressDialog("Loading comparison images...", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        try:
            # Load images from comparison directory
            supported_formats = self.config.get_setting("supported_formats", [])
            print(f"[DEBUG] Loading images from comparison directory...")

            image_data = self.similarity_service.load_images_from_directory(
                comparison_dir,
                supported_formats
            )

            print(f"[DEBUG] Loaded {len(image_data)} comparison images")

            if not image_data:
                progress.close()
                QMessageBox.warning(
                    self,
                    "No Images",
                    f"No images found in comparison directory:\n{comparison_dir}\n\n"
                    "Make sure the directory exists and contains images."
                )
                return

            # Convert to ComparisonImage objects
            self.comparison_images = [
                ComparisonImage(img['path'], img['features'])
                for img in image_data
            ]

            progress.setValue(30)
            progress.setLabelText("Finding similar images...")

            print(f"[DEBUG] Calling similarity_service.find_similar_images()...")

            # Find similar images
            self.similar_images = self.similarity_service.find_similar_images(
                self.target_image,
                self.comparison_images,
                top_k=top_k,
                min_similarity=min_similarity
            )

            print(f"[DEBUG] find_similar_images() returned {len(self.similar_images)} results")

            progress.setValue(80)

            # Display results
            print(f"[DEBUG] Displaying results...")
            self.display_results()

            progress.setValue(100)

            if not self.similar_images:
                msg = "No similar images found. Try lowering the minimum similarity threshold."
                print(f"[DEBUG] {msg}")
                self.status_label.setText(msg)
            else:
                msg = f"Found {len(self.similar_images)} similar images in comparison directory"
                print(f"[DEBUG] {msg}")
                self.status_label.setText(msg)

        except Exception as e:
            print(f"[DEBUG] ERROR in find_similar(): {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to find similar images: {str(e)}\n\n"
                "Make sure PyTorch is installed: pip install torch torchvision"
            )
        finally:
            progress.close()

    def display_results(self):
        """Display similar images in a grid."""
        print(f"[DEBUG] display_results() called, {len(self.similar_images)} images to display")
        self.clear_results()

        if not self.similar_images:
            print(f"[DEBUG] No images to display")
            return

        # Display in grid (4 columns)
        columns = 4

        for i, (image_item, similarity) in enumerate(self.similar_images):
            row = i // columns
            col = i % columns

            print(f"[DEBUG] Creating thumbnail {i+1}/{len(self.similar_images)}: {image_item.file_path}, similarity={similarity:.4f}")

            thumbnail = ImageThumbnail(image_item, similarity)
            thumbnail.clicked.connect(self.on_thumbnail_clicked)

            self.results_layout.addWidget(thumbnail, row, col)

        print(f"[DEBUG] All thumbnails added to grid")

    def on_thumbnail_clicked(self, image_item):
        """Handle clicking on a similar image."""
        # Emit signal so MainWindow can handle it (e.g., scroll to that image)
        self.image_selected.emit(image_item)

        # Show info
        import os
        filename = os.path.basename(image_item.file_path)
        self.status_label.setText(f"Selected: {filename}")
