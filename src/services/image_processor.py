import os
import shutil
from datetime import datetime
from typing import Optional
from PIL import Image
import piexif


class ImageProcessor:
    """Service for processing images: EXIF reading, renaming, thumbnails."""

    @staticmethod
    def read_exif_date(file_path: str) -> Optional[datetime]:
        """Extract date taken from EXIF data."""
        try:
            # Wrapper for HEIC support
            import pillow_heif
            pillow_heif.register_heif_opener()

            # For HEIC and potentially others, standard piexif.load(path) might fail
            # or simply not work. We'll try a robust approach using Pillow for metadata.
            
            # First try Pillow directly as it's cleaner for HEIC
            try:
                with Image.open(file_path) as img:
                    exif = img.getexif()
                    if exif:
                        # 36867 is DateTimeOriginal, 306 is DateTime
                        date_str = exif.get(36867) or exif.get(306)
                        if date_str:
                            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except Exception:
                pass # Fallback to strict piexif if Pillow fails or returns nothing

            # Legacy/Fallback method (Piexif)
            exif_dict = piexif.load(file_path)

            # Try to get DateTimeOriginal first (when photo was taken)
            if piexif.ExifIFD.DateTimeOriginal in exif_dict.get("Exif", {}):
                date_str = exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal].decode('utf-8')
                return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")

            # Fallback to DateTime
            if piexif.ImageIFD.DateTime in exif_dict.get("0th", {}):
                date_str = exif_dict["0th"][piexif.ImageIFD.DateTime].decode('utf-8')
                return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")

        except Exception as e:
            print(f"Could not read EXIF from {file_path}: {e}")

        # Fallback to file modification time
        try:
            mtime = os.path.getmtime(file_path)
            return datetime.fromtimestamp(mtime)
        except Exception as e:
            print(f"Could not get file time from {file_path}: {e}")

        return None

    @staticmethod
    def rename_by_date(project, date_format: str = "%Y%m%d_%H%M%S") -> int:
        """
        Rename all images in project based on date taken.
        Returns the number of files successfully renamed.
        """
        renamed_count = 0
        name_counter = {}  # To handle duplicate timestamps

        for image_item in project.images:
            # Read EXIF date if not already read
            if image_item.date_taken is None:
                image_item.date_taken = ImageProcessor.read_exif_date(image_item.file_path)

            if image_item.date_taken is None:
                print(f"Skipping {image_item.file_path}: no date available")
                continue

            # Generate new filename
            base_name = image_item.date_taken.strftime(date_format)

            # Handle duplicates by adding a counter
            if base_name in name_counter:
                name_counter[base_name] += 1
                base_name = f"{base_name}_{name_counter[base_name]}"
            else:
                name_counter[base_name] = 0

            # Get file extension
            _, ext = os.path.splitext(image_item.file_path)
            new_filename = f"{base_name}{ext}"

            # Build new file path
            directory = os.path.dirname(image_item.file_path)
            new_file_path = os.path.join(directory, new_filename)

            # Skip if already has the correct name
            if image_item.file_path == new_file_path:
                continue

            # Rename the file
            try:
                shutil.move(image_item.file_path, new_file_path)
                image_item.file_path = new_file_path
                renamed_count += 1
                print(f"Renamed to: {new_filename}")
            except Exception as e:
                print(f"Error renaming {image_item.file_path}: {e}")

        return renamed_count

    @staticmethod
    def generate_thumbnail(file_path: str, size: int = 200) -> Optional[Image.Image]:
        """Generate a thumbnail for an image file."""
        try:
            img = Image.open(file_path)
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            print(f"Error generating thumbnail for {file_path}: {e}")
            return None
