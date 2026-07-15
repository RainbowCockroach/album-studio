import os
from typing import Optional
from PIL import Image
# Compatibility shim for older smartcrop library with Pillow 10+
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
import smartcrop
from PyQt6.QtCore import QThread, pyqtSignal
from .date_stamp_service import DateStampService
from ..utils.image_loader import open_oriented


# Longest edge, in pixels, that smartcrop's saliency search runs on. Smartcrop
# cost is roughly linear in pixel count and it only picks a *region*, so full
# resolution buys nothing: a 12MP phone photo took 9.0s to analyse, versus 0.29s
# at 1200px, for a crop offset differing by ~6% of image height. See
# _find_smart_crop_box for why the library's own prescale never fires here.
SMARTCROP_ANALYSIS_SIZE = 1200

# Memo of computed smartcrop boxes: (path, mtime, size_tag, tw, th) -> box.
# Module-level because callers are short-lived — the image viewer builds a fresh
# CropService for every load, so an instance attribute would never hit. Keyed by
# mtime so a rotated or replaced file recomputes rather than reusing a box for
# pixels that no longer exist.
#
# Deliberately NOT written back to ``ImageItem.crop_box``: that field means "the
# user positioned this by hand" and is persisted to the project file, while these
# are throwaway guesses. Conflating them would persist a box locked to one
# aspect ratio, which re-tagging to a different size does not clear
# (see docs/KNOWN_BUGS.md).
_SMART_CROP_MEMO: dict = {}
_SMART_CROP_MEMO_MAX = 256


def _memo_key(image_path: str, size_tag: str, target_width: int,
              target_height: int):
    """Cache key for a smartcrop result, or None if the file is unreadable."""
    try:
        mtime = os.path.getmtime(image_path)
    except OSError:
        return None
    return (os.path.abspath(image_path), mtime, size_tag,
            target_width, target_height)


def clear_smart_crop_memo():
    """Drop every memoised smartcrop box. For tests and after bulk file edits."""
    _SMART_CROP_MEMO.clear()


class CropService:
    """Service for cropping images using smartcrop library."""

    def __init__(self, config):
        self.config = config
        self.smartcrop = smartcrop.SmartCrop()
        self.date_stamp_service = DateStampService(config)

    def _smart_crop_box_cached(self, img: Image.Image, image_path: str,
                               size_tag: str, target_width: int,
                               target_height: int) -> tuple:
        """``_find_smart_crop_box`` memoised on (path, mtime, size_tag, target)."""
        key = _memo_key(image_path, size_tag, target_width, target_height)
        if key is not None and key in _SMART_CROP_MEMO:
            return _SMART_CROP_MEMO[key]

        box = self._find_smart_crop_box(img, target_width, target_height)

        if key is not None:
            if len(_SMART_CROP_MEMO) >= _SMART_CROP_MEMO_MAX:
                # Plain FIFO eviction — insertion order is enough for a cache
                # this small, and it keeps a project-wide crop from unbounded growth.
                _SMART_CROP_MEMO.pop(next(iter(_SMART_CROP_MEMO)))
            _SMART_CROP_MEMO[key] = box
        return box

    def _find_smart_crop_box(self, img: Image.Image, target_width: int,
                             target_height: int) -> tuple:
        """Run smartcrop on a downscaled copy; return (x, y, w, h) in ``img`` coords.

        Smartcrop has a built-in prescale, but it is dead code for this app.
        It only engages when the requested crop is much smaller than the source,
        whereas ``get_crop_dimensions`` returns the *largest* crop that fits —
        4000px wide out of a 4000px-wide photo. That makes smartcrop's internal
        ``scale`` 1.0, so its ``prescale_size`` lands at exactly 1.0, misses the
        ``< 1`` branch, and it analyses every one of the 12M pixels.

        So downscale here instead. Coordinates come back divided by the same
        factor, and callers get full-resolution ``img`` coords either way.
        """
        longest_edge = max(img.size)
        if longest_edge <= SMARTCROP_ANALYSIS_SIZE:
            analysis_img = img
            factor = 1.0
        else:
            factor = SMARTCROP_ANALYSIS_SIZE / longest_edge
            analysis_img = img.copy()
            analysis_img.thumbnail(
                (SMARTCROP_ANALYSIS_SIZE, SMARTCROP_ANALYSIS_SIZE),
                Image.Resampling.LANCZOS)
            # thumbnail() floors to preserve aspect, so re-derive the true factor
            # from the result rather than trusting the nominal one.
            factor = analysis_img.size[0] / img.size[0]

        # Never ask for a target bigger than the image we are analysing.
        scaled_w = max(1, min(int(target_width * factor), analysis_img.size[0]))
        scaled_h = max(1, min(int(target_height * factor), analysis_img.size[1]))

        result = self.smartcrop.crop(analysis_img, scaled_w, scaled_h)
        box = result['top_crop']

        if factor == 1.0:
            return (box['x'], box['y'], box['width'], box['height'])

        # Map back to full-res coords. Width/height come from the caller's exact
        # target, not from the scaled-up result, so the crop keeps its precise
        # aspect ratio; only the offset is taken from the analysis.
        x = int(round(box['x'] / factor))
        y = int(round(box['y'] / factor))
        # Clamp so the box stays inside the image after rounding.
        x = max(0, min(x, img.size[0] - target_width))
        y = max(0, min(y, img.size[1] - target_height))
        return (x, y, target_width, target_height)

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

    def get_crop_box(self, image_path: str, size_tag: str, manual_crop_box: Optional[dict] = None) -> Optional[tuple]:
        """
        Get crop coordinates (x, y, width, height) for an image.
        Uses manual_crop_box if provided, otherwise calculates via smartcrop.
        Returns tuple (x, y, width, height) or None if unable to calculate.
        """
        try:
            # Open image to get dimensions (EXIF orientation applied — crop boxes
            # and smartcrop analysis both live in upright coords)
            img = open_oriented(image_path)

            # Convert to RGB if necessary (smartcrop requires RGB)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Get image dimensions
            image_width, image_height = img.size

            # Calculate crop dimensions based on image size and ratio
            dimensions = self.get_crop_dimensions(size_tag, image_width, image_height)
            if not dimensions:
                return None

            target_width, target_height = dimensions

            # Determine crop coordinates
            if manual_crop_box:
                # Use manual crop position
                x = manual_crop_box['x']
                y = manual_crop_box['y']
                width = manual_crop_box['width']
                height = manual_crop_box['height']
            else:
                x, y, width, height = self._smart_crop_box_cached(
                    img, image_path, size_tag, target_width, target_height)

            return (x, y, width, height)

        except Exception as e:
            print(f"Error calculating crop box for {image_path}: {e}")
            return None

    def crop_image(
            self,
            image_path: str,
            size_tag: str,
            output_path: str,
            manual_crop_box: Optional[dict] = None,
            image_item=None) -> bool:
        """
        Crop a single image using manual crop box or smartcrop.
        If manual_crop_box is provided, uses it; otherwise uses smartcrop.
        If image_item is provided and has add_date_stamp flag, applies date stamp before saving.
        Returns True if successful, False otherwise.
        """
        try:
            # Open image first to get its dimensions (EXIF orientation applied).
            # The crop is taken from upright pixels and saved without an EXIF
            # block, so the output needs no orientation tag to display right.
            img = open_oriented(image_path)

            # Convert to RGB if necessary (smartcrop requires RGB)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Get image dimensions
            image_width, image_height = img.size

            # Calculate crop dimensions based on image size and ratio
            dimensions = self.get_crop_dimensions(size_tag, image_width, image_height)
            if not dimensions:
                return False

            target_width, target_height = dimensions

            # Determine crop coordinates
            if manual_crop_box:
                # Use manual crop position
                x = manual_crop_box['x']
                y = manual_crop_box['y']
                width = manual_crop_box['width']
                height = manual_crop_box['height']
            else:
                # Memoised, so an export reuses the exact box the viewer
                # previewed instead of re-deriving a slightly different one.
                x, y, width, height = self._smart_crop_box_cached(
                    img, image_path, size_tag, target_width, target_height)

            # Crop the image
            cropped_img = img.crop((x, y, x + width, y + height))

            # Resize to exact dimensions
            final_img = cropped_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # Apply date stamp if requested
            if image_item and image_item.add_date_stamp:
                # Get display date (EXIF, filename, or file modification time)
                display_date = image_item.get_display_date()
                if display_date:
                    final_img = self.date_stamp_service.apply_date_stamp(
                        final_img,
                        display_date,
                        size_tag,
                        output_path
                    )

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Save the cropped image with quality preservation
            save_params = {
                'format': 'JPEG',
                'quality': 95,
                'optimize': True
            }

            final_img.save(output_path, **save_params)

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
            return 0

        for image_item in tagged_images:
            # Build output path: output/Size/filename.jpg
            filename = os.path.basename(image_item.file_path)
            base_name, _ = os.path.splitext(filename)
            new_filename = f"{base_name}.jpg"
            output_path = os.path.join(
                project.output_folder,
                image_item.size_tag,
                new_filename
            )

            # Crop the image (use manual crop_box if available)
            success = self.crop_image(
                image_item.file_path,
                image_item.size_tag,
                output_path,
                manual_crop_box=image_item.crop_box,
                image_item=image_item
            )

            if success:
                image_item.is_cropped = True
                cropped_count += 1

        print(f"Cropped {cropped_count}/{len(tagged_images)} images")
        return cropped_count


class CropWorker(QThread):
    """Background worker thread for cropping images with progress updates."""

    progress_updated = pyqtSignal(int, int, str)  # current, total, filename
    finished_signal = pyqtSignal(int)  # total cropped count

    def __init__(self, crop_service, project):
        super().__init__()
        self.crop_service = crop_service
        self.project = project
        self.cancelled = False

    def run(self):
        """Crop all tagged images with progress updates."""
        cropped_count = 0
        tagged_images = self.project.get_tagged_images()

        if not tagged_images:
            self.finished_signal.emit(0)
            return

        total = len(tagged_images)

        for i, image_item in enumerate(tagged_images):
            # Check if cancelled
            if self.cancelled:
                print(f"Crop operation cancelled. Cropped {cropped_count}/{total} images")
                self.finished_signal.emit(cropped_count)
                return

            # Build output path
            filename = os.path.basename(image_item.file_path)
            base_name, _ = os.path.splitext(filename)
            new_filename = f"{base_name}.jpg"
            output_path = os.path.join(
                self.project.output_folder,
                image_item.size_tag,
                new_filename
            )

            # Emit progress
            self.progress_updated.emit(i + 1, total, filename)

            # Crop the image
            success = self.crop_service.crop_image(
                image_item.file_path,
                image_item.size_tag,
                output_path,
                manual_crop_box=image_item.crop_box,
                image_item=image_item
            )

            if success:
                image_item.is_cropped = True
                cropped_count += 1

        print(f"Cropped {cropped_count}/{total} images")
        self.finished_signal.emit(cropped_count)

    def cancel(self):
        """Cancel the crop operation."""
        self.cancelled = True
