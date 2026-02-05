"""Service for applying vintage-style date stamps to images."""

import os
import math
from datetime import datetime
from typing import List, Optional, Tuple, Union, cast
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


def generate_temperature_gradient(
    temp_outer: int,
    temp_core: int,
    num_steps: int = 9
) -> List[Tuple[int, int, int]]:
    """
    Generate a color gradient based on color temperature range.

    Args:
        temp_outer: Temperature for outer glow (warmest, e.g., 1800K)
        temp_core: Temperature for core text (hottest, e.g., 6500K)
        num_steps: Number of colors in the gradient

    Returns:
        List of RGB tuples from outer (warm) to core (hot)
    """
    gradient = []
    for i in range(num_steps):
        # Interpolate temperature from outer to core
        t = i / (num_steps - 1) if num_steps > 1 else 1.0
        temp = temp_outer + (temp_core - temp_outer) * t
        gradient.append(kelvin_to_rgb(int(temp)))
    return gradient


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
        margin = cast(int, self.config.get_setting("date_stamp_margin", 30))

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
        physical_height = cast(float, self.config.get_setting("date_stamp_physical_height", 0.2))
        pixels_per_unit = cast(int, self.config.get_setting("date_stamp_target_dpi", 300))

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
        Create multi-layer date stamp with physics-based warm-edge glow effect.

        Uses a blackbody-inspired color temperature gradient:
        - Outer edges: Cooler temperature = warmer/redder colors (subsurface scattering)
        - Inner core: Hotter temperature = brighter/yellower colors (light emission)

        The outer layers use Linear Dodge (Add) blend mode for saturated edges,
        while inner layers use Screen blend for light projection effect.

        This accurately simulates how light passing through film substrate
        creates warm-shifted edges due to scattering and absorption.

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
        glow_intensity = cast(int, self.config.get_setting("date_stamp_glow_intensity", 80) or 80)
        opacity = cast(int, self.config.get_setting("date_stamp_opacity", 90) or 90)
        temp_outer = cast(int, self.config.get_setting("date_stamp_temp_outer", 1800) or 1800)
        temp_core = cast(int, self.config.get_setting("date_stamp_temp_core", 6500) or 6500)

        # Generate color gradient from temperature range
        gradient = generate_temperature_gradient(temp_outer, temp_core, num_steps=9)

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
        font_size = getattr(font, 'size', text_height)

        # =================================================================
        # LAYER DEFINITION: Physics-based color temperature gradient
        # Each layer has: (blur_multiplier, gradient_position, alpha, use_linear_dodge)
        #
        # gradient_position: 0.0 = outermost (warmest, temp_outer)
        #                    1.0 = core (hottest, temp_core)
        #
        # Outer layers use Linear Dodge for saturated warm edges
        # Inner layers use Screen for light projection
        # =================================================================

        layers = [
            # OUTER GLOW - Linear Dodge for saturated warm edges
            # These create the characteristic warm bleed at the transition zone
            (6.0, 0.0, 0.20, True),   # Extreme outer - warmest
            (5.0, 0.1, 0.25, True),   # Very wide
            (4.0, 0.2, 0.30, True),   # Wide
            (3.5, 0.3, 0.35, True),   # Medium-wide - transitioning

            # TRANSITION ZONE - Switch to Screen, colors getting hotter
            (3.0, 0.4, 0.40, False),  # Medium
            (2.5, 0.5, 0.50, False),  # Medium-inner
            (2.0, 0.55, 0.55, False), # Inner-wide

            # INNER GLOW - Screen mode, building brightness
            (1.5, 0.65, 0.60, False), # Inner
            (1.0, 0.75, 0.70, False), # Close
            (0.5, 0.85, 0.80, False), # Near
            (0.25, 0.92, 0.85, False),# Very near

            # CORE - Sharp text with hottest color
            (0.0, 0.95, 0.90, False), # Core text - bright
            (0.05, 1.0, 0.50, False), # Highlight - hottest center
        ]

        def create_glow_layer(
            blur_radius: int,
            color_rgb: Tuple[int, int, int],
            alpha_multiplier: float
        ) -> Image.Image:
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

        # Build each layer with temperature-based color and appropriate blend mode
        for blur_mult, grad_pos, alpha, use_linear_dodge in layers:
            # Calculate blur radius from multiplier
            blur_radius = int(font_size * blur_mult) if blur_mult > 0 else 0
            blur_radius = max(blur_radius, 1) if blur_mult > 0 else 0

            # Get color from temperature gradient
            color = self._get_gradient_color(gradient, grad_pos)

            # Calculate final alpha with glow intensity
            final_alpha = alpha * glow_factor

            # Apply opacity setting to core layers (last two)
            if blur_mult <= 0.05:
                final_alpha *= (opacity / 100.0)

            # Create the layer
            layer = create_glow_layer(blur_radius, color, final_alpha)

            # Blend using appropriate mode
            if use_linear_dodge:
                # Linear Dodge for outer layers - creates saturated warm edges
                canvas = self._linear_dodge_blend(canvas, layer)
            else:
                # Screen for inner layers - light projection effect
                canvas = self._screen_blend(canvas, layer)

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

    @staticmethod
    def _linear_dodge_blend(base: Image.Image, overlay: Image.Image) -> Image.Image:
        """
        Blend overlay onto base using Linear Dodge (Add) blend mode.

        Linear Dodge simply adds the pixel values, creating intense, saturated
        glow effects at edges. This produces more saturated colors than Screen
        mode, making glows appear "hotter" and more luminous.

        Formula: Result = A + B (clamped to 1.0)

        This is ideal for outer glow layers where we want that characteristic
        saturated warm edge that real light emissions have.

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

        # Linear Dodge (Add) formula: A + B
        # This creates intense, saturated edges - key for "hot" glow look
        added_rgb = base_rgb + overlay_rgb

        # Blend added result with base using overlay's alpha
        result_rgb = base_rgb * (1.0 - overlay_alpha) + added_rgb * overlay_alpha

        # Clamp to valid range (addition can exceed 1.0)
        result_rgb = np.clip(result_rgb, 0.0, 1.0)

        # Combine alpha channels (standard alpha compositing)
        result_alpha = base_alpha + overlay_alpha * (1.0 - base_alpha)

        # Combine RGB and alpha
        result = np.concatenate([result_rgb, result_alpha], axis=2)

        # Convert back to 8-bit and create PIL image
        result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
        return Image.fromarray(result, mode='RGBA')

    @staticmethod
    def _get_gradient_color(
        gradient: List[Tuple[int, int, int]],
        position: float
    ) -> Tuple[int, int, int]:
        """
        Interpolate a color from a gradient based on position.

        Args:
            gradient: List of RGB tuples representing the gradient
            position: Position in gradient, 0.0 = first color, 1.0 = last color

        Returns:
            Interpolated RGB tuple
        """
        if position <= 0.0:
            return gradient[0]
        if position >= 1.0:
            return gradient[-1]

        # Find the two colors to interpolate between
        num_colors = len(gradient)
        scaled_pos = position * (num_colors - 1)
        lower_idx = int(scaled_pos)
        upper_idx = min(lower_idx + 1, num_colors - 1)
        t = scaled_pos - lower_idx  # Interpolation factor

        # Linear interpolation between the two colors
        c1 = gradient[lower_idx]
        c2 = gradient[upper_idx]

        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )
