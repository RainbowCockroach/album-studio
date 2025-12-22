from datetime import datetime
from typing import Optional
from PIL import Image
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
        self._thumbnail: Optional[QPixmap] = None

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
                pixmap = QPixmap(self.file_path)
                if not pixmap.isNull():
                    self._thumbnail = pixmap.scaled(
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

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "album_tag": self.album_tag,
            "size_tag": self.size_tag,
            "date_taken": self.date_taken.isoformat() if self.date_taken else None,
            "is_cropped": self.is_cropped
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ImageItem':
        """Create ImageItem from dictionary."""
        item = cls(data["file_path"])
        item.album_tag = data.get("album_tag")
        item.size_tag = data.get("size_tag")
        item.is_cropped = data.get("is_cropped", False)

        date_str = data.get("date_taken")
        if date_str:
            try:
                item.date_taken = datetime.fromisoformat(date_str)
            except ValueError:
                pass

        return item

    def __repr__(self):
        return f"ImageItem(file_path={self.file_path}, album={self.album_tag}, size={self.size_tag})"
