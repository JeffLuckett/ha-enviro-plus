# Code Review: Python Best Practices & Improvements

## Overview

This document identifies opportunities for improvement in the codebase to align with Python best practices, improve readability, terseness, and separation of concerns.

## Key Issues Identified

### 1. **agent.py - Excessive File Size & Mixed Responsibilities** ⚠️ HIGH PRIORITY

**Current State**: 1000+ lines mixing multiple concerns

**Issues**:
- Configuration loading at module level (hard to test, tight coupling)
- System info functions mixed with MQTT logic
- Discovery logic mixed with main loop
- Large functions that do multiple things

**Recommendations**:

#### 1.1 Extract Configuration Class
```python
# ha_enviro_plus/config.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    """Application configuration loaded from environment."""
    mqtt_host: str = "homeassistant.local"
    mqtt_port: int = 1883
    mqtt_user: str = ""
    mqtt_pass: str = ""
    mqtt_discovery_prefix: str = "homeassistant"
    poll_sec: float = 2.0
    temp_offset: float = 0.0
    hum_offset: float = 0.0
    cpu_temp_factor: float = 1.8
    cpu_temp_smoothing: float = 0.1
    temp_smoothing_minutes: float = 5.0
    display_enabled: bool = True
    sensor_warmup_sec: float = 2.0
    units: str = "metric"
    device_location: str = ""
    log_to_file: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        def _get(key: str, default: str) -> str:
            return os.getenv(key, default)

        return cls(
            mqtt_host=_get("MQTT_HOST", "homeassistant.local"),
            mqtt_port=int(_get("MQTT_PORT", "1883")),
            # ... etc
        )
```

#### 1.2 Extract System Info Module
```python
# ha_enviro_plus/system_info.py
"""System information gathering utilities."""
# Move all get_* functions here
```

#### 1.3 Extract MQTT Discovery Module
```python
# ha_enviro_plus/mqtt_discovery.py
"""MQTT discovery payload generation."""
# Move publish_discovery, disc_payload, discovery helpers here
```

#### 1.4 Extract MQTT Handlers Module
```python
# ha_enviro_plus/mqtt_handlers.py
"""MQTT message handlers."""
# Move _handle_command, _handle_calibration_setting, on_connect, on_message here
```

### 2. **settings.py - Repetitive Getter/Setter Methods** ⚠️ MEDIUM PRIORITY

**Current State**: Many repetitive getter/setter pairs

**Issues**:
- 14 getter/setter methods for 7 settings
- Repetitive code that could use a descriptor or property pattern

**Recommendations**:

#### Option A: Use Properties with Descriptors
```python
class SettingDescriptor:
    """Descriptor for settings with type conversion."""
    def __init__(self, key: str, type_converter=float):
        self.key = key
        self.type_converter = type_converter

    def __get__(self, obj: "SettingsManager", objtype=None):
        value = obj.get_setting(self.key)
        return self.type_converter(value) if value is not None else self.type_converter()

    def __set__(self, obj: "SettingsManager", value):
        obj.set_setting(self.key, value)

class SettingsManager:
    temp_offset = SettingDescriptor("temp_offset", float)
    hum_offset = SettingDescriptor("hum_offset", float)
    cpu_temp_factor = SettingDescriptor("cpu_temp_factor", float)
    cpu_temp_smoothing = SettingDescriptor("cpu_temp_smoothing", float)
    temp_smoothing_minutes = SettingDescriptor("temp_smoothing_minutes", float)
    units = SettingDescriptor("units", str)

    # Remove all get_*/set_* methods
```

#### Option B: Use a Registry Pattern
```python
class SettingsManager:
    _SETTING_TYPES = {
        "temp_offset": float,
        "hum_offset": float,
        "cpu_temp_factor": float,
        "cpu_temp_smoothing": float,
        "temp_smoothing_minutes": float,
        "units": str,
    }

    def __getattr__(self, name: str):
        if name.startswith("get_") and name[4:] in self._SETTING_TYPES:
            key = name[4:]
            return lambda: self._get_typed_setting(key)
        elif name.startswith("set_") and name[4:] in self._SETTING_TYPES:
            key = name[4:]
            return lambda value: self.set_setting(key, value)
        raise AttributeError(f"{name} not found")

    def _get_typed_setting(self, key: str):
        value = self.get_setting(key)
        converter = self._SETTING_TYPES[key]
        return converter(value) if value is not None else converter()
```

### 3. **sensors.py - Repetitive Sensor Reading Code** ⚠️ MEDIUM PRIORITY

**Current State**: Many similar methods for reading sensors

**Issues**:
- `temp()`, `temp_raw()`, `humidity()`, `humidity_raw()`, `pressure()`, `pressure_raw()`, etc. all follow similar patterns
- Repetitive error handling

**Recommendations**:

#### Extract Common Reading Pattern
```python
def _read_sensor_value(
    self,
    sensor_name: str,
    sensor_obj: Optional[Any],
    method_name: str,
    fallback: float = 0.0,
    process_func: Optional[Callable[[float], float]] = None,
) -> float:
    """Generic sensor reading with error handling."""
    if sensor_obj is None:
        self.logger.debug(f"{sensor_name} unavailable: not initialized")
        return fallback

    try:
        method = getattr(sensor_obj, method_name)
        value = float(method())
        if process_func:
            value = process_func(value)
        return round(value, 2)
    except Exception as e:
        self.logger.error(f"Failed to read {sensor_name}: {e}")
        self.logger.info(f"{sensor_name} will be reported as {fallback}")
        return fallback

def temp(self) -> float:
    """Get compensated, calibrated, and smoothed temperature."""
    return self._read_sensor_value(
        "temperature",
        self.bme280,
        "get_temperature",
        process_func=lambda raw: self._get_smoothed_temp(
            self._apply_temp_compensation(raw) + self.temp_offset
        ),
    )

def temp_raw(self) -> float:
    """Get raw temperature reading."""
    return self._read_sensor_value("temperature", self.bme280, "get_temperature")
```

### 4. **agent.py - Magic Numbers & Constants** ⚠️ LOW PRIORITY

**Issues**:
- Magic numbers scattered throughout (e.g., `0.01` tolerance, `17` for MAC length)
- Hard-coded values in multiple places

**Recommendations**:
```python
# ha_enviro_plus/constants.py
class Constants:
    """Application-wide constants."""
    # Network
    MAC_ADDRESS_LENGTH = 17
    PREFERRED_INTERFACES = ["wlan0", "eth0"]

    # MQTT
    MQTT_QOS_DISCOVERY = 1
    MQTT_QOS_STATE = 1
    MQTT_RETAIN_DISCOVERY = True
    MQTT_RETAIN_STATE = True

    # Value comparison
    FLOAT_TOLERANCE = 0.01

    # Temperature
    DEFAULT_CPU_TEMP = 40.6  # Pi Zero typical temp in °C

    # File paths
    SETTINGS_DIR = Path("/var/lib/ha-enviro-plus")
    LOG_PATH = Path("/var/log/ha-enviro-plus.log")
```

### 5. **agent.py - read_all() Function** ⚠️ MEDIUM PRIORITY

**Current State**: Repetitive sensor availability checks

**Issues**:
- Repetitive if/else blocks for each sensor type
- Could use a more data-driven approach

**Recommendations**:
```python
def read_all(enviro_sensors: EnviroPlusSensors) -> Dict[str, Any]:
    """Read all sensor and system data."""
    sensor_data = enviro_sensors.get_all_sensor_data()

    # Define sensor mappings
    SENSOR_MAPPINGS = {
        "bme280": {
            "sensor_key": "bme280",
            "fields": ["temperature", "humidity", "pressure"],
        },
        "ltr559": {
            "sensor_key": "ltr559",
            "fields": ["lux"],
        },
        "gas": {
            "sensor_key": "gas",
            "fields": ["gas_oxidising", "gas_reducing", "gas_nh3"],
        },
    }

    vals = {
        "host/cpu_temp": round(enviro_sensors.cpu_temp(), 1),
        "host/cpu_usage": round(psutil.cpu_percent(interval=None), 1),
        "host/mem_usage": round(mem.percent, 1),
        "host/mem_size": round(mem.total / 1024 / 1024 / 1024, 3),
        "host/uptime": get_uptime_seconds(),
        "host/hostname": str(hostname),
        "host/network": get_ipv4_prefer_wlan0(),
        "host/os_release": get_os_release(),
        "meta/last_update": datetime.now(timezone.utc).isoformat(),
    }

    # Add sensor data using mapping
    for sensor_type, mapping in SENSOR_MAPPINGS.items():
        prefix = mapping["sensor_key"]
        if enviro_sensors.has_sensor(sensor_type):
            for field in mapping["fields"]:
                vals[f"{prefix}/{field}"] = sensor_data[field]
        else:
            for field in mapping["fields"]:
                vals[f"{prefix}/{field}"] = "unavailable"

    return vals
```

### 6. **Type Hints Improvements** ⚠️ LOW PRIORITY

**Issues**:
- Some functions use `Any` where more specific types could be used
- Missing type hints for some return values

**Recommendations**:
- Replace `Any` with more specific types where possible
- Use `Protocol` for duck typing where appropriate
- Add return type hints to all public methods

### 7. **Error Handling - Too Broad Exception Catching** ⚠️ MEDIUM PRIORITY

**Issues**:
- Many `except Exception:` blocks that could be more specific
- Some functions catch exceptions but don't provide enough context

**Recommendations**:
```python
# Instead of:
except Exception as e:
    logger.error("Failed to read sensor: %s", e)

# Use:
except (ValueError, IOError, AttributeError) as e:
    logger.error("Failed to read sensor %s: %s", sensor_name, e, exc_info=True)
```

### 8. **Documentation Improvements** ⚠️ LOW PRIORITY

**Issues**:
- Some docstrings could be more concise
- Missing type information in some docstrings

**Recommendations**:
- Use Google-style docstrings consistently
- Add examples for complex functions
- Document side effects where applicable

## Priority Summary

### High Priority (Do First)
1. **Extract Configuration Class** - Makes testing easier and reduces coupling
2. **Split agent.py** - Break into logical modules (config, system_info, mqtt_discovery, mqtt_handlers)

### Medium Priority (Do Next)
3. **Simplify SettingsManager** - Remove repetitive getter/setter methods
4. **Simplify sensor reading** - Extract common patterns
5. **Improve read_all()** - Use data-driven approach
6. **Specific exception handling** - Replace broad Exception catches

### Low Priority (Nice to Have)
7. **Extract constants** - Move magic numbers to constants file
8. **Improve type hints** - Replace Any with specific types
9. **Documentation polish** - Enhance docstrings

## Implementation Strategy

1. **Start with Configuration Class** - This will enable other refactorings
2. **Extract System Info** - Low risk, clear separation
3. **Extract MQTT Modules** - Medium risk, needs careful testing
4. **Simplify SettingsManager** - Medium risk, ensure backward compatibility
5. **Refactor sensor reading** - Lower risk, internal improvements
6. **Polish** - Constants, type hints, documentation

## Testing Considerations

- All refactorings should maintain 100% test coverage
- Focus on integration tests after major refactorings
- Ensure backward compatibility for public APIs

