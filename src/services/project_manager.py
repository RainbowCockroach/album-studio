import json
import os
from typing import List, Optional
from ..models.project import Project


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

    def create_project(self, name: str, input_folder: str, output_folder: str) -> Optional[Project]:
        """Create a new project."""
        # Check if project with same name already exists
        if self.get_project_by_name(name):
            print(f"Project with name '{name}' already exists")
            return None

        # Validate folders
        if not os.path.exists(input_folder):
            print(f"Input folder does not exist: {input_folder}")
            return None

        # Create output folder if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)

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
        """Save a specific project (updates projects.json)."""
        # Project is already in the list, just save all
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
