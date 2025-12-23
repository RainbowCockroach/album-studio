from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                             QMessageBox, QApplication)
from PyQt6.QtCore import Qt
from .widgets.project_toolbar import ProjectToolbar
from .widgets.image_grid import ImageGrid
from .widgets.tag_panel import TagPanel
from ..models.config import Config
from ..services.project_manager import ProjectManager
from ..services.image_processor import ImageProcessor
from ..services.crop_service import CropService


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.project_manager = ProjectManager()
        self.crop_service = CropService(self.config)
        self.current_project = None

        self.init_ui()
        self.load_projects()

    def init_ui(self):
        self.setWindowTitle("Album Studio - Image Sorting & Processing")

        # Start in full screen
        self.showMaximized()

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create widgets
        self.project_toolbar = ProjectToolbar()
        self.image_grid = ImageGrid(self.config)
        self.tag_panel = TagPanel(self.config)

        # Add widgets to layout
        layout.addWidget(self.project_toolbar)
        layout.addWidget(self.image_grid, stretch=1)
        layout.addWidget(self.tag_panel)

        central_widget.setLayout(layout)

        # Connect signals
        self.connect_signals()

        # Initially disable tag panel until a project is loaded
        self.tag_panel.set_enabled(False)

    def connect_signals(self):
        """Connect all widget signals to their handlers."""
        # Project toolbar
        self.project_toolbar.project_changed.connect(self.on_project_changed)
        self.project_toolbar.new_project_created.connect(self.on_new_project)

        # Tag panel
        self.tag_panel.crop_requested.connect(self.on_crop_requested)
        self.tag_panel.refresh_requested.connect(self.on_refresh_requested)
        self.tag_panel.preview_requested.connect(self.on_preview_requested)

        # Image grid
        self.image_grid.image_clicked.connect(self.on_image_clicked)
        self.image_grid.image_double_clicked.connect(self.on_image_double_clicked)

    def load_projects(self):
        """Load all projects from disk."""
        self.project_manager.load_projects()
        project_names = self.project_manager.get_project_names()
        self.project_toolbar.set_projects(project_names)

        # Load first project if available
        if project_names:
            self.load_project(project_names[0])

    def load_project(self, project_name: str):
        """Load a specific project."""
        project = self.project_manager.get_project_by_name(project_name)
        if not project:
            QMessageBox.warning(self, "Error", f"Project not found: {project_name}")
            return

        self.current_project = project

        # Load images from folder
        supported_formats = self.config.get_setting("supported_formats", [])
        project.load_images(supported_formats)

        # Update image grid
        self.image_grid.set_project(project)

        # Enable tag panel
        self.tag_panel.set_enabled(True)

        print(f"Loaded project: {project_name} with {len(project.images)} images")

    def on_project_changed(self, project_name: str):
        """Handle project selection change."""
        self.load_project(project_name)

    def on_new_project(self, name: str, input_folder: str, output_folder: str):
        """Handle new project creation."""
        if not name or not input_folder or not output_folder:
            QMessageBox.warning(self, "Invalid Input",
                              "Please fill in all fields.")
            return

        project = self.project_manager.create_project(name, input_folder, output_folder)
        if project:
            # Refresh project list
            project_names = self.project_manager.get_project_names()
            self.project_toolbar.set_projects(project_names)
            self.project_toolbar.set_current_project(name)

            QMessageBox.information(self, "Success",
                                  f"Project '{name}' created successfully!")
        else:
            QMessageBox.warning(self, "Error",
                              f"Failed to create project. Project may already exist.")

    def on_image_clicked(self, image_item):
        """Handle single click on image - apply current tags."""
        album, size = self.tag_panel.get_selected_tags()

        if not album or not size:
            QMessageBox.warning(self, "No Tags Selected",
                              "Please select both album and size before tagging images.")
            return

        # Apply tags
        image_item.set_tags(album, size)

        # Refresh display
        self.image_grid.refresh_display()

        # Save project
        self.project_manager.save_project(self.current_project)

    def on_image_double_clicked(self, image_item):
        """Handle double click on image - clear tags."""
        image_item.clear_tags()

        # Refresh display
        self.image_grid.refresh_display()

        # Save project
        self.project_manager.save_project(self.current_project)

    def on_refresh_requested(self):
        """Handle refresh & rename button click."""
        if not self.current_project:
            return

        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            "Refresh Images",
            "This will:\n"
            "1. Refresh the image list from the input folder\n"
            "2. Rename all images based on their date taken\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Reload images
        supported_formats = self.config.get_setting("supported_formats", [])
        self.current_project.load_images(supported_formats)

        # Rename by date
        date_format = self.config.get_setting("date_format", "%Y%m%d_%H%M%S")
        renamed_count = ImageProcessor.rename_by_date(
            self.current_project,
            date_format
        )

        # Refresh display
        self.image_grid.set_project(self.current_project)

        # Save project
        self.project_manager.save_project(self.current_project)

        QMessageBox.information(
            self,
            "Refresh Complete",
            f"Refreshed {len(self.current_project.images)} images.\n"
            f"Renamed {renamed_count} files."
        )

    def on_preview_requested(self):
        """Handle preview & adjust crops button click."""
        if not self.current_project:
            return

        tagged_images = self.current_project.get_tagged_images()

        if not tagged_images:
            QMessageBox.warning(
                self,
                "No Tagged Images",
                "No fully tagged images to preview. Please tag images first."
            )
            return

        # Toggle preview mode
        if self.image_grid.preview_mode:
            # Exit preview mode
            self.image_grid.exit_preview_mode()
            self.tag_panel.preview_btn.setText("Preview & Adjust Crops")

            # Save project with updated crop positions
            self.project_manager.save_project(self.current_project)

            QMessageBox.information(
                self,
                "Preview Closed",
                f"Crop positions saved for {len(tagged_images)} images.\n"
                "Click 'Crop All Tagged Images' to apply the crops."
            )
        else:
            # Enter preview mode
            self.image_grid.enter_preview_mode()
            self.tag_panel.preview_btn.setText("Exit Preview Mode")

            QMessageBox.information(
                self,
                "Preview Mode",
                "Drag the crop rectangles to adjust the crop area for each image.\n"
                "The aspect ratio is locked based on the size tag.\n\n"
                "Click 'Exit Preview Mode' when done."
            )

    def on_crop_requested(self):
        """Handle crop all tagged images button click."""
        if not self.current_project:
            return

        tagged_images = self.current_project.get_tagged_images()

        if not tagged_images:
            QMessageBox.warning(
                self,
                "No Tagged Images",
                "No fully tagged images to crop. Please tag images first."
            )
            return

        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            "Crop Images",
            f"This will crop {len(tagged_images)} tagged images.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Show progress
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            # Crop images
            cropped_count = self.crop_service.crop_project(self.current_project)

            # Save project
            self.project_manager.save_project(self.current_project)

            QMessageBox.information(
                self,
                "Crop Complete",
                f"Successfully cropped {cropped_count}/{len(tagged_images)} images.\n"
                f"Output folder: {self.current_project.output_folder}"
            )
        finally:
            QApplication.restoreOverrideCursor()

    def closeEvent(self, event):
        """Handle window close event."""
        # Save current project
        if self.current_project:
            self.project_manager.save_project(self.current_project)

        event.accept()
