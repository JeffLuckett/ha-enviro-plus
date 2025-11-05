#!/usr/bin/env python3
"""
Sensor Display Plugin

Default sensor display plugin showing time/date, temperature, humidity, and pressure.
This serves as an example of how to implement display plugins.
"""

import logging
import os
import glob
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

    This serves as an example of how to implement display plugins.
    """

    # Display configuration constants
    FONT_SIZE_BANNER = 32  # Date/time font size
    FONT_SIZE_LARGE = 64  # Sensor value font size
    BANNER_HEIGHT = 20  # Height of black banner at top
    BANNER_Y_OFFSET = 3  # Vertical offset for text in banner
    CONTENT_Y_OFFSET = 5  # Vertical spacing from banner to content
    ROW_SPACING = 28  # Vertical spacing between sensor rows

    # Icon configuration
    ICON_SIZE = 28  # Size of icons (matches font size)
    ICON_TEXT_SPACING = 5  # Horizontal spacing between icon and text

    # Layout configuration
    TIME_X = 5  # X position for time in banner
    DATE_X = 100  # X position for date in banner
    LEFT_COLUMN_X = 5  # X position for left column (temperature, humidity)
    RIGHT_COLUMN_X = 85  # X position for right column (pressure)

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

    def name(self) -> str:
        """Get the name of this plugin."""
        return "Sensor Display"

    def is_available(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> bool:
        """
        Check if sensor display is available.

        Requires at least BME280 sensor for temperature/humidity/pressure.
        """
        try:
            return sensors.has_sensor("bme280")
        except Exception:
            return False

    def duration(self) -> float:
        """Get display duration."""
        return 0.1  # Update continuously (very short duration)

    def render(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> "Image.Image":
        """
        Render the sensor display screen.

        Shows time/date, temperature, humidity, and barometric pressure.
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not available")

        # Get units setting
        units = settings.get_units() if hasattr(settings, "get_units") else "metric"

        # Get sensor readings first to calculate background color and determine icons
        temp_c = None
        humidity = None
        pressure_hpa = None
        if sensors.has_sensor("bme280"):
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

        # Calculate background color based on temperature
        # Comfort zone: green, below = cool blue, above = orangey red
        if temp_c is not None:
            if units == "imperial":
                temp_f = celsius_to_fahrenheit(temp_c)
                # Comfort zone
                if self.TEMP_COMFORT_MIN_F <= temp_f <= self.TEMP_COMFORT_MAX_F:
                    # Green for comfort zone
                    bg_color = (34, 139, 34)  # Forest green
                elif temp_f < self.TEMP_COMFORT_MIN_F:
                    # Cool blue (colder = more blue)
                    ratio = max(0, min(1, (temp_f - 32) / (self.TEMP_COMFORT_MIN_F - 32)))
                    bg_color = (
                        int(25 + ratio * 50),  # R: 25-75
                        int(100 + ratio * 50),  # G: 100-150
                        int(200 + ratio * 55),  # B: 200-255
                    )
                else:
                    # Orangey red (hotter = more red)
                    ratio = max(0, min(1, (temp_f - self.TEMP_COMFORT_MAX_F) / (90 - self.TEMP_COMFORT_MAX_F)))
                    bg_color = (
                        int(255 - ratio * 30),  # R: 255-225
                        int(140 - ratio * 40),  # G: 140-100
                        int(0),  # B: 0
                    )
            else:
                # Comfort zone
                if self.TEMP_COMFORT_MIN_C <= temp_c <= self.TEMP_COMFORT_MAX_C:
                    # Green for comfort zone
                    bg_color = (34, 139, 34)  # Forest green
                elif temp_c < self.TEMP_COMFORT_MIN_C:
                    # Cool blue (colder = more blue)
                    ratio = max(0, min(1, (temp_c - 0) / (self.TEMP_COMFORT_MIN_C - 0)))
                    bg_color = (
                        int(25 + ratio * 50),  # R: 25-75
                        int(100 + ratio * 50),  # G: 100-150
                        int(200 + ratio * 55),  # B: 200-255
                    )
                else:
                    # Orangey red (hotter = more red)
                    ratio = max(0, min(1, (temp_c - self.TEMP_COMFORT_MAX_C) / (35 - self.TEMP_COMFORT_MAX_C)))
                    bg_color = (
                        int(255 - ratio * 30),  # R: 255-225
                        int(140 - ratio * 40),  # G: 140-100
                        int(0),  # B: 0
                    )
        else:
            # Default orange background if no temperature
            bg_color = (255, 140, 0)  # Orange

        # Create image with temperature-based background
        image = Image.new("RGB", (160, 80), color=bg_color)
        draw = ImageDraw.Draw(image)

        # Black banner at top for time/date
        draw.rectangle([(0, 0), (160, self.BANNER_HEIGHT)], fill=(0, 0, 0))

        # Try to load fonts - much larger fonts to match icon size and be easily readable
        try:
            font_path_banner = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_path_large = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_banner = ImageFont.truetype(font_path_banner, self.FONT_SIZE_BANNER)
            font_large = ImageFont.truetype(font_path_large, self.FONT_SIZE_LARGE)
        except (OSError, IOError):
            # Fallback to default font
            try:
                font_banner = ImageFont.load_default()
                font_large = ImageFont.load_default()
            except Exception:
                font_banner = None
                font_large = None

        # Get current time/date - 12h format
        now = datetime.now()
        time_str = now.strftime("%I:%M")  # 12h format without seconds
        if time_str.startswith("0"):
            time_str = time_str[1:]  # Remove leading zero
        date_str = now.strftime("%d %b %y")  # e.g., "15 Nov 19"

        # Draw time/date in black banner (white text, bold)
        draw.text((self.TIME_X, self.BANNER_Y_OFFSET), time_str, font=font_banner, fill=(255, 255, 255))
        draw.text((self.DATE_X, self.BANNER_Y_OFFSET), date_str, font=font_banner, fill=(255, 255, 255))

        # Load icons from repository or installed location
        # Icons are stored in the repo at icons/ and copied to /opt/ha-enviro-plus/icons/ during install
        # Try to find package directory first (for development/testing)
        package_icon_path = None
        try:
            import ha_enviro_plus
            package_dir = os.path.dirname(
                os.path.dirname(os.path.abspath(ha_enviro_plus.__file__))
            )
            repo_icons = os.path.join(package_dir, "icons")
            if os.path.isdir(repo_icons):
                package_icon_path = repo_icons
        except Exception:
            pass

        icon_paths = []
        if package_icon_path:
            icon_paths.append(package_icon_path)  # Development/repo location
        icon_paths.extend(
            [
                "/opt/ha-enviro-plus/icons",  # Primary installed location
                "/usr/local/lib/python3.*/site-packages/enviroplus/icons",
                "/opt/enviroplus-python/examples/icons",
                "~/.local/lib/python3.*/site-packages/enviroplus/icons",
            ]
        )

        icon_temp = None
        icon_humidity = None
        icon_pressure = None

        # Try to find icon directory
        icon_dir = None
        for pattern in icon_paths:
            expanded = os.path.expanduser(pattern)
            matches = glob.glob(expanded)
            if matches:
                icon_dir = matches[0]
                break

        # Load icons based on sensor readings
        if icon_dir:
            try:
                # Load temperature icon (generic - background color indicates state)
                temp_icon_path = os.path.join(icon_dir, "icon_temperature.png")
                if os.path.exists(temp_icon_path):
                    icon_temp = Image.open(temp_icon_path).convert("RGBA")
                else:
                    # Fallback to temperature.png if icon_temperature.png doesn't exist
                    fallback_path = os.path.join(icon_dir, "temperature.png")
                    if os.path.exists(fallback_path):
                        icon_temp = Image.open(fallback_path).convert("RGBA")
            except Exception:
                pass

            try:
                # Load humidity icon (variant based on reading)
                if humidity is not None:
                    # Good humidity range
                    if self.HUMIDITY_GOOD_MIN <= humidity <= self.HUMIDITY_GOOD_MAX:
                        hum_icon_name = "humidity-good.png"
                    else:
                        hum_icon_name = "humidity-bad.png"
                    hum_icon_path = os.path.join(icon_dir, hum_icon_name)
                    if os.path.exists(hum_icon_path):
                        icon_humidity = Image.open(hum_icon_path).convert("RGBA")
                    else:
                        # Fallback to generic humidity icon
                        fallback_path = os.path.join(icon_dir, "icon_humidity.png")
                        if os.path.exists(fallback_path):
                            icon_humidity = Image.open(fallback_path).convert("RGBA")
            except Exception:
                pass

            try:
                # Load pressure icon (weather-based)
                if pressure_hpa is not None:
                    # Standard atmospheric pressure: ~1013.25 hPa
                    # Low pressure: storm/rain
                    # Normal: fair
                    # High: dry/clear
                    if pressure_hpa < self.PRESSURE_STORM_MAX:
                        pressure_icon_name = "weather-storm.png"
                    elif pressure_hpa < self.PRESSURE_RAIN_MAX:
                        pressure_icon_name = "weather-rain.png"
                    elif pressure_hpa <= self.PRESSURE_FAIR_MAX:
                        pressure_icon_name = "weather-fair.png"
                    else:
                        pressure_icon_name = "weather-dry.png"
                    pressure_icon_path = os.path.join(icon_dir, pressure_icon_name)
                    if os.path.exists(pressure_icon_path):
                        icon_pressure = Image.open(pressure_icon_path).convert("RGBA")
                    else:
                        # Fallback to generic pressure icon (if it exists)
                        fallback_path = os.path.join(icon_dir, "icon_pressure.png")
                        if os.path.exists(fallback_path):
                            icon_pressure = Image.open(fallback_path).convert("RGBA")
            except Exception:
                pass

        # Main content area starts below banner
        # Add vertical spacing between banner and content, and between rows
        content_y = self.BANNER_HEIGHT + self.CONTENT_Y_OFFSET

        # Left column - Temperature (top row, left side)
        y_temp = content_y
        if sensors.has_sensor("bme280"):
            try:
                if temp_c is None:
                    temp_c = sensors.temp()
                if units == "imperial":
                    temp_value = celsius_to_fahrenheit(temp_c)
                    temp_unit = "°F"
                else:
                    temp_value = temp_c
                    temp_unit = "°C"

                temp_str = f"{temp_value:.0f}{temp_unit}"

                # Draw icon if available, otherwise use text
                icon_x = self.LEFT_COLUMN_X
                text_x = icon_x + self.ICON_SIZE + self.ICON_TEXT_SPACING if icon_temp else icon_x
                if icon_temp:
                    # Resize icon to fit (matches font size)
                    icon_resized = icon_temp.resize(
                        (self.ICON_SIZE, self.ICON_SIZE), Image.Resampling.LANCZOS
                    )
                    # Paste icon with alpha blending
                    image.paste(icon_resized, (icon_x, y_temp), icon_resized)
                else:
                    # Fallback: use "T" text
                    draw.text((icon_x, y_temp), "T", font=font_large, fill=(255, 255, 255))
                draw.text((text_x, y_temp), temp_str, font=font_large, fill=(255, 255, 255))
            except Exception as e:
                self.logger.warning("Failed to read temperature: %s", e)
                draw.text((self.LEFT_COLUMN_X, y_temp), "T --", font=font_large, fill=(255, 255, 255))

        # Left column - Humidity (middle row, left side)
        y_hum = content_y + self.ROW_SPACING
        if sensors.has_sensor("bme280"):
            try:
                if humidity is None:
                    humidity = sensors.humidity()
                hum_str = f"{humidity:.0f}%"

                # Draw icon if available, otherwise use text
                icon_x = self.LEFT_COLUMN_X
                text_x = icon_x + self.ICON_SIZE + self.ICON_TEXT_SPACING if icon_humidity else icon_x
                if icon_humidity:
                    # Resize icon to fit (matches font size)
                    icon_resized = icon_humidity.resize(
                        (self.ICON_SIZE, self.ICON_SIZE), Image.Resampling.LANCZOS
                    )
                    # Paste icon with alpha blending
                    image.paste(icon_resized, (icon_x, y_hum), icon_resized)
                else:
                    # Fallback: use "H" text
                    draw.text((icon_x, y_hum), "H", font=font_large, fill=(255, 255, 255))
                draw.text((text_x, y_hum), hum_str, font=font_large, fill=(255, 255, 255))
            except Exception as e:
                self.logger.warning("Failed to read humidity: %s", e)
                draw.text((self.LEFT_COLUMN_X, y_hum), "H --%", font=font_large, fill=(255, 255, 255))

        # Right column - Pressure (top row, right side)
        y_pressure = content_y
        if sensors.has_sensor("bme280"):
            try:
                if pressure_hpa is None:
                    pressure_hpa = sensors.pressure()
                if units == "imperial":
                    pressure_value = hpa_to_inhg(pressure_hpa)
                    pressure_unit = "in"
                    pressure_str = f"{pressure_value:.1f}"
                else:
                    pressure_value = pressure_hpa
                    pressure_unit = "hPa"
                    pressure_str = f"{pressure_value:.0f}"

                # Draw icon if available, otherwise use text
                icon_x = self.RIGHT_COLUMN_X
                text_x = icon_x + self.ICON_SIZE + self.ICON_TEXT_SPACING if icon_pressure else icon_x
                if icon_pressure:
                    # Resize icon to fit (matches font size)
                    icon_resized = icon_pressure.resize(
                        (self.ICON_SIZE, self.ICON_SIZE), Image.Resampling.LANCZOS
                    )
                    # Paste icon with alpha blending
                    image.paste(icon_resized, (icon_x, y_pressure), icon_resized)
                else:
                    # Fallback: use "P" text
                    draw.text((icon_x, y_pressure), "P", font=font_large, fill=(255, 255, 255))
                draw.text((text_x, y_pressure), pressure_str, font=font_large, fill=(255, 255, 255))
            except Exception as e:
                self.logger.warning("Failed to read pressure: %s", e)
                draw.text((self.RIGHT_COLUMN_X, y_pressure), "P --", font=font_large, fill=(255, 255, 255))

        return image
