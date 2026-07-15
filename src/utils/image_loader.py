import os
from typing import Optional
from PIL import Image, ImageOps
from PyQt6.QtGui import QPixmap, QImage, QImageReader
from PyQt6.QtCore import Qt, QSize
import pillow_heif

# Register HEIC opener with Pillow
pillow_heif.register_heif_opener()


def open_oriented(file_path: str) -> Image.Image:
    """
    Open an image with its EXIF orientation already applied to the pixels.

    Upright pixels are this app's internal coordinate space: crop boxes,
    smartcrop analysis and exports all assume it. Phone cameras write the raw
    sensor buffer and record the needed rotation in EXIF tag 274 instead of
    re-encoding, so a plain Image.open() yields sideways or upside-down pixels
    for those files. Every path that touches pixels must go through here.

    pillow_heif already rotates HEIC at decode, so exif_transpose is a no-op
    there; this matters for JPEG, which gets no such treatment.

    The returned image has no orientation tag left (exif_transpose strips it),
    so re-saving it cannot double-apply the rotation.
    """
    img = Image.open(file_path)
    oriented = ImageOps.exif_transpose(img) or img
    # exif_transpose returns a transposed *copy*, and Pillow's copies carry no
    # .format — restore it, or a caller that infers its save format from it
    # (ImageProcessor.rotate_image) would write JPEG bytes into a .heic.
    oriented.format = img.format
    return oriented


def pil_to_qimage(img: Image.Image) -> QImage:
    """Convert a PIL image to a QImage by copying raw bytes.

    The obvious alternative — ``img.save(buf, format='PNG')`` then
    ``loadFromData`` — costs a full PNG encode *and* decode for pixels that
    never touch a disk: 2.8s versus 20ms for a 12MP frame. Always go this way.

    The QImage is copied because it does not own ``data``, which Python is free
    to free the moment this function returns.
    """
    if img.mode != 'RGB':
        img = img.convert('RGB')
    data = img.tobytes("raw", "RGB")
    q_image = QImage(data, img.width, img.height, img.width * 3,
                     QImage.Format.Format_RGB888)
    return q_image.copy()


class ImageLoader:
    """Utility class for robust image loading, supporting HEIC and other formats."""

    @staticmethod
    def load_qimage(file_path: str, max_size: Optional[int] = None) -> QImage:
        """
        Load a QImage from a file path, supporting HEIC via Pillow.
        Uses QImageReader for efficient JPEG DCT scaling when possible.

        This is the thread-safe half of ``load_pixmap``: QImage may be built on
        any thread, whereas QPixmap is a QPaintDevice and is GUI-thread-only.
        Background loaders must call this and convert on the main thread.

        Args:
            file_path: Path to the image file.
            max_size: Optional maximum size (width or height) to scale down to.

        Returns:
            QImage: The loaded image, or a null QImage if loading failed.
        """
        if not os.path.exists(file_path):
            return QImage()

        lower_path = file_path.lower()
        is_heic = lower_path.endswith('.heic') or lower_path.endswith('.heif')
        is_jpeg = lower_path.endswith('.jpg') or lower_path.endswith('.jpeg')

        # Use QImageReader for JPEG files - it supports efficient DCT scaling
        if is_jpeg and max_size:
            try:
                reader = QImageReader(file_path)

                # Apply EXIF orientation; off by default, so without this a
                # rotated JPEG decodes to raw sensor pixels. size() stays
                # pre-transform, which is the space setScaledSize wants.
                reader.setAutoTransform(True)

                # Get original size
                original_size = reader.size()
                if original_size.isValid():
                    # max_size is a ceiling, not a target. QSize.scaled() grows
                    # as happily as it shrinks, so without this guard a photo
                    # smaller than max_size gets upscaled — burning memory to
                    # invent pixels, and leaving the viewer showing a blur above
                    # 1:1. The Pillow branch below has never done this; the two
                    # must agree, or behaviour depends on the file format.
                    fits_already = (original_size.width() <= max_size and
                                    original_size.height() <= max_size)
                    scaled_size = original_size if fits_already else (
                        original_size.scaled(
                            QSize(max_size, max_size),
                            Qt.AspectRatioMode.KeepAspectRatio
                        )
                    )

                    # Set the scaled size BEFORE reading for efficient decoding
                    reader.setScaledSize(scaled_size)

                    # Set quality for good balance (75 = floating point DCT + bilinear)
                    reader.setQuality(75)

                    # Read the image at scaled size (uses JPEG DCT partial decoding)
                    image = reader.read()

                    if not image.isNull():
                        return image
            except Exception as e:
                print(f"Error using QImageReader for JPEG: {file_path} - {e}")
                # Fall through to standard loading

        # For non-JPEG or if QImageReader failed, use standard loading.
        # Read via QImageReader rather than QPixmap(path) so EXIF orientation is
        # applied here too — this is the path a full-size JPEG (no max_size) takes.
        if not is_heic:
            reader = QImageReader(file_path)
            reader.setAutoTransform(True)
            image = reader.read()
            if not image.isNull():
                # Ceiling, not target — see the JPEG branch above.
                if max_size and (image.width() > max_size or
                                 image.height() > max_size):
                    return image.scaled(max_size, max_size,
                                        aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                                        transformMode=Qt.TransformationMode.SmoothTransformation)
                return image

        # Fallback to Pillow (handles HEIC and others QPixmap might miss)
        try:
            with open_oriented(file_path) as img:
                # Resize with Pillow if requested (often higher quality/faster than Qt for large images)
                if max_size:
                    width, height = img.size
                    if width > max_size or height > max_size:
                        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                return pil_to_qimage(img)

        except Exception as e:
            print(f"Error loading image with Pillow: {file_path} - {e}")
            return QImage()

    @staticmethod
    def load_pixmap(file_path: str, max_size: Optional[int] = None) -> QPixmap:
        """
        Load a QPixmap from a file path, supporting HEIC via Pillow.

        GUI-thread only — see ``load_qimage``, which does the actual work and is
        what background loaders should call. The conversion here is essentially
        free (~0ms even for a 12MP frame).

        Args:
            file_path: Path to the image file.
            max_size: Optional maximum size (width or height) to scale down to.

        Returns:
            QPixmap: The loaded pixmap, or a null pixmap if loading failed.
        """
        image = ImageLoader.load_qimage(file_path, max_size=max_size)
        if image.isNull():
            return QPixmap()
        return QPixmap.fromImage(image)

    @staticmethod
    def is_heic(file_path: str) -> bool:
        """Check if file path suggests a HEIC image."""
        lower = file_path.lower()
        return lower.endswith('.heic') or lower.endswith('.heif')

    @staticmethod
    def get_image_dimensions(file_path: str) -> tuple[int, int]:
        """
        Get image dimensions (width, height) as displayed, i.e. with EXIF
        orientation applied — a 90°-rotated photo reports swapped axes.
        Returns (0, 0) if failed.
        """
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                # Orientations 5-8 are the 90°/270° cases, which swap the axes.
                if (img.getexif() or {}).get(274) in (5, 6, 7, 8):
                    return (height, width)
                return (width, height)
        except Exception as e:
            print(f"Error getting dimensions for {file_path}: {e}")
            return (0, 0)
