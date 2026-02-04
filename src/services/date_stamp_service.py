"""Service for applying vintage-style date stamps to images."""

import os
from datetime import datetime
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np
from ..models.config import Config
from ..utils.paths import get_assets_dir


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
        date_format = self.config.get_setting("date_stamp_format", "'YY.MM.DD")
        position = self.config.get_setting("date_stamp_position", "bottom-right")
        margin = self.config.get_setting("date_stamp_margin", 30)

        # Calculate font size based on physical dimensions
        font_size = self._calculate_font_size(size_tag)

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

    def _calculate_font_size(self, size_tag: str) -> int:
        """
        Calculate font size in pixels based on physical print dimensions.

        The date stamp maintains a fixed physical size (e.g., 0.2 units tall)
        regardless of print size, so it appears consistent across different prints.

        Args:
            size_tag: Size tag like "9x6" representing 9×6 units (cm, inches, etc.)

        Returns:
            Font size in pixels
        """
        physical_height = self.config.get_setting("date_stamp_physical_height", 0.2)
        pixels_per_unit = self.config.get_setting("date_stamp_target_dpi", 300)

        # Calculate pixel size: physical_size (units) × pixels_per_unit = pixels
        font_size = int(physical_height * pixels_per_unit)

        # Ensure reasonable bounds (minimum 18px, maximum 120px)
        font_size = max(18, min(120, font_size))

        return font_size

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

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
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
        font: ImageFont.FreeTypeFont,
        position: str,
        margin: int
    ) -> Image.Image:
        """
        Create multi-layer date stamp with vintage glow effect.

        Uses proper alpha channel handling to avoid dark edges:
        1. Create grayscale masks for text shapes
        2. Blur the masks
        3. Apply colors using the masks as alpha channels

        This prevents PIL's antialiasing from creating grey edges by separating
        the shape/alpha from the color information.

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

        # Get color settings with proper defaults (vintage orange tones)
        main_color = self.config.get_setting("date_stamp_color", "#FFAA44") or "#FFAA44"  # Bright orange-yellow core (LED look)
        glow_color = self.config.get_setting("date_stamp_glow_color", "#FF7700") or "#FF7700"  # Warm orange glow
        glow_intensity = self.config.get_setting("date_stamp_glow_intensity", 80) or 80
        opacity = self.config.get_setting("date_stamp_opacity", 90) or 90

        # Create transparent canvas
        canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))

        # Get text bounding box using temporary draw object
        temp_draw = ImageDraw.Draw(canvas)
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_width = int(bbox[2] - bbox[0])
        text_height = int(bbox[3] - bbox[1])

        # Calculate position
        x, y = self._calculate_position(
            width, height,
            text_width, text_height,
            position, margin
        )

        # Normalize glow intensity (0-100 to 0-1)
        glow_factor = glow_intensity / 100.0

        # Get font size for proportional scaling
        font_size = font.size if hasattr(font, 'size') else text_height

        # Parse colors from config
        main_rgb = self._hex_to_rgb(main_color)
        glow_rgb = self._hex_to_rgb(glow_color)

        # Create color gradient from outer glow to core text
        # Outer glow: Use configured glow color
        outer_glow_color = glow_rgb

        # Mid glow: Blend 50% between glow and main color
        mid_color = (
            (glow_rgb[0] + main_rgb[0]) // 2,
            (glow_rgb[1] + main_rgb[1]) // 2,
            (glow_rgb[2] + main_rgb[2]) // 2
        )

        # Core color: Use configured main color
        core_color = main_rgb

        # Bright highlight: Lighten main color by 20% for center brightness
        bright_color = (
            min(255, int(main_rgb[0] * 1.0 + (255 - main_rgb[0]) * 0.2)),
            min(255, int(main_rgb[1] * 1.0 + (255 - main_rgb[1]) * 0.2)),
            min(255, int(main_rgb[2] * 1.0 + (255 - main_rgb[2]) * 0.2))
        )

        # =================================================================
        # PROPER TECHNIQUE: Create grayscale masks, then apply colors
        # This prevents dark edges from antialiasing
        # =================================================================

        def create_glow_layer(blur_radius: int, color_rgb: Tuple[int, int, int], alpha_multiplier: float):
            """Create a single glow layer with proper alpha handling."""
            # Step 1: Create grayscale mask (white text on black background)
            mask = Image.new('L', (width, height), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.text((x, y), text, font=font, fill=255)

            # Step 2: Blur the mask
            if blur_radius > 0:
                mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))

            # Step 3: Adjust mask opacity
            if alpha_multiplier < 1.0:
                mask = mask.point(lambda p: int(p * alpha_multiplier))

            # Step 4: Create colored RGBA image using mask as alpha
            colored_layer = Image.new('RGBA', (width, height), (*color_rgb, 0))
            colored_layer.putalpha(mask)

            return colored_layer

        # =================================================================
        # OUTER GLOW LAYERS - Configurable glow color, wide diffusion
        # =================================================================

        canvas = self._screen_blend(canvas, create_glow_layer(
            int(font_size * 4.0), outer_glow_color, 0.35 * glow_factor
        ))

        canvas = self._screen_blend(canvas, create_glow_layer(
            int(font_size * 3.0), outer_glow_color, 0.45 * glow_factor
        ))

        canvas = self._screen_blend(canvas, create_glow_layer(
            int(font_size * 2.0), mid_color, 0.55 * glow_factor
        ))

        canvas = self._screen_blend(canvas, create_glow_layer(
            int(font_size * 1.5), mid_color, 0.65 * glow_factor
        ))

        # =================================================================
        # INNER GLOW LAYERS - Orange core, build up brightness
        # =================================================================

        canvas = self._screen_blend(canvas, create_glow_layer(
            int(font_size * 1.0), core_color, 0.75 * glow_factor
        ))

        canvas = self._screen_blend(canvas, create_glow_layer(
            int(font_size * 0.5), core_color, 0.85 * glow_factor
        ))

        canvas = self._screen_blend(canvas, create_glow_layer(
            max(1, int(font_size * 0.25)), core_color, 0.95 * glow_factor
        ))

        # =================================================================
        # CORE TEXT - Sharp edges for crisp appearance
        # =================================================================

        # Sharp core text (no blur for crisp edges)
        core_opacity = (opacity / 100) * 0.9
        canvas = self._screen_blend(canvas, create_glow_layer(
            0, core_color, core_opacity
        ))

        # =================================================================
        # BRIGHT CENTER HIGHLIGHT - Minimal blur for sharpness
        # =================================================================

        canvas = self._screen_blend(canvas, create_glow_layer(
            max(1, int(font_size * 0.05)), bright_color, 0.5
        ))

        return canvas

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
