#!/usr/bin/env python3
"""
Display Plugin System for Enviro+ LCD

This module provides a plugin-based architecture for display screens.
Plugins can be easily added to extend display functionality.
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from PIL import Image
    from .sensors import EnviroPlusSensors
    from .settings import SettingsManager

try:
    from PIL import Image

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
                    plugin_logger = logging.getLogger(__name__)
                    plugin_logger.warning("Failed to import plugin module %s: %s", modname, e)
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
    sensors: "EnviroPlusSensors",
    settings: "SettingsManager",
) -> List[DisplayPlugin]:
    """
    Get all available plugins that can be displayed.

    Args:
        sensors: EnviroPlusSensors instance
        settings: SettingsManager instance

    Returns:
        List of available plugin instances, with "Sensor Display" first
    """
    available = []
    sensor_display_plugin = None

    for plugin_class in _plugin_registry:
        try:
            plugin = plugin_class()
            if plugin.is_available(sensors, settings):
                # Prioritize "Sensor Display" (dashboard) to be first
                if plugin.name() == "Sensor Display":
                    sensor_display_plugin = plugin
                else:
                    available.append(plugin)
        except Exception as e:
            plugin_logger = logging.getLogger(__name__)
            plugin_logger.warning(
                "Failed to instantiate plugin %s: %s",
                plugin_class.__name__,
                e,
            )

    # Put Sensor Display first if available
    if sensor_display_plugin:
        available.insert(0, sensor_display_plugin)

    return available


# Import default plugin to ensure it's registered
# The SensorDisplayPlugin is now in plugins/sensor_display.py
try:
    from .plugins import sensor_display  # noqa: F401, W0611
except ImportError:
    # Plugin directory may not be available during testing
    pass
