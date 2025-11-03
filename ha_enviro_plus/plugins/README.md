# Display Plugins

This directory (`ha_enviro_plus/plugins/`) contains user-created display plugins for ha-enviro-plus. Plugins in this directory will be automatically discovered and added to the display cycle.

## Default Plugin

The default sensor display (showing time/date, temperature, humidity, and pressure) is implemented as `SensorDisplayPlugin` in `ha_enviro_plus/display_plugins.py`. This plugin serves as the reference implementation and is automatically registered and available. It is defined in the base plugin system file, not in this directory.

## Plugin Architecture

Display plugins extend the `DisplayPlugin` base class and are automatically registered when imported. The system will:

1. Discover all available plugins
2. Filter plugins based on their `is_available()` method
3. Cycle through available plugins automatically
4. Handle errors gracefully with descriptive error messages

## Creating a Plugin

To create a new display plugin:

1. Create a new Python file in this directory
2. Import the necessary classes and functions
3. Create a class extending `DisplayPlugin`
4. Use the `@register_plugin` decorator
5. Implement the required methods

### Required Methods

- `name()` - Returns the plugin name (string)
- `is_available(sensors, settings)` - Returns True if the plugin can be displayed
- `render(sensors, settings)` - Returns a PIL Image (160x80 pixels)
- `duration()` - Returns display duration in seconds (float)

### Optional Methods

- `error_message(error)` - Generate a custom error message (default implementation provided)

## Example: Hello Enviro Plugin

Here's a simple "Hello Enviro" plugin example. This plugin is provided as `hello_enviro.py` in this directory but is **NOT registered by default** - it's just an example template.

To enable it, uncomment the `@register_plugin` decorator in `hello_enviro.py`.

```python
#!/usr/bin/env python3
"""
Hello Enviro - A simple example display plugin

This plugin demonstrates how to create a basic display plugin
that shows a greeting message.
"""

from ha_enviro_plus.display_plugins import DisplayPlugin, register_plugin

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@register_plugin  # Note: This is commented out in the actual file
class HelloEnviroPlugin(DisplayPlugin):
    """
    A simple "Hello Enviro" display plugin.

    This plugin serves as a template for creating your own display plugins.
    """

    def name(self) -> str:
        """Get the name of this plugin."""
        return "Hello Enviro"

    def is_available(self, sensors, settings) -> bool:
        """
        Check if this plugin can be displayed.

        This plugin is always available (no sensor requirements).
        """
        return True

    def duration(self) -> float:
        """Get display duration in seconds."""
        return 3.0  # Show for 3 seconds

    def render(self, sensors, settings):
        """
        Render the display screen.

        Creates a simple "Hello Enviro" message with a decorative icon.
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not available")

        # Create image (160x80 for ST7735 display)
        image = Image.new("RGB", (160, 80), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Try to load a font, fallback to default if unavailable
        try:
            font_large = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16
            )
            font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12
            )
        except (OSError, IOError):
            # Fallback to default font
            try:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            except Exception:
                font_large = None
                font_small = None

        # Draw "Hello Enviro" message
        # Center the text
        message = "Hello Enviro!"
        y_pos = 20

        # Draw with icon
        draw.text((10, y_pos), "👋", font=font_large, fill=(255, 255, 255))
        draw.text((30, y_pos), message, font=font_large, fill=(255, 255, 255))

        # Draw subtitle
        subtitle = "Custom Display"
        y_pos += 30
        draw.text((10, y_pos), subtitle, font=font_small, fill=(200, 200, 200))

        return image
```

## Plugin Registration

Plugins are automatically registered when they use the `@register_plugin` decorator. The decorator must be applied to a class that extends `DisplayPlugin`:

```python
from ha_enviro_plus.display_plugins import DisplayPlugin, register_plugin

@register_plugin
class MyPlugin(DisplayPlugin):
    # ... implementation ...
```

## Accessing Sensor Data

The `render()` method receives `sensors` and `settings` parameters:

- `sensors` - An `EnviroPlusSensors` instance with methods like:
  - `sensors.temp()` - Temperature in °C
  - `sensors.humidity()` - Humidity in %
  - `sensors.pressure()` - Pressure in hPa
  - `sensors.lux()` - Light level in lux
  - `sensors.has_sensor(sensor_type)` - Check if sensor is available

- `settings` - A `SettingsManager` instance with methods like:
  - `settings.get_units()` - Get units ("metric" or "imperial")
  - `settings.get_temp_offset()` - Get temperature offset
  - Other calibration settings

## Unit Conversion

Use the provided conversion functions for imperial units:

```python
from ha_enviro_plus.display_plugins import celsius_to_fahrenheit, hpa_to_inhg

units = settings.get_units()
if units == "imperial":
    temp_f = celsius_to_fahrenheit(sensors.temp())
    pressure_inhg = hpa_to_inhg(sensors.pressure())
```

## Error Handling

All plugin methods should handle errors gracefully. The system will:

- Catch exceptions during plugin instantiation
- Catch exceptions during availability checking
- Catch exceptions during rendering and show an error message
- Continue cycling through other plugins even if one fails

Implement error handling in your plugin:

```python
def render(self, sensors, settings):
    try:
        # Your rendering code
        if not sensors.has_sensor("bme280"):
            # Return a fallback image or raise an informative error
            pass
    except Exception as e:
        # Log the error (logger is available via self.logger)
        self.logger.error("Plugin error: %s", e)
        # Re-raise or return an error image
        raise
```

## Display Specifications

- **Image Size**: 160x80 pixels (RGB mode)
- **Color Format**: RGB tuples, e.g., `(255, 255, 255)` for white
- **Background**: Typically black `(0, 0, 0)`
- **Text Color**: White `(255, 255, 255)` or light gray `(200, 200, 200)`

## Best Practices

1. **Always check sensor availability** before reading sensor data
2. **Handle missing PIL gracefully** - check `PIL_AVAILABLE` or catch ImportError
3. **Provide meaningful error messages** - override `error_message()` if needed
4. **Use appropriate icons** - Unicode characters work well (🌡️, 💧, 📊, etc.)
5. **Show units** - Always display units (°C/°F, hPa/inHg, %, etc.)
6. **Keep duration reasonable** - 3-10 seconds is typical
7. **Test error cases** - Ensure your plugin handles missing sensors gracefully

## Plugin Discovery

Plugins are discovered automatically when the module is imported. To ensure your plugin is loaded, you may need to:

1. Import the plugin module explicitly in `__init__.py`, or
2. Ensure the plugin file is in the Python path and uses the `@register_plugin` decorator

The system will automatically:
- Discover all registered plugins
- Filter available plugins based on `is_available()`
- Cycle through available plugins
- Handle errors gracefully

## Example: Sensor Data Plugin

Here's a more complete example showing sensor data:

```python
@register_plugin
class MySensorPlugin(DisplayPlugin):
    def name(self) -> str:
        return "My Sensors"

    def is_available(self, sensors, settings) -> bool:
        # Only show if BME280 is available
        return sensors.has_sensor("bme280")

    def duration(self) -> float:
        return 5.0

    def render(self, sensors, settings):
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not available")

        image = Image.new("RGB", (160, 80), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Get units
        units = settings.get_units()

        # Read sensors
        if sensors.has_sensor("bme280"):
            temp = sensors.temp()
            if units == "imperial":
                temp = celsius_to_fahrenheit(temp)
                temp_str = f"{temp:.1f}°F"
            else:
                temp_str = f"{temp:.1f}°C"

            # Draw temperature
            draw.text((10, 10), f"🌡️ {temp_str}", fill=(255, 255, 255))

        return image
```

## Troubleshooting

If your plugin doesn't appear:

1. **Check registration** - Ensure you use `@register_plugin` decorator
2. **Check availability** - Verify `is_available()` returns True
3. **Check imports** - Ensure the plugin module is imported
4. **Check errors** - Look for error messages in logs
5. **Check PIL** - Ensure PIL/Pillow is available

## Display Cycle

The system automatically cycles through all available plugins:

1. Each plugin displays for its `duration()` seconds
2. After duration expires, the next plugin is shown
3. When all plugins have been shown, the cycle repeats
4. If a plugin fails, an error message is shown and the cycle continues

## See Also

- `ha_enviro_plus.display_plugins.SensorDisplayPlugin` - The default sensor display plugin (example implementation)
- `ha_enviro_plus.display_plugins.DisplayPlugin` - Base class documentation
- `ha_enviro_plus.sensors.EnviroPlusSensors` - Sensor API documentation
- `ha_enviro_plus.settings.SettingsManager` - Settings API documentation

