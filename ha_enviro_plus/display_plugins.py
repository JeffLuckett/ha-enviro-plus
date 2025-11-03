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
        return 5.0  # Show for 5 seconds

    def render(self, sensors: "EnviroPlusSensors", settings: "SettingsManager") -> "Image.Image":
        """
        Render the sensor display screen.

        Shows time/date, temperature, humidity, and barometric pressure.
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not available")

        # Create image (160x80 for ST7735)
        image = Image.new("RGB", (160, 80), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Try to load a font, fallback to default if unavailable
        try:
            # Try to use a smaller font first
            font_path_small = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            font_path_large = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_small = ImageFont.truetype(font_path_small, 10)
            font_large = ImageFont.truetype(font_path_large, 12)
        except (OSError, IOError):
            # Fallback to default font
            try:
                font_small = ImageFont.load_default()
                font_large = ImageFont.load_default()
            except Exception:
                font_small = None
                font_large = None

        # Get units setting
        units = settings.get_units() if hasattr(settings, "get_units") else "metric"

        # Get current time/date
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%m/%d/%Y")

        # Draw time/date at top
        y_pos = 2
        draw.text((5, y_pos), "🕐", font=font_small)  # Clock icon
        draw.text((20, y_pos), time_str, font=font_small, fill=(255, 255, 255))
        draw.text((5, y_pos + 12), date_str, font=font_small, fill=(200, 200, 200))

        # Get sensor readings
        y_pos = 30

        # Temperature
        if sensors.has_sensor("bme280"):
            try:
                temp_c = sensors.temp()
                if units == "imperial":
                    temp_value = celsius_to_fahrenheit(temp_c)
                    temp_unit = "°F"
                    temp_icon = "🌡️"
                else:
                    temp_value = temp_c
                    temp_unit = "°C"
                    temp_icon = "🌡️"

                temp_str = f"{temp_icon} {temp_value:.1f}{temp_unit}"
                draw.text((5, y_pos), temp_str, font=font_large, fill=(255, 255, 255))
            except Exception as e:
                self.logger.warning("Failed to read temperature: %s", e)
                draw.text((5, y_pos), "🌡️ --°C", font=font_large, fill=(128, 128, 128))

        # Humidity
        y_pos += 18
        if sensors.has_sensor("bme280"):
            try:
                humidity = sensors.humidity()
                hum_str = f"💧 {humidity:.1f}%"
                draw.text((5, y_pos), hum_str, font=font_large, fill=(255, 255, 255))
            except Exception as e:
                self.logger.warning("Failed to read humidity: %s", e)
                draw.text((5, y_pos), "💧 --%", font=font_large, fill=(128, 128, 128))

        # Pressure
        y_pos += 18
        if sensors.has_sensor("bme280"):
            try:
                pressure_hpa = sensors.pressure()
                if units == "imperial":
                    pressure_value = hpa_to_inhg(pressure_hpa)
                    pressure_unit = "inHg"
                    pressure_icon = "📊"
                else:
                    pressure_value = pressure_hpa
                    pressure_unit = "hPa"
                    pressure_icon = "📊"

                pressure_str = f"{pressure_icon} {pressure_value:.1f}{pressure_unit}"
                draw.text((5, y_pos), pressure_str, font=font_large, fill=(255, 255, 255))
            except Exception as e:
                self.logger.warning("Failed to read pressure: %s", e)
                draw.text((5, y_pos), "📊 --hPa", font=font_large, fill=(128, 128, 128))

        return image
