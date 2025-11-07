#!/usr/bin/env python3
"""
Display Management for Enviro+ LCD

This module provides display functionality for the ST7735 LCD display
on the Pimoroni Enviro+ and Enviro HAT.
"""

import time
import logging
import threading
from typing import Optional, Callable, TYPE_CHECKING, Any
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
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore


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

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        enabled: bool = True,
        auto_rotate: bool = True,
        rotation_interval: float = 10.0,
    ):
        """
        Initialize the display manager.

        Args:
            logger: Logger instance for display operations
            enabled: Whether display is enabled (from DISPLAY_ENABLED env var)
            auto_rotate: Whether to auto-rotate display plugins (from DISPLAY_AUTO_ROTATE env var)
            rotation_interval: Seconds between auto-rotations (from DISPLAY_ROTATION_INTERVAL env var)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.enabled = enabled
        self.display = None
        self.display_available = False

        # Threading control
        self._display_queue: list[DisplayItem] = []
        self._current_display: Optional[DisplayItem] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Plugin cycling control
        self._plugin_cycle_active = False
        self._plugin_cycle_plugins: list[Any] = []
        self._plugin_cycle_index = 0
        self._plugin_cycle_sensors: Optional[Any] = None
        self._plugin_cycle_settings: Optional[Any] = None
        self._auto_rotate = auto_rotate  # Enable auto-rotation by default
        self._rotation_interval = rotation_interval  # Seconds between auto-rotations (configurable)
        self._plugin_start_time: Optional[float] = None  # Track when current plugin started showing

        # Tap detection state
        # Proximity sensor baseline is ~30, max tap is ~1236
        # Threshold should be high to detect actual contact/near-contact
        self._proximity_baseline = 30  # Normal baseline value (no object detected)
        self._proximity_threshold = (
            1000  # Threshold for tap detection - detects near-contact (max ~1236)
        )
        self._proximity_last_value = 0.0
        self._proximity_last_change_time = 0.0
        self._tap_debounce_time = 0.1  # seconds between taps (reduced for responsiveness)
        self._proximity_high_time = 0.0
        self._proximity_high_threshold_time = (
            0.05  # minimum time proximity must be high (reduced for responsiveness)
        )

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

            # Clear display immediately to remove any old content from previous session
            # This prevents flashing of old content on startup
            if PIL_AVAILABLE:
                try:
                    black_image = Image.new("RGB", (160, 80), color=(0, 0, 0))
                    self.display.display(black_image)
                    self.logger.debug("Display: Cleared old content on startup")
                except Exception as e:
                    self.logger.debug("Display: Could not clear on startup: %s", e)

            # Clear any queued items and current display state to ensure clean startup
            with self._lock:
                self._display_queue.clear()
                self._current_display = None

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

        self.logger.info(
            "Splash: Queuing splash screen (duration=%.1fs, fade_duration=%.1fs)",
            duration,
            fade_duration,
        )

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
        self.logger.debug("Splash: Added to display queue")

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
        display_start_time: Optional[float] = None
        fade_out_start_time: Optional[float] = None

        while not self._stop_event.is_set():
            try:
                # Always check for new queued items first (for immediate tap response)
                # This ensures taps switch displays immediately
                with self._lock:
                    if self._display_queue and (
                        self._current_display is None
                        or self._current_display.duration < 0.5  # Continuous updates
                    ):
                        # If we have queued items and either no current display
                        # or current display is continuous (can be interrupted)
                        if self._current_display is not None:
                            # Interrupt current continuous display for new item
                            pass
                            self._current_display = self._display_queue.pop(0)
                            display_start_time = time.time()
                            fade_out_start_time = None
                        # Track plugin start time for rotation interval
                        if self._plugin_cycle_active:
                            self._plugin_start_time = time.time()
                        # Render the new display immediately
                        if self.display:
                            self.logger.debug(
                                "Display: Starting display (duration=%.1fs, fade_out=%s)",
                                self._current_display.duration,
                                self._current_display.fade_out,
                            )
                            self._render_display_immediate(self._current_display)
                        continue  # Skip rest of loop, process next iteration

                # Get next display item if we don't have one
                if self._current_display is None:
                    # No queued items, just sleep
                    time.sleep(0.1)
                    continue

                # If we have a current display, check if it should end
                if self._current_display is not None:
                    assert display_start_time is not None
                    elapsed = time.time() - display_start_time
                    # Use default 2.0s fade time (can be customized per item later)
                    fade_time = 2.0 if self._current_display.fade_out else 0

                    # Check rotation interval for auto-rotation (happens every loop iteration)
                    if (
                        self._plugin_cycle_active
                        and self._auto_rotate
                        and self._plugin_start_time is not None
                    ):
                        plugin_elapsed = time.time() - self._plugin_start_time
                        if plugin_elapsed >= self._rotation_interval:
                            # Time to rotate to next plugin
                            self.logger.debug(
                                "Rotation interval reached (%.1fs), advancing to next plugin",
                                plugin_elapsed,
                            )
                            self._advance_plugin_cycle()
                            # Clear current display to force next plugin
                            self._current_display = None
                            display_start_time = None
                            self._plugin_start_time = None  # Reset for next plugin
                            continue  # Skip rest of loop, get next plugin

                    # Handle fade out state
                    if fade_out_start_time is not None:
                        # We're in fade out phase
                        fade_elapsed = time.time() - fade_out_start_time
                        if fade_elapsed >= fade_time:
                            # Fade complete, turn off display and move to next
                            self.logger.info("Display: Fade complete, clearing display")
                            if self.display:
                                try:
                                    self.display.set_backlight(0)
                                    self.logger.debug("Display: Backlight turned off")
                                except (AttributeError, Exception) as e:
                                    self.logger.debug(
                                        "Display: Could not turn off backlight: %s", e
                                    )
                            self._current_display = None
                            display_start_time = None
                            fade_out_start_time = None
                            # Queue first plugin after splash completes
                            if self._plugin_cycle_active:
                                # Queue the first plugin (index 0) after splash
                                self._queue_next_plugin()
                        else:
                            # Continue fading
                            progress = fade_elapsed / fade_time
                            self._fade_out_step(progress)
                            if int(fade_elapsed * 10) % 10 == 0:  # Log every 0.1s
                                self.logger.debug(
                                    "Display: Fading (progress=%.1f%%, brightness=%d%%)",
                                    progress * 100,
                                    int(100 * (1 - progress)),
                                )
                    # Check if we should start fade out or update
                    elif elapsed >= (self._current_display.duration - fade_time):
                        if self._current_display.fade_out:
                            self.logger.info(
                                "Display: Starting fade-out (elapsed=%.1fs of %.1fs)",
                                elapsed,
                                self._current_display.duration,
                            )
                            fade_out_start_time = time.time()
                        else:
                            # For continuous updates (very short duration), update in place
                            if self._current_display.duration < 0.5:
                                # Re-render the current display without clearing
                                # (prevents blinking)
                                self._render_display_immediate(self._current_display)
                                display_start_time = time.time()  # Reset timer
                            else:
                                # Just turn off immediately for longer displays
                                self.logger.info("Display: Turning off (no fade)")
                                if self.display:
                                    try:
                                        self.display.set_backlight(0)
                                    except (AttributeError, Exception):
                                        pass
                                self._current_display = None
                                display_start_time = None
                                # Only queue next plugin automatically if auto-rotate is enabled
                                # Otherwise, plugins only advance on tap
                                if self._plugin_cycle_active and self._auto_rotate:
                                    self._queue_next_plugin()
                    else:
                        # For continuous displays, check for queued items more frequently
                        # This ensures taps are responded to immediately
                        if self._current_display.duration < 0.5:
                            # Check for queued items (tap might have happened)
                            with self._lock:
                                if self._display_queue:
                                    # Interrupt current display for queued item
                                    self._current_display = self._display_queue.pop(0)
                                    display_start_time = time.time()
                                    fade_out_start_time = None
                                    if self._plugin_cycle_active:
                                        self._plugin_start_time = time.time()
                                    if self.display:
                                        self.logger.debug(
                                            "Display: Starting display (duration=%.1fs, fade_out=%s)",
                                            self._current_display.duration,
                                            self._current_display.fade_out,
                                        )
                                        self._render_display_immediate(self._current_display)
                                    continue  # Skip sleep, process immediately

                # Small delay to prevent busy waiting
                # Use shorter sleep for continuous displays to improve tap responsiveness
                if self._current_display is not None and self._current_display.duration < 0.5:
                    time.sleep(0.01)  # 10ms for continuous displays - faster tap response
                else:
                    time.sleep(0.05)  # 50ms for other displays

            except Exception as e:
                self.logger.error("Error in display loop: %s", e)
                time.sleep(1)  # Wait before retrying

    def _render_display_immediate(self, display_item: DisplayItem) -> None:
        """
        Render a display item immediately without timing.

        Args:
            display_item: The display item to render
        """
        try:
            self.logger.debug("Display: Rendering image immediately")
            # Render the image
            image = display_item.render_func()

            # Display with fade in if requested
            if display_item.fade_in:
                self.logger.debug("Display: Using fade-in")
                self._fade_in(image)
            else:
                if self.display:
                    self.display.display(image)
                    try:
                        self.logger.debug("Display: Setting backlight to 100%")
                        self.display.set_backlight(100)  # Full brightness
                    except (AttributeError, Exception) as e:
                        self.logger.warning("Display: Could not set backlight: %s", e)

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

    def _fade_out_step(self, progress: float) -> None:
        """
        Update fade out brightness based on progress (0.0 to 1.0).

        Non-blocking fade out that's called incrementally from the loop.

        Args:
            progress: Progress from 0.0 (start) to 1.0 (complete)
        """
        if not self.display:
            return

        initial_brightness = 100
        brightness = int(initial_brightness * (1 - progress))
        brightness = max(0, min(100, brightness))

        try:
            self.display.set_backlight(brightness)
        except (AttributeError, Exception):
            pass

    def clear_display(self) -> None:
        """
        Clear the display by showing a black image.

        This ensures the display is blank before shutdown or before showing new content.
        """
        if not self.display_available or not self.display:
            return

        try:
            if PIL_AVAILABLE:
                # Create a black image and display it
                black_image = Image.new("RGB", (160, 80), color=(0, 0, 0))
                self.display.display(black_image)
                self.logger.debug("Display: Cleared with black image")
        except Exception as e:
            self.logger.debug("Display: Could not clear display: %s", e)

    def cleanup(self) -> None:
        """
        Clean up display resources and stop display thread.

        Ensures the display is cleared (black) before shutdown to prevent
        old content from flashing on next startup.
        """
        # Stop plugin cycle first to prevent new items from being queued
        with self._lock:
            self._plugin_cycle_active = False
            # Clear any queued items to prevent them from flashing
            self._display_queue.clear()
            self._current_display = None

        # Clear the display (show black image) - this ensures clean
        # shutdown and prevents old content from appearing on next startup
        self.clear_display()

        # Give the clear a moment to display before stopping thread
        if self.display_available:
            time.sleep(0.1)

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

    def start_plugin_cycle(self, plugins: list[Any]) -> None:
        """
        Start cycling through display plugins.

        The first plugin will be queued after the current display item
        (typically the splash screen) completes. This prevents plugins
        from flashing before the splash screen.

        Args:
            plugins: List of DisplayPlugin instances to cycle through
        """
        if not self.display_available:
            self.logger.debug("Plugin cycle skipped (display unavailable)")
            return

        if not plugins:
            self.logger.warning("No plugins available for cycling")
            return

        with self._lock:
            self._plugin_cycle_active = True
            self._plugin_cycle_plugins = plugins
            self._plugin_cycle_index = 0
            plugin_count = len(self._plugin_cycle_plugins)
            self.logger.info("Starting plugin cycle with %d plugin(s)", plugin_count)

        # Don't queue the first plugin immediately - wait for current display
        # (splash screen) to complete. The first plugin will be queued when
        # the splash screen finishes and advances the cycle.
        self.logger.debug("Plugin cycle ready - first plugin will queue after splash completes")

    def _queue_next_plugin(self) -> None:
        """Queue the next plugin in the cycle."""
        if not self._plugin_cycle_active:
            self.logger.debug("_queue_next_plugin: plugin cycle not active")
            return
        if not self._plugin_cycle_plugins:
            self.logger.debug("_queue_next_plugin: no plugins available")
            return

        with self._lock:
            if not self._plugin_cycle_plugins:
                self.logger.debug("_queue_next_plugin: no plugins in lock")
                return

            plugin = self._plugin_cycle_plugins[self._plugin_cycle_index]
            self.logger.debug(
                "Queueing plugin: %s (index %d)", plugin.name(), self._plugin_cycle_index
            )

            # Capture plugin at closure creation time
            def render_plugin() -> "Image.Image":
                """Render the current plugin with error handling."""
                try:
                    # Use current sensors and settings from display manager
                    current_sensors = self._plugin_cycle_sensors
                    current_settings = self._plugin_cycle_settings
                    if current_sensors is None or current_settings is None:
                        err_msg = f"{plugin.name()}: No sensor/settings data"
                        return self._create_error_image(err_msg)
                    return plugin.render(current_sensors, current_settings)
                except Exception as e:
                    self.logger.error("Plugin %s render error: %s", plugin.name(), e)
                    return self._create_error_image(plugin.error_message(e))

            # Use continuous updates (0.1s) for all plugins to prevent blinking
            # Auto-rotation is handled separately via rotation interval timer
            item = DisplayItem(
                duration=0.1,  # Continuous updates - prevents blinking
                render_func=render_plugin,
                fade_out=False,
                fade_in=False,
            )
            self._display_queue.append(item)

    def _create_error_image(self, message: str) -> "Image.Image":
        """
        Create an error message image.

        Args:
            message: Error message text

        Returns:
            PIL Image with error message

        Raises:
            RuntimeError: If PIL is not available
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not available")

        image = Image.new("RGB", (160, 80), color=(255, 0, 0))
        draw = ImageDraw.Draw(image)

        try:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            font = ImageFont.truetype(font_path, 10)
        except (OSError, IOError):
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None

        # Split message into lines if too long
        words = message.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line + " " + word) <= 20:  # Approx 20 chars per line
                current_line = current_line + " " + word if current_line else word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        # Draw error message
        y_pos = 10
        for line in lines[:5]:  # Max 5 lines
            draw.text((5, y_pos), line, font=font, fill=(255, 255, 255))
            y_pos += 15

        return image

    def show_error_message(self, message: str) -> None:
        """
        Queue an error message for display.

        Args:
            message: Error message text
        """
        if not self.display_available:
            return

        def render_error() -> "Image.Image":
            return self._create_error_image(message)

        with self._lock:
            item = DisplayItem(duration=3.0, render_func=render_error, fade_out=False)
            self._display_queue.append(item)

    def update_plugin_data(self, sensors: Any, settings: Any) -> None:
        """
        Update sensor and settings data for plugin rendering.

        This should be called periodically from the main loop to keep plugin
        data fresh.

        Args:
            sensors: EnviroPlusSensors instance
            settings: SettingsManager instance
        """
        with self._lock:
            if self._plugin_cycle_active:
                self._plugin_cycle_sensors = sensors
                self._plugin_cycle_settings = settings

    def _advance_plugin_cycle(self) -> None:
        """
        Advance to the next plugin in the cycle.

        This is called when a plugin display completes to move to the next one,
        or when rotation interval expires, or when tap is detected.
        """
        if not self._plugin_cycle_active or not self._plugin_cycle_plugins:
            return

        with self._lock:
            self._plugin_cycle_index = (self._plugin_cycle_index + 1) % len(
                self._plugin_cycle_plugins
            )
            self.logger.debug("Advancing plugin cycle to index %d", self._plugin_cycle_index)
            # Reset plugin start time for rotation interval tracking
            self._plugin_start_time = None

        # Queue next plugin (outside lock to avoid reentrant lock issue)
        self._queue_next_plugin()

    def check_proximity_tap(self, proximity_value: float) -> bool:
        """
        Check if proximity sensor indicates a tap gesture.

        Tap detection logic:
        - Proximity value rises above threshold (object detected, > baseline)
        - Proximity value stays high for minimum time
        - Tap is detected immediately when threshold is met (no need to wait for low)
        - Debounce: ignore taps within debounce time window
        - Supports rapid taps while hovering (doesn't require return to baseline)

        Note: Proximity sensor baseline is ~30, max tap is ~1236.
        Threshold is set to 1000 to detect actual contact/near-contact taps.

        Args:
            proximity_value: Current proximity reading (baseline ~30, max ~1236)

        Returns:
            True if tap detected, False otherwise
        """
        if not self._plugin_cycle_active:
            return False

        current_time = time.time()
        # Detect when proximity rises significantly above baseline
        proximity_high = proximity_value > self._proximity_threshold
        # Detect when proximity returns to near baseline
        proximity_low = proximity_value <= (self._proximity_baseline + 20)

        # Track when proximity goes high (above threshold)
        if proximity_high and self._proximity_last_value <= self._proximity_threshold:
            # Proximity just went high - start tracking
            self._proximity_high_time = current_time

        # Detect tap when proximity has been high for minimum time
        # This allows immediate tap detection without waiting for return to baseline
        if (
            proximity_high
            and self._proximity_high_time > 0
            and self._proximity_last_value > self._proximity_threshold
        ):
            # Proximity is currently high and has been high for a while
            high_duration = current_time - self._proximity_high_time

            # Check debounce: ignore taps too close together
            time_since_last_change = current_time - self._proximity_last_change_time

            if (
                high_duration >= self._proximity_high_threshold_time
                and time_since_last_change >= self._tap_debounce_time
            ):
                # Valid tap detected - proximity has been high long enough
                self._proximity_last_change_time = current_time
                # Reset high time to allow detecting another tap while still hovering
                self._proximity_high_time = current_time
                return True

        # Reset tracking when proximity goes low
        if proximity_low and self._proximity_high_time > 0:
            # Proximity returned to baseline - reset tracking
            self._proximity_high_time = 0.0

        # Update last value
        self._proximity_last_value = proximity_value

        return False

    def handle_tap(self) -> None:
        """
        Handle tap gesture by immediately switching to next plugin in cycle.

        This method should be called when a tap is detected.
        """
        if not self._plugin_cycle_active:
            return

        # Clear current display and queue FIRST to force immediate switch
        with self._lock:
            self._current_display = None
            self._display_queue.clear()
            # Reset plugin start time for rotation interval tracking
            self._plugin_start_time = None
        # THEN advance to next plugin (this will queue it)
        self._advance_plugin_cycle()
