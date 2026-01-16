import os
import json
from typing import List, Optional
from .image_item import ImageItem


class Project:
    """Represents a project with input folder, output folder, and images."""

    def __init__(self, name: str, input_folder: str, output_folder: str):
        self.name = name
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.images: List[ImageItem] = []

    def load_images(self, supported_formats: List[str]):
        """Load all images from input folder."""
        self.images.clear()

        if not os.path.exists(self.input_folder):
            print(f"Warning: Input folder does not exist: {self.input_folder}")
            return

        try:
            for filename in sorted(os.listdir(self.input_folder)):
                file_path = os.path.join(self.input_folder, filename)

                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in [fmt.lower() for fmt in supported_formats]:
                        image_item = ImageItem(file_path)
                        self.images.append(image_item)

            print(f"Loaded {len(self.images)} images from {self.input_folder}")
        except Exception as e:
            print(f"Error loading images: {e}")

    def get_image_by_path(self, file_path: str) -> Optional[ImageItem]:
        """Get an image item by its file path."""
        for image in self.images:
            if image.file_path == file_path:
                return image
        return None

    def get_tagged_images(self) -> List[ImageItem]:
        """Get all images that have both album and size tags."""
        return [img for img in self.images if img.is_fully_tagged()]

    def get_untagged_images(self) -> List[ImageItem]:
        """Get all images that don't have any tags."""
        return [img for img in self.images if not img.has_tags()]

    def clear_all_thumbnails(self):
        """Clear all cached thumbnails to free memory."""
        for image in self.images:
            image.clear_thumbnail_cache()

    def to_dict(self) -> dict:
        """Convert project to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "input_folder": self.input_folder,
            "output_folder": self.output_folder,
            "images": [img.to_dict() for img in self.images]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Project':
        """Create Project from dictionary."""
        project = cls(
            name=data["name"],
            input_folder=data["input_folder"],
            output_folder=data["output_folder"]
        )

        for img_data in data.get("images", []):
            image_item = ImageItem.from_dict(img_data)
            project.images.append(image_item)

        return project

    def get_project_data_path(self, data_dir: str = "data") -> str:
        """Get the path to the project data file."""
        project_folder = os.path.join(data_dir, "projects", self.name)
        return os.path.join(project_folder, "project_data.json")

    def save_project_data(self, data_dir: str = "data"):
        """Save project image data (tags and crop positions) to individual project file."""
        try:
            # Create project folder
            project_folder = os.path.join(data_dir, "projects", self.name)
            os.makedirs(project_folder, exist_ok=True)

            # Prepare data - only save image data (tags and crop positions)
            data = {
                "version": "1.0",
                "images": []
            }

            for img in self.images:
                # Only save images that have tags or crop data
                if img.has_tags() or img.crop_box or img.is_cropped:
                    data["images"].append({
                        "file_path": img.file_path,
                        "album_tag": img.album_tag,
                        "size_tag": img.size_tag,
                        "is_cropped": img.is_cropped,
                        "crop_box": img.crop_box
                    })

            # Save to file
            data_path = self.get_project_data_path(data_dir)
            with open(data_path, 'w') as f:
                json.dump(data, f, indent=2)

            print(f"Saved project data for '{self.name}' to {data_path}")
        except Exception as e:
            print(f"Error saving project data for '{self.name}': {e}")

    def load_project_data(self, data_dir: str = "data"):
        """Load project image data (tags and crop positions) from individual project file."""
        data_path = self.get_project_data_path(data_dir)

        if not os.path.exists(data_path):
            print(f"No saved data found for project '{self.name}'")
            return

        try:
            with open(data_path, 'r') as f:
                data = json.load(f)

            # Create a lookup dict for fast matching
            saved_images = {img_data["file_path"]: img_data for img_data in data.get("images", [])}

            # Apply saved data to matching images
            loaded_count = 0
            for img in self.images:
                if img.file_path in saved_images:
                    saved_data = saved_images[img.file_path]
                    img.album_tag = saved_data.get("album_tag")
                    img.size_tag = saved_data.get("size_tag")
                    img.is_cropped = saved_data.get("is_cropped", False)
                    img.crop_box = saved_data.get("crop_box")
                    loaded_count += 1

            print(f"Loaded data for {loaded_count} images in project '{self.name}'")
        except json.JSONDecodeError as e:
            print(f"Error parsing project data file for '{self.name}': {e}")
        except Exception as e:
            print(f"Error loading project data for '{self.name}': {e}")

    def __repr__(self):
        return f"Project(name={self.name}, images={len(self.images)})"
