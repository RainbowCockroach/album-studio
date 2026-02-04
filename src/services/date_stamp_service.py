"""Service for applying vintage-style date stamps to images."""

import os
from datetime import datetime
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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

        # Composite stamp onto image
        result = Image.alpha_composite(image.convert('RGBA'), stamp_image)

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
        assets_dir = get_assets_dir()
        font_path = os.path.join(assets_dir, "fonts", "DSEG7Classic-Regular.ttf")

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

        Layers (bottom to top):
        5. White halo (for dark backgrounds)
        4. Dark outline (for light backgrounds)
        3. Outer glow (orange)
        2. Inner glow (yellow-orange)
        1. Main text (orange)

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

        # Get color settings
        main_color = self.config.get_setting("date_stamp_color", "#FF7700")
        glow_intensity = self.config.get_setting("date_stamp_glow_intensity", 80)
        opacity = self.config.get_setting("date_stamp_opacity", 90)

        # Create transparent canvas
        canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))

        # Get text bounding box
        draw = ImageDraw.Draw(canvas)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Calculate position
        x, y = self._calculate_position(
            width, height,
            text_width, text_height,
            position, margin
        )

        # Layer 5: White halo (for dark backgrounds)
        halo_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        halo_draw = ImageDraw.Draw(halo_layer)
        halo_opacity = int(255 * 0.25)  # 25% opacity
        halo_draw.text((x, y), text, font=font, fill=(255, 255, 204, halo_opacity))
        halo_layer = halo_layer.filter(ImageFilter.GaussianBlur(radius=40))
        canvas = Image.alpha_composite(canvas, halo_layer)

        # Layer 4: Dark outline (for light backgrounds)
        outline_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        outline_draw = ImageDraw.Draw(outline_layer)
        outline_opacity = int(255 * 0.40)  # 40% opacity
        # Draw text slightly offset in all directions for stroke effect
        for offset_x, offset_y in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
            outline_draw.text(
                (x + offset_x, y + offset_y),
                text,
                font=font,
                fill=(34, 17, 0, outline_opacity)  # Dark brown
            )
        canvas = Image.alpha_composite(canvas, outline_layer)

        # Layer 3: Outer glow (orange)
        outer_glow_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        outer_glow_draw = ImageDraw.Draw(outer_glow_layer)
        outer_glow_opacity = int(255 * (glow_intensity / 100) * 0.80)
        outer_glow_draw.text((x, y), text, font=font, fill=(255, 85, 0, outer_glow_opacity))
        outer_glow_layer = outer_glow_layer.filter(ImageFilter.GaussianBlur(radius=20))
        canvas = Image.alpha_composite(canvas, outer_glow_layer)

        # Layer 2: Inner glow (yellow-orange)
        inner_glow_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        inner_glow_draw = ImageDraw.Draw(inner_glow_layer)
        inner_glow_opacity = int(255 * 0.50)
        inner_glow_draw.text((x, y), text, font=font, fill=(255, 204, 0, inner_glow_opacity))
        inner_glow_layer = inner_glow_layer.filter(ImageFilter.GaussianBlur(radius=2))
        canvas = Image.alpha_composite(canvas, inner_glow_layer)

        # Layer 1: Main text (orange)
        main_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        main_draw = ImageDraw.Draw(main_layer)
        main_rgb = self._hex_to_rgb(main_color)
        main_opacity = int(255 * (opacity / 100))
        main_draw.text((x, y), text, font=font, fill=(*main_rgb, main_opacity))
        canvas = Image.alpha_composite(canvas, main_layer)

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
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
