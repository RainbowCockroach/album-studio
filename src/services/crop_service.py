import os
from typing import Optional
from PIL import Image
# Compatibility shim for older smartcrop library with Pillow 10+
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS
import smartcrop


class CropService:
    """Service for cropping images using smartcrop library."""

    def __init__(self, config):
        self.config = config
        self.smartcrop = smartcrop.SmartCrop()

    def get_crop_dimensions(self, size_tag: str, image_width: int, image_height: int) -> Optional[tuple]:
        """
        Calculate target width and height for a size tag based on the image dimensions.
        Returns the largest possible crop dimensions that fit within the image while maintaining the ratio.
        """
        size_info = self.config.get_size_info(size_tag)
        if not size_info:
            return None

        ratio = size_info.get("ratio")
        if not ratio:
            return None

        # Calculate the largest possible crop dimensions that fit within the image
        # while maintaining the target ratio (ratio = width / height)

        # Try fitting by width (use full width, calculate height)
        crop_width_by_width = image_width
        crop_height_by_width = int(image_width / ratio)

        # Try fitting by height (use full height, calculate width)
        crop_height_by_height = image_height
        crop_width_by_height = int(image_height * ratio)

        # Choose the option that fits within the image bounds
        if crop_height_by_width <= image_height:
            # Fit by width
            return (crop_width_by_width, crop_height_by_width)
        else:
            # Fit by height
            return (crop_width_by_height, crop_height_by_height)


    def crop_image(self, image_path: str, size_tag: str, output_path: str, manual_crop_box: Optional[dict] = None) -> bool:
        """
        Crop a single image using manual crop box or smartcrop.
        If manual_crop_box is provided, uses it; otherwise uses smartcrop.
        Returns True if successful, False otherwise.
        """
        try:
            # Open image first to get its dimensions
            img = Image.open(image_path)

            # Convert to RGB if necessary (smartcrop requires RGB)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Get image dimensions
            image_width, image_height = img.size

            # Calculate crop dimensions based on image size and ratio
            dimensions = self.get_crop_dimensions(size_tag, image_width, image_height)
            if not dimensions:
                print(f"No dimensions found for size: {size_tag}")
                return False

            target_width, target_height = dimensions

            # Determine crop coordinates
            if manual_crop_box:
                # Use manual crop position
                x = manual_crop_box['x']
                y = manual_crop_box['y']
                width = manual_crop_box['width']
                height = manual_crop_box['height']
                print(f"Using manual crop: {x}, {y}, {width}, {height}")
            else:
                # Use smartcrop to find best crop
                result = self.smartcrop.crop(img, target_width, target_height)

                # Extract crop coordinates
                crop_box = result['top_crop']
                x = crop_box['x']
                y = crop_box['y']
                width = crop_box['width']
                height = crop_box['height']
                print(f"Using smart crop: {x}, {y}, {width}, {height}")

            # Crop the image
            cropped_img = img.crop((x, y, x + width, y + height))

            # Resize to exact dimensions
            final_img = cropped_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Save the cropped image
            final_img.save(output_path, quality=95)

            print(f"Cropped and saved: {output_path}")
            return True

        except Exception as e:
            print(f"Error cropping {image_path}: {e}")
            return False

    def crop_project(self, project) -> int:
        """
        Crop all fully tagged images in a project.
        Returns the number of successfully cropped images.
        """
        cropped_count = 0
        tagged_images = project.get_tagged_images()

        if not tagged_images:
            print("No fully tagged images to crop")
            return 0

        for image_item in tagged_images:
            # Build output path: output/AlbumName/Size/filename.jpg
            filename = os.path.basename(image_item.file_path)
            base_name, _ = os.path.splitext(filename)
            new_filename = f"{base_name}.jpg"
            output_path = os.path.join(
                project.output_folder,
                image_item.album_tag,
                image_item.size_tag,
                new_filename
            )

            # Crop the image (use manual crop_box if available)
            success = self.crop_image(
                image_item.file_path,
                image_item.size_tag,
                output_path,
                manual_crop_box=image_item.crop_box
            )

            if success:
                image_item.is_cropped = True
                cropped_count += 1

        print(f"Cropped {cropped_count}/{len(tagged_images)} images")
        return cropped_count
