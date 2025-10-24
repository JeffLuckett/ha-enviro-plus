#!/usr/bin/env python3
import os
import json
import time
import socket
import psutil
import subprocess
import logging
import platform
import signal
import sys
from datetime import datetime, timezone
from typing import List, Any, Dict, Optional

import paho.mqtt.client as mqtt
from .sensors import EnviroPlusSensors
from .settings import SettingsManager
from . import __version__

APP_NAME = "ha-enviro-plus"
VERSION = __version__

# ---------- CONFIG via /etc/default/ha-enviro-plus ----------
MQTT_HOST = os.getenv("MQTT_HOST", "homeassistant.local")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_DISCOVERY_PREFIX = os.getenv("MQTT_DISCOVERY_PREFIX", "homeassistant")
POLL_SEC = float(os.getenv("POLL_SEC", "2"))
TEMP_OFFSET = float(os.getenv("TEMP_OFFSET", "0.0"))
HUM_OFFSET = float(os.getenv("HUM_OFFSET", "0.0"))
CPU_TEMP_FACTOR = float(os.getenv("CPU_TEMP_FACTOR", "1.8"))
CPU_TEMP_SMOOTHING = float(os.getenv("CPU_TEMP_SMOOTHING", "0.1"))
LOG_TO_FILE = int(os.getenv("LOG_TO_FILE", "0")) == 1
LOG_PATH = f"/var/log/{APP_NAME}.log"
# ------------------------------------------------------------

hostname = socket.gethostname()
device_id = f"enviro_{hostname.replace('-', '')}"
root = device_id  # topic root for states & commands
avail_t = f"{root}/status"
cmd_t = f"{root}/cmd"  # expects: reboot|shutdown|restart
set_t = f"{root}/set/+"  # retained settings, e.g. set/temp_offset


def get_ipv4_prefer_wlan0() -> str:
    """
    Get IPv4 address with preference for wlan0 interface.

    Returns:
        IPv4 address string, or "unknown" if unable to determine

    Raises:
        Never raises - always returns a fallback value
    """
    try:
        addrs = psutil.net_if_addrs()
        # prefer wlan0, else first non-loopback IPv4
        if "wlan0" in addrs:
            for a in addrs["wlan0"]:
                if a.family.name == "AF_INET" and not a.address.startswith("127."):
                    logger.debug("Using wlan0 IPv4 address: %s", a.address)
                    return str(a.address)
        for iface, lst in addrs.items():
            for a in lst:
                if a.family.name == "AF_INET" and not a.address.startswith("127."):
                    logger.debug("Using %s IPv4 address: %s", iface, a.address)
                    return str(a.address)
    except Exception as e:
        logger.error("Failed to get network address: %s", e)
        logger.info("Network address will be reported as 'unknown'")
    return "unknown"


def get_uptime_seconds() -> int:
    """
    Get system uptime in seconds from /proc/uptime.

    Returns:
        Uptime in seconds, or 0 if unable to read

    Raises:
        Never raises - always returns a fallback value
    """
    try:
        with open("/proc/uptime", "r") as f:
            uptime_str = f.read().split()[0]
            uptime_seconds = int(float(uptime_str))
            logger.debug("System uptime: %d seconds", uptime_seconds)
            return uptime_seconds
    except (FileNotFoundError, ValueError, IndexError) as e:
        logger.error("Failed to read system uptime: %s", e)
        logger.info("Uptime will be reported as 0 seconds")
        return 0
    except Exception as e:
        logger.error("Unexpected error reading uptime: %s", e)
        logger.info("Uptime will be reported as 0 seconds")
        return 0


def get_model() -> str:
    """
    Get device model from /proc/device-tree/model.

    Returns:
        Device model string, or "Raspberry Pi" if unable to read

    Raises:
        Never raises - always returns a fallback value
    """
    try:
        with open("/proc/device-tree/model", "rb") as f:
            model_bytes = f.read()
            model_str = model_bytes.decode(errors="ignore").strip("\x00")
            logger.debug("Device model: %s", model_str)
            return model_str
    except FileNotFoundError:
        logger.warning("Device model file not found, using default")
        logger.info("Device model will be reported as 'Raspberry Pi'")
        return "Raspberry Pi"
    except Exception as e:
        logger.error("Failed to read device model: %s", e)
        logger.info("Device model will be reported as 'Raspberry Pi'")
        return "Raspberry Pi"


def get_serial() -> str:
    """
    Get device serial number from /proc/cpuinfo.

    Returns:
        Serial number string, or "unknown" if unable to read

    Raises:
        Never raises - always returns a fallback value
    """
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("Serial"):
                    serial = line.split(":")[1].strip()
                    logger.debug("Device serial: %s", serial)
                    return serial
        logger.warning("Serial number not found in cpuinfo")
        logger.info("Serial number will be reported as 'unknown'")
        return "unknown"
    except FileNotFoundError:
        logger.error("CPU info file not found")
        logger.info("Serial number will be reported as 'unknown'")
        return "unknown"
    except Exception as e:
        logger.error("Failed to read device serial: %s", e)
        logger.info("Serial number will be reported as 'unknown'")
        return "unknown"


def get_os_release() -> str:
    """
    Get OS release information from /etc/os-release or platform fallback.

    Returns:
        OS release string, or "unknown" if unable to determine

    Raises:
        Never raises - always returns a fallback value
    """
    try:
        # Try to get more detailed OS info
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r") as f:
                lines = f.readlines()
            for line in lines:
                if line.startswith("PRETTY_NAME="):
                    os_name = line.split("=", 1)[1].strip().strip('"')
                    logger.debug("OS release from os-release: %s", os_name)
                    return os_name

        # Fallback to platform info
        platform_info = platform.platform()
        logger.debug("OS release from platform: %s", platform_info)
        return platform_info

    except FileNotFoundError:
        logger.warning("OS release file not found, using platform fallback")
        try:
            platform_info = platform.platform()
            logger.info("OS release will be reported as: %s", platform_info)
            return platform_info
        except Exception as e:
            logger.error("Platform fallback failed: %s", e)
            logger.info("OS release will be reported as 'unknown'")
            return "unknown"
    except Exception as e:
        logger.error("Failed to get OS release: %s", e)
        logger.info("OS release will be reported as 'unknown'")
        return "unknown"


# ---------- logging ----------
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
handlers: List[logging.Handler] = [logging.StreamHandler()]
if LOG_TO_FILE:
    try:
        fh = logging.FileHandler(LOG_PATH)
        fh.setFormatter(fmt)
        handlers.append(fh)
    except Exception:
        pass
for h in handlers:
    h.setFormatter(fmt)
    logger.handlers = []
    logger.addHandler(h)
# ----------------------------

DEVICE_INFO = {
    "identifiers": [device_id],
    "name": "Enviro+",
    "manufacturer": "Pimoroni",
    "model": "Enviro+ (no PMS5003)",
    "sw_version": f"{APP_NAME} {VERSION}",
    "configuration_url": "https://github.com/JeffLuckett/ha-enviro-plus",
}

SENSORS = {
    "bme280/temperature": ("Temperature", "°C", "temperature"),
    "bme280/humidity": ("Humidity", "%", "humidity"),
    "bme280/pressure": ("Pressure", "hPa", "atmospheric_pressure"),
    "ltr559/lux": ("Illuminance", "lx", "illuminance"),
    "gas/oxidising": ("Gas Oxidising (kΩ)", "kΩ", None),
    "gas/reducing": ("Gas Reducing (kΩ)", "kΩ", None),
    "gas/nh3": ("Gas NH3 (kΩ)", "kΩ", None),
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
) -> Dict[str, Any]:
    cfg = {
        "name": name,
        "uniq_id": f"{device_id}_{topic_tail.replace('/', '_')}",
        "state_topic": f"{root}/{topic_tail}",
        "availability_topic": avail_t,
        "device": DEVICE_INFO,
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


def publish_discovery(c: mqtt.Client) -> None:
    # sensors
    for tail, (name, unit, devcls) in SENSORS.items():
        obj = tail.replace("/", "_")
        topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{device_id}/{obj}/config"
        # For text sensors (no unit), don't set state_class
        state_class = None if unit is None else "measurement"
        c.publish(
            topic,
            json.dumps(disc_payload(tail, name, unit, devcls, state_class)),
            qos=1,
            retain=True,
        )

    # controls: simple button commands
    def button(topic_key: str, name: str, icon: str) -> None:
        cfg = {
            "name": name,
            "uniq_id": f"{device_id}_btn_{topic_key}",
            "cmd_t": f"{root}/cmd",
            "pl_prs": topic_key,
            "availability_topic": avail_t,
            "device": DEVICE_INFO,
            "icon": icon,
        }
        topic = f"{MQTT_DISCOVERY_PREFIX}/button/{device_id}/{topic_key}/config"
        c.publish(topic, json.dumps(cfg), qos=1, retain=True)

    button("reboot", "Reboot Enviro Zero", "mdi:restart")
    button("shutdown", "Shutdown Enviro Zero", "mdi:power")
    button("restart_service", "Restart Agent", "mdi:refresh")
    button("reset_settings", "Reset Settings to Defaults", "mdi:restore")

    # number entities for offsets (so HA shows exact values)
    def number(
        name: str, key: str, unit: Optional[str], minv: float, maxv: float, step: float
    ) -> None:
        cfg = {
            "name": name,
            "uniq_id": f"{device_id}_num_{key}",
            "cmd_t": f"{root}/set/{key}",
            "stat_t": f"{root}/set/{key}",
            "availability_topic": avail_t,
            "device": DEVICE_INFO,
            "unit_of_measurement": unit,
            "min": minv,
            "max": maxv,
            "step": step,
            "mode": "box",
        }
        topic = f"{MQTT_DISCOVERY_PREFIX}/number/{device_id}/{key}/config"
        c.publish(topic, json.dumps(cfg), qos=1, retain=True)

    number("Temp Offset", "temp_offset", "°C", -10, 10, 0.1)
    number("Humidity Offset", "hum_offset", "%", -20, 20, 0.5)
    number("CPU Temp Factor", "cpu_temp_factor", None, 0.5, 5.0, 0.1)
    number("CPU Temp Smoothing", "cpu_temp_smoothing", None, 0.01, 1.0, 0.01)


def read_all(enviro_sensors: EnviroPlusSensors) -> Dict[str, Any]:
    """Read all sensor and system data using the EnviroPlusSensors class."""
    # Get sensor data from the encapsulated sensor manager
    sensor_data = enviro_sensors.get_all_sensor_data()

    # Get system metrics
    mem = psutil.virtual_memory()

    vals = {
        # Sensor data (processed)
        "bme280/temperature": sensor_data["temperature"],
        "bme280/humidity": sensor_data["humidity"],
        "bme280/pressure": sensor_data["pressure"],
        "ltr559/lux": sensor_data["lux"],
        "gas/oxidising": sensor_data["gas_oxidising"],
        "gas/reducing": sensor_data["gas_reducing"],
        "gas/nh3": sensor_data["gas_nh3"],
        # System metrics
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
    return vals


def on_connect(
    client: mqtt.Client, userdata: Any, flags: Any, rc: int, properties: Any = None
) -> None:
    logger.info("Connected to MQTT (%s:%s) RC=%s", MQTT_HOST, MQTT_PORT, mqtt.connack_string(rc))
    client.publish(avail_t, "online", retain=True)
    # (Re)publish discovery on connect
    publish_discovery(client)

    # Get settings manager from userdata
    settings_manager = userdata.get("settings_manager") if userdata else None
    if settings_manager:
        # Publish retained offsets so HA shows the current values
        client.publish(
            f"{root}/set/temp_offset", str(settings_manager.get_temp_offset()), retain=True
        )
        client.publish(
            f"{root}/set/hum_offset", str(settings_manager.get_hum_offset()), retain=True
        )
        client.publish(
            f"{root}/set/cpu_temp_factor", str(settings_manager.get_cpu_temp_factor()), retain=True
        )
        client.publish(
            f"{root}/set/cpu_temp_smoothing",
            str(settings_manager.get_cpu_temp_smoothing()),
            retain=True,
        )
    else:
        # Fallback to environment variables if settings manager not available
        client.publish(f"{root}/set/temp_offset", str(TEMP_OFFSET), retain=True)
        client.publish(f"{root}/set/hum_offset", str(HUM_OFFSET), retain=True)
        client.publish(f"{root}/set/cpu_temp_factor", str(CPU_TEMP_FACTOR), retain=True)
        client.publish(f"{root}/set/cpu_temp_smoothing", str(CPU_TEMP_SMOOTHING), retain=True)

    # Subscribe to commands and setters
    client.subscribe([(cmd_t, 1), (set_t, 1)])


def _handle_command(
    client: mqtt.Client, payload: str, settings_manager: Optional[SettingsManager] = None
) -> None:
    """Handle system commands."""
    if payload == "reboot":
        logger.info("Command: reboot")
        client.publish(avail_t, "offline", retain=True)
        subprocess.Popen(["sudo", "reboot"])
    elif payload == "shutdown":
        logger.info("Command: shutdown")
        client.publish(avail_t, "offline", retain=True)
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
                    f"{root}/set/temp_offset", str(settings_manager.get_temp_offset()), retain=True
                )
                client.publish(
                    f"{root}/set/hum_offset", str(settings_manager.get_hum_offset()), retain=True
                )
                client.publish(
                    f"{root}/set/cpu_temp_factor",
                    str(settings_manager.get_cpu_temp_factor()),
                    retain=True,
                )
                client.publish(
                    f"{root}/set/cpu_temp_smoothing",
                    str(settings_manager.get_cpu_temp_smoothing()),
                    retain=True,
                )
                logger.info("Settings reset successfully")
            except Exception as e:
                logger.error("Failed to reset settings: %s", e)
        else:
            logger.error("Settings manager not available for reset")


def _handle_calibration_setting(
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
            _handle_calibration_setting(topic, payload, enviro_sensors, settings_manager)
    except Exception as e:
        logger.exception("on_message error: %s", e)


def validate_config() -> None:
    """
    Validate required configuration on startup.

    Raises:
        SystemExit: If critical configuration is missing
    """
    logger.info("Validating configuration...")

    # Check MQTT_HOST
    if not MQTT_HOST or MQTT_HOST == "":
        logger.error("MQTT_HOST is required but not set")
        logger.error("Please set MQTT_HOST in /etc/default/ha-enviro-plus")
        sys.exit(1)

    # Check MQTT_PORT
    if not isinstance(MQTT_PORT, int) or MQTT_PORT <= 0 or MQTT_PORT > 65535:
        logger.error("MQTT_PORT must be a valid port number (1-65535), got: %s", MQTT_PORT)
        sys.exit(1)

    # Warn about missing authentication
    if not MQTT_USER:
        logger.warning("MQTT_USER not set - using anonymous connection")
        logger.warning("Consider setting MQTT_USER and MQTT_PASS for security")

    # Check poll interval
    if POLL_SEC <= 0:
        logger.error("POLL_SEC must be positive, got: %s", POLL_SEC)
        sys.exit(1)

    # Check calibration values are numeric
    try:
        float(TEMP_OFFSET)
        float(HUM_OFFSET)
        float(CPU_TEMP_FACTOR)
        float(CPU_TEMP_SMOOTHING)
    except (ValueError, TypeError) as e:
        logger.error("Invalid calibration values: %s", e)
        sys.exit(1)

    logger.info("Configuration validation passed")


def signal_handler(signum: int, frame: Any, client: Optional[mqtt.Client] = None) -> None:
    """
    Handle shutdown signals gracefully.

    Args:
        signum: Signal number
        frame: Current stack frame
        client: MQTT client to disconnect gracefully
    """
    signal_name = signal.Signals(signum).name
    logger.info("Received signal %s (%d), shutting down gracefully", signal_name, signum)

    if client:
        try:
            client.publish(avail_t, "offline", retain=True)
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
    logger.info("%s starting (v%s)", APP_NAME, VERSION)

    # Validate configuration before proceeding
    validate_config()

    logger.info("Root topic: %s", root)
    logger.info("Discovery prefix: %s", MQTT_DISCOVERY_PREFIX)
    logger.info("Poll interval: %ss", POLL_SEC)

    # Initialize settings manager
    settings_manager = SettingsManager(logger=logger)

    # Load persistent settings, falling back to environment variables
    temp_offset = settings_manager.get_temp_offset()
    hum_offset = settings_manager.get_hum_offset()
    cpu_temp_factor = settings_manager.get_cpu_temp_factor()
    cpu_temp_smoothing = settings_manager.get_cpu_temp_smoothing()

    logger.info(
        "Initial offsets: TEMP=%s°C HUM=%s%% CPU_FACTOR=%s CPU_SMOOTHING=%s",
        temp_offset,
        hum_offset,
        cpu_temp_factor,
        cpu_temp_smoothing,
    )

    # Initialize sensor manager with current calibration values
    enviro_sensors = EnviroPlusSensors(
        temp_offset=temp_offset,
        hum_offset=hum_offset,
        cpu_temp_factor=cpu_temp_factor,
        cpu_temp_smoothing=cpu_temp_smoothing,
        logger=logger,
    )

    client = mqtt.Client(client_id=root, protocol=mqtt.MQTTv5)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.will_set(avail_t, "offline", retain=True)

    # Set userdata to pass settings manager to callbacks
    client.user_data_set({"settings_manager": settings_manager})

    client.on_connect = on_connect

    # Create a wrapper for on_message that includes the sensor instance
    def message_wrapper(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        on_message(client, userdata, msg, enviro_sensors)

    client.on_message = message_wrapper

    # Register signal handlers for graceful shutdown
    def sigterm_handler(signum: int, frame: Any) -> None:
        signal_handler(signum, frame, client)

    def sigint_handler(signum: int, frame: Any) -> None:
        signal_handler(signum, frame, client)

    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigint_handler)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    # Publish static device attributes once
    static = {
        "model": get_model(),
        "serial": get_serial(),
    }
    client.publish(f"{root}/device/attributes", json.dumps(static), retain=True)

    try:
        while True:
            vals = read_all(enviro_sensors)
            for tail, val in vals.items():
                client.publish(f"{root}/{tail}", str(val), retain=True)
            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down gracefully")
        signal_handler(signal.SIGINT, None, client)
    except Exception as e:
        logger.error("Unexpected error in main loop: %s", e)
        logger.info("Shutting down gracefully due to error")
        signal_handler(signal.SIGTERM, None, client)
    finally:
        # This should not be reached due to signal_handler calling sys.exit()
        # But keeping it as a safety net for cases where signal_handler wasn't called
        try:
            if client:
                client.publish(avail_t, "offline", retain=True)
                client.loop_stop()
                client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
