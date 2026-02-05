import os
from typing import Optional
from PIL import Image
from PyQt6.QtGui import QPixmap, QImage, QImageReader
from PyQt6.QtCore import Qt, QSize
import pillow_heif

# Register HEIC opener with Pillow
pillow_heif.register_heif_opener()


class ImageLoader:
    """Utility class for robust image loading, supporting HEIC and other formats."""

    @staticmethod
    def load_pixmap(file_path: str, max_size: Optional[int] = None) -> QPixmap:
        """
        Load a QPixmap from a file path, supporting HEIC via Pillow.
        Uses QImageReader for efficient JPEG DCT scaling when possible.

        Args:
            file_path: Path to the image file.
            max_size: Optional maximum size (width or height) to scale down to.

        Returns:
            QPixmap: The loaded pixmap, or a null pixmap if loading failed.
        """
        if not os.path.exists(file_path):
            return QPixmap()

        lower_path = file_path.lower()
        is_heic = lower_path.endswith('.heic') or lower_path.endswith('.heif')
        is_jpeg = lower_path.endswith('.jpg') or lower_path.endswith('.jpeg')

        # Use QImageReader for JPEG files - it supports efficient DCT scaling
        if is_jpeg and max_size:
            try:
                reader = QImageReader(file_path)

                # Get original size
                original_size = reader.size()
                if original_size.isValid():
                    # Calculate scaled size maintaining aspect ratio
                    scaled_size = original_size.scaled(
                        QSize(max_size, max_size),
                        Qt.AspectRatioMode.KeepAspectRatio
                    )

                    # Set the scaled size BEFORE reading for efficient decoding
                    reader.setScaledSize(scaled_size)

                    # Set quality for good balance (75 = floating point DCT + bilinear)
                    reader.setQuality(75)

                    # Read the image at scaled size (uses JPEG DCT partial decoding)
                    image = reader.read()

                    if not image.isNull():
                        return QPixmap.fromImage(image)
            except Exception as e:
                print(f"Error using QImageReader for JPEG: {file_path} - {e}")
                # Fall through to standard loading

        # For non-JPEG or if QImageReader failed, use standard loading
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
