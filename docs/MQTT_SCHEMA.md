# MQTT Schema Documentation

This document describes the MQTT schema used by `ha-enviro-plus` for publishing sensor data and integrating with Home Assistant.

## Overview

The agent uses MQTT to publish sensor readings and device information, and implements Home Assistant's MQTT Discovery protocol for automatic device configuration. The schema is designed to support multiple devices with unique identification and location-based naming.

## Device Identification

### Device ID

The device ID is generated using the device's serial number (Home Assistant best practice):

- **Format**: `enviro_{serial_number}`
- **Example**: `enviro_1234567890abcdef`
- **Fallback**: If serial number is unavailable, uses `enviro_{hostname}` (with hyphens removed)

The device ID is used as the root topic prefix for all state and command topics.

### Device Location

You can configure a custom location/name for the device using the `DEVICE_LOCATION` environment variable:

```bash
export DEVICE_LOCATION="Living Room"
```

When set, the device name in Home Assistant will be `"Enviro+ Living Room"` instead of just `"Enviro+"`.

## Topic Structure

### Root Topic

All topics use the device ID as the root prefix:

```
{device_id}/
```

Example: `enviro_1234567890abcdef/`

### Availability Topic

The device publishes its availability status:

```
{device_id}/status
```

**Values**:
- `"online"` - Device is connected and operational
- `"offline"` - Device is disconnected

**QoS**: 1
**Retained**: Yes

### State Topics

Sensor readings are published to state topics with the format:

```
{device_id}/{sensor_path}
```

#### Sensor Paths

| Sensor Path | Description | Unit | Device Class | Example Value |
|------------|-------------|------|--------------|---------------|
| `bme280/temperature` | Temperature | °C | `temperature` | `22.5` |
| `bme280/humidity` | Humidity | % | `humidity` | `45.0` |
| `bme280/pressure` | Atmospheric Pressure | hPa | `atmospheric_pressure` | `1013.25` |
| `ltr559/lux` | Illuminance | lx | `illuminance` | `150.0` |
| `gas/oxidising` | Gas Oxidising Resistance | kΩ | None | `50.0` |
| `gas/reducing` | Gas Reducing Resistance | kΩ | None | `50.0` |
| `gas/nh3` | Gas NH3 Resistance | kΩ | None | `50.0` |
| `host/cpu_temp` | CPU Temperature | °C | `temperature` | `42.0` |
| `host/cpu_usage` | CPU Usage | % | None | `12.5` |
| `host/mem_usage` | Memory Usage | % | None | `45.2` |
| `host/mem_size` | Total Memory Size | GB | None | `1.0` |
| `host/uptime` | System Uptime | s | `duration` | `86400` |
| `host/hostname` | Hostname | None | None | `"raspberrypi"` |
| `host/network` | Network Address | None | None | `"192.168.1.100"` |
| `host/os_release` | OS Release | None | None | `"Raspberry Pi OS"` |
| `meta/last_update` | Last Update Timestamp | None | None | `"2024-01-15T10:30:00Z"` |

**Note**: If a sensor is not present, the value `"unavailable"` is published instead.

**QoS**: 1
**Retained**: Yes
**Change Detection**: Values are only published when they change (0.01 tolerance for floats)

### Command Topic

The device subscribes to commands:

```
{device_id}/cmd
```

**Commands**:
- `"reboot"` - Reboot the device
- `"shutdown"` - Shutdown the device
- `"restart_service"` - Restart the agent service
- `"reset_settings"` - Reset all settings to defaults

**QoS**: 1

### Settings Topics

Settings can be read and updated via MQTT:

```
{device_id}/set/{setting_name}
```

**Settings**:
- `temp_offset` - Temperature offset in °C (range: -10.0 to 10.0, step: 0.1)
- `hum_offset` - Humidity offset in % (range: -20.0 to 20.0, step: 0.5)
- `cpu_temp_factor` - CPU temperature compensation factor (range: 0.5 to 5.0, step: 0.1)
- `cpu_temp_smoothing` - CPU temperature smoothing factor (range: 0.01 to 1.0, step: 0.01)
- `temp_smoothing_minutes` - Temperature smoothing window in minutes (range: 0.0 to 60.0, step: 0.1)
- `pressure_offset` - Pressure offset in hPa (range: -10.0 to 10.0, step: 0.01)
- `elevation_meters` - Elevation in meters above sea level for sea-level pressure correction (range: 0.0 to 8848.0, step: 0.1)

**QoS**: 1
**Retained**: Yes

### Device Attributes Topic

Device metadata is published once:

```
{device_id}/device/attributes
```

**Payload** (JSON):
```json
{
  "model": "Raspberry Pi Zero W Rev 1.1",
  "serial": "1234567890abcdef"
}
```

**QoS**: 1
**Retained**: Yes

## Home Assistant Discovery

The agent implements Home Assistant's MQTT Discovery protocol to automatically register devices and entities.

### Discovery Prefix

The discovery prefix is configurable via `MQTT_DISCOVERY_PREFIX` (default: `"homeassistant"`).

### Discovery Topics

Discovery messages are published to:

```
{discovery_prefix}/{component}/{object_id}/{entity_id}/config
```

Where:
- `{component}` - Entity component type (`sensor`, `button`, `number`)
- `{object_id}` - Device identifier (e.g., `enviro_{serial_number}`)
- `{entity_id}` - Entity identifier (e.g., `bme280_temperature`)

**QoS**: 1
**Retained**: Yes

### Sensor Discovery

Each sensor publishes a discovery message with the following structure:

```json
{
  "name": "Temperature",
  "unique_id": "enviro_{serial}_bme280_temperature",
  "state_topic": "enviro_{serial}/bme280/temperature",
  "availability_topic": "enviro_{serial}/status",
  "unit_of_measurement": "°C",
  "device_class": "temperature",
  "state_class": "measurement",
  "device": {
    "identifiers": ["{serial_number}"],
    "connections": [["mac", "{mac_address}"]],
    "name": "Enviro+ {location}",
    "manufacturer": "Pimoroni",
    "model": "{device_model}",
    "sw_version": "ha-enviro-plus {version}",
    "configuration_url": "https://github.com/JeffLuckett/ha-enviro-plus"
  }
}
```

**Key Fields**:
- `unique_id` - Globally unique identifier (uses serial number)
- `state_topic` - Topic where sensor values are published
- `availability_topic` - Topic for device availability
- `device` - Device information for grouping entities

### Button Discovery

Control buttons are discovered as button entities:

```json
{
  "name": "Reboot Enviro Zero",
  "unique_id": "enviro_{serial}_btn_reboot",
  "cmd_t": "enviro_{serial}/cmd",
  "pl_prs": "reboot",
  "availability_topic": "enviro_{serial}/status",
  "device": { ... },
  "icon": "mdi:restart"
}
```

**Available Buttons**:
- `reboot` - Reboot device
- `shutdown` - Shutdown device
- `restart_service` - Restart agent service
- `reset_settings` - Reset settings to defaults

### Number Entity Discovery

Settings are exposed as number entities for easy adjustment in Home Assistant:

```json
{
  "name": "Temp Offset",
  "unique_id": "enviro_{serial}_num_temp_offset",
  "cmd_t": "enviro_{serial}/set/temp_offset",
  "stat_t": "enviro_{serial}/set/temp_offset",
  "availability_topic": "enviro_{serial}/status",
  "unit_of_measurement": "°C",
  "min": -10.0,
  "max": 10.0,
  "step": 0.1,
  "mode": "box",
  "device": { ... }
}
```

**Available Number Entities**:
- `temp_offset` - Temperature offset in °C (range: -10.0 to 10.0, step: 0.1)
- `hum_offset` - Humidity offset in % (range: -20.0 to 20.0, step: 0.5)
- `cpu_temp_factor` - CPU temperature compensation factor (range: 0.5 to 5.0, step: 0.1)
- `cpu_temp_smoothing` - CPU temperature smoothing factor (range: 0.01 to 1.0, step: 0.01)
- `temp_smoothing_minutes` - Temperature smoothing window in minutes (range: 0.0 to 60.0, step: 0.1)
- `pressure_offset` - Pressure offset in hPa (range: -10.0 to 10.0, step: 0.01)
- `elevation_meters` - Elevation in meters above sea level for sea-level pressure correction (range: 0.0 to 8848.0, step: 0.1)

## Device Information

### Device Identifiers

The device uses the following identifiers (in order of preference):

1. **Serial Number** - Primary identifier (Home Assistant best practice)
2. **Device ID** - Fallback if serial unavailable

### Device Connections

If available, the device's MAC address is included in the `connections` array:

```json
{
  "connections": [["mac", "aa:bb:cc:dd:ee:ff"]]
}
```

The MAC address is detected from the primary network interface (prefers wlan0, then eth0).

### Device Name

The device name follows this pattern:

- Without location: `"Enviro+"`
- With location: `"Enviro+ {DEVICE_LOCATION}"`

Example: `"Enviro+ Living Room"`

## Best Practices

The MQTT schema follows Home Assistant best practices:

1. **Unique Identification**: Uses serial number for `unique_id` and device `identifiers`
2. **MAC Address**: Includes MAC address in device `connections` for device tracking
3. **Change-Only Publishing**: Only publishes state changes to reduce network traffic
4. **Retained Messages**: All state and discovery messages are retained
5. **Availability Tracking**: Publishes availability status for device monitoring
6. **Device Grouping**: All entities are grouped under a single device in Home Assistant

## Example: Complete Topic Tree

For a device with serial `1234567890abcdef`:

```
enviro_1234567890abcdef/
├── status                          # Device availability
├── bme280/
│   ├── temperature                 # Temperature sensor
│   ├── humidity                    # Humidity sensor
│   └── pressure                    # Pressure sensor
├── ltr559/
│   └── lux                         # Illuminance sensor
├── gas/
│   ├── oxidising                   # Gas sensor
│   ├── reducing                    # Gas sensor
│   └── nh3                         # Gas sensor
├── host/
│   ├── cpu_temp                    # CPU temperature
│   ├── cpu_usage                   # CPU usage
│   ├── mem_usage                   # Memory usage
│   ├── mem_size                    # Memory size
│   ├── uptime                      # System uptime
│   ├── hostname                    # Hostname
│   ├── network                     # Network address
│   └── os_release                  # OS version
├── meta/
│   └── last_update                 # Last update timestamp
├── cmd                             # Command topic (subscribe)
├── set/
│   ├── temp_offset                 # Temperature offset setting
│   ├── hum_offset                  # Humidity offset setting
│   ├── cpu_temp_factor             # CPU temp factor setting
│   ├── cpu_temp_smoothing          # CPU temp smoothing setting
│   ├── temp_smoothing_minutes      # Temperature smoothing window setting
│   ├── pressure_offset             # Pressure offset setting (hPa)
│   └── elevation_meters             # Elevation for sea-level pressure correction (m)
└── device/
    └── attributes                  # Device metadata
```

## Configuration

### Environment Variables

The following environment variables affect the MQTT schema:

- `DEVICE_LOCATION` - Custom location/name for the device (e.g., `"Living Room"`)
- `MQTT_DISCOVERY_PREFIX` - Home Assistant discovery prefix (default: `"homeassistant"`)

### Example Configuration

```bash
# /etc/default/ha-enviro-plus
DEVICE_LOCATION="Living Room"
MQTT_DISCOVERY_PREFIX="homeassistant"
```

## Multiple Devices

The schema supports multiple devices on the same MQTT broker:

1. Each device is uniquely identified by its serial number
2. Each device has its own topic namespace (`enviro_{serial}/`)
3. Each device's entities have unique `unique_id` values
4. Home Assistant automatically groups entities by device identifier

Example with two devices:
- Device 1 (serial: `abc123`): `enviro_abc123/...`
- Device 2 (serial: `def456`): `enviro_def456/...`

Both devices can coexist without conflicts.

## Troubleshooting

### Device Not Appearing in Home Assistant

1. Check that `MQTT_DISCOVERY_PREFIX` matches your Home Assistant configuration
2. Verify the device is publishing to the availability topic
3. Check that discovery messages are being published (retained messages)
4. Ensure the serial number is being read correctly

### Entities Not Updating

1. Verify the device is publishing state changes (not just initial values)
2. Check that the state topic matches the discovery configuration
3. Ensure QoS 1 is being used for state messages
4. Verify the device is online (check availability topic)

### Duplicate Entities

1. Ensure each device has a unique serial number
2. Check that `unique_id` values are unique across devices
3. Verify device identifiers are properly set

## References

- [Home Assistant MQTT Integration](https://www.home-assistant.io/integrations/mqtt/)
- [Home Assistant MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)
- [Home Assistant Device Registry](https://developers.home-assistant.io/docs/device_registry_index/)
- [Home Assistant Entity Registry](https://developers.home-assistant.io/docs/entity_registry_index/)

