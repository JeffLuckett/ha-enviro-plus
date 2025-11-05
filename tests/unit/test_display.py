#!/usr/bin/env python3
"""
Unit tests for display.py module
"""

import os
import sys
import time
from unittest.mock import Mock, patch

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestDisplayManager:
    """Test cases for DisplayManager"""

    def test_display_init_without_st7735(self):
        """Test DisplayManager initialization when ST7735 is not available"""
        with patch("ha_enviro_plus.display.ST7735_AVAILABLE", False):
            from ha_enviro_plus.display import DisplayManager

            display = DisplayManager(enabled=True)

            assert display.enabled is True
            assert display.display_available is False
            assert display.display is None

    def test_display_init_without_pil(self):
        """Test DisplayManager initialization when PIL is not available"""
        with patch("ha_enviro_plus.display.PIL_AVAILABLE", False):
            from ha_enviro_plus.display import DisplayManager

            display = DisplayManager(enabled=True)

            assert display.enabled is True
            assert display.display_available is False
            assert display.display is None

    def test_display_init_disabled(self):
        """Test DisplayManager initialization when display is disabled"""
        from ha_enviro_plus.display import DisplayManager

        display = DisplayManager(enabled=False)

        assert display.enabled is False
        assert display.display_available is False
        assert display.display is None

    def test_show_splash_disabled(self):
        """Test splash screen when display is disabled"""
        from ha_enviro_plus.display import DisplayManager

        display = DisplayManager(enabled=False)
        display.show_splash()
        # Should handle gracefully without crashing

    def test_fade_out_step_progress(self):
        """Test that fade-out step calculates brightness correctly"""
        from ha_enviro_plus.display import DisplayManager

        # Create a mock display
        mock_display = Mock()
        display = DisplayManager(enabled=False)
        display.display = mock_display
        display.display_available = True

        # Test progressive brightness values
        # At progress 0.0 (start of fade), brightness should be 100
        display._fade_out_step(0.0)
        assert mock_display.set_backlight.called
        assert mock_display.set_backlight.call_args[0][0] == 100

        # At progress 0.5 (middle), brightness should be 50
        mock_display.reset_mock()
        display._fade_out_step(0.5)
        assert mock_display.set_backlight.call_args[0][0] == 50

        # At progress 1.0 (end of fade), brightness should be 0
        mock_display.reset_mock()
        display._fade_out_step(1.0)
        assert mock_display.set_backlight.call_args[0][0] == 0

        # Test edge cases
        mock_display.reset_mock()
        display._fade_out_step(1.5)  # Beyond 1.0
        assert mock_display.set_backlight.call_args[0][0] == 0

    def test_display_item_structure(self):
        """Test DisplayItem dataclass structure"""
        from ha_enviro_plus.display import DisplayItem

        render_func = Mock()

        # Test creating display items
        item1 = DisplayItem(duration=5.0, render_func=render_func, fade_out=True)
        assert item1.duration == 5.0
        assert item1.render_func == render_func
        assert item1.fade_out is True
        assert item1.fade_in is False

        item2 = DisplayItem(duration=10.0, render_func=render_func, fade_in=True, fade_out=False)
        assert item2.duration == 10.0
        assert item2.fade_in is True
        assert item2.fade_out is False

    def test_start_plugin_cycle(self):
        """Test starting plugin cycle."""
        from ha_enviro_plus.display import DisplayManager

        display = DisplayManager(enabled=False)
        display.display_available = True

        # Create mock plugins
        mock_plugin1 = Mock()
        mock_plugin1.name.return_value = "Plugin 1"
        mock_plugin1.duration.return_value = 5.0

        mock_plugin2 = Mock()
        mock_plugin2.name.return_value = "Plugin 2"
        mock_plugin2.duration.return_value = 3.0

        plugins = [mock_plugin1, mock_plugin2]

        # Start plugin cycle
        display.start_plugin_cycle(plugins)

        assert display._plugin_cycle_active is True
        assert len(display._plugin_cycle_plugins) == 2
        assert display._plugin_cycle_index == 0

    def test_start_plugin_cycle_no_plugins(self):
        """Test starting plugin cycle with no plugins."""
        from ha_enviro_plus.display import DisplayManager

        display = DisplayManager(enabled=False)
        display.display_available = True

        # Start plugin cycle with empty list
        display.start_plugin_cycle([])

        # Should not activate cycle
        assert display._plugin_cycle_active is False

    def test_start_plugin_cycle_display_unavailable(self):
        """Test starting plugin cycle when display is unavailable."""
        from ha_enviro_plus.display import DisplayManager

        display = DisplayManager(enabled=False)
        display.display_available = False

        mock_plugin = Mock()
        plugins = [mock_plugin]

        # Start plugin cycle
        display.start_plugin_cycle(plugins)

        # Should not activate cycle
        assert display._plugin_cycle_active is False

    def test_update_plugin_data(self):
        """Test updating plugin data."""
        from ha_enviro_plus.display import DisplayManager

        display = DisplayManager(enabled=False)
        display._plugin_cycle_active = True

        mock_sensors = Mock()
        mock_settings = Mock()

        # Update plugin data
        display.update_plugin_data(mock_sensors, mock_settings)

        assert display._plugin_cycle_sensors == mock_sensors
        assert display._plugin_cycle_settings == mock_settings

    def test_show_error_message(self):
        """Test showing error message."""
        from ha_enviro_plus.display import DisplayManager

        display = DisplayManager(enabled=False)
        display.display_available = True

        # Show error message
        display.show_error_message("Test error")

        # Should queue error display
        assert len(display._display_queue) == 1

    def test_show_error_message_display_unavailable(self):
        """Test showing error message when display is unavailable."""
        from ha_enviro_plus.display import DisplayManager

        display = DisplayManager(enabled=False)
        display.display_available = False

        # Show error message
        display.show_error_message("Test error")

        # Should not queue error display
        assert len(display._display_queue) == 0

    @patch("ha_enviro_plus.display.PIL_AVAILABLE", True)
    @patch("ha_enviro_plus.display.Image")
    @patch("ha_enviro_plus.display.ImageDraw")
    @patch("ha_enviro_plus.display.ImageFont")
    def test_create_error_image(self, mock_font, mock_draw, mock_image):
        """Test error image creation."""
        from ha_enviro_plus.display import DisplayManager

        display = DisplayManager(enabled=False)

        # Setup mocks
        mock_img_instance = Mock()
        mock_image.new.return_value = mock_img_instance
        mock_draw_instance = Mock()
        mock_draw.Draw.return_value = mock_draw_instance
        mock_font_instance = Mock()
        mock_font.truetype.return_value = mock_font_instance

        # Create error image
        error_image = display._create_error_image("Test error message")

        # Verify image was created
        mock_image.new.assert_called_once()
        assert error_image == mock_img_instance

    @patch("ha_enviro_plus.display.PIL_AVAILABLE", False)
    def test_create_error_image_no_pil(self):
        """Test error image creation when PIL is not available."""
        from ha_enviro_plus.display import DisplayManager
        import pytest

        display = DisplayManager(enabled=False)

        # Should raise RuntimeError when PIL is not available
        with pytest.raises(RuntimeError, match="PIL/Pillow not available"):
            display._create_error_image("Test error message")
