#!/usr/bin/env python3
"""
Sensor Display Plugin

Default sensor display plugin showing time/date, temperature, humidity, and pressure.

This plugin serves as a reference implementation for creating display plugins.
It demonstrates:
- Font loading and discovery
- Icon loading and rendering
- Temperature-based background color gradients
- Sensor value formatting with unit conversion
- Error handling and fallbacks

Example:
    The plugin automatically registers when imported::

        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        plugin = SensorDisplayPlugin()
        if plugin.is_available(sensors, settings):
            image = plugin.render(sensors, settings)
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
from ..display_plugins import (
    DisplayPlugin,
    register_plugin,
    celsius_to_fahrenheit,
    hpa_to_inhg,
)


@register_plugin
class SensorDisplayPlugin(DisplayPlugin):
    """
    Default sensor display plugin showing time/date, temperature, humidity, and pressure.

    This plugin displays:
    - Time and date in a black banner at the top
    - Temperature (left) and humidity (right) on the top row
    - Pressure on the bottom row
    - Temperature-based background color (green for comfort, blue for
      cold, red for hot)

    The plugin automatically handles:
    - Font discovery and loading
    - Icon loading with fallbacks
    - Unit conversion (metric/imperial)
    - Error handling with graceful degradation

    Configuration is done via class constants that can be easily adjusted:
    - Font sizes, spacing, and layout positions
    - Temperature ranges for color gradients
    - Humidity and pressure thresholds for icon selection
    """

    # Display configuration constants
    FONT_SIZE_BANNER = 16  # Date/time font size
    FONT_SIZE_LARGE = 20  # Sensor value font size
    BANNER_HEIGHT = 20  # Height of black banner at top
    BANNER_Y_OFFSET = 3  # Vertical offset for text in banner
    CONTENT_Y_OFFSET = 5  # Vertical spacing from banner to content
    ROW_SPACING = 28  # Vertical spacing between sensor rows

    # Icon configuration
    ICON_SIZE = 28  # Size of icons (matches font size)
    ICON_TEXT_SPACING = 5  # Horizontal spacing between icon and text

    # Layout configuration
    TIME_X = 5  # X position for time in banner
    DATE_X = 70  # X position for date (closer to time to fit year)
    LEFT_COLUMN_X = 5  # X position for left column (temperature, pressure)
    RIGHT_COLUMN_X = 85  # X position for right column (humidity)

    # Temperature ranges (for background color and icon selection)
    TEMP_COMFORT_MIN_C = 18  # Minimum comfort zone temperature (°C)
    TEMP_COMFORT_MAX_C = 24  # Maximum comfort zone temperature (°C)
    TEMP_COMFORT_MIN_F = 65  # Minimum comfort zone temperature (°F)
    TEMP_COMFORT_MAX_F = 75  # Maximum comfort zone temperature (°F)

    # Humidity ranges (for icon selection)
    HUMIDITY_GOOD_MIN = 30  # Minimum good humidity (%)
    HUMIDITY_GOOD_MAX = 60  # Maximum good humidity (%)

    # Pressure ranges (for weather icon selection)
    PRESSURE_STORM_MAX = 1000  # Maximum pressure for storm icon (hPa)
    PRESSURE_RAIN_MAX = 1005  # Maximum pressure for rain icon (hPa)
    PRESSURE_FAIR_MAX = 1025  # Maximum pressure for fair weather icon (hPa)
    # Above PRESSURE_FAIR_MAX = dry weather

    # Display dimensions
    DISPLAY_WIDTH = 160
    DISPLAY_HEIGHT = 80

    def name(self) -> str:
        """Get the name of this plugin."""
        return "Sensor Display"

    def is_available(
        self, sensors: "EnviroPlusSensors", settings: "SettingsManager"
    ) -> bool:
        """
        Check if sensor display is available.

        Requires at least BME280 sensor for temperature/humidity/pressure.

        Args:
            sensors: EnviroPlusSensors instance
            settings: SettingsManager instance

        Returns:
            True if BME280 sensor is available, False otherwise
        """
        try:
            return sensors.has_sensor("bme280")
        except Exception:
            return False

    def duration(self) -> float:
        """
        Get display duration.

        Returns:
            Duration in seconds (0.1 for continuous updates)
        """
        return 0.1  # Update continuously (very short duration)

    def render(
        self, sensors: "EnviroPlusSensors", settings: "SettingsManager"
    ) -> "Image.Image":
        """
        Render the sensor display screen.

        Shows time/date, temperature, humidity, and barometric pressure with
        temperature-based background color and appropriate icons.

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

        units = self._get_units(settings)

        # Get sensor readings
        temp_c, humidity, pressure_hpa = self._read_sensors(sensors)

        # Calculate background color based on temperature
        bg_color = self._calculate_background_color(temp_c, units)

        # Create image with temperature-based background
        image = Image.new(
            "RGB", (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), color=bg_color
        )
        draw = ImageDraw.Draw(image)

        # Draw black banner at top
        self._draw_banner(draw)

        # Load fonts
        font_banner, font_large = self._load_fonts()

        # Draw time and date
        self._draw_time_date(draw, font_banner)

        # Find icon directory
        icon_dir = self._find_icon_directory()

        # Load icons
        icon_temp = self._load_temperature_icon(icon_dir)
        icon_humidity = self._load_humidity_icon(icon_dir, humidity)
        icon_pressure = self._load_pressure_icon(icon_dir, pressure_hpa)

        # Draw sensor values
        content_y = self.BANNER_HEIGHT + self.CONTENT_Y_OFFSET
        self._draw_temperature(
            draw,
            image,
            sensors,
            units,
            temp_c,
            icon_temp,
            font_large,
            content_y,
        )
        self._draw_humidity(
            draw,
            image,
            sensors,
            humidity,
            icon_humidity,
            font_large,
            content_y,
        )
        self._draw_pressure(
            draw,
            image,
            sensors,
            units,
            pressure_hpa,
            icon_pressure,
            font_large,
            content_y,
        )

        return image

    def _get_units(self, settings: "SettingsManager") -> str:
        """Get units setting, defaulting to metric."""
        return (
            settings.get_units()
            if hasattr(settings, "get_units")
            else "metric"
        )

    def _read_sensors(
        self, sensors: "EnviroPlusSensors"
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Read sensor values safely.

        Returns:
            Tuple of (temperature_c, humidity, pressure_hpa) or None for each
            if unavailable
        """
        temp_c = None
        humidity = None
        pressure_hpa = None

        if not sensors.has_sensor("bme280"):
            return temp_c, humidity, pressure_hpa

        try:
            temp_c = sensors.temp()
        except Exception:
            pass

        try:
            humidity = sensors.humidity()
        except Exception:
            pass

        try:
            pressure_hpa = sensors.pressure()
        except Exception:
            pass

        return temp_c, humidity, pressure_hpa

    def _calculate_background_color(
        self, temp_c: Optional[float], units: str
    ) -> Tuple[int, int, int]:
        """
        Calculate background color based on temperature.

        Color scheme:
        - Comfort zone (18-24°C / 65-75°F): Green
        - Below comfort: Cool blue gradient (colder = more blue)
        - Above comfort: Orangey red gradient (hotter = more red)

        Args:
            temp_c: Temperature in Celsius, or None if unavailable
            units: Unit system ("metric" or "imperial")

        Returns:
            RGB tuple (r, g, b) for background color
        """
        if temp_c is None:
            return (255, 140, 0)  # Default orange

        if units == "imperial":
            temp = celsius_to_fahrenheit(temp_c)
            comfort_min = self.TEMP_COMFORT_MIN_F
            comfort_max = self.TEMP_COMFORT_MAX_F
            cold_range_start = 32
            hot_range_end = 90
        else:
            temp = temp_c
            comfort_min = self.TEMP_COMFORT_MIN_C
            comfort_max = self.TEMP_COMFORT_MAX_C
            cold_range_start = 0
            hot_range_end = 35

        # Comfort zone: green
        if comfort_min <= temp <= comfort_max:
            return (34, 139, 34)  # Forest green

        # Below comfort: cool blue gradient
        if temp < comfort_min:
            ratio = max(
                0,
                min(
                    1,
                    (temp - cold_range_start)
                    / (comfort_min - cold_range_start),
                ),
            )
            return (
                int(25 + ratio * 50),  # R: 25-75
                int(100 + ratio * 50),  # G: 100-150
                int(200 + ratio * 55),  # B: 200-255
            )

        # Above comfort: orangey red gradient
        ratio = max(
            0, min(1, (temp - comfort_max) / (hot_range_end - comfort_max))
        )
        return (
            int(255 - ratio * 30),  # R: 255-225
            int(140 - ratio * 40),  # G: 140-100
            0,  # B: 0
        )

    def _draw_banner(self, draw: "ImageDraw.ImageDraw") -> None:
        """Draw black banner at top of display."""
        draw.rectangle(
            [(0, 0), (self.DISPLAY_WIDTH, self.BANNER_HEIGHT)], fill=(0, 0, 0)
        )

    def _load_fonts(
        self,
    ) -> Tuple[
        Optional["ImageFont.FreeTypeFont"], Optional["ImageFont.FreeTypeFont"]
    ]:
        """
        Load fonts with fallback to default font.

        Attempts to find and load DejaVu fonts using fontconfig and find
        commands.
        Falls back to default bitmap font if truetype fonts are unavailable.

        Returns:
            Tuple of (font_banner, font_large) or (None, None) if loading fails
        """
        font_paths = self._discover_font_paths()

        # Try to load fonts from discovered paths
        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    self.logger.debug("Loading font from: %s", font_path)
                    # Test if font can be loaded
                    ImageFont.truetype(font_path, 12)
                    # Load actual sizes
                    font_banner = ImageFont.truetype(
                        font_path, self.FONT_SIZE_BANNER
                    )
                    font_large = ImageFont.truetype(
                        font_path, self.FONT_SIZE_LARGE
                    )
                    self.logger.info(
                        "Loaded font from %s (banner: %dpt, large: %dpt)",
                        font_path,
                        self.FONT_SIZE_BANNER,
                        self.FONT_SIZE_LARGE,
                    )
                    return font_banner, font_large
            except (OSError, IOError) as e:
                self.logger.debug(
                    "Failed to load font from %s: %s", font_path, e
                )
                continue

        # Fallback to default font
        self.logger.warning(
            "Failed to load truetype fonts, using default bitmap font"
        )
        try:
            default_font = ImageFont.load_default()
            return default_font, default_font
        except Exception as e:
            self.logger.error("Failed to load any font: %s", e)
            return None, None

    def _discover_font_paths(self) -> List[str]:
        """
        Discover font file paths using fontconfig and find commands.

        Returns:
            List of font file paths, with Bold fonts prioritized
        """
        font_paths = []

        # Try fontconfig (fc-list)
        font_paths.extend(self._find_fonts_with_fc_list())

        # Add common hardcoded paths
        font_paths.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]
        )

        # Try find command
        font_paths.extend(self._find_fonts_with_find())

        # Remove duplicates while preserving order
        seen = set()
        unique_paths = []
        for path in font_paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)

        self.logger.debug("Discovered %d font paths", len(unique_paths))
        return unique_paths

    def _find_fonts_with_fc_list(self) -> List[str]:
        """Find fonts using fontconfig fc-list command."""
        font_paths = []

        for fc_cmd in [
            ["fc-list", ":family=DejaVu", "file"],
            ["fc-list", "DejaVu", "file"],
            ["fc-list", "DejaVu"],
        ]:
            try:
                result = subprocess.run(
                    fc_cmd, capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0 and result.stdout:
                    for line in result.stdout.strip().split("\n"):
                        line = line.strip()
                        if line and "DejaVu" in line and ":" in line:
                            file_path = line.split(":")[0].strip()
                            if file_path and os.path.exists(file_path):
                                if "Bold" in line or "bold" in line.lower():
                                    font_paths.append(file_path)
                                elif ".ttf" in file_path.lower():
                                    if file_path not in font_paths:
                                        font_paths.append(file_path)
                    if font_paths:
                        break
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                continue

        return font_paths

    def _find_fonts_with_find(self) -> List[str]:
        """Find fonts using find command."""
        font_paths = []

        for find_pattern in [
            [
                "find",
                "/usr/share/fonts",
                "-name",
                "*DejaVu*Bold*.ttf",
                "-type",
                "f",
            ],
            [
                "find",
                "/usr/share/fonts",
                "-name",
                "*DejaVu*.ttf",
                "-type",
                "f",
            ],
            [
                "find",
                "/usr/share/fonts",
                "-name",
                "DejaVuSans-Bold.ttf",
                "-type",
                "f",
            ],
        ]:
            try:
                result = subprocess.run(
                    find_pattern,
                    capture_output=True,
                    text=True,
                    timeout=3,
                    shell=False,
                )
                if result.returncode == 0 and result.stdout:
                    for line in result.stdout.strip().split("\n"):
                        line = line.strip()
                        if line and os.path.exists(line):
                            if "Bold" in line:
                                if line not in font_paths:
                                    font_paths.insert(
                                        0, line
                                    )  # Prefer Bold fonts
                            elif ".ttf" in line.lower():
                                if line not in font_paths:
                                    font_paths.append(line)
                    if font_paths:
                        break
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                continue

        return font_paths

    def _draw_time_date(
        self,
        draw: "ImageDraw.ImageDraw",
        font: Optional["ImageFont.FreeTypeFont"],
    ) -> None:
        """Draw time and date in the banner."""
        now = datetime.now()
        time_str = now.strftime("%I:%M")  # 12h format without seconds
        if time_str.startswith("0"):
            time_str = time_str[1:]  # Remove leading zero
        date_str = now.strftime("%d %b %y")  # e.g., "15 Nov 19"

        draw.text(
            (self.TIME_X, self.BANNER_Y_OFFSET),
            time_str,
            font=font,
            fill=(255, 255, 255),
        )
        draw.text(
            (self.DATE_X, self.BANNER_Y_OFFSET),
            date_str,
            font=font,
            fill=(255, 255, 255),
        )

    def _find_icon_directory(self) -> Optional[str]:
        """
        Find icon directory by checking multiple locations.

        Checks in order:
        1. Repository icons/ directory (for development)
        2. Installed location /opt/ha-enviro-plus/icons/
        3. Other system locations

        Returns:
            Path to icon directory, or None if not found
        """
        icon_paths = []

        # Try to find package directory (for development/testing)
        try:
            import ha_enviro_plus

            package_dir = os.path.dirname(
                os.path.dirname(os.path.abspath(ha_enviro_plus.__file__))
            )
            repo_icons = os.path.join(package_dir, "icons")
            if os.path.isdir(repo_icons):
                icon_paths.append(repo_icons)
        except Exception:
            pass

        # Add installed locations
        icon_paths.extend(
            [
                "/opt/ha-enviro-plus/icons",
                "/usr/local/lib/python3.*/site-packages/enviroplus/icons",
                "/opt/enviroplus-python/examples/icons",
                "~/.local/lib/python3.*/site-packages/enviroplus/icons",
            ]
        )

        # Try to find icon directory
        for pattern in icon_paths:
            expanded = os.path.expanduser(pattern)
            matches = glob.glob(expanded)
            if matches:
                return matches[0]

        return None

    def _load_temperature_icon(
        self, icon_dir: Optional[str]
    ) -> Optional["Image.Image"]:
        """Load temperature icon from icon directory."""
        if not icon_dir:
            return None

        try:
            icon_path = os.path.join(icon_dir, "icon_temperature.png")
            if os.path.exists(icon_path):
                return Image.open(icon_path).convert("RGBA")

            # Fallback to temperature.png
            fallback_path = os.path.join(icon_dir, "temperature.png")
            if os.path.exists(fallback_path):
                return Image.open(fallback_path).convert("RGBA")
        except Exception:
            pass

        return None

    def _load_humidity_icon(
        self, icon_dir: Optional[str], humidity: Optional[float]
    ) -> Optional["Image.Image"]:
        """Load humidity icon based on humidity reading."""
        if not icon_dir or humidity is None:
            return None

        try:
            # Select icon based on humidity range
            if self.HUMIDITY_GOOD_MIN <= humidity <= self.HUMIDITY_GOOD_MAX:
                icon_name = "humidity-good.png"
            else:
                icon_name = "humidity-bad.png"

            icon_path = os.path.join(icon_dir, icon_name)
            if os.path.exists(icon_path):
                return Image.open(icon_path).convert("RGBA")

            # Fallback to generic humidity icon
            fallback_path = os.path.join(icon_dir, "icon_humidity.png")
            if os.path.exists(fallback_path):
                return Image.open(fallback_path).convert("RGBA")
        except Exception:
            pass

        return None

    def _load_pressure_icon(
        self, icon_dir: Optional[str], pressure_hpa: Optional[float]
    ) -> Optional["Image.Image"]:
        """
        Load pressure icon based on pressure reading.

        Icon selection based on pressure ranges:
        - < 1000 hPa: storm
        - 1000-1005 hPa: rain
        - 1005-1025 hPa: fair
        - > 1025 hPa: dry
        """
        if not icon_dir or pressure_hpa is None:
            return None

        try:
            # Select icon based on pressure range
            if pressure_hpa < self.PRESSURE_STORM_MAX:
                icon_name = "weather-storm.png"
            elif pressure_hpa < self.PRESSURE_RAIN_MAX:
                icon_name = "weather-rain.png"
            elif pressure_hpa <= self.PRESSURE_FAIR_MAX:
                icon_name = "weather-fair.png"
            else:
                icon_name = "weather-dry.png"

            icon_path = os.path.join(icon_dir, icon_name)
            if os.path.exists(icon_path):
                return Image.open(icon_path).convert("RGBA")

            # Fallback to generic pressure icon
            fallback_path = os.path.join(icon_dir, "icon_pressure.png")
            if os.path.exists(fallback_path):
                return Image.open(fallback_path).convert("RGBA")
        except Exception:
            pass

        return None

    def _draw_icon_and_text(
        self,
        image: "Image.Image",
        draw: "ImageDraw.ImageDraw",
        icon: Optional["Image.Image"],
        text: str,
        x: int,
        y: int,
        font: Optional["ImageFont.FreeTypeFont"],
        fallback_char: str = "?",
    ) -> None:
        """
        Draw icon and text at specified position.

        If icon is available, draws it and positions text next to it.
        Otherwise, draws fallback character and text.

        Args:
            image: PIL Image to draw on
            draw: ImageDraw instance
            icon: Optional icon image (RGBA)
            text: Text to display
            x: X position
            y: Y position
            font: Font to use for text
            fallback_char: Character to use if icon is unavailable
        """
        text_x = x
        if icon:
            # Resize and paste icon
            icon_resized = icon.resize(
                (self.ICON_SIZE, self.ICON_SIZE), Image.Resampling.LANCZOS
            )
            image.paste(icon_resized, (x, y), icon_resized)
            text_x = x + self.ICON_SIZE + self.ICON_TEXT_SPACING
        else:
            # Draw fallback character
            draw.text((x, y), fallback_char, font=font, fill=(255, 255, 255))

        # Draw text
        draw.text((text_x, y), text, font=font, fill=(255, 255, 255))

    def _draw_temperature(
        self,
        draw: "ImageDraw.ImageDraw",
        image: "Image.Image",
        sensors: "EnviroPlusSensors",
        units: str,
        temp_c: Optional[float],
        icon: Optional["Image.Image"],
        font: Optional["ImageFont.FreeTypeFont"],
        y: int,
    ) -> None:
        """Draw temperature reading with icon."""
        if not sensors.has_sensor("bme280"):
            return

        try:
            if temp_c is None:
                temp_c = sensors.temp()

            if units == "imperial":
                temp_value = celsius_to_fahrenheit(temp_c)
                temp_str = f"{temp_value:.0f}°F"
            else:
                temp_str = f"{temp_c:.0f}°C"

            self._draw_icon_and_text(
                image,
                draw,
                icon,
                temp_str,
                self.LEFT_COLUMN_X,
                y,
                font,
                fallback_char="T",
            )
        except Exception as e:
            self.logger.warning("Failed to read temperature: %s", e)
            draw.text(
                (self.LEFT_COLUMN_X, y),
                "T --",
                font=font,
                fill=(255, 255, 255),
            )

    def _draw_humidity(
        self,
        draw: "ImageDraw.ImageDraw",
        image: "Image.Image",
        sensors: "EnviroPlusSensors",
        humidity: Optional[float],
        icon: Optional["Image.Image"],
        font: Optional["ImageFont.FreeTypeFont"],
        y: int,
    ) -> None:
        """Draw humidity reading with icon."""
        if not sensors.has_sensor("bme280"):
            return

        try:
            if humidity is None:
                humidity = sensors.humidity()

            hum_str = f"{humidity:.0f}%"
            self._draw_icon_and_text(
                image,
                draw,
                icon,
                hum_str,
                self.RIGHT_COLUMN_X,
                y,
                font,
                fallback_char="H",
            )
        except Exception as e:
            self.logger.warning("Failed to read humidity: %s", e)
            draw.text(
                (self.RIGHT_COLUMN_X, y),
                "H --%",
                font=font,
                fill=(255, 255, 255),
            )

    def _draw_pressure(
        self,
        draw: "ImageDraw.ImageDraw",
        image: "Image.Image",
        sensors: "EnviroPlusSensors",
        units: str,
        pressure_hpa: Optional[float],
        icon: Optional["Image.Image"],
        font: Optional["ImageFont.FreeTypeFont"],
        y: int,
    ) -> None:
        """Draw pressure reading with icon."""
        if not sensors.has_sensor("bme280"):
            return

        try:
            if pressure_hpa is None:
                pressure_hpa = sensors.pressure()

            if units == "imperial":
                pressure_value = hpa_to_inhg(pressure_hpa)
                pressure_str = f"{pressure_value:.1f} inHg"
            else:
                pressure_str = f"{pressure_hpa:.0f} hPa"

            y_pressure = y + self.ROW_SPACING
            self._draw_icon_and_text(
                image,
                draw,
                icon,
                pressure_str,
                self.LEFT_COLUMN_X,
                y_pressure,
                font,
                fallback_char="P",
            )
        except Exception as e:
            self.logger.warning("Failed to read pressure: %s", e)
            draw.text(
                (self.LEFT_COLUMN_X, y + self.ROW_SPACING),
                "P --",
                font=font,
                fill=(255, 255, 255),
            )
