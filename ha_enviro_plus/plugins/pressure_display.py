#!/usr/bin/env python3
"""
Pressure Display Plugin

Individual barometric pressure sensor display showing large pressure reading.
"""

import os
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

from ..display_plugins import DisplayPlugin, register_plugin, hpa_to_inhg


@register_plugin
class PressureDisplayPlugin(DisplayPlugin):
    """Pressure-only display plugin showing large pressure reading."""

    FONT_SIZE_LARGE = 28
    FONT_SIZE_SMALL = 14
    DISPLAY_WIDTH = 160
    DISPLAY_HEIGHT = 80

    def name(self) -> str:
        """Get the name of this plugin."""
        return "Pressure"

    def is_available(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> bool:
        """Check if pressure display is available."""
        try:
            return sensors.has_sensor("bme280")
        except Exception:
            return False

    def duration(self) -> float:
        """Get display duration."""
        return 5.0

    def render(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> "Image.Image":
        """Render the pressure display screen."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not available")

        units = settings.get_units() if hasattr(settings, "get_units") else "metric"

        # Get pressure reading
        try:
            pressure_hpa = sensors.pressure()
        except Exception:
            pressure_hpa = None

        # Calculate background color based on pressure
        bg_color = self._calculate_background_color(pressure_hpa)

        # Create image
        image = Image.new("RGB", (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), color=bg_color)
        draw = ImageDraw.Draw(image)

        # Load fonts
        font_large, font_small = self._load_fonts()

        # Format pressure value
        if pressure_hpa is not None:
            if units == "imperial":
                pressure_value = hpa_to_inhg(pressure_hpa)
                pressure_str = f"{pressure_value:.2f} inHg"
            else:
                pressure_str = f"{pressure_hpa:.2f} hPa"
        else:
            pressure_str = "---"

        # Draw pressure (centered)
        bbox = draw.textbbox((0, 0), pressure_str, font=font_large)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (self.DISPLAY_WIDTH - text_width) // 2
        y = (self.DISPLAY_HEIGHT - text_height) // 2 - 10

        draw.text((x, y), pressure_str, font=font_large, fill=(255, 255, 255))

        # Draw label
        label = "Pressure"
        bbox_label = draw.textbbox((0, 0), label, font=font_small)
        label_width = bbox_label[2] - bbox_label[0]
        x_label = (self.DISPLAY_WIDTH - label_width) // 2
        y_label = y + text_height + 5

        draw.text((x_label, y_label), label, font=font_small, fill=(255, 255, 255))

        return image

    def _calculate_background_color(self, pressure_hpa: Optional[float]) -> Tuple[int, int, int]:
        """Calculate background color based on pressure."""
        if pressure_hpa is None:
            return (128, 128, 128)  # Gray

        # Pressure ranges for weather indication
        if pressure_hpa < 1000:
            return (100, 50, 150)  # Purple (storm)
        elif pressure_hpa < 1005:
            return (50, 100, 200)  # Blue (rain)
        elif pressure_hpa <= 1025:
            return (100, 200, 100)  # Green (fair)
        else:
            return (200, 150, 50)  # Orange (dry)

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

        try:
            default_font = ImageFont.load_default()
            return default_font, default_font
        except Exception:
            return None, None

    def _discover_font_paths(self) -> List[str]:
        """Discover font file paths."""
        font_paths = []

        for fc_cmd in [["fc-list", ":family=DejaVu", "file"], ["fc-list", "DejaVu"]]:
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

        font_paths.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
        )

        seen = set()
        unique_paths = []
        for path in font_paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)

        return unique_paths
