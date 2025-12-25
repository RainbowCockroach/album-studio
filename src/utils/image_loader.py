import os
from PIL import Image, ImageQt
from PyQt6.QtGui import QPixmap, QImage
import pillow_heif

from PyQt6.QtCore import Qt

# Register HEIC opener with Pillow
pillow_heif.register_heif_opener()

class ImageLoader:
    """Utility class for robust image loading, supporting HEIC and other formats."""

    @staticmethod
    def load_pixmap(file_path: str, max_size: int = None) -> QPixmap:
        """
        Load a QPixmap from a file path, supporting HEIC via Pillow.
        
        Args:
            file_path: Path to the image file.
            max_size: Optional maximum size (width or height) to scale down to.
            
        Returns:
            QPixmap: The loaded pixmap, or a null pixmap if loading failed.
        """
        if not os.path.exists(file_path):
            return QPixmap()

        # Try loading directly with QPixmap first (fastest for supported formats like PNG/JPG)
        # Note: We skip this for .heic/.heif extensions to avoid potential issues 
        # or partial support on some platforms, ensuring we use the robust Pillow method.
        lower_path = file_path.lower()
        is_heic = lower_path.endswith('.heic') or lower_path.endswith('.heif')
        
        if not is_heic:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                if max_size:
                    return pixmap.scaled(max_size, max_size, 
                                       aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                                       transformMode=Qt.TransformationMode.SmoothTransformation)
                return pixmap

        # Fallback to Pillow (handles HEIC and others QPixmap might miss)
        try:
            with Image.open(file_path) as img:
                # Convert to RGB (standard for display)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize with Pillow if requested (often higher quality/faster than Qt for large images)
                if max_size:
                    width, height = img.size
                    if width > max_size or height > max_size:
                        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Convert PIL Image to QImage
                # We save to a buffer or use ImageQt, but ImageQt can be tricky.
                # A reliable way is to ensure it's RGB and create QImage from bytes.
                
                # Method 1 using ImageQt:
                # q_image = ImageQt.ImageQt(img)
                
                # Method 2 (more explicit):
                data = img.tobytes("raw", "RGB")
                q_image = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
                
                # Copy to detach from the byte data which might disappear
                pixmap = QPixmap.fromImage(q_image.copy())
                return pixmap

        except Exception as e:
            print(f"Error loading image with Pillow: {file_path} - {e}")
            return QPixmap()
            
    @staticmethod
    def is_heic(file_path: str) -> bool:
        """Check if file path suggests a HEIC image."""
        lower = file_path.lower()
        return lower.endswith('.heic') or lower.endswith('.heif')

    @staticmethod
    def get_image_dimensions(file_path: str) -> tuple[int, int]:
        """
        Get image dimensions (width, height) without fully loading the pixel data.
        Returns (0, 0) if failed.
        """
        try:
            with Image.open(file_path) as img:
                return img.size
        except Exception as e:
            print(f"Error getting dimensions for {file_path}: {e}")
            return (0, 0)
