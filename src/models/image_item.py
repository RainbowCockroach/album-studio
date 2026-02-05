from datetime import datetime
from typing import Optional
import numpy as np
import os
import re
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt


class ImageItem:
    """Represents an image file with tags and metadata."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.album_tag: Optional[str] = None
        self.size_tag: Optional[str] = None
        self.date_taken: Optional[datetime] = None
        self.is_cropped = False
        self.crop_box: Optional[dict] = None  # {x, y, width, height} in image coordinates
        self._thumbnail: Optional[QPixmap] = None
        self.feature_vector: Optional[np.ndarray] = None  # Cached ResNet50 features for similarity search
        self.exif_data: Optional[dict] = None  # Cached EXIF info to avoid re-reading
        self.add_date_stamp: bool = False  # Flag to indicate if date stamp should be added on export

    def set_tags(self, album: Optional[str] = None, size: Optional[str] = None):
        """Set album and/or size tags."""
        if album is not None:
            self.album_tag = album
        if size is not None:
            self.size_tag = size

    def clear_tags(self):
        """Clear all tags from this image."""
        self.album_tag = None
        self.size_tag = None
        self.crop_box = None  # Clear crop position when tags are cleared

    def has_tags(self) -> bool:
        """Check if image has any tags assigned."""
        return self.album_tag is not None or self.size_tag is not None

    def is_fully_tagged(self) -> bool:
        """Check if image has both album and size tags."""
        return self.album_tag is not None and self.size_tag is not None

    def get_thumbnail(self, size: int = 200) -> Optional[QPixmap]:
        """Get or create a thumbnail for this image."""
        if self._thumbnail is None:
            try:
                from ..utils.image_loader import ImageLoader
                # Use ImageLoader which handles HEIC and resizing efficiently
                # We request 2x size initially for better quality on high DPI,
                # but limit it to avoid massive memory usage for huge files.
                load_size = size * 2
                self._thumbnail = ImageLoader.load_pixmap(self.file_path, max_size=load_size)

                if not self._thumbnail.isNull() and (self._thumbnail.width() > size or self._thumbnail.height() > size):
                    self._thumbnail = self._thumbnail.scaled(
                        size, size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
            except Exception as e:
                print(f"Error creating thumbnail for {self.file_path}: {e}")
                return None
        return self._thumbnail

    def clear_thumbnail_cache(self):
        """Clear cached thumbnail to free memory."""
        self._thumbnail = None

    def get_exif_data(self) -> dict:
        """Get or read EXIF data (cached after first read)."""
        if self.exif_data is None:
            from ..services.image_processor import ImageProcessor
            self.exif_data = ImageProcessor.get_exif_info(self.file_path)
        return self.exif_data

    def clear_exif_cache(self):
        """Clear cached EXIF data to force re-reading."""
        self.exif_data = None

    def get_display_date(self) -> Optional[datetime]:
        """
        Get the date to display on the date stamp.
        Priority: 1) EXIF date_taken, 2) Parse from filename, 3) File modification time
        """
        # Return cached EXIF date if available
        if self.date_taken is not None:
            return self.date_taken

        # Try to parse date from filename (format: YYYYMMDD_HHMMSS)
        filename = os.path.basename(self.file_path)
        name_without_ext = os.path.splitext(filename)[0]

        # Pattern: 20231225_143022 or similar
        pattern = r'^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})'
        match = re.match(pattern, name_without_ext)

        if match:
            try:
                year, month, day, hour, minute, second = map(int, match.groups())
                return datetime(year, month, day, hour, minute, second)
            except ValueError:
                pass  # Invalid date values, continue to fallback

        # Fallback to file modification time
        try:
            mtime = os.path.getmtime(self.file_path)
            return datetime.fromtimestamp(mtime)
        except Exception:
            pass

        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "album_tag": self.album_tag,
            "size_tag": self.size_tag,
            "date_taken": self.date_taken.isoformat() if self.date_taken else None,
            "is_cropped": self.is_cropped,
            "crop_box": self.crop_box,
            "feature_vector": self.feature_vector.tolist() if self.feature_vector is not None else None,
            "add_date_stamp": self.add_date_stamp
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ImageItem':
        """Create ImageItem from dictionary."""
        item = cls(data["file_path"])
        item.album_tag = data.get("album_tag")
        item.size_tag = data.get("size_tag")
        item.is_cropped = data.get("is_cropped", False)
        item.crop_box = data.get("crop_box")
        item.add_date_stamp = data.get("add_date_stamp", False)

        date_str = data.get("date_taken")
        if date_str:
            try:
                item.date_taken = datetime.fromisoformat(date_str)
            except ValueError:
                pass

        # Restore feature vector if present
        feature_list = data.get("feature_vector")
        if feature_list is not None:
            item.feature_vector = np.array(feature_list)

        return item

    def __repr__(self):
        return f"ImageItem(file_path={self.file_path}, album={self.album_tag}, size={self.size_tag})"
