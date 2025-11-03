#!/usr/bin/env python3
"""
Integration tests for display plugin system
"""

import os
import sys
import time
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestDisplayPluginIntegration:
    """Integration tests for display plugin system."""

    @pytest.fixture
    def mock_sensors(self):
        """Create mock sensors."""
        sensors = Mock()
        sensors.has_sensor.return_value = True
        sensors.temp.return_value = 25.5
        sensors.humidity.return_value = 45.0
        sensors.pressure.return_value = 1013.25
        sensors.cpu_temp.return_value = 42.0
        return sensors

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.get_units.return_value = "metric"
        return settings

    @patch("ha_enviro_plus.display.ST7735_AVAILABLE", False)
    def test_plugin_discovery_without_display(self, mock_sensors, mock_settings):
        """Test plugin discovery when display is not available."""
        from ha_enviro_plus.display_plugins import get_available_plugins

        # Should not raise exception
        plugins = get_available_plugins(mock_sensors, mock_settings)
        assert isinstance(plugins, list)

    def test_plugin_discovery_and_availability(self, mock_sensors, mock_settings):
        """Test plugin discovery and availability checking."""
        from ha_enviro_plus.display_plugins import (
            get_available_plugins,
            SensorDisplayPlugin,
        )

        # Test discovery
        plugins = get_available_plugins(mock_sensors, mock_settings)
        assert isinstance(plugins, list)

        # Should include sensor display plugin if BME280 is available
        sensor_plugin = None
        for plugin in plugins:
            if isinstance(plugin, SensorDisplayPlugin):
                sensor_plugin = plugin
                break

        if mock_sensors.has_sensor("bme280"):
            assert sensor_plugin is not None
            assert sensor_plugin.is_available(mock_sensors, mock_settings) is True

    @patch("ha_enviro_plus.display.ST7735_AVAILABLE", True)
    @patch("ha_enviro_plus.display.PIL_AVAILABLE", True)
    def test_display_manager_plugin_cycle(self, mock_sensors, mock_settings):
        """Test DisplayManager plugin cycling."""
        import ha_enviro_plus.display
        from ha_enviro_plus.display import DisplayManager
        from ha_enviro_plus.display_plugins import get_available_plugins
        from unittest.mock import MagicMock

        # Setup mock st7735 module
        mock_st7735_module = MagicMock()
        mock_display_instance = Mock()
        mock_display_instance.begin = Mock()
        mock_display_instance.display = Mock()
        mock_display_instance.set_backlight = Mock()
        mock_st7735_module.ST7735 = Mock(return_value=mock_display_instance)
        ha_enviro_plus.display.st7735 = mock_st7735_module

        # Setup mock PIL
        ha_enviro_plus.display.Image = MagicMock()

        # Create display manager
        display = DisplayManager(enabled=True)
        assert display.display_available is True

        # Discover plugins
        plugins = get_available_plugins(mock_sensors, mock_settings)
        if plugins:
            # Start plugin cycle
            display.start_plugin_cycle(plugins)
            assert display._plugin_cycle_active is True

            # Update plugin data
            display.update_plugin_data(mock_sensors, mock_settings)
            assert display._plugin_cycle_sensors == mock_sensors
            assert display._plugin_cycle_settings == mock_settings

    @patch("ha_enviro_plus.display.ST7735_AVAILABLE", True)
    @patch("ha_enviro_plus.display.PIL_AVAILABLE", True)
    def test_display_manager_error_message(self, mock_sensors, mock_settings):
        """Test DisplayManager error message display."""
        import ha_enviro_plus.display
        from ha_enviro_plus.display import DisplayManager
        from unittest.mock import MagicMock

        # Setup mock st7735 module
        mock_st7735_module = MagicMock()
        mock_display_instance = Mock()
        mock_display_instance.begin = Mock()
        mock_display_instance.display = Mock()
        mock_display_instance.set_backlight = Mock()
        mock_st7735_module.ST7735 = Mock(return_value=mock_display_instance)
        ha_enviro_plus.display.st7735 = mock_st7735_module

        # Setup mock PIL
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()
        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(return_value=mock_font_instance)
        ha_enviro_plus.display.Image = mock_image
        ha_enviro_plus.display.ImageDraw = mock_draw
        ha_enviro_plus.display.ImageFont = mock_font

        # Create display manager
        display = DisplayManager(enabled=True)
        assert display.display_available is True

        # Show error message
        display.show_error_message("Test error message")
        # Should not raise exception

    @patch("ha_enviro_plus.display.ST7735_AVAILABLE", True)
    @patch("ha_enviro_plus.display.PIL_AVAILABLE", True)
    def test_plugin_render_error_handling(self, mock_sensors, mock_settings):
        """Test that plugin render errors are handled gracefully."""
        import ha_enviro_plus.display
        import ha_enviro_plus.display_plugins
        from ha_enviro_plus.display import DisplayManager
        from ha_enviro_plus.display_plugins import DisplayPlugin
        from unittest.mock import MagicMock

        # Setup mock st7735 module
        mock_st7735_module = MagicMock()
        mock_display_instance = Mock()
        mock_display_instance.begin = Mock()
        mock_display_instance.display = Mock()
        mock_display_instance.set_backlight = Mock()
        mock_st7735_module.ST7735 = Mock(return_value=mock_display_instance)
        ha_enviro_plus.display.st7735 = mock_st7735_module

        # Setup mock PIL
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()
        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(return_value=mock_font_instance)
        ha_enviro_plus.display.Image = mock_image
        ha_enviro_plus.display.ImageDraw = mock_draw
        ha_enviro_plus.display.ImageFont = mock_font

        # Setup PIL for display_plugins too
        ha_enviro_plus.display_plugins.Image = mock_image
        ha_enviro_plus.display_plugins.ImageDraw = mock_draw
        ha_enviro_plus.display_plugins.ImageFont = mock_font

        # Create a plugin that raises an error
        class ErrorPlugin(DisplayPlugin):
            def name(self):
                return "Error Plugin"

            def is_available(self, sensors, settings):
                return True

            def render(self, sensors, settings):
                raise Exception("Render error")

            def duration(self):
                return 1.0

        plugin = ErrorPlugin()

        # Create display manager
        display = DisplayManager(enabled=True)

        # Start plugin cycle with error plugin
        display.start_plugin_cycle([plugin])
        display.update_plugin_data(mock_sensors, mock_settings)

        # Should not raise exception, should handle error gracefully
        # The error should be caught in the render function closure

    def test_plugin_cycle_with_multiple_plugins(self, mock_sensors, mock_settings):
        """Test plugin cycling with multiple plugins."""
        from ha_enviro_plus.display_plugins import (
            DisplayPlugin,
            register_plugin,
            get_available_plugins,
            _plugin_registry,
        )

        # Create additional test plugin
        class TestPlugin(DisplayPlugin):
            def name(self):
                return "Test Plugin"

            def is_available(self, sensors, settings):
                return True

            def render(self, sensors, settings):
                from PIL import Image

                return Image.new("RGB", (160, 80), color=(0, 0, 0))

            def duration(self):
                return 3.0

        # Register test plugin
        original_plugins = list(_plugin_registry)
        register_plugin(TestPlugin)

        # Discover plugins
        plugins = get_available_plugins(mock_sensors, mock_settings)
        assert len(plugins) >= len(original_plugins)

        # Clean up
        _plugin_registry.remove(TestPlugin)

    def test_units_conversion_in_plugin_rendering(self, mock_sensors, mock_settings):
        """Test that units conversion is applied correctly in plugin rendering."""
        from ha_enviro_plus.display_plugins import (
            SensorDisplayPlugin,
            celsius_to_fahrenheit,
            hpa_to_inhg,
        )

        # Test metric rendering
        mock_settings.get_units.return_value = "metric"
        plugin = SensorDisplayPlugin()

        with patch("ha_enviro_plus.display_plugins.PIL_AVAILABLE", True):
            with patch("ha_enviro_plus.display_plugins.Image") as mock_image:
                with patch("ha_enviro_plus.display_plugins.ImageDraw") as mock_draw:
                    with patch("ha_enviro_plus.display_plugins.ImageFont") as mock_font:
                        mock_img_instance = Mock()
                        mock_image.new.return_value = mock_img_instance
                        mock_draw_instance = Mock()
                        mock_draw.Draw.return_value = mock_draw_instance
                        mock_font_instance = Mock()
                        mock_font.truetype.return_value = mock_font_instance

                        plugin.render(mock_sensors, mock_settings)

                        # Verify temperature was read (should be in Celsius)
                        mock_sensors.temp.assert_called()

        # Test imperial rendering
        mock_settings.get_units.return_value = "imperial"
        mock_sensors.temp.return_value = 25.0  # Reset

        with patch("ha_enviro_plus.display_plugins.PIL_AVAILABLE", True):
            with patch("ha_enviro_plus.display_plugins.Image") as mock_image:
                with patch("ha_enviro_plus.display_plugins.ImageDraw") as mock_draw:
                    with patch("ha_enviro_plus.display_plugins.ImageFont") as mock_font:
                        mock_img_instance = Mock()
                        mock_image.new.return_value = mock_img_instance
                        mock_draw_instance = Mock()
                        mock_draw.Draw.return_value = mock_draw_instance
                        mock_font_instance = Mock()
                        mock_font.truetype.return_value = mock_font_instance

                        plugin.render(mock_sensors, mock_settings)

                        # Verify temperature was read and will be converted
                        mock_sensors.temp.assert_called()
                        # The conversion happens in the plugin render method
