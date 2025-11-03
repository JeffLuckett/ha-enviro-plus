#!/usr/bin/env python3
"""
Hello Enviro - A simple example display plugin

This plugin demonstrates how to create a basic display plugin
that shows a greeting message.

This serves as a template for creating your own display plugins.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image
    from ..sensors import EnviroPlusSensors
    from ..settings import SettingsManager

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Note: This plugin is NOT registered by default - it's just an example
# To enable it, uncomment the @register_plugin decorator below

# Import from the base plugin system
from ha_enviro_plus.display_plugins import DisplayPlugin

# from ha_enviro_plus.display_plugins import register_plugin


# @register_plugin  # Uncomment to enable this plugin
class HelloEnviroPlugin(DisplayPlugin):
    """
    A simple "Hello Enviro" display plugin.

    This plugin serves as a template for creating your own display plugins.
    """

    def name(self) -> str:
        """Get the name of this plugin."""
        return "Hello Enviro"

    def is_available(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> bool:
        """
        Check if this plugin can be displayed.

        This plugin is always available (no sensor requirements).

        Args:
            sensors: EnviroPlusSensors instance
            settings: SettingsManager instance

        Returns:
            True (always available)
        """
        return True

    def duration(self) -> float:
        """Get display duration in seconds."""
        return 3.0  # Show for 3 seconds

    def render(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> "Image.Image":
        """
        Render the display screen.

        Creates a simple "Hello Enviro" message with a decorative icon.

        Args:
            sensors: EnviroPlusSensors instance
            settings: SettingsManager instance

        Returns:
            PIL Image object (160x80) representing the display

        Raises:
            RuntimeError: If PIL/Pillow is not available
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not available")

        # Create image (160x80 for ST7735 display)
        image = Image.new("RGB", (160, 80), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Try to load a font, fallback to default if unavailable
        try:
            font_path_large = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_path_small = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            font_large = ImageFont.truetype(font_path_large, 16)
            font_small = ImageFont.truetype(font_path_small, 12)
        except (OSError, IOError):
            # Fallback to default font
            try:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            except Exception:
                font_large = None
                font_small = None

        # Draw "Hello Enviro" message
        # Center the text
        message = "Hello Enviro!"
        y_pos = 20

        # Draw with icon
        draw.text((10, y_pos), "👋", font=font_large, fill=(255, 255, 255))
        draw.text((30, y_pos), message, font=font_large, fill=(255, 255, 255))

        # Draw subtitle
        subtitle = "Custom Display"
        y_pos += 30
        draw.text((10, y_pos), subtitle, font=font_small, fill=(200, 200, 200))

        return image
