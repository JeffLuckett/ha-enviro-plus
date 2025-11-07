#!/usr/bin/env python3
"""
Main MQTT agent for Home Assistant integration.

This module provides the main application loop that reads sensors,
publishes to MQTT, and handles commands from Home Assistant.
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psutil
import paho.mqtt.client as mqtt

from . import __version__
from .config import Config
from .constants import Constants
from .display import DisplayManager
from .display_plugins import get_available_plugins
from .sensors import EnviroPlusSensors
from .settings import SettingsManager
from .system_info import (
    get_device_id,
    get_device_info,
    get_model,
    get_serial,
)

APP_NAME = "ha-enviro-plus"
VERSION = __version__

# Initialize device ID and topic root
device_id = get_device_id()
root = device_id  # topic root for states & commands
avail_t = f"{root}/status"
cmd_t = f"{root}/cmd"  # expects: reboot|shutdown|restart
set_t = f"{root}/set/+"  # retained settings, e.g. set/temp_offset


# ---------- logging ----------
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
handlers: List[logging.Handler] = [logging.StreamHandler()]
# Logging will be configured in main() with config
# ----------------------------

# Note: DEVICE_INFO is now a function call, not a constant
# This ensures device info is refreshed with current location/serial/etc
# Individual discovery payloads call get_device_info() directly

SENSORS = {
    "bme280/temperature": ("Temperature", "°C", "temperature"),
    "bme280/humidity": ("Humidity", "%", "humidity"),
    "bme280/pressure": ("Pressure", "hPa", "atmospheric_pressure"),
    "ltr559/lux": ("Illuminance", "lx", "illuminance"),
    "ltr559/proximity": ("Proximity", None, None),
    "gas/oxidising": ("Gas Oxidising (kΩ)", "kΩ", None),
    "gas/reducing": ("Gas Reducing (kΩ)", "kΩ", None),
    "gas/nh3": ("Gas NH3 (kΩ)", "kΩ", None),
    "noise/spl_db": ("Noise Level", "dB(A)", None),
    "noise/spl_raw": ("Noise Level Raw", None, None),
    "host/cpu_temp": ("CPU Temp", "°C", "temperature"),
    "host/cpu_usage": ("CPU Usage", "%", None),
    "host/mem_usage": ("Mem Usage", "%", None),
    "host/mem_size": ("Mem Size", "GB", None),
    "host/uptime": ("Uptime", "s", "duration"),
    "host/hostname": ("Host Name", None, None),
    "host/network": ("Network Address", None, None),
    "host/os_release": ("OS Release", None, None),
    "meta/last_update": ("Last Update", None, None),
}


def disc_payload(
    topic_tail: str,
    name: str,
    unit: Optional[str],
    device_class: Optional[str] = None,
    state_class: Optional[str] = "measurement",
    icon: Optional[str] = None,
    config: Optional[Config] = None,
) -> Dict[str, Any]:
    """
    Create discovery payload for Home Assistant MQTT integration.

    Args:
        topic_tail: Sensor topic path (e.g., "bme280/temperature")
        name: Display name for the sensor
        unit: Unit of measurement (e.g., "°C", "%")
        device_class: Device class (e.g., "temperature", "humidity")
        state_class: State class (default: "measurement")
        icon: Optional icon name
        config: Optional Config instance for device location

    Returns:
        Dictionary with discovery configuration
    """
    # Use serial number for unique_id if available (HA best practice)
    serial = get_serial()
    if serial and serial != "unknown":
        uniq_id = f"enviro_{serial}_{topic_tail.replace('/', '_')}"
    else:
        # Fallback to device_id
        uniq_id = f"{device_id}_{topic_tail.replace('/', '_')}"

    # Get device info with location if config provided
    device_location = config.device_location if config else ""
    device_info_dict = get_device_info(device_location, APP_NAME, VERSION)

    cfg = {
        "name": name,
        "uniq_id": uniq_id,
        "state_topic": f"{root}/{topic_tail}",
        "availability_topic": avail_t,
        "device": device_info_dict,
    }
    if unit:
        cfg["unit_of_measurement"] = unit
    if device_class:
        cfg["device_class"] = device_class
    if state_class:
        cfg["state_class"] = state_class
    if icon:
        cfg["icon"] = icon
    return cfg


def publish_discovery(
    c: mqtt.Client,
    config: Config,
    enviro_sensors: Optional[EnviroPlusSensors] = None,
) -> None:
    """
    Publish MQTT discovery payloads for all sensors.

    Args:
        c: MQTT client
        config: Config instance
        enviro_sensors: Optional sensors instance for availability checking
    """
    # Use serial number for object_id if available (for topic consistency)
    serial = get_serial()
    if serial and serial != "unknown":
        obj_id = f"enviro_{serial}"
    else:
        obj_id = device_id

    # Get device info with location
    device_info_dict = get_device_info(config.device_location, APP_NAME, VERSION)

    for tail, (name, unit, devcls) in SENSORS.items():
        # Check if sensor is available
        if enviro_sensors is not None:
            # Skip gas sensors if not available
            if tail.startswith("gas/") and not enviro_sensors.has_sensor("gas"):
                continue
            # Skip BME280 sensors if not available
            if tail.startswith("bme280/") and not enviro_sensors.has_sensor("bme280"):
                continue
            # Skip LTR559 sensors if not available
            if tail.startswith("ltr559/") and not enviro_sensors.has_sensor("ltr559"):
                continue
            # Skip noise sensors if not available
            if tail.startswith("noise/") and not enviro_sensors.has_sensor("noise"):
                continue

        obj = tail.replace("/", "_")
        topic = f"{config.mqtt_discovery_prefix}/sensor/{obj_id}/{obj}/config"
        # For text sensors (no unit), don't set state_class
        state_class = None if unit is None else "measurement"
        # Update device info in payload
        payload = disc_payload(tail, name, unit, devcls, state_class, config=config)
        # Device info already set in disc_payload, but ensure it's correct
        payload["device"] = device_info_dict
        c.publish(
            topic,
            json.dumps(payload),
            qos=Constants.MQTT_QOS_DISCOVERY,
            retain=Constants.MQTT_RETAIN_DISCOVERY,
        )

    # controls: simple button commands
    def button(topic_key: str, name: str, icon: str) -> None:
        # Use serial number for unique_id if available
        serial = get_serial()
        if serial and serial != "unknown":
            uniq_id = f"enviro_{serial}_btn_{topic_key}"
            obj_id = f"enviro_{serial}"
        else:
            uniq_id = f"{device_id}_btn_{topic_key}"
            obj_id = device_id

        cfg = {
            "name": name,
            "uniq_id": uniq_id,
            "cmd_t": f"{root}/cmd",
            "pl_prs": topic_key,
            "availability_topic": avail_t,
            "device": get_device_info(config.device_location, APP_NAME, VERSION),
            "icon": icon,
        }
        topic = f"{config.mqtt_discovery_prefix}/button/{obj_id}/{topic_key}/config"
        c.publish(
            topic,
            json.dumps(cfg),
            qos=Constants.MQTT_QOS_DISCOVERY,
            retain=Constants.MQTT_RETAIN_DISCOVERY,
        )

    button("reboot", "Reboot Enviro Zero", "mdi:restart")
    button("shutdown", "Shutdown Enviro Zero", "mdi:power")
    button("restart_service", "Restart Agent", "mdi:refresh")
    button("reset_settings", "Reset Settings to Defaults", "mdi:restore")

    # number entities for offsets (so HA shows exact values)
    def number(
        name: str, key: str, unit: Optional[str], minv: float, maxv: float, step: float
    ) -> None:
        # Use serial number for unique_id if available
        serial = get_serial()
        if serial and serial != "unknown":
            uniq_id = f"enviro_{serial}_num_{key}"
            obj_id = f"enviro_{serial}"
        else:
            uniq_id = f"{device_id}_num_{key}"
            obj_id = device_id

        cfg = {
            "name": name,
            "uniq_id": uniq_id,
            "cmd_t": f"{root}/set/{key}",
            "stat_t": f"{root}/set/{key}",
            "availability_topic": avail_t,
            "device": get_device_info(config.device_location, APP_NAME, VERSION),
            "unit_of_measurement": unit,
            "min": minv,
            "max": maxv,
            "step": step,
            "mode": "box",
        }
        topic = f"{config.mqtt_discovery_prefix}/number/{obj_id}/{key}/config"
        c.publish(
            topic,
            json.dumps(cfg),
            qos=Constants.MQTT_QOS_DISCOVERY,
            retain=Constants.MQTT_RETAIN_DISCOVERY,
        )

    number("Temp Offset", "temp_offset", "°C", -10, 10, 0.1)
    number("Humidity Offset", "hum_offset", "%", -20, 20, 0.5)
    number("CPU Temp Factor", "cpu_temp_factor", None, 0.5, 5.0, 0.1)
    number("CPU Temp Smoothing", "cpu_temp_smoothing", None, 0.01, 1.0, 0.01)
    number("Temp Smoothing Window", "temp_smoothing_minutes", "min", 0.0, 60.0, 0.1)
    number("Pressure Offset", "pressure_offset", "hPa", -10.0, 10.0, 0.01)
    number("Elevation", "elevation_meters", "m", 0.0, 8848.0, 0.1)  # 0 to Mount Everest


def read_all(enviro_sensors: EnviroPlusSensors) -> Dict[str, Any]:
    """
    Read all sensor and system data using the EnviroPlusSensors class.

    Returns a dictionary with all sensor readings, using "unavailable" for
    missing sensors to ensure Home Assistant knows about all sensors.
    """
    from .system_info import (
        get_uptime_seconds,
        get_ipv4_prefer_wlan0,
        get_os_release,
        get_hostname,
    )

    # Get sensor data from the encapsulated sensor manager
    sensor_data = enviro_sensors.get_all_sensor_data()

    # Get system metrics
    mem = psutil.virtual_memory()

    # Define sensor mappings for data-driven approach
    SENSOR_MAPPINGS = {
        "bme280": {
            "sensor_key": "bme280",
            "fields": ["temperature", "humidity", "pressure"],
        },
        "ltr559": {
            "sensor_key": "ltr559",
            "fields": ["lux", "proximity"],
        },
        "gas": {
            "sensor_key": "gas",
            "fields": ["oxidising", "reducing", "nh3"],
        },
        "noise": {
            "sensor_key": "noise",
            "fields": ["spl_db", "spl_raw"],
        },
    }

    # Build values dictionary with system metrics
    vals = {
        # System metrics (always available)
        "host/cpu_temp": round(enviro_sensors.cpu_temp(), 1),
        "host/cpu_usage": round(psutil.cpu_percent(interval=None), 1),
        "host/mem_usage": round(mem.percent, 1),
        "host/mem_size": round(mem.total / 1024 / 1024 / 1024, 3),
        "host/uptime": get_uptime_seconds(),
        "host/hostname": get_hostname(),
        "host/network": get_ipv4_prefer_wlan0(),
        "host/os_release": get_os_release(),
        "meta/last_update": datetime.now(timezone.utc).isoformat(),
    }

    # Add sensor data using mapping (data-driven approach)
    for sensor_type, mapping in SENSOR_MAPPINGS.items():
        prefix = mapping["sensor_key"]
        if enviro_sensors.has_sensor(sensor_type):
            for field in mapping["fields"]:
                # For gas sensors, map topic field name to sensor data key
                # Topic: gas/oxidising -> Sensor data key: gas_oxidising
                # For noise sensors, map topic field name to sensor data key
                # Topic: noise/spl_db -> Sensor data key: noise_spl_db
                # For ltr559, most fields map directly, but proximity is just "proximity"
                if sensor_type == "gas":
                    sensor_data_key = f"{prefix}_{field}"
                elif sensor_type == "noise":
                    sensor_data_key = f"{prefix}_{field}"
                elif sensor_type == "ltr559" and field == "proximity":
                    sensor_data_key = "proximity"
                else:
                    sensor_data_key = field
                vals[f"{prefix}/{field}"] = sensor_data[sensor_data_key]
        else:
            for field in mapping["fields"]:
                vals[f"{prefix}/{field}"] = "unavailable"

    return vals


def on_connect(
    client: mqtt.Client,
    userdata: Any,
    flags: Any,
    rc: int,
    properties: Any = None,
    config: Optional[Config] = None,
) -> None:
    """
    Handle MQTT connection callback.

    Args:
        client: MQTT client
        userdata: User data containing config, sensors, settings_manager
        flags: Connection flags
        rc: Return code
        properties: MQTT properties (optional)
        config: Config instance (optional, may be in userdata)
    """
    # Get config from userdata if not provided
    if config is None and userdata:
        config = userdata.get("config")

    if config is None:
        # Fallback: create config from env (shouldn't happen in normal flow)
        config = Config.from_env()

    logger.info(
        "Connected to MQTT (%s:%s) RC=%s",
        config.mqtt_host,
        config.mqtt_port,
        mqtt.connack_string(rc),
    )
    client.publish(avail_t, "online", retain=Constants.MQTT_RETAIN_STATE)
    # (Re)publish discovery on connect
    # Get enviro_sensors from userdata if available for discovery filtering
    enviro_sensors = userdata.get("enviro_sensors") if userdata else None
    publish_discovery(client, config, enviro_sensors)

    # Get settings manager from userdata
    settings_manager = userdata.get("settings_manager") if userdata else None
    if settings_manager:
        # Publish retained offsets so HA shows the current values
        client.publish(
            f"{root}/set/temp_offset",
            str(settings_manager.temp_offset),
            retain=Constants.MQTT_RETAIN_STATE,
        )
        client.publish(
            f"{root}/set/hum_offset",
            str(settings_manager.hum_offset),
            retain=Constants.MQTT_RETAIN_STATE,
        )
        client.publish(
            f"{root}/set/cpu_temp_factor",
            str(settings_manager.cpu_temp_factor),
            retain=Constants.MQTT_RETAIN_STATE,
        )
        client.publish(
            f"{root}/set/cpu_temp_smoothing",
            str(settings_manager.cpu_temp_smoothing),
            retain=Constants.MQTT_RETAIN_STATE,
        )
        client.publish(
            f"{root}/set/temp_smoothing_minutes",
            str(settings_manager.get_temp_smoothing_minutes()),
            retain=Constants.MQTT_RETAIN_STATE,
        )
        client.publish(
            f"{root}/set/pressure_offset",
            str(settings_manager.pressure_offset),
            retain=Constants.MQTT_RETAIN_STATE,
        )
        client.publish(
            f"{root}/set/elevation_meters",
            str(settings_manager.elevation_meters),
            retain=Constants.MQTT_RETAIN_STATE,
        )
    else:
        # Fallback to config if settings manager not available
        if config:
            client.publish(
                f"{root}/set/temp_offset",
                str(config.temp_offset),
                retain=Constants.MQTT_RETAIN_STATE,
            )
            client.publish(
                f"{root}/set/hum_offset", str(config.hum_offset), retain=Constants.MQTT_RETAIN_STATE
            )
            client.publish(
                f"{root}/set/cpu_temp_factor",
                str(config.cpu_temp_factor),
                retain=Constants.MQTT_RETAIN_STATE,
            )
            client.publish(
                f"{root}/set/cpu_temp_smoothing",
                str(config.cpu_temp_smoothing),
                retain=Constants.MQTT_RETAIN_STATE,
            )
            client.publish(
                f"{root}/set/temp_smoothing_minutes",
                str(config.temp_smoothing_minutes),
                retain=Constants.MQTT_RETAIN_STATE,
            )
            client.publish(
                f"{root}/set/pressure_offset",
                str(config.pressure_offset),
                retain=Constants.MQTT_RETAIN_STATE,
            )
            client.publish(
                f"{root}/set/elevation_meters",
                str(config.elevation_meters),
                retain=Constants.MQTT_RETAIN_STATE,
            )

    # Subscribe to commands and setters
    client.subscribe([(cmd_t, Constants.MQTT_QOS_COMMAND), (set_t, Constants.MQTT_QOS_COMMAND)])


def _handle_command(
    client: mqtt.Client,
    payload: str,
    settings_manager: Optional[SettingsManager] = None,
) -> None:
    """Handle system commands."""
    if payload == "reboot":
        logger.info("Command: reboot")
        client.publish(avail_t, "offline", retain=Constants.MQTT_RETAIN_STATE)
        subprocess.Popen(["sudo", "reboot"])
    elif payload == "shutdown":
        logger.info("Command: shutdown")
        client.publish(avail_t, "offline", retain=Constants.MQTT_RETAIN_STATE)
        subprocess.Popen(["sudo", "shutdown", "-h", "now"])
    elif payload == "restart_service":
        logger.info("Command: restart service")
        subprocess.Popen(["sudo", "systemctl", "restart", f"{APP_NAME}.service"])
    elif payload == "reset_settings":
        logger.info("Command: reset settings to defaults")
        if settings_manager:
            try:
                settings_manager.reset_to_defaults()
                # Publish the reset values to MQTT
                client.publish(
                    f"{root}/set/temp_offset",
                    str(settings_manager.temp_offset),
                    retain=Constants.MQTT_RETAIN_STATE,
                )
                client.publish(
                    f"{root}/set/hum_offset",
                    str(settings_manager.hum_offset),
                    retain=Constants.MQTT_RETAIN_STATE,
                )
                client.publish(
                    f"{root}/set/cpu_temp_factor",
                    str(settings_manager.cpu_temp_factor),
                    retain=Constants.MQTT_RETAIN_STATE,
                )
                client.publish(
                    f"{root}/set/cpu_temp_smoothing",
                    str(settings_manager.cpu_temp_smoothing),
                    retain=Constants.MQTT_RETAIN_STATE,
                )
                client.publish(
                    f"{root}/set/temp_smoothing_minutes",
                    str(settings_manager.get_temp_smoothing_minutes()),
                    retain=Constants.MQTT_RETAIN_STATE,
                )
                client.publish(
                    f"{root}/set/pressure_offset",
                    str(settings_manager.pressure_offset),
                    retain=Constants.MQTT_RETAIN_STATE,
                )
                client.publish(
                    f"{root}/set/elevation_meters",
                    str(settings_manager.elevation_meters),
                    retain=Constants.MQTT_RETAIN_STATE,
                )
                logger.info("Settings reset successfully")
            except Exception as e:
                logger.error("Failed to reset settings: %s", e)
        else:
            logger.error("Settings manager not available for reset")


def _handle_calibration_setting(
    client: mqtt.Client,
    topic: str,
    payload: str,
    enviro_sensors: EnviroPlusSensors,
    settings_manager: Optional[SettingsManager] = None,
) -> None:
    """Handle calibration setting updates."""
    key = topic.split("/")[-1]

    try:
        if key == "temp_offset":
            value = float(payload)
            enviro_sensors.update_calibration(temp_offset=value)
            if settings_manager:
                settings_manager.set_temp_offset(value)
        elif key == "hum_offset":
            value = float(payload)
            enviro_sensors.update_calibration(hum_offset=value)
            if settings_manager:
                settings_manager.set_hum_offset(value)
        elif key == "cpu_temp_factor":
            value = float(payload)
            enviro_sensors.update_calibration(cpu_temp_factor=value)
            if settings_manager:
                settings_manager.set_cpu_temp_factor(value)
        elif key == "cpu_temp_smoothing":
            value = float(payload)
            enviro_sensors.update_calibration(cpu_temp_smoothing=value)
            if settings_manager:
                settings_manager.set_cpu_temp_smoothing(value)
        elif key == "temp_smoothing_minutes":
            original_value = float(payload)
            value = original_value
            value_changed = False

            if value < 0.0:
                logger.warning("Temperature smoothing window must be >= 0, got %s", value)
                value = 0.0
                value_changed = True
            if value > 60.0:
                logger.warning("Temperature smoothing window should be <= 60, got %s", value)
                value = 60.0
                value_changed = True

            enviro_sensors.update_calibration(temp_smoothing_minutes=value)
            if settings_manager:
                settings_manager.set_temp_smoothing_minutes(value)

            # Only publish back if value was clamped (changed from original)
            # This prevents infinite loops while still updating HA if we corrected the value
            if value_changed:
                client.publish(
                    f"{root}/set/temp_smoothing_minutes",
                    str(value),
                    retain=Constants.MQTT_RETAIN_STATE,
                )
        elif key == "pressure_offset":
            value = float(payload)
            enviro_sensors.update_calibration(pressure_offset=value)
            if settings_manager:
                settings_manager.pressure_offset = value
        elif key == "elevation_meters":
            value = float(payload)
            if value < 0.0:
                logger.warning("Elevation cannot be negative, got %s", value)
                value = 0.0
            enviro_sensors.update_calibration(elevation_meters=value)
            if settings_manager:
                settings_manager.elevation_meters = value
        else:
            logger.warning("Unknown calibration setting: %s", key)
    except ValueError:
        logger.error("Invalid value for %s: %s", key, payload)
    except Exception as e:
        logger.error("Failed to update %s: %s", key, e)


def on_message(
    client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage, enviro_sensors: EnviroPlusSensors
) -> None:
    """Handle incoming MQTT messages."""
    try:
        topic = msg.topic
        payload = msg.payload.decode().strip()

        # Get settings manager from userdata
        settings_manager = userdata.get("settings_manager") if userdata else None

        if topic == cmd_t:
            _handle_command(client, payload, settings_manager)
        elif topic.startswith(f"{root}/set/"):
            _handle_calibration_setting(client, topic, payload, enviro_sensors, settings_manager)
    except Exception as e:
        logger.exception("on_message error: %s", e)


def validate_config(config: Config) -> None:
    """
    Validate required configuration on startup.

    Args:
        config: Config instance to validate

    Raises:
        SystemExit: If critical configuration is missing
    """
    logger.info("Validating configuration...")

    try:
        config.validate()
    except ValueError as e:
        logger.error("Configuration validation failed: %s", e)
        logger.error("Please check /etc/default/ha-enviro-plus")
        sys.exit(1)

    # Warn about missing authentication
    if not config.mqtt_user:
        logger.warning("MQTT_USER not set - using anonymous connection")
        logger.warning("Consider setting MQTT_USER and MQTT_PASS for security")

    logger.info("Configuration validation passed")


def signal_handler(
    signum: int,
    frame: Any,
    client: Optional[mqtt.Client] = None,
    display: Optional[Any] = None,
) -> None:
    """
    Handle shutdown signals gracefully.

    Args:
        signum: Signal number
        frame: Current stack frame
        client: MQTT client to disconnect gracefully
        display: Display manager to clean up
    """
    signal_name = signal.Signals(signum).name
    logger.info("Received signal %s (%d), shutting down gracefully", signal_name, signum)

    # Clean up display if provided
    if display:
        try:
            display.cleanup()
            logger.info("Display cleaned up gracefully")
        except Exception as e:
            logger.error("Error during display cleanup: %s", e)

    if client:
        try:
            client.publish(avail_t, "offline", retain=Constants.MQTT_RETAIN_STATE)
            client.loop_stop()
            client.disconnect()
            logger.info("MQTT client disconnected gracefully")
        except Exception as e:
            logger.error("Error during MQTT disconnect: %s", e)

    logger.info("Graceful shutdown complete")

    # Check if we're running in a test environment
    if "pytest" in sys.modules:
        # In tests, raise SystemExit instead of calling sys.exit()
        raise SystemExit(0)
    else:
        # In production, call sys.exit()
        sys.exit(0)


def main() -> None:
    """Main application entry point."""
    # Load and validate configuration
    config = Config.from_env()

    # Configure logging with config
    if config.log_to_file:
        try:
            fh = logging.FileHandler(config.log_path)
            fh.setFormatter(fmt)
            handlers.append(fh)
        except Exception:
            pass

    for h in handlers:
        h.setFormatter(fmt)
        logger.handlers = []
        logger.addHandler(h)

    logger.info("%s starting (v%s)", APP_NAME, VERSION)

    # Validate configuration before proceeding
    validate_config(config)

    logger.info("Root topic: %s", root)
    logger.info("Discovery prefix: %s", config.mqtt_discovery_prefix)
    logger.info("Poll interval: %ss", config.poll_sec)

    # Initialize settings manager
    settings_manager = SettingsManager(logger=logger)

    # Load persistent settings, falling back to config
    temp_offset: float = settings_manager.temp_offset
    hum_offset: float = settings_manager.hum_offset
    cpu_temp_factor: float = settings_manager.cpu_temp_factor
    cpu_temp_smoothing: float = settings_manager.cpu_temp_smoothing
    temp_smoothing_minutes: float = config.temp_smoothing_minutes
    pressure_offset: float = (
        settings_manager.pressure_offset
        if hasattr(settings_manager, "pressure_offset")
        else config.pressure_offset
    )
    elevation_meters: float = (
        settings_manager.elevation_meters
        if hasattr(settings_manager, "elevation_meters")
        else config.elevation_meters
    )

    # Load units setting (from config or settings file)
    units = config.units
    if units not in ("metric", "imperial"):
        logger.warning("Invalid units setting: %s, using 'metric'", units)
        units = "metric"
    settings_manager.units = units

    logger.info(
        "Initial offsets: TEMP=%s°C HUM=%s%% CPU_FACTOR=%s CPU_SMOOTHING=%s TEMP_SMOOTHING=%s min PRESSURE=%s hPa ELEVATION=%s m UNITS=%s",
        temp_offset,
        hum_offset,
        cpu_temp_factor,
        cpu_temp_smoothing,
        temp_smoothing_minutes,
        pressure_offset,
        elevation_meters,
        units,
    )

    # Initialize sensor manager with current calibration values
    enviro_sensors = EnviroPlusSensors(
        temp_offset=temp_offset,
        hum_offset=hum_offset,
        cpu_temp_factor=cpu_temp_factor,
        cpu_temp_smoothing=cpu_temp_smoothing,
        temp_smoothing_minutes=temp_smoothing_minutes,
        pressure_offset=pressure_offset,
        elevation_meters=elevation_meters,
        logger=logger,
    )

    # Initialize display and show splash screen (skip in tests when disabled)
    display = None
    # Display splash screen during startup (skipped in tests)
    if config.display_enabled and os.getenv("PYTEST_CURRENT_TEST") is None:
        try:
            display = DisplayManager(
                logger=logger,
                enabled=config.display_enabled,
                auto_rotate=config.display_auto_rotate,
                rotation_interval=config.display_rotation_interval,
            )
            if display.display_available:
                # Display is already cleared during initialization
                # Queue splash screen - this is non-blocking now!
                display.show_splash(duration=8, fade_duration=2)
                logger.info("Splash screen queued for display")
        except Exception as e:
            logger.warning("Failed to initialize display: %s, continuing without splash", e)

    # Sensor warm-up period - read sensors and discard initial readings
    if config.sensor_warmup_sec > 0:
        logger.info("Warming up sensors for %.1f seconds...", config.sensor_warmup_sec)
        warmup_start = time.time()

        while time.time() - warmup_start < config.sensor_warmup_sec:
            # Read sensors but don't publish (only if available)
            try:
                if enviro_sensors.has_sensor("bme280"):
                    _ = enviro_sensors.temp()
                    _ = enviro_sensors.humidity()
                    _ = enviro_sensors.pressure()
            except Exception:
                pass  # Ignore errors during warm-up
            time.sleep(0.1)  # Small delay between reads

        logger.info("Sensor warm-up complete")

    # Discover and start display plugins after splash screen
    if display and display.display_available:
        try:
            # Wait a bit for splash screen to display, then discover plugins
            # We'll start plugin cycle after splash completes
            available_plugins = get_available_plugins(enviro_sensors, settings_manager)
            if available_plugins:
                logger.info(
                    "Found %d available display plugin(s): %s",
                    len(available_plugins),
                    ", ".join([p.name() for p in available_plugins]),
                )
                # Initialize plugin data first, before starting cycle
                display.update_plugin_data(enviro_sensors, settings_manager)
                # Start plugin cycle (will begin after splash completes)
                display.start_plugin_cycle(available_plugins)
            else:
                logger.warning("No display plugins available")
        except Exception as e:
            logger.error("Failed to initialize display plugins: %s", e)
            if display:
                display.show_error_message(f"Plugin error: {str(e)}")

    client = mqtt.Client(client_id=root, protocol=mqtt.MQTTv5)
    if config.mqtt_user:
        client.username_pw_set(config.mqtt_user, config.mqtt_pass)
    client.will_set(avail_t, "offline", retain=Constants.MQTT_RETAIN_STATE)

    # Set userdata to pass config, settings manager and sensors to callbacks
    client.user_data_set(
        {
            "config": config,
            "settings_manager": settings_manager,
            "enviro_sensors": enviro_sensors,
        }
    )

    # Create wrapper for on_connect that includes config
    def connect_wrapper(
        client: mqtt.Client, userdata: Any, flags: Any, rc: int, properties: Any = None
    ) -> None:
        on_connect(client, userdata, flags, rc, properties, config=config)

    client.on_connect = connect_wrapper

    # Create a wrapper for on_message that includes the sensor instance
    def message_wrapper(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        on_message(client, userdata, msg, enviro_sensors)

    client.on_message = message_wrapper

    # Register signal handlers for graceful shutdown
    def sigterm_handler(signum: int, frame: Any) -> None:
        signal_handler(signum, frame, client, display)

    def sigint_handler(signum: int, frame: Any) -> None:
        signal_handler(signum, frame, client, display)

    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigint_handler)

    client.connect(config.mqtt_host, config.mqtt_port, keepalive=Constants.MQTT_KEEPALIVE)
    client.loop_start()

    # Publish static device attributes once
    static = {
        "model": get_model(),
        "serial": get_serial(),
    }
    client.publish(
        f"{root}/device/attributes", json.dumps(static), retain=Constants.MQTT_RETAIN_STATE
    )

    # Track previous values to only publish changes
    previous_vals: Dict[str, Any] = {}

    try:
        while True:
            vals = read_all(enviro_sensors)
            for tail, val in vals.items():
                # Convert value to string for comparison
                val_str = str(val)

                # Check if value has changed (with tolerance for floats)
                if tail not in previous_vals:
                    # First time seeing this value - always publish
                    client.publish(f"{root}/{tail}", val_str, retain=Constants.MQTT_RETAIN_STATE)
                    previous_vals[tail] = val_str
                else:
                    # Compare with previous value
                    prev_val_str = previous_vals[tail]

                    # For numeric values, compare with small tolerance
                    try:
                        prev_val_float = float(prev_val_str)
                        val_float = float(val_str)
                        # Use tolerance for floating point comparison
                        if abs(val_float - prev_val_float) > Constants.FLOAT_TOLERANCE:
                            client.publish(
                                f"{root}/{tail}", val_str, retain=Constants.MQTT_RETAIN_STATE
                            )
                            previous_vals[tail] = val_str
                    except (ValueError, TypeError):
                        # Non-numeric values - string comparison
                        if val_str != prev_val_str:
                            client.publish(
                                f"{root}/{tail}", val_str, retain=Constants.MQTT_RETAIN_STATE
                            )
                            previous_vals[tail] = val_str

            # Update display plugin data periodically
            if display and display.display_available:
                try:
                    display.update_plugin_data(enviro_sensors, settings_manager)

                    # Check for proximity tap detection
                    if enviro_sensors.has_sensor("ltr559"):
                        try:
                            proximity_value = enviro_sensors.proximity()
                            if display.check_proximity_tap(proximity_value):
                                display.handle_tap()
                        except Exception as e:
                            logger.debug("Failed to check proximity tap: %s", e)
                except Exception as e:
                    logger.warning("Failed to update display plugin data: %s", e)

            time.sleep(config.poll_sec)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down gracefully")
        signal_handler(signal.SIGINT, None, client, display)
    except Exception as e:
        logger.error("Unexpected error in main loop: %s", e)
        logger.info("Shutting down gracefully due to error")
        signal_handler(signal.SIGTERM, None, client, display)
    finally:
        # This should not be reached due to signal_handler calling sys.exit()
        # But keeping it as a safety net for cases where signal_handler wasn't called
        try:
            if client:
                client.publish(avail_t, "offline", retain=Constants.MQTT_RETAIN_STATE)
                client.loop_stop()
                client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
