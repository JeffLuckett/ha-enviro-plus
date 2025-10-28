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
