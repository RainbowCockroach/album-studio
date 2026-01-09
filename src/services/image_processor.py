import os
import shutil
from datetime import datetime
from typing import Optional
from PIL import Image, ImageOps
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
    def get_exif_info(file_path: str) -> dict:
        """Extract detailed EXIF information from image."""
        info = {
            "Filename": os.path.basename(file_path),
            "Size": f"{os.path.getsize(file_path) / 1024 / 1024:.2f} MB",
            "Date Modified": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            # Try efficient Pillow reading first
            with Image.open(file_path) as img:
                info["Dimensions"] = f"{img.width} x {img.height}"
                info["Format"] = img.format or "Unknown"
                
                exif = img.getexif()
                if exif:
                    # Common EXIF tags
                    # 271: Make, 272: Model
                    # 33434: ExposureTime, 33437: FNumber
                    # 34855: ISOSpeedRatings
                    # 36867: DateTimeOriginal
                    
                    if 271 in exif: info["Camera Make"] = str(exif[271])
                    if 272 in exif: info["Camera Model"] = str(exif[272])
                    
                    # Exposure details often in ExifOffset (34665)
                    # Pillow doesn't always automatically parse sub-IFDs with getexif()
                    # So we might need to rely on piexif for deep dive or use get_ifd if available in newer Pillow
                    
            # Use piexif for more detailed EXIF data if available
            try:
                exif_dict = piexif.load(file_path)
                
                if "0th" in exif_dict:
                    if piexif.ImageIFD.Make in exif_dict["0th"]:
                        info["Camera Make"] = exif_dict["0th"][piexif.ImageIFD.Make].decode('utf-8', errors='ignore')
                    if piexif.ImageIFD.Model in exif_dict["0th"]:
                        info["Camera Model"] = exif_dict["0th"][piexif.ImageIFD.Model].decode('utf-8', errors='ignore')

                if "Exif" in exif_dict:
                    exif_ifd = exif_dict["Exif"]
                    
                    if piexif.ExifIFD.DateTimeOriginal in exif_ifd:
                        info["Date Taken"] = exif_ifd[piexif.ExifIFD.DateTimeOriginal].decode('utf-8', errors='ignore')
                    
                    if piexif.ExifIFD.ISOSpeedRatings in exif_ifd:
                        info["ISO"] = str(exif_ifd[piexif.ExifIFD.ISOSpeedRatings])
                        
                    if piexif.ExifIFD.ExposureTime in exif_ifd:
                        num, den = exif_ifd[piexif.ExifIFD.ExposureTime]
                        if den != 0:
                            info["Exposure"] = f"{num}/{den} s"
                        else:
                            info["Exposure"] = f"{num} s"
                            
                    if piexif.ExifIFD.FNumber in exif_ifd:
                        num, den = exif_ifd[piexif.ExifIFD.FNumber]
                        if den != 0:
                            info["Aperture"] = f"f/{num/den:.1f}"
                            
                    if piexif.ExifIFD.FocalLength in exif_ifd:
                        num, den = exif_ifd[piexif.ExifIFD.FocalLength]
                        if den != 0:
                            info["Focal Length"] = f"{num/den:.1f} mm"

            except Exception:
                # If piexif fails (e.g. HEIC sometimes), stick to what we got from Pillow or basic file stats
                pass

        except Exception as e:
            print(f"Error reading EXIF for {file_path}: {e}")
            
        return info

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

    @staticmethod
    def correct_image_orientation(file_path: str) -> bool:
        """
        Correct image orientation based on EXIF orientation tag.
        Rotates/flips the image as needed and saves it back with corrected orientation.

        Args:
            file_path: Path to the image file

        Returns:
            True if orientation was corrected, False otherwise
        """
        try:
            # Register HEIC support
            import pillow_heif
            pillow_heif.register_heif_opener()

            # Open the image
            with Image.open(file_path) as img:
                # Check if image has EXIF orientation tag
                exif = img.getexif()
                orientation = exif.get(274) if exif else None  # 274 is the Orientation tag

                # If no orientation tag or orientation is normal (1), no correction needed
                if not orientation or orientation == 1:
                    return False

                # Apply EXIF orientation transformation
                # This automatically rotates/flips based on the EXIF orientation tag
                corrected_img = ImageOps.exif_transpose(img)

                # If correction was needed (image was rotated/flipped)
                if corrected_img is not None:
                    # Save the corrected image back
                    # This will bake the rotation into the image and remove the orientation tag
                    corrected_img.save(file_path, quality=95, optimize=True)
                    print(f"Corrected orientation for: {os.path.basename(file_path)}")
                    return True

            return False

        except Exception as e:
            print(f"Error correcting orientation for {file_path}: {e}")
            return False
