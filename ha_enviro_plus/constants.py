#!/usr/bin/env python3
"""
Application-wide constants.

This module contains all magic numbers and string constants used throughout
the application to improve maintainability and readability.
"""

from pathlib import Path


class Constants:
    """Application-wide constants."""

    # Network
    MAC_ADDRESS_LENGTH = 17
    MAC_ADDRESS_SEPARATOR = ":"
    PREFERRED_INTERFACES = ["wlan0", "eth0"]

    # MQTT
    MQTT_QOS_DISCOVERY = 1
    MQTT_QOS_STATE = 1
    MQTT_QOS_COMMAND = 1
    MQTT_RETAIN_DISCOVERY = True
    MQTT_RETAIN_STATE = True
    MQTT_KEEPALIVE = 60

    # Value comparison
    FLOAT_TOLERANCE = 0.01

    # Temperature
    DEFAULT_CPU_TEMP_CELSIUS = 40.6  # Pi Zero typical temp in °C (105°F)

    # File paths
    SETTINGS_DIR = Path("/var/lib/ha-enviro-plus")
    LOG_PATH = Path("/var/log/ha-enviro-plus.log")

    # Sensor I2C addresses
    BME280_I2C_ADDR = 0x76

    # Rounding precision
    TEMP_ROUND_PRECISION = 2
    HUMIDITY_ROUND_PRECISION = 2
    PRESSURE_ROUND_PRECISION = 2
