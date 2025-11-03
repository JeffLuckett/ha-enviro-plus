#!/usr/bin/env python3
"""
Display Plugin System for Enviro+ LCD

This module provides a plugin-based architecture for display screens.
Plugins can be easily added to extend display functionality.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Any

if TYPE_CHECKING:
    from PIL import Image, ImageDraw, ImageFont
    from .sensors import EnviroPlusSensors
    from .settings import SettingsManager

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# Unit conversion helpers
def celsius_to_fahrenheit(celsius: float) -> float:
    """
    Convert Celsius to Fahrenheit.

    Args:
        celsius: Temperature in Celsius

    Returns:
        Temperature in Fahrenheit
    """
    return (celsius * 9.0 / 5.0) + 32.0


def hpa_to_inhg(hpa: float) -> float:
    """
    Convert hectopascals to inches of mercury.

    Args:
        hpa: Pressure in hectopascals

    Returns:
        Pressure in inches of mercury
    """
    return hpa / 33.8639


class DisplayPlugin(ABC):
    """
    Base class for display plugins.

    All display plugins must extend this class and implement the required methods.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the display plugin.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)

    @abstractmethod
    def name(self) -> str:
        """
        Get the name of this display plugin.

        Returns:
            Plugin name string
        """
        pass

    @abstractmethod
    def is_available(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> bool:
        """
        Check if this plugin can be displayed.

        Args:
            sensors: EnviroPlusSensors instance
            settings: SettingsManager instance

        Returns:
            True if plugin can be displayed, False otherwise
        """
        pass

    @abstractmethod
    def render(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> "Image.Image":
        """
        Render the display screen.

        Args:
            sensors: EnviroPlusSensors instance
            settings: SettingsManager instance

        Returns:
            PIL Image object (160x80) representing the display

        Raises:
            Exception: If rendering fails (will be caught and error message shown)
        """
        pass

    @abstractmethod
    def duration(self) -> float:
        """
        Get the display duration for this plugin.

        Returns:
            Duration in seconds
        """
        pass

    def error_message(self, error: Exception) -> str:
        """
        Generate a descriptive error message for this plugin.

        Args:
            error: The exception that occurred

        Returns:
            Error message string
        """
        return f"{self.name()}: {str(error)}"


# Plugin registry
_plugin_registry: List[type[DisplayPlugin]] = []

# Auto-import user plugins from plugins directory
try:
    # Import user plugins if the directory exists
    import importlib
    import pkgutil
    from pathlib import Path

    # Check if plugins package exists
    plugin_package_path = Path(__file__).parent / "plugins"
    if plugin_package_path.exists() and plugin_package_path.is_dir():
        # Import all modules in the plugins package
        for importer, modname, ispkg in pkgutil.iter_modules([str(plugin_package_path)]):
            if not modname.startswith("_") and modname != "__init__":
                try:
                    importlib.import_module(f"ha_enviro_plus.plugins.{modname}")
                except Exception as e:
                    # Log but don't fail - user plugins may have errors
                    logger = logging.getLogger(__name__)
                    logger.warning("Failed to import plugin module %s: %s", modname, e)
except Exception:
    # Silently fail - user plugins directory may not exist
    pass


def register_plugin(plugin_class: type[DisplayPlugin]) -> type[DisplayPlugin]:
    """
    Register a display plugin.

    Args:
        plugin_class: Plugin class to register

    Returns:
        The plugin class (for use as decorator)
    """
    if plugin_class not in _plugin_registry:
        _plugin_registry.append(plugin_class)
    return plugin_class


def get_available_plugins(
    sensors: "EnviroPlusSensors", settings: "SettingsManager"
) -> List[DisplayPlugin]:
    """
    Get all available plugins that can be displayed.

    Args:
        sensors: EnviroPlusSensors instance
        settings: SettingsManager instance

    Returns:
        List of available plugin instances
    """
    available = []
    for plugin_class in _plugin_registry:
        try:
            plugin = plugin_class()
            if plugin.is_available(sensors, settings):
                available.append(plugin)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning("Failed to instantiate plugin %s: %s", plugin_class.__name__, e)
    return available


@register_plugin
class SensorDisplayPlugin(DisplayPlugin):
    """
    Default sensor display plugin showing time/date, temperature, humidity, and pressure.

    This serves as an example of how to implement display plugins.
    """

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

        # Get sensor readings first to calculate background color
        temp_c = None
        if sensors.has_sensor("bme280"):
            try:
                temp_c = sensors.temp()
            except Exception:
                pass

        # Calculate background color based on temperature
        # Comfort zone: 18-24°C (65-75°F) = green
        # Below 18°C = cool blue
        # Above 24°C = orangey red
        if temp_c is not None:
            if units == "imperial":
                temp_f = celsius_to_fahrenheit(temp_c)
                # Comfort zone: 65-75°F
                if 65 <= temp_f <= 75:
                    # Green for comfort zone
                    bg_color = (34, 139, 34)  # Forest green
                elif temp_f < 65:
                    # Cool blue (colder = more blue)
                    ratio = max(0, min(1, (temp_f - 32) / (65 - 32)))
                    bg_color = (
                        int(25 + ratio * 50),  # R: 25-75
                        int(100 + ratio * 50),  # G: 100-150
                        int(200 + ratio * 55),  # B: 200-255
                    )
                else:
                    # Orangey red (hotter = more red)
                    ratio = max(0, min(1, (temp_f - 75) / (90 - 75)))
                    bg_color = (
                        int(255 - ratio * 30),  # R: 255-225
                        int(140 - ratio * 40),  # G: 140-100
                        int(0),  # B: 0
                    )
            else:
                # Comfort zone: 18-24°C
                if 18 <= temp_c <= 24:
                    # Green for comfort zone
                    bg_color = (34, 139, 34)  # Forest green
                elif temp_c < 18:
                    # Cool blue (colder = more blue)
                    ratio = max(0, min(1, (temp_c - 0) / (18 - 0)))
                    bg_color = (
                        int(25 + ratio * 50),  # R: 25-75
                        int(100 + ratio * 50),  # G: 100-150
                        int(200 + ratio * 55),  # B: 200-255
                    )
                else:
                    # Orangey red (hotter = more red)
                    ratio = max(0, min(1, (temp_c - 24) / (35 - 24)))
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

        # Try to load fonts - need larger fonts for readability
        try:
            font_path_small = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            font_path_medium = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_path_large = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_small = ImageFont.truetype(font_path_small, 9)
            font_medium = ImageFont.truetype(font_path_medium, 11)
            font_large = ImageFont.truetype(font_path_large, 14)
        except (OSError, IOError):
            # Fallback to default font
            try:
                font_small = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_large = ImageFont.load_default()
            except Exception:
                font_small = None
                font_medium = None
                font_large = None

        # Get current time/date - 12h format
        now = datetime.now()
        time_str = now.strftime("%I:%M")  # 12h format without seconds
        if time_str.startswith("0"):
            time_str = time_str[1:]  # Remove leading zero
        date_str = now.strftime("%d %b %y")  # e.g., "15 Nov 19"

        # Draw time/date at top (no icon)
        draw.text((5, 2), time_str, font=font_medium, fill=(255, 255, 255))
        draw.text((85, 2), date_str, font=font_small, fill=(255, 255, 255))

        # Two-column layout
        # Left column: Temperature, Humidity
        # Right column: Light (if available), Pressure

        # Left column - Temperature
        y_left = 20
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

                # Temperature icon (ASCII thermometer)
                draw.text((5, y_left), "T", font=font_medium, fill=(255, 255, 255))
                temp_str = f"{temp_value:.0f}{temp_unit}"
                draw.text((18, y_left), temp_str, font=font_large, fill=(255, 255, 255))
                # Temperature range indicator
                if units == "imperial":
                    range_str = "65-75"
                else:
                    range_str = "18-24"
                draw.text((5, y_left + 16), range_str, font=font_small, fill=(255, 255, 255))
            except Exception as e:
                self.logger.warning("Failed to read temperature: %s", e)
                draw.text((5, y_left), "T --", font=font_large, fill=(255, 255, 255))

        # Left column - Humidity
        y_left = 48
        if sensors.has_sensor("bme280"):
            try:
                humidity = sensors.humidity()
                # Humidity icon (ASCII droplet: ~)
                draw.text((5, y_left), "~", font=font_medium, fill=(255, 255, 255))
                hum_str = f"{humidity:.0f}%"
                draw.text((18, y_left), hum_str, font=font_large, fill=(255, 255, 255))
                # Status indicator
                if 40 <= humidity <= 60:
                    status = "GOOD"
                elif humidity < 40:
                    status = "LOW"
                else:
                    status = "HIGH"
                draw.text((5, y_left + 16), status, font=font_small, fill=(255, 255, 255))
            except Exception as e:
                self.logger.warning("Failed to read humidity: %s", e)
                draw.text((5, y_left), "~ --%", font=font_large, fill=(255, 255, 255))

        # Right column - Light (if available)
        y_right = 20
        if sensors.has_sensor("ltr559"):
            try:
                lux = sensors.lux()
                # Light icon (ASCII bulb: *)
                draw.text((85, y_right), "*", font=font_medium, fill=(255, 255, 255))
                lux_str = f"{lux:.0f}"
                # Format with comma for thousands
                if lux >= 1000:
                    lux_str = f"{lux/1000:.1f}k"
                draw.text((98, y_right), lux_str, font=font_large, fill=(255, 255, 255))
                # Status indicator
                if lux < 100:
                    status = "DIM"
                elif lux < 1000:
                    status = "GOOD"
                elif lux < 10000:
                    status = "BRIGHT"
                else:
                    status = "BRIGHT"
                draw.text((85, y_right + 16), status, font=font_small, fill=(255, 255, 255))
            except Exception:
                pass

        # Right column - Pressure
        y_right = 48
        if sensors.has_sensor("bme280"):
            try:
                pressure_hpa = sensors.pressure()
                if units == "imperial":
                    pressure_value = hpa_to_inhg(pressure_hpa)
                    pressure_unit = "in"
                    pressure_str = f"{pressure_value:.2f}"
                else:
                    pressure_value = pressure_hpa
                    pressure_unit = "hPa"
                    pressure_str = f"{pressure_value:.0f}"

                # Pressure icon (ASCII: P)
                draw.text((85, y_right), "P", font=font_medium, fill=(255, 255, 255))
                draw.text((98, y_right), pressure_str, font=font_large, fill=(255, 255, 255))
                # Status indicator
                if units == "imperial":
                    # Standard atmospheric pressure: ~29.92 inHg
                    if 29.5 <= pressure_value <= 30.5:
                        status = "FAIR"
                    elif pressure_value < 29.5:
                        status = "LOW"
                    else:
                        status = "HIGH"
                else:
                    # Standard atmospheric pressure: ~1013 hPa
                    if 990 <= pressure_value <= 1030:
                        status = "FAIR"
                    elif pressure_value < 990:
                        status = "LOW"
                    else:
                        status = "HIGH"
                draw.text((85, y_right + 16), status, font=font_small, fill=(255, 255, 255))
            except Exception as e:
                self.logger.warning("Failed to read pressure: %s", e)
                draw.text((85, y_right), "P --", font=font_large, fill=(255, 255, 255))

        return image
