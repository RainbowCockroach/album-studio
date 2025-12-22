import os
from typing import List
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

    def get_image_by_path(self, file_path: str) -> ImageItem:
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

    def __repr__(self):
        return f"Project(name={self.name}, images={len(self.images)})"
