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

    def archive_project(self, project_name: str, workspace_dir: str = None, thumbnail_size: int = 800) -> dict:
        """Archive a project by:
        1. Creating thumbnails of all output folder images → save to 'printed' folder at workspace root
        2. Zipping the output folder
        3. Deleting both input and output folders
        4. Removing project from projects.json

        Args:
            project_name: Name of the project to archive
            workspace_dir: Workspace directory root (for printed folder location)
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
        print(f"[DEBUG] Step 1: Creating thumbnails from {project.output_folder}")

        # Get input parent directory for zip file location
        input_parent = os.path.dirname(project.input_folder)
        print(f"[DEBUG] Input parent directory: {input_parent}")

        # Determine printed folder location
        if workspace_dir:
            # Use workspace directory root for global printed folder
            printed_folder = os.path.join(workspace_dir, "printed")
            print(f"[DEBUG] Using workspace-based printed folder")
        else:
            # Fallback to old behavior (parent directory of input folder)
            printed_folder = os.path.join(input_parent, "printed")
            print(f"[DEBUG] Using input-parent-based printed folder")

        print(f"[DEBUG] Printed folder location: {printed_folder}")
        os.makedirs(printed_folder, exist_ok=True)

        if os.path.exists(project.output_folder):
            print(f"[DEBUG] Output folder exists: {project.output_folder}")

            # Count files before processing
            total_files = 0
            for root, dirs, files in os.walk(project.output_folder):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.heic')):
                        total_files += 1
            print(f"[DEBUG] Found {total_files} image files in output folder")

            # Process files
            for root, dirs, files in os.walk(project.output_folder):
                print(f"[DEBUG] Walking directory: {root}")
                print(f"[DEBUG] Files in this directory: {files}")

                for file in files:
                    print(f"[DEBUG] Processing file: {file}")
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.heic')):
                        src_path = os.path.join(root, file)
                        print(f"[DEBUG] Creating thumbnail for: {src_path}")
                        try:
                            # Open image and create thumbnail
                            with Image.open(src_path) as img:
                                print(f"[DEBUG] Opened image: {src_path}, size: {img.size}, mode: {img.mode}")

                                # Convert to RGB if necessary
                                if img.mode in ('RGBA', 'LA', 'P'):
                                    img = img.convert('RGB')
                                    print(f"[DEBUG] Converted to RGB")

                                # Calculate thumbnail size maintaining aspect ratio
                                img.thumbnail((thumbnail_size, thumbnail_size), Image.Resampling.LANCZOS)
                                print(f"[DEBUG] Thumbnail size: {img.size}")

                                # Save as JPG to printed folder
                                base_name = os.path.splitext(file)[0]
                                thumb_path = os.path.join(printed_folder, f"{base_name}.jpg")
                                print(f"[DEBUG] Saving thumbnail to: {thumb_path}")
                                img.save(thumb_path, 'JPEG', quality=85)

                                stats['thumbnails_created'] += 1
                                print(f"[DEBUG] ✓ Created thumbnail: {thumb_path}")
                        except Exception as e:
                            print(f"[DEBUG] ERROR creating thumbnail for {src_path}: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print(f"[DEBUG] Skipping non-image file: {file}")
        else:
            print(f"[DEBUG] WARNING: Output folder does not exist: {project.output_folder}")

        # Step 2: Zip the output folder
        print(f"[DEBUG] Step 2: Zipping output folder")
        if os.path.exists(project.output_folder):
            zip_path = os.path.join(input_parent, f"{project_name}_output.zip")
            print(f"[DEBUG] Zip path: {zip_path}")

            try:
                # Count files to zip
                zip_file_count = 0
                for root, dirs, files in os.walk(project.output_folder):
                    zip_file_count += len(files)
                print(f"[DEBUG] Found {zip_file_count} total files to zip")

                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(project.output_folder):
                        print(f"[DEBUG] Zipping directory: {root}")
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(project.output_folder))
                            print(f"[DEBUG] Adding to zip: {file_path} -> {arcname}")
                            zipf.write(file_path, arcname)

                # Verify zip was created
                if os.path.exists(zip_path):
                    zip_size = os.path.getsize(zip_path)
                    print(f"[DEBUG] ✓ Zip created successfully: {zip_path} ({zip_size} bytes)")
                    stats['zip_created'] = True
                else:
                    print(f"[DEBUG] ERROR: Zip file not found after creation: {zip_path}")

            except Exception as e:
                print(f"[DEBUG] ERROR creating zip: {e}")
                import traceback
                traceback.print_exc()
                raise
        else:
            print(f"[DEBUG] WARNING: Output folder does not exist for zipping: {project.output_folder}")

        # Step 3: Delete both input and output folders
        print(f"[DEBUG] Step 3: Deleting input and output folders")
        try:
            if os.path.exists(project.input_folder):
                print(f"[DEBUG] Deleting input folder: {project.input_folder}")
                shutil.rmtree(project.input_folder)
                print(f"[DEBUG] ✓ Deleted input folder: {project.input_folder}")
            else:
                print(f"[DEBUG] Input folder already gone: {project.input_folder}")

            if os.path.exists(project.output_folder):
                print(f"[DEBUG] Deleting output folder: {project.output_folder}")
                shutil.rmtree(project.output_folder)
                print(f"[DEBUG] ✓ Deleted output folder: {project.output_folder}")
            else:
                print(f"[DEBUG] Output folder already gone: {project.output_folder}")

            stats['folders_deleted'] = True
        except Exception as e:
            print(f"[DEBUG] ERROR deleting folders: {e}")
            import traceback
            traceback.print_exc()
            raise

        # Step 4: Remove project from projects.json
        print(f"[DEBUG] Step 4: Removing project from projects list")
        if self.delete_project(project_name):
            stats['project_removed'] = True
            print(f"[DEBUG] ✓ Project removed from projects.json")
        else:
            print(f"[DEBUG] WARNING: Failed to remove project from projects.json")

        print(f"[DEBUG] Archive complete. Stats: {stats}")
        return stats
