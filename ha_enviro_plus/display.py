#!/usr/bin/env python3
"""
Display Management for Enviro+ LCD

This module provides display functionality for the ST7735 LCD display
on the Pimoroni Enviro+ and Enviro HAT.
"""

import time
import logging
from typing import Optional
from pathlib import Path

# Hardware imports with fallback for testing
try:
    import st7735

    ST7735_AVAILABLE = True
except ImportError:
    ST7735_AVAILABLE = False

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class DisplayManager:
    """
    Manages the ST7735 LCD display for Enviro+ with graceful degradation.

    Provides splash screen functionality with configurable enable/disable.
    All display operations are non-blocking and degrade gracefully on hardware failure.
    """

    def __init__(self, logger: Optional[logging.Logger] = None, enabled: bool = True):
        """
        Initialize the display manager.

        Args:
            logger: Logger instance for display operations
            enabled: Whether display is enabled (from DISPLAY_ENABLED env var)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.enabled = enabled
        self.display = None
        self.display_available = False

        if not enabled:
            self.logger.debug("Display disabled by configuration")
            return

        if not ST7735_AVAILABLE:
            self.logger.warning("ST7735 library not available, display disabled")
            return

        if not PIL_AVAILABLE:
            self.logger.warning("PIL/Pillow library not available, display disabled")
            return

        try:
            # Initialize ST7735 display
            # Parameters: port=0, cs=1, dc=9, backlight=12, rotation=270, spi_speed_hz=10000000
            self.display = st7735.ST7735(
                port=0, cs=1, dc=9, backlight=12, rotation=270, spi_speed_hz=10000000
            )
            self.display.begin()
            self.display_available = True
            self.logger.info("Display initialized successfully")
        except Exception as e:
            self.logger.warning(
                "Display hardware initialization failed: %s, " "continuing without display", e
            )
            self.display = None
            self.display_available = False

    def show_splash(
        self,
        splash_path: str = "assets/ha-enviro-plus-banner_160x80.png",
        duration: int = 5,
        fade_duration: int = 2,
    ) -> None:
        """
        Display splash screen for specified duration with fade.

        Args:
            splash_path: Path to splash screen image (160x80 PNG)
            duration: Display duration in seconds (default: 5)
            fade_duration: Fade-out duration in seconds (default: 2)
        """
        if not self.enabled or not self.display_available or not self.display:
            self.logger.debug("Splash screen skipped (display unavailable or disabled)")
            return

        try:
            # Load splash image
            image_path = Path(splash_path)
            if not image_path.exists():
                self.logger.warning("Splash image not found: %s", splash_path)
                return

            image = Image.open(image_path)

            # Display the image
            self.display.display(image)
            self.logger.info("Displaying splash screen for %d seconds", duration)

            # Wait for display duration
            time.sleep(duration - fade_duration)

            # Fade out over the specified duration
            fade_start = time.time()
            initial_brightness = 100  # Assume full brightness

            while time.time() - fade_start < fade_duration:
                elapsed = time.time() - fade_start
                brightness = int(initial_brightness * (1 - elapsed / fade_duration))
                brightness = max(0, min(100, brightness))

                # Set backlight brightness (if supported)
                try:
                    self.display.set_backlight(brightness)
                except AttributeError:
                    # set_backlight not available, use alternative method
                    pass

                time.sleep(0.05)  # 50ms update intervals

            # Turn off display
            try:
                self.display.set_backlight(0)
            except AttributeError:
                pass

            self.logger.info("Splash screen fade complete")
        except Exception as e:
            self.logger.warning(
                "Failed to display splash screen: %s, " "continuing without display", e
            )

    def cleanup(self) -> None:
        """
        Clean up display resources.
        """
        if self.display:
            try:
                # Turn off backlight
                self.display.set_backlight(0)
            except (AttributeError, Exception):
                pass
            self.display = None
            self.display_available = False
