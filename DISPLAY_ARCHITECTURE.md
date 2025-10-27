# Non-Blocking Display Architecture

## Overview

The display system has been refactored to be **completely non-blocking**, allowing the application to continue operating (polling sensors, publishing to MQTT, etc.) while managing display updates in the background.

## Key Features

### 1. Threaded Display Manager
- Displays run in a **background thread** (daemon thread)
- Main application loop is never blocked by display operations
- Thread starts automatically when display is initialized

### 2. Display Queue System
- Queue multiple displays to cycle through automatically
- Each display has its own timing and duration
- Supports fade in/out effects
- Thread-safe with proper locking

### 3. Non-Blocking API

#### Splash Screen (Non-Blocking)
```python
display.show_splash(duration=8, fade_duration=2)
# Returns immediately, doesn't block
```

#### Queue Sensor Displays (Non-Blocking)
```python
def render_temp():
    # Create image with temperature reading
    pass

display.update_sensor_display(render_temp, duration=5)
# Returns immediately, displays in background
```

#### Add Multiple Displays for Cycling
```python
display.add_to_display_cycle(render_temp, duration=5)
display.add_to_display_cycle(render_humidity, duration=5)
display.add_to_display_cycle(render_pressure, duration=5)
# All displays will cycle through automatically
```

## Future Usage Pattern

You can now create real-time sensor displays that update while your main loop continues:

```python
# In your main loop (after splash)
try:
    while True:
        vals = read_all(enviro_sensors)

        # Update MQTT
        for tail, val in vals.items():
            client.publish(f"{root}/{tail}", str(val), retain=True)

        # Optionally update display with latest sensor data
        if display:
            def render_current():
                # Create image showing current sensor readings
                pass
            display.update_sensor_display(render_current, duration=2)

        time.sleep(POLL_SEC)
except KeyboardInterrupt:
    # cleanup handled automatically
    pass
```

## Changes Made

1. **DisplayManager** (`ha_enviro_plus/display.py`):
   - Added threading support with background display loop
   - Implemented display queue system
   - Added thread-safe operations with locks
   - All display operations now return immediately

2. **Agent** (`ha_enviro_plus/agent.py`):
   - Updated to use non-blocking splash screen
   - Added display cleanup to signal handlers
   - Prepared for future sensor display integration

## Configuration

- **Warmup**: Shortened from 5s to 2s (configurable via `SENSOR_WARMUP_SEC`)
- **Splash Duration**: Now 8 seconds (configurable in `show_splash()` call)

## Benefits

1. **Non-blocking**: Main application loop never waits for display operations
2. **Flexible**: Easy to add multiple display pages
3. **Future-ready**: Ready for cycling through multiple sensor displays
4. **Thread-safe**: Proper locking prevents race conditions
5. **Graceful degradation**: Works even if display hardware fails

## Example: Adding Real-Time Sensor Display

```python
# Define your render function
def create_sensor_display(sensor_data):
    def render():
        # Create PIL Image with sensor data
        img = Image.new("RGB", (160, 80), color=(0, 0, 0))
        # Draw temperature, humidity, etc.
        return img
    return render

# In main loop:
if display and display.display_available:
    sensor_renderer = create_sensor_display(vals)
    display.add_to_display_cycle(sensor_renderer, duration=5)
```

## Thread Management

- Display thread is automatically started when DisplayManager is initialized
- Thread is daemonized (won't prevent application shutdown)
- Thread is properly stopped during cleanup
- All cleanup happens in signal handlers for graceful shutdown

