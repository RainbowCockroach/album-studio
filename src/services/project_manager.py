import json
import os
import shutil
import zipfile
from typing import List, Optional
from ..models.project import Project
from PIL import Image


class ProjectManager:
    """Service for managing projects: CRUD operations and persistence."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.projects_file = os.path.join(data_dir, "projects.json")
        self.projects: List[Project] = []

    def load_projects(self) -> List[Project]:
        """Load all projects from projects.json."""
        self.projects.clear()

        if not os.path.exists(self.projects_file):
            print(f"No projects file found at {self.projects_file}")
            return self.projects

        try:
            with open(self.projects_file, 'r') as f:
                data = json.load(f)
                for project_data in data.get("projects", []):
                    project = Project.from_dict(project_data)
                    self.projects.append(project)

            print(f"Loaded {len(self.projects)} projects")
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

            print(f"Saved {len(self.projects)} projects")
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
            print(f"Project with name '{name}' already exists")
            return None

        # Validate workspace directory
        if not workspace_directory or not os.path.exists(workspace_directory):
            print(f"Workspace directory does not exist: {workspace_directory}")
            return None

        # Create project folder structure
        project_folder = os.path.join(workspace_directory, name)
        input_folder = os.path.join(project_folder, "input")
        output_folder = os.path.join(project_folder, "output")

        try:
            # Create folders
            os.makedirs(input_folder, exist_ok=True)
            os.makedirs(output_folder, exist_ok=True)
            print(f"Created project folders at: {project_folder}")
        except Exception as e:
            print(f"Failed to create project folders: {e}")
            return None

        # Create project
        project = Project(name, input_folder, output_folder)
        self.projects.append(project)
        self.save_projects()

        print(f"Created project: {name}")
        return project

    def delete_project(self, name: str) -> bool:
        """Delete a project by name."""
        project = self.get_project_by_name(name)
        if project:
            self.projects.remove(project)
            self.save_projects()
            print(f"Deleted project: {name}")
            return True
        else:
            print(f"Project not found: {name}")
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

        if total_cleared > 0:
            print(f"Cleared tags from {total_cleared} images due to deleted sizes/groups")

    def archive_project(self, project_name: str, thumbnail_size: int = 800) -> dict:
        """Archive a project by:
        1. Creating thumbnails of all output folder images → save to 'printed' folder
        2. Zipping the output folder
        3. Deleting both input and output folders
        4. Removing project from projects.json

        Args:
            project_name: Name of the project to archive
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
        print(f"Step 1: Creating thumbnails from {project.output_folder}")

        # Get parent directory of input folder for 'printed' folder
        input_parent = os.path.dirname(project.input_folder)
        printed_folder = os.path.join(input_parent, "printed")
        os.makedirs(printed_folder, exist_ok=True)

        if os.path.exists(project.output_folder):
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
                                print(f"Created thumbnail: {thumb_path}")
                        except Exception as e:
                            print(f"Error creating thumbnail for {src_path}: {e}")

        # Step 2: Zip the output folder
        print(f"Step 2: Zipping output folder")
        if os.path.exists(project.output_folder):
            zip_path = os.path.join(input_parent, f"{project_name}_output.zip")
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(project.output_folder):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(project.output_folder))
                            zipf.write(file_path, arcname)

                stats['zip_created'] = True
                print(f"Created zip: {zip_path}")
            except Exception as e:
                print(f"Error creating zip: {e}")
                raise

        # Step 3: Delete both input and output folders
        print(f"Step 3: Deleting input and output folders")
        try:
            if os.path.exists(project.input_folder):
                shutil.rmtree(project.input_folder)
                print(f"Deleted input folder: {project.input_folder}")

            if os.path.exists(project.output_folder):
                shutil.rmtree(project.output_folder)
                print(f"Deleted output folder: {project.output_folder}")

            stats['folders_deleted'] = True
        except Exception as e:
            print(f"Error deleting folders: {e}")
            raise

        # Step 4: Remove project from projects.json
        print(f"Step 4: Removing project from projects list")
        if self.delete_project(project_name):
            stats['project_removed'] = True

        return stats
