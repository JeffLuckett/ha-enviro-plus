#!/usr/bin/env python3
"""
Temperature Display Plugin

Individual temperature sensor display showing large temperature reading with unit conversion.
"""

import os
import glob
import subprocess
from typing import TYPE_CHECKING, Optional, Tuple, List

if TYPE_CHECKING:
    from PIL import Image, ImageDraw, ImageFont
    from ..sensors import EnviroPlusSensors
    from ..settings import SettingsManager

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from datetime import datetime
from ..display_plugins import DisplayPlugin, register_plugin, celsius_to_fahrenheit


@register_plugin
class TemperatureDisplayPlugin(DisplayPlugin):
    """Temperature-only display plugin showing large temperature reading."""

    FONT_SIZE_LARGE = 32
    FONT_SIZE_SMALL = 14
    DISPLAY_WIDTH = 160
    DISPLAY_HEIGHT = 80

    def name(self) -> str:
        """Get the name of this plugin."""
        return "Temperature"

    def is_available(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> bool:
        """Check if temperature display is available."""
        try:
            return sensors.has_sensor("bme280")
        except Exception:
            return False

    def duration(self) -> float:
        """Get display duration."""
        return 5.0  # Show for 5 seconds

    def render(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> "Image.Image":
        """Render the temperature display screen."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not available")

        units = settings.get_units() if hasattr(settings, "get_units") else "metric"

        # Get temperature reading
        try:
            temp_c = sensors.temp()
        except Exception:
            temp_c = None

        # Calculate background color based on temperature
        bg_color = self._calculate_background_color(temp_c, units)

        # Create image
        image = Image.new("RGB", (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), color=bg_color)
        draw = ImageDraw.Draw(image)

        # Load fonts
        font_large, font_small = self._load_fonts()

        # Format temperature value
        if temp_c is not None:
            if units == "imperial":
                temp_value = celsius_to_fahrenheit(temp_c)
                temp_str = f"{temp_value:.0f}°F"
            else:
                temp_str = f"{temp_c:.1f}°C"
        else:
            temp_str = "---"

        # Draw temperature (centered)
        bbox = draw.textbbox((0, 0), temp_str, font=font_large)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (self.DISPLAY_WIDTH - text_width) // 2
        y = (self.DISPLAY_HEIGHT - text_height) // 2 - 10

        draw.text((x, y), temp_str, font=font_large, fill=(255, 255, 255))

        # Draw label
        label = "Temperature"
        bbox_label = draw.textbbox((0, 0), label, font=font_small)
        label_width = bbox_label[2] - bbox_label[0]
        x_label = (self.DISPLAY_WIDTH - label_width) // 2
        y_label = y + text_height + 5

        draw.text((x_label, y_label), label, font=font_small, fill=(255, 255, 255))

        return image

    def _calculate_background_color(
        self, temp_c: Optional[float], units: str
    ) -> Tuple[int, int, int]:
        """Calculate background color based on temperature."""
        if temp_c is None:
            return (128, 128, 128)  # Gray

        if units == "imperial":
            temp = celsius_to_fahrenheit(temp_c)
            comfort_min = 65
            comfort_max = 75
        else:
            temp = temp_c
            comfort_min = 18
            comfort_max = 24

        # Comfort zone: green
        if comfort_min <= temp <= comfort_max:
            return (34, 139, 34)  # Forest green

        # Below comfort: cool blue
        if temp < comfort_min:
            return (25, 100, 200)  # Cool blue

        # Above comfort: warm red
        return (255, 140, 0)  # Orange-red

    def _load_fonts(
        self,
    ) -> Tuple[Optional["ImageFont.FreeTypeFont"], Optional["ImageFont.FreeTypeFont"]]:
        """Load fonts with fallback."""
        font_paths = self._discover_font_paths()

        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    font_large = ImageFont.truetype(font_path, self.FONT_SIZE_LARGE)
                    font_small = ImageFont.truetype(font_path, self.FONT_SIZE_SMALL)
                    return font_large, font_small
            except (OSError, IOError):
                continue

        # Fallback to default font
        try:
            default_font = ImageFont.load_default()
            return default_font, default_font
        except Exception:
            return None, None

    def _discover_font_paths(self) -> List[str]:
        """Discover font file paths."""
        font_paths = []

        # Try fontconfig
        for fc_cmd in [
            ["fc-list", ":family=DejaVu", "file"],
            ["fc-list", "DejaVu"],
        ]:
            try:
                result = subprocess.run(fc_cmd, capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and result.stdout:
                    for line in result.stdout.strip().split("\n"):
                        if ":" in line:
                            file_path = line.split(":")[0].strip()
                            if file_path and os.path.exists(file_path):
                                font_paths.append(file_path)
                    if font_paths:
                        break
            except Exception:
                continue

        # Add common paths
        font_paths.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
        )

        # Remove duplicates
        seen = set()
        unique_paths = []
        for path in font_paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)

        return unique_paths
