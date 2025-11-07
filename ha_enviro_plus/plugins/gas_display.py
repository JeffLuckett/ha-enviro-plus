#!/usr/bin/env python3
"""
Gas Display Plugin

Gas sensor display showing all three gas categories (oxidising, reducing, NH3).
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

from ..display_plugins import DisplayPlugin, register_plugin


@register_plugin
class GasDisplayPlugin(DisplayPlugin):
    """Gas sensor display plugin showing all three gas categories."""

    FONT_SIZE_MEDIUM = 16
    FONT_SIZE_SMALL = 12
    DISPLAY_WIDTH = 160
    DISPLAY_HEIGHT = 80
    ROW_SPACING = 20

    def name(self) -> str:
        """Get the name of this plugin."""
        return "Gas"

    def is_available(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> bool:
        """Check if gas display is available."""
        try:
            return sensors.has_sensor("gas")
        except Exception:
            return False

    def duration(self) -> float:
        """Get display duration."""
        return 5.0

    def render(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> "Image.Image":
        """Render the gas display screen."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not available")

        # Get gas readings
        try:
            oxidising = sensors.gas_oxidising()
            reducing = sensors.gas_reducing()
            nh3 = sensors.gas_nh3()
        except Exception:
            oxidising = None
            reducing = None
            nh3 = None

        # Create image with dark background
        image = Image.new("RGB", (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), color=(20, 20, 40))
        draw = ImageDraw.Draw(image)

        # Load fonts
        font_medium, font_small = self._load_fonts()

        # Draw title
        title = "Gas Sensors"
        bbox_title = draw.textbbox((0, 0), title, font=font_medium)
        title_width = bbox_title[2] - bbox_title[0]
        x_title = (self.DISPLAY_WIDTH - title_width) // 2
        draw.text((x_title, 5), title, font=font_medium, fill=(255, 255, 255))

        # Draw gas readings
        y_start = 25
        y = y_start

        # Oxidising
        if oxidising is not None:
            oxidising_str = f"Ox: {oxidising:.1f} kΩ"
        else:
            oxidising_str = "Ox: ---"
        draw.text((10, y), oxidising_str, font=font_small, fill=(255, 200, 100))
        y += self.ROW_SPACING

        # Reducing
        if reducing is not None:
            reducing_str = f"Red: {reducing:.1f} kΩ"
        else:
            reducing_str = "Red: ---"
        draw.text((10, y), reducing_str, font=font_small, fill=(100, 200, 255))
        y += self.ROW_SPACING

        # NH3
        if nh3 is not None:
            nh3_str = f"NH3: {nh3:.1f} kΩ"
        else:
            nh3_str = "NH3: ---"
        draw.text((10, y), nh3_str, font=font_small, fill=(200, 100, 255))

        return image

    def _load_fonts(
        self,
    ) -> Tuple[Optional["ImageFont.FreeTypeFont"], Optional["ImageFont.FreeTypeFont"]]:
        """Load fonts with fallback."""
        font_paths = self._discover_font_paths()

        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    font_medium = ImageFont.truetype(font_path, self.FONT_SIZE_MEDIUM)
                    font_small = ImageFont.truetype(font_path, self.FONT_SIZE_SMALL)
                    return font_medium, font_small
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
