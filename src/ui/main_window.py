from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QMessageBox, QApplication)
from PyQt6.QtCore import Qt
from .widgets.toolbar_top import ProjectToolbar
from .widgets.image_grid import ImageGrid
from .widgets.toolbar_bottom import ToolbarBottom
from .widgets.detail_panel import DetailPanel
from ..models.config import Config
from ..services.project_manager import ProjectManager
from ..services.image_processor import ImageProcessor
from ..services.crop_service import CropService
from ..services.image_similarity_service import ImageSimilarityService


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.project_manager = ProjectManager()
        self.crop_service = CropService(self.config)
        self.similarity_service = None  # Lazy load when needed
        self.current_project = None
        self.last_clicked_image = None  # Track last clicked image for similarity search

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
        self.tag_panel = ToolbarBottom(self.config)
        self.detail_panel = DetailPanel()

        # Content layout (Horizontal) - holds sidebar and grid
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        content_layout.addWidget(self.detail_panel)
        content_layout.addWidget(self.image_grid, stretch=1)

        # Add widgets to main layout
        layout.addWidget(self.project_toolbar)
        layout.addLayout(content_layout, stretch=1)
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
        self.project_toolbar.archive_requested.connect(self.on_archive_requested)
        self.project_toolbar.add_photo_requested.connect(self.on_add_photo_requested)
        self.project_toolbar.delete_mode_toggled.connect(self.on_delete_mode_toggled)
        self.project_toolbar.delete_confirmed.connect(self.on_delete_confirmed)

        # Tag panel
        self.tag_panel.crop_requested.connect(self.on_crop_requested)
        self.tag_panel.save_requested.connect(self.on_save_requested)
        self.tag_panel.cancel_requested.connect(self.on_cancel_requested)
        self.tag_panel.refresh_requested.connect(self.on_refresh_requested)
        self.tag_panel.config_requested.connect(self.on_config_requested)
        self.tag_panel.detail_toggled.connect(self.detail_panel.setVisible)
        self.tag_panel.find_similar_requested.connect(self.on_find_similar_requested)

        # Detail panel
        self.detail_panel.rename_requested.connect(self.on_rename_requested)

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

        # Load saved project data (tags and crop positions)
        project.load_project_data(self.project_manager.data_dir)

        # Update image grid
        self.image_grid.set_project(project)

        # Enable tag panel
        self.tag_panel.set_enabled(True)

        print(f"Loaded project: {project_name} with {len(project.images)} images")

    def on_project_changed(self, project_name: str):
        """Handle project selection change."""
        self.load_project(project_name)

    def on_new_project(self, name: str):
        """Handle new project creation."""
        if not name:
            QMessageBox.warning(self, "Invalid Input",
                              "Please enter a project name.")
            return

        # Get workspace directory from settings
        workspace_directory = self.config.get_setting("workspace_directory", "")

        if not workspace_directory:
            reply = QMessageBox.question(
                self,
                "Workspace Not Set",
                "No workspace directory configured. Would you like to configure it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # Open config dialog to set workspace
                from .dialogs.config_dialog import ConfigDialog
                dialog = ConfigDialog(self.config, self.project_manager, self)
                if dialog.exec() == dialog.DialogCode.Accepted:
                    # Check if workspace was set
                    workspace_directory = self.config.get_setting("workspace_directory", "")
                    if not workspace_directory:
                        return  # User cancelled or didn't set workspace
                else:
                    return  # User cancelled dialog
            else:
                return  # User chose not to configure workspace

        project = self.project_manager.create_project(name, workspace_directory)
        if project:
            # Refresh project list
            project_names = self.project_manager.get_project_names()
            self.project_toolbar.set_projects(project_names)
            self.project_toolbar.set_current_project(name)

            QMessageBox.information(self, "Success",
                                  f"Project '{name}' created successfully!\n"
                                  f"Location: {project.input_folder}")
        else:
            QMessageBox.warning(self, "Error",
                              f"Failed to create project. Project may already exist.")

    def on_archive_requested(self, project_name: str):
        """Handle archive project request."""
        if not project_name:
            return

        # Show confirmation dialog with detailed info
        reply = QMessageBox.question(
            self,
            "Archive Project",
            f"Archive project '{project_name}'?\n\n"
            "This will:\n"
            "1. Create thumbnails of all output images → saved to 'printed' folder\n"
            "2. Zip the output folder\n"
            "3. Delete both input and output folders\n"
            "4. Remove project from the projects list\n\n"
            "This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Show busy cursor
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            # Archive the project
            workspace_dir = self.config.get_setting("workspace_directory", "")
            stats = self.project_manager.archive_project(project_name, workspace_dir=workspace_dir)

            QApplication.restoreOverrideCursor()

            # Clear current project if it's the one being archived
            if self.current_project and self.current_project.name == project_name:
                self.current_project = None
                self.image_grid.set_project(None)
                self.tag_panel.set_enabled(False)

            # Reload projects list (will load first available project if any exist)
            self.load_projects()

            # Show success message
            QMessageBox.information(
                self,
                "Archive Complete",
                f"Project '{project_name}' archived successfully!\n\n"
                f"Created {stats['thumbnails_created']} thumbnails\n"
                f"Zip created: {'Yes' if stats['zip_created'] else 'No'}\n"
                f"Folders deleted: {'Yes' if stats['folders_deleted'] else 'No'}\n"
                f"Project removed: {'Yes' if stats['project_removed'] else 'No'}"
            )

        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(
                self,
                "Archive Failed",
                f"Failed to archive project: {str(e)}"
            )

    def on_add_photo_requested(self):
        """Handle add photo request."""
        if not self.current_project:
            return

        from PyQt6.QtWidgets import QFileDialog
        
        # Get supported formats for filter
        # e.g. "Images (*.png *.jpg *.jpeg)"
        formats = self.config.get_setting("supported_formats", [".png", ".jpg", ".jpeg"])
        filter_str = f"Images ({' '.join(['*' + f for f in formats])})"

        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Images to Add",
            "",
            filter_str
        )

        if not file_paths:
            return

        # Show busy cursor
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            import shutil
            import os
            
            added_count = 0
            
            for src_path in file_paths:
                if not os.path.exists(src_path):
                    continue
                    
                # Copy to project input folder
                filename = os.path.basename(src_path)
                dest_path = os.path.join(self.current_project.input_folder, filename)
                
                # Handle potential duplicate names before renaming
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(self.current_project.input_folder, f"{base}_{counter}{ext}")
                    counter += 1
                
                try:
                    shutil.copy2(src_path, dest_path)
                    
                    # Manually add to project images temporarily so they can be processed
                    from ..models.image_item import ImageItem
                    image_item = ImageItem(dest_path)
                    self.current_project.images.append(image_item)
                    
                    added_count += 1
                except Exception as e:
                    print(f"Error copying file {src_path}: {e}")

            if added_count > 0:
                # Rename all images in project (including new ones) by date
                date_format = self.config.get_setting("date_format", "%Y%m%d_%H%M%S")
                ImageProcessor.rename_by_date(self.current_project, date_format)
                
                # Reload project to refresh everything cleanly
                self.load_project(self.current_project.name)
                
                QApplication.restoreOverrideCursor()
                QMessageBox.information(
                    self,
                    "Photos Added",
                    f"Successfully added and sorted {added_count} photos."
                )
            
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error", f"Failed to add photos: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def on_delete_mode_toggled(self, enabled: bool):
        """Handle delete mode toggle."""
        self.image_grid.toggle_selection_mode(enabled)
        
        if not enabled:
            # Just exit mode, clear selection
            pass

    def on_delete_confirmed(self):
        """Handle delete confirmation - delete selected images."""
        selected_items = self.image_grid.get_selected_items()
        
        if not selected_items:
            # No items selected, just exit delete mode
            self.project_toolbar.toggle_delete_mode(False)
            return

        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete {len(selected_items)} selected photos?\n"
            "This will delete the files from your computer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        import os
        deleted_count = 0
        
        for item in selected_items:
            try:
                # Remove file
                if os.path.exists(item.file_path):
                    os.remove(item.file_path)
                
                # Remove from project
                if item in self.current_project.images:
                    self.current_project.images.remove(item)
                    
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting file {item.file_path}: {e}")

        # Save project
        self.project_manager.save_project(self.current_project)
        
        # Refresh grid
        self.image_grid.set_project(self.current_project)
        
        # Exit delete mode
        self.project_toolbar.toggle_delete_mode(False)
        
        QMessageBox.information(self, "Deletion Complete", f"Deleted {deleted_count} photos.")

    def on_image_clicked(self, image_item):
        """Handle single click on image - apply current tags."""
        # Track last clicked image for similarity search
        self.last_clicked_image = image_item

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

        # Update detail panel if visible
        if self.detail_panel.isVisible():
            self.update_detail_panel(image_item)

    def update_detail_panel(self, image_item):
        """Update detail panel with EXIF info."""
        if not image_item:
            self.detail_panel.clear()
            return
            
        info = ImageProcessor.get_exif_info(image_item.file_path)
        self.detail_panel.set_data(info, image_item)

    def on_image_double_clicked(self, image_item):
        """Handle double click on image - clear tags."""
        image_item.clear_tags()

        # Refresh display
        self.image_grid.refresh_display()

        # Save project
        self.project_manager.save_project(self.current_project)

    def on_rename_requested(self, image_item):
        """Handle rename request from detail panel."""
        if not image_item or not self.current_project:
            return
        
        import os
        from PyQt6.QtWidgets import QInputDialog
        
        # Get current filename
        current_filename = os.path.basename(image_item.file_path)
        current_dir = os.path.dirname(image_item.file_path)
        
        # Show input dialog
        new_filename, ok = QInputDialog.getText(
            self,
            "Rename Image",
            "Enter new filename:",
            text=current_filename
        )
        
        if not ok or not new_filename:
            return
        
        # Validate filename
        new_filename = new_filename.strip()
        if not new_filename:
            QMessageBox.warning(self, "Invalid Filename", "Filename cannot be empty.")
            return
        
        # Ensure extension is preserved if not provided
        _, current_ext = os.path.splitext(current_filename)
        _, new_ext = os.path.splitext(new_filename)
        if not new_ext:
            new_filename += current_ext
        
        # Check if filename already exists
        new_path = os.path.join(current_dir, new_filename)
        if os.path.exists(new_path) and new_path != image_item.file_path:
            QMessageBox.warning(
                self,
                "File Exists",
                f"A file named '{new_filename}' already exists."
            )
            return
        
        # Rename the file
        try:
            os.rename(image_item.file_path, new_path)
            
            # Update image item
            image_item.file_path = new_path
            image_item.clear_thumbnail_cache()  # Clear cached thumbnail
            
            # Save project
            self.project_manager.save_project(self.current_project)
            
            # Refresh grid to show new filename
            self.image_grid.load_images()
            
            # Update detail panel if visible
            if self.detail_panel.isVisible():
                self.update_detail_panel(image_item)
            
            QMessageBox.information(
                self,
                "Rename Successful",
                f"File renamed to '{new_filename}'"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Rename Failed",
                f"Failed to rename file: {str(e)}"
            )


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

    def on_crop_requested(self):
        """Handle crop button click - enter preview mode."""
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

        # Enter preview mode
        self.image_grid.enter_preview_mode()

        QMessageBox.information(
            self,
            "Crop Preview",
            "Drag the crop rectangles to adjust the crop area for each image.\n"
            "The aspect ratio is locked based on the size tag.\n\n"
            "Click 'Save' to crop and save images, or 'Cancel' to exit without cropping."
        )

    def on_cancel_requested(self):
        """Handle cancel button click - exit preview mode without saving."""
        if not self.current_project:
            return

        # Exit preview mode without saving crop positions
        self.image_grid.exit_preview_mode()

    def on_save_requested(self):
        """Handle save button click - crop and save all tagged images."""
        if not self.current_project:
            return

        tagged_images = self.current_project.get_tagged_images()

        if not tagged_images:
            return

        # Exit preview mode and save crop positions
        self.image_grid.exit_preview_mode()
        self.project_manager.save_project(self.current_project)

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

    def on_config_requested(self):
        """Handle config button click - open configuration dialog."""
        from .dialogs.config_dialog import ConfigDialog

        dialog = ConfigDialog(self.config, self.project_manager, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            # Reload UI components after config changes
            self.tag_panel.load_size_group()

            # Refresh the current project to update display if needed
            if self.current_project:
                self.image_grid.set_project(self.current_project)

    def on_find_similar_requested(self):
        """Handle find similar button click - open similarity dialog."""

        if not self.current_project:
            QMessageBox.warning(
                self,
                "No Project",
                "Please load a project first."
            )
            return

        if not self.current_project.images:
            QMessageBox.warning(
                self,
                "No Images",
                "No images in the current project."
            )
            return

        # Lazy load similarity service
        if self.similarity_service is None:
            try:
                self.similarity_service = ImageSimilarityService()
            except ImportError as e:
                QMessageBox.critical(
                    self,
                    "Missing Dependencies",
                    f"PyTorch is required for image similarity.\n\n{str(e)}\n\n"
                    "Install with: pip install torch torchvision"
                )
                return
            except Exception as e:
                import traceback
                traceback.print_exc()
                return

        # Show the dialog
        from .dialogs.find_similar_dialog import FindSimilarDialog

        dialog = FindSimilarDialog(self.current_project, self.similarity_service, self.config, self)

        # If user clicked an image before opening dialog, use that as target
        if self.last_clicked_image:
            dialog.set_target_image(self.last_clicked_image)

        dialog.exec()

    def closeEvent(self, event):
        """Handle window close event."""
        # Save current project
        if self.current_project:
            self.project_manager.save_project(self.current_project)

        event.accept()
