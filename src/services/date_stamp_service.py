"""Service for applying vintage-style date stamps to images."""

import os
import math
from datetime import datetime
from typing import Optional, Tuple, Union, cast
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
from ..models.config import Config
from ..utils.paths import get_assets_dir


def kelvin_to_rgb(temperature: int) -> Tuple[int, int, int]:
    """
    Convert color temperature in Kelvin to RGB values.

    Uses the algorithm by Tanner Helland, which provides accurate
    approximations for temperatures in the 1000K-40000K range.

    Args:
        temperature: Color temperature in Kelvin (1000-40000)

    Returns:
        RGB tuple (0-255 for each channel)
    """
    # Clamp temperature to valid range
    temp = max(1000, min(40000, temperature)) / 100.0

    # Calculate red
    if temp <= 66:
        red = 255
    else:
        red = temp - 60
        red = 329.698727446 * (red ** -0.1332047592)
        red = max(0, min(255, red))

    # Calculate green
    if temp <= 66:
        green = temp
        green = 99.4708025861 * math.log(green) - 161.1195681661
    else:
        green = temp - 60
        green = 288.1221695283 * (green ** -0.0755148492)
    green = max(0, min(255, green))

    # Calculate blue
    if temp >= 66:
        blue = 255
    elif temp <= 19:
        blue = 0
    else:
        blue = temp - 10
        blue = 138.5177312231 * math.log(blue) - 305.0447927307
        blue = max(0, min(255, blue))

    return (int(red), int(green), int(blue))


class DateStampService:
    """Service for rendering vintage film camera-style date stamps on images."""

    def __init__(self, config: Config):
        self.config = config
        self._font_cache = {}

    def apply_date_stamp(
        self,
        image: Image.Image,
        date: datetime,
        size_tag: str,
        output_path: Optional[str] = None
    ) -> Image.Image:
        """
        Apply a vintage-style date stamp to an image.

        Args:
            image: PIL Image to apply stamp to
            date: Date to display on stamp
            size_tag: Size tag (e.g., "9x6") to determine print dimensions
            output_path: Optional output path for debugging

        Returns:
            PIL Image with date stamp applied
        """
        # Get settings
        date_format = cast(str, self.config.get_setting("date_stamp_format", "'YY.MM.DD"))
        position = cast(str, self.config.get_setting("date_stamp_position", "bottom-right"))

        # Calculate font size based on physical dimensions and image size
        font_size = self._calculate_font_size(size_tag, image.height)

        # Auto-calculate margin based on font size (50% of font height)
        margin = max(10, int(font_size * 0.5))

        # Format the date string
        date_str = self._format_date(date, date_format)

        # Load font
        font = self._load_font(font_size)

        # Create the date stamp layers
        stamp_image = self._create_stamp_with_glow(
            image.size,
            date_str,
            font,
            position,
            margin
        )

        # Composite stamp onto image using Screen blend mode
        # This simulates light projection - the glow actually brightens the image
        result = self._screen_blend(image.convert('RGBA'), stamp_image)

        # Convert back to RGB for JPEG saving
        return result.convert('RGB')

    def _calculate_font_size(self, size_tag: str, image_height: int) -> int:
        """
        Calculate font size in pixels based on physical print dimensions.

        The date stamp maintains a fixed physical size (e.g., 0.5 units tall)
        regardless of print size. This means for larger prints, the stamp takes
        up a smaller percentage of the image, and for smaller prints, it takes
        up a larger percentage.

        Formula: font_pixel_height = (configured_height / print_height) × image_pixel_height

        Example with configured height of 0.5:
        - For 10x15 print: 0.5/15 = 0.0333 → stamp is 3.33% of image height
        - For 9x5 print: 0.5/5 = 0.1 → stamp is 10% of image height

        Args:
            size_tag: Size tag like "9x6" representing 9×6 units (cm, inches, etc.)
            image_height: Height of the image in pixels

        Returns:
            Font size in pixels
        """
        configured_height = cast(float, self.config.get_setting("date_stamp_physical_height", 0.5))

        # Parse print height from size_tag (e.g., "9x6" → 6, "10x15" → 15)
        print_height = self._parse_print_height(size_tag)

        # Calculate ratio: configured physical height / print physical height
        ratio = configured_height / print_height

        # Calculate font size in pixels
        font_size = int(ratio * image_height)

        # Ensure reasonable bounds (minimum 12px for readability)
        font_size = max(12, font_size)

        return font_size

    def _parse_print_height(self, size_tag: str) -> float:
        """
        Parse the print height from a size tag.

        Size tags are in format "WxH" where W is width and H is height.
        Examples: "9x6" → 6, "10x15" → 15, "4x6" → 6

        Args:
            size_tag: Size tag string like "9x6"

        Returns:
            Print height as float
        """
        try:
            # Split by 'x' and get the second part (height)
            parts = size_tag.lower().split('x')
            if len(parts) == 2:
                return float(parts[1])
        except (ValueError, IndexError):
            pass

        # Default fallback if parsing fails
        return 6.0

    def _format_date(self, date: datetime, format_str: str) -> str:
        """
        Format date according to the specified format string.

        Supports vintage camera formats like:
        - 'YY.MM.DD (e.g., '23.12.25)
        - MM.DD.'YY (e.g., 12.25.'23)
        - DD.MM.'YY (e.g., 25.12.'23)

        Args:
            date: datetime object
            format_str: Format string with tokens like YY, MM, DD

        Returns:
            Formatted date string
        """
        # Replace tokens with actual values
        result = format_str
        result = result.replace("YY", date.strftime("%y"))
        result = result.replace("MM", date.strftime("%m"))
        result = result.replace("DD", date.strftime("%d"))

        return result

    def _load_font(self, size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        """
        Load DSEG7 Classic font at the specified size with caching.

        Args:
            size: Font size in pixels

        Returns:
            ImageFont object
        """
        # Check cache
        if size in self._font_cache:
            return self._font_cache[size]

        # Try to load bundled DSEG7 font
        # Prefer Bold Mini (thicker, more authentic), fallback to Regular
        assets_dir = get_assets_dir()
        font_path_bold = os.path.join(assets_dir, "fonts", "DSEG7ClassicMini-Bold.ttf")

        font_path = font_path_bold

        try:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, size)
                self._font_cache[size] = font
                return font
        except Exception as e:
            print(f"Error loading DSEG7 font: {e}")

        # Fallback to default font
        try:
            font = ImageFont.load_default()
            self._font_cache[size] = font
            return font
        except Exception:
            # Last resort: create a basic font
            font = ImageFont.load_default()
            self._font_cache[size] = font
            return font

    def _create_stamp_with_glow(
        self,
        image_size: Tuple[int, int],
        text: str,
        font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
        position: str,
        margin: int
    ) -> Image.Image:
        """
        Create date stamp simulating backlit film camera projection effect.

        Real film camera date stamps work by projecting light through a mask
        from BEHIND the film, creating:
        - Sharp, well-defined text segments
        - Very tight rim glow (1-3 pixels) from light scatter at edges
        - Warm color from incandescent bulb + film's orange base

        This implementation uses:
        1. Morphological dilation to create consistent thin rim
        2. Tiny blur for subtle edge glow (not wide diffuse spread)
        3. Temperature gradient: warm rim → bright core

        Args:
            image_size: Size of the target image (width, height)
            text: Date text to render
            font: Font to use
            position: Position string (bottom-right, bottom-left, etc.)
            margin: Margin from edges in pixels

        Returns:
            RGBA image with date stamp
        """
        width, height = image_size

        # Get settings
        glow_intensity = cast(int, self.config.get_setting("date_stamp_glow_intensity", 80) or 80) / 100.0
        opacity = cast(int, self.config.get_setting("date_stamp_opacity", 90) or 90) / 100.0
        temp_outer = cast(int, self.config.get_setting("date_stamp_temp_outer", 1800) or 1800)
        temp_core = cast(int, self.config.get_setting("date_stamp_temp_core", 6500) or 6500)

        # Get colors from temperature settings
        outer_rgb = np.array(kelvin_to_rgb(temp_outer), dtype=np.float32)
        core_rgb = np.array(kelvin_to_rgb(temp_core), dtype=np.float32)

        # Create temporary canvas to measure text
        temp_canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_canvas)
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_width = int(bbox[2] - bbox[0])
        text_height = int(bbox[3] - bbox[1])

        # Calculate position
        x, y = self._calculate_position(
            width, height,
            text_width, text_height,
            position, margin
        )

        # Get font size for proportional scaling
        font_size = getattr(font, 'size', text_height)

        # =====================================================================
        # STEP 1: Create sharp text mask (the core segments)
        # =====================================================================
        text_mask = Image.new('L', (width, height), 0)
        text_draw = ImageDraw.Draw(text_mask)
        text_draw.text((x, y), text, font=font, fill=255)
        text_array = np.array(text_mask, dtype=np.float32) / 255.0

        # =====================================================================
        # STEP 2: Create rim using morphological dilation
        # This simulates the tight glow from backlit projection
        # Rim width scales with font size (about 2-4% of font height)
        # =====================================================================
        rim_width = max(1, int(font_size * 0.04))  # Tight rim, ~4% of font size

        # Dilate text mask to expand edges
        dilated_mask = text_mask.filter(ImageFilter.MaxFilter(size=rim_width * 2 + 1))
        dilated_array = np.array(dilated_mask, dtype=np.float32) / 255.0

        # Apply tiny blur to dilated mask for soft edge (not sharp cutoff)
        blur_radius = max(1, int(font_size * 0.02))  # Very small blur
        dilated_blurred = dilated_mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        dilated_blurred_array = np.array(dilated_blurred, dtype=np.float32) / 255.0

        # =====================================================================
        # STEP 3: Create intensity map with gradient from rim to core
        # - Rim area: lower intensity (warm color)
        # - Core area: HIGH intensity (bright, sharp)
        # =====================================================================

        # Rim = dilated area minus the sharp text
        rim_only = np.clip(dilated_blurred_array - text_array, 0, 1)

        # Rim gets partial intensity for warm color (0.3-0.5 range)
        rim_intensity = rim_only * 0.4

        # Add subtle outer halo beyond the rim
        outer_blur_radius = max(1, int(font_size * 0.03))
        outer_glow = text_mask.filter(ImageFilter.GaussianBlur(radius=outer_blur_radius))
        outer_glow_array = np.array(outer_glow, dtype=np.float32) / 255.0
        outer_only = np.clip(outer_glow_array - dilated_array, 0, 1)
        outer_intensity = outer_only * 0.2

        # Combine rim and outer halo
        glow_intensity_map = np.maximum(rim_intensity, outer_intensity)

        # Core gets FULL intensity (1.0) - this is the sharp text
        # Use the original sharp text mask, NOT blurred
        core_intensity = text_array * 1.0

        # Final intensity: glow provides warm rim, core provides bright center
        intensity = np.maximum(glow_intensity_map, core_intensity)

        # =====================================================================
        # STEP 4: Map intensity to color using temperature gradient
        # Low intensity (rim/edge) → outer temperature (warm orange)
        # High intensity (core) → core temperature (bright)
        # =====================================================================
        intensity_3d = intensity[:, :, np.newaxis]
        colors = outer_rgb + (core_rgb - outer_rgb) * intensity_3d

        # =====================================================================
        # STEP 5: Boost core brightness
        # Add extra brightness to the sharp text center for "hot" look
        # =====================================================================
        # Brighten the core by blending toward white where text is solid
        brightness_boost = 1.3  # 30% brighter in core
        core_boost = text_array[:, :, np.newaxis] * (brightness_boost - 1.0)
        colors = colors + core_boost * colors  # Multiplicative boost
        colors = np.clip(colors, 0, 255)

        # =====================================================================
        # STEP 6: Calculate alpha
        # Sharp core = full opacity, rim = partial opacity
        # =====================================================================
        # Core (sharp text) gets full alpha for crisp edges
        core_alpha = text_array * 1.0

        # Rim and outer glow get reduced alpha
        glow_alpha = np.maximum(rim_only * 0.7, outer_only * 0.4)

        # Combine: core dominates, glow surrounds
        alpha_base = np.maximum(core_alpha, glow_alpha)
        alpha = alpha_base * glow_intensity * opacity

        # =====================================================================
        # STEP 6: Assemble final RGBA image
        # =====================================================================
        result = np.zeros((height, width, 4), dtype=np.float32)
        result[:, :, :3] = colors
        result[:, :, 3] = alpha * 255

        result = np.clip(result, 0, 255).astype(np.uint8)
        return Image.fromarray(result, mode='RGBA')

    def _calculate_position(
        self,
        image_width: int,
        image_height: int,
        text_width: int,
        text_height: int,
        position: str,
        margin: int
    ) -> Tuple[int, int]:
        """
        Calculate text position based on position string.

        Args:
            image_width: Width of image
            image_height: Height of image
            text_width: Width of rendered text
            text_height: Height of rendered text
            position: Position string (bottom-right, bottom-left, top-right, top-left)
            margin: Margin from edges

        Returns:
            (x, y) coordinates for text placement
        """
        if position == "bottom-right":
            x = image_width - text_width - margin
            y = image_height - text_height - margin
        elif position == "bottom-left":
            x = margin
            y = image_height - text_height - margin
        elif position == "top-right":
            x = image_width - text_width - margin
            y = margin
        elif position == "top-left":
            x = margin
            y = margin
        else:
            # Default to bottom-right
            x = image_width - text_width - margin
            y = image_height - text_height - margin

        return (x, y)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """
        Convert hex color to RGB tuple.

        Args:
            hex_color: Hex color string like "#FF7700"

        Returns:
            (R, G, B) tuple
        """
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)

    @staticmethod
    def _screen_blend(base: Image.Image, overlay: Image.Image) -> Image.Image:
        """
        Blend overlay onto base using Screen blend mode.

        Screen blend simulates light projection - lighter colors have more effect.
        Formula: Result = 1 - (1 - A) * (1 - B)

        This creates realistic light glow effects where the glow brightens
        the underlying image rather than just adding semi-transparent color.

        Args:
            base: Base RGBA image
            overlay: Overlay RGBA image with alpha channel controlling intensity

        Returns:
            Blended RGBA image
        """
        # Convert to numpy arrays for faster computation
        base_array = np.array(base, dtype=np.float32) / 255.0
        overlay_array = np.array(overlay, dtype=np.float32) / 255.0

        # Extract RGB and alpha channels
        base_rgb = base_array[:, :, :3]
        base_alpha = base_array[:, :, 3:4]
        overlay_rgb = overlay_array[:, :, :3]
        overlay_alpha = overlay_array[:, :, 3:4]

        # Screen blend formula: 1 - (1 - A) * (1 - B)
        # This simulates light: brighter colors have stronger effect
        screened_rgb = 1.0 - (1.0 - base_rgb) * (1.0 - overlay_rgb)

        # Blend screened result with base using overlay's alpha
        # Where overlay is transparent, keep base; where opaque, use screened result
        result_rgb = base_rgb * (1.0 - overlay_alpha) + screened_rgb * overlay_alpha

        # Combine alpha channels (standard alpha compositing for opacity)
        result_alpha = base_alpha + overlay_alpha * (1.0 - base_alpha)

        # Combine RGB and alpha
        result = np.concatenate([result_rgb, result_alpha], axis=2)

        # Convert back to 8-bit and create PIL image
        result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
        return Image.fromarray(result, mode='RGBA')

