#!/usr/bin/env python3
"""
Display Management for Enviro+ LCD

This module provides display functionality for the ST7735 LCD display
on the Pimoroni Enviro+ and Enviro HAT.
"""

import time
import logging
import threading
from typing import Optional, Callable, TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass

if TYPE_CHECKING:
    from PIL import Image

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


@dataclass
class DisplayItem:
    """Represents a display item with timing and update function."""

    duration: float  # Duration to show this display in seconds
    render_func: Callable[[], "Image.Image"]  # Function to render the display
    fade_in: bool = False  # Whether to fade in
    fade_out: bool = False  # Whether to fade out


@dataclass
class SplashDisplayItem:
    """Represents a splash screen with image and fade."""

    image_path: str
    duration: float
    fade_duration: float = 2.0


class DisplayManager:
    """
    Manages the ST7735 LCD display for Enviro+ with graceful degradation.

    Provides non-blocking display functionality with configurable enable/disable.
    All display operations run in a background thread and degrade gracefully
    on hardware failure.
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

        # Threading control
        self._display_queue = []
        self._current_display = None
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

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

            # Start the display thread
            self._thread = threading.Thread(target=self._display_loop, daemon=True)
            self._thread.start()
        except Exception as e:
            self.logger.warning(
                "Display hardware initialization failed: %s, " "continuing without display", e
            )
            self.display = None
            self.display_available = False

    def show_splash(
        self,
        splash_path: str = "assets/ha-enviro-plus-banner_160x80.png",
        duration: float = 5,
        fade_duration: float = 2,
    ) -> None:
        """
        Queue splash screen for display (non-blocking).

        Args:
            splash_path: Path to splash screen image (160x80 PNG)
            duration: Display duration in seconds (default: 5)
            fade_duration: Fade-out duration in seconds (default: 2)
        """
        if not self.enabled or not self.display_available:
            self.logger.debug("Splash screen skipped (display unavailable or disabled)")
            return

            def render_splash():  # type: ignore
                """Render the splash screen image."""
                image_path = Path(splash_path)
                if not image_path.exists():
                    self.logger.warning("Splash image not found: %s", splash_path)
                    # Return a blank image
                    return Image.new("RGB", (160, 80), color=(0, 0, 0))
                return Image.open(image_path)

        # Create a display item for the splash
        display_item = SplashDisplayItem(
            image_path=splash_path, duration=duration, fade_duration=fade_duration
        )

        # Queue the splash screen
        self._queue_display(display_item, render_splash, fade_out=True)

    def _queue_display(
        self,
        display_item: SplashDisplayItem,
        render_func: Callable[[], "Image.Image"],
        fade_out: bool = False,
    ) -> None:
        """
        Queue a display item for rendering.

        Args:
            display_item: Splash display item with timing
            render_func: Function to render the display
            fade_out: Whether to fade out at the end
        """
        if not self.display_available:
            return

        with self._lock:
            item = DisplayItem(
                duration=display_item.duration,
                render_func=render_func,
                fade_out=fade_out,
            )
            self._display_queue.append(item)

    def update_sensor_display(
        self, render_func: Callable[[], "Image.Image"], duration: float = 5
    ) -> None:
        """
        Queue a sensor display update (non-blocking).

        Args:
            render_func: Function to render sensor data as Image
            duration: Duration to show this display in seconds
        """
        if not self.display_available:
            return

        with self._lock:
            item = DisplayItem(duration=duration, render_func=render_func)
            self._display_queue.append(item)

    def _display_loop(self) -> None:
        """Background thread loop for displaying queued items."""
        while not self._stop_event.is_set():
            try:
                # Get next display item
                with self._lock:
                    if self._display_queue:
                        self._current_display = self._display_queue.pop(0)
                    else:
                        self._current_display = None

                # Display the current item
                if self._current_display and self.display:
                    self._render_display(self._current_display)

                # Small delay to prevent busy waiting
                time.sleep(0.1)

            except Exception as e:
                self.logger.error("Error in display loop: %s", e)
                time.sleep(1)  # Wait before retrying

    def _render_display(self, display_item: DisplayItem) -> None:
        """
        Render a display item with timing and optional fade effects.

        Args:
            display_item: The display item to render
        """
        try:
            # Render the image (cast to any for type checking)
            image = display_item.render_func()

            # Fade in if requested
            if display_item.fade_in:
                self._fade_in(image)
            else:
                self.display.display(image)
                try:
                    self.display.set_backlight(100)  # Full brightness
                except (AttributeError, Exception):
                    pass

            # Wait for duration minus fade out time
            fade_time = 2.0 if display_item.fade_out else 0
            sleep_time = max(0, display_item.duration - fade_time)
            start_time = time.time()

            while time.time() - start_time < sleep_time:
                if self._stop_event.is_set():
                    return
                time.sleep(0.1)

            # Fade out if requested
            if display_item.fade_out:
                self._fade_out()
            else:
                # Just turn off
                try:
                    self.display.set_backlight(0)
                except (AttributeError, Exception):
                    pass

        except Exception as e:
            self.logger.error("Error rendering display: %s", e)

    def _fade_in(self, image) -> None:  # type: ignore
        """
        Fade in an image over ~1 second.

        Args:
            image: Image to fade in
        """
        if not self.display:
            return

        fade_duration = 1.0
        start_time = time.time()

        self.display.display(image)

        while time.time() - start_time < fade_duration:
            elapsed = time.time() - start_time
            brightness = int(100 * (elapsed / fade_duration))
            brightness = max(0, min(100, brightness))

            try:
                self.display.set_backlight(brightness)
            except (AttributeError, Exception):
                pass

            time.sleep(0.05)  # 50ms update intervals

    def _fade_out(self) -> None:
        """Fade out the current display over ~2 seconds."""
        if not self.display:
            return

        fade_duration = 2.0
        start_time = time.time()
        initial_brightness = 100

        while time.time() - start_time < fade_duration:
            if self._stop_event.is_set():
                break

            elapsed = time.time() - start_time
            brightness = int(initial_brightness * (1 - elapsed / fade_duration))
            brightness = max(0, min(100, brightness))

            try:
                self.display.set_backlight(brightness)
            except (AttributeError, Exception):
                pass

            time.sleep(0.05)  # 50ms update intervals

        # Turn off display
        try:
            self.display.set_backlight(0)
        except (AttributeError, Exception):
            pass

    def cleanup(self) -> None:
        """
        Clean up display resources and stop display thread.
        """
        # Signal the thread to stop
        self._stop_event.set()

        # Wait for thread to finish (with timeout)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        # Turn off display
        if self.display:
            try:
                # Turn off backlight
                self.display.set_backlight(0)
            except (AttributeError, Exception):
                pass
            self.display = None
            self.display_available = False

    def add_to_display_cycle(
        self, render_func: Callable[[], "Image.Image"], duration: float
    ) -> None:
        """
        Add a display to the cycle queue (non-blocking).

        This allows you to queue multiple displays that will cycle through
        automatically. Each display shows for its specified duration.

        Args:
            render_func: Function to render sensor data as Image
            duration: Duration to show this display in seconds
        """
        self.update_sensor_display(render_func, duration)
