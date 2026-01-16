import json
import os
import shutil
import zipfile
from typing import List, Optional
from ..models.project import Project
from ..utils.paths import get_user_data_dir
from PIL import Image


class ProjectManager:
    """Service for managing projects: CRUD operations and persistence."""

    def __init__(self, data_dir: str = None):
        # Use user data directory by default (persists across updates)
        self.data_dir = data_dir if data_dir else get_user_data_dir()
        self.projects_file = os.path.join(self.data_dir, "projects.json")
        self.projects: List[Project] = []

    def load_projects(self) -> List[Project]:
        """Load all projects from projects.json."""
        self.projects.clear()

        if not os.path.exists(self.projects_file):
            return self.projects

        try:
            with open(self.projects_file, 'r') as f:
                data = json.load(f)
                for project_data in data.get("projects", []):
                    project = Project.from_dict(project_data)
                    self.projects.append(project)

        except json.JSONDecodeError as e:
            print(f"Error loading projects.json: {e}")
        except Exception as e:
            print(f"Error loading projects: {e}")

        return self.projects

    def save_projects(self):
        """Save all projects to projects.json."""
        try:
            os.makedirs(self.data_dir, exist_ok=True)

            data = {
                "projects": [project.to_dict() for project in self.projects]
            }

            with open(self.projects_file, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            print(f"Error saving projects: {e}")

    def create_project(self, name: str, workspace_directory: str) -> Optional[Project]:
        """Create a new project with automatic folder structure.

        Creates: workspace_directory/project_name/input and workspace_directory/project_name/output

        Args:
            name: Project name
            workspace_directory: Base workspace directory path

        Returns:
            Created Project object or None if failed
        """
        # Check if project with same name already exists
        if self.get_project_by_name(name):
            return None

        # Validate workspace directory
        if not workspace_directory or not os.path.exists(workspace_directory):
            return None

        # Create project folder structure
        project_folder = os.path.join(workspace_directory, name)
        input_folder = os.path.join(project_folder, "input")
        output_folder = os.path.join(project_folder, "output")

        try:
            # Create folders
            os.makedirs(input_folder, exist_ok=True)
            os.makedirs(output_folder, exist_ok=True)
        except Exception as e:
            print(f"Failed to create project folders: {e}")
            return None

        # Create project
        project = Project(name, input_folder, output_folder)
        self.projects.append(project)
        self.save_projects()

        return project

    def delete_project(self, name: str) -> bool:
        """Delete a project by name."""
        project = self.get_project_by_name(name)
        if project:
            self.projects.remove(project)
            self.save_projects()
            return True
        else:
            return False

    def get_project_by_name(self, name: str) -> Optional[Project]:
        """Get a project by its name."""
        for project in self.projects:
            if project.name == name:
                return project
        return None

    def get_project_names(self) -> List[str]:
        """Get list of all project names."""
        return [project.name for project in self.projects]

    def save_project(self, project: Project):
        """Save a specific project (updates projects.json and individual project data file)."""
        # Save project-specific data (tags and crop positions)
        project.save_project_data(self.data_dir)

        # Also save to central projects.json for backwards compatibility
        self.save_projects()

    def clear_tags_for_deleted_sizes(self, deleted_size_ids: set, deleted_size_groups: set):
        """Clear tags from images if their size or size group was deleted.

        Args:
            deleted_size_ids: Set of size IDs that were deleted
            deleted_size_groups: Set of size group names that were deleted
        """
        total_cleared = 0

        for project in self.projects:
            for image_item in project.images:
                # Clear if size group was deleted
                if image_item.album in deleted_size_groups:
                    if image_item.album or image_item.size_id:
                        image_item.album = None
                        image_item.size_id = None
                        total_cleared += 1
                # Clear if size was deleted
                elif image_item.size_id in deleted_size_ids:
                    if image_item.size_id:
                        image_item.size_id = None
                        total_cleared += 1

            # Save project if any tags were cleared
            if total_cleared > 0:
                self.save_project(project)

    def archive_project(self, project_name: str, workspace_dir: str = None, thumbnail_size: int = 800) -> dict:
        """Archive a project by:
        1. Creating thumbnails of all output folder images → save to 'printed' folder at workspace root
        2. Zipping the output folder → save to workspace root
        3. Deleting entire project directory
        4. Removing project from projects.json

        Args:
            project_name: Name of the project to archive
            workspace_dir: Workspace directory root (for printed folder and zip location)
            thumbnail_size: Maximum size for thumbnail (default 800px)

        Returns:
            dict with stats about the archive operation
        """
        project = self.get_project_by_name(project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")

        stats = {
            'thumbnails_created': 0,
            'zip_created': False,
            'folders_deleted': False,
            'project_removed': False
        }

        # Step 1: Create thumbnails from output folder

        # Get project directory (parent of input folder)
        project_directory = os.path.dirname(project.input_folder)

        # Determine workspace root and printed folder location
        if workspace_dir:
            # Use workspace directory root for global printed folder and zip location
            printed_folder = os.path.join(workspace_dir, "printed")
            zip_location = workspace_dir
        else:
            # Fallback to old behavior (parent directory of project folder)
            workspace_root = os.path.dirname(project_directory)
            printed_folder = os.path.join(workspace_root, "printed")
            zip_location = workspace_root

        os.makedirs(printed_folder, exist_ok=True)

        if os.path.exists(project.output_folder):

            # Count files before processing
            total_files = 0
            for root, dirs, files in os.walk(project.output_folder):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.heic')):
                        total_files += 1

            # Process files
            for root, dirs, files in os.walk(project.output_folder):

                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.heic')):
                        src_path = os.path.join(root, file)
                        try:
                            # Open image and create thumbnail
                            with Image.open(src_path) as img:

                                # Convert to RGB if necessary
                                if img.mode in ('RGBA', 'LA', 'P'):
                                    img = img.convert('RGB')

                                # Calculate thumbnail size maintaining aspect ratio
                                img.thumbnail((thumbnail_size, thumbnail_size), Image.Resampling.LANCZOS)

                                # Save as JPG to printed folder
                                base_name = os.path.splitext(file)[0]
                                thumb_path = os.path.join(printed_folder, f"{base_name}.jpg")
                                img.save(thumb_path, 'JPEG', quality=85)

                                stats['thumbnails_created'] += 1
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                    else:
                        pass
        else:
            pass

        # Step 2: Zip the output folder
        if os.path.exists(project.output_folder):
            zip_path = os.path.join(zip_location, f"{project_name}_output.zip")

            try:
                # Count files to zip
                zip_file_count = 0
                for root, dirs, files in os.walk(project.output_folder):
                    zip_file_count += len(files)

                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(project.output_folder):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(project.output_folder))
                            zipf.write(file_path, arcname)

                # Verify zip was created
                if os.path.exists(zip_path):
                    zip_size = os.path.getsize(zip_path)
                    stats['zip_created'] = True
                else:
                    pass

            except Exception as e:
                import traceback
                traceback.print_exc()
                raise
        else:
            pass

        # Step 3: Delete entire project directory
        try:
            if os.path.exists(project_directory):
                shutil.rmtree(project_directory)
            else:
                pass

            stats['folders_deleted'] = True
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise

        # Step 4: Remove project from projects.json
        if self.delete_project(project_name):
            stats['project_removed'] = True
        else:
            pass

        return stats
