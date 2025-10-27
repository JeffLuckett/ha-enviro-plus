#!/usr/bin/env python3
"""
Unit tests for display.py module
"""

import os
import sys
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
