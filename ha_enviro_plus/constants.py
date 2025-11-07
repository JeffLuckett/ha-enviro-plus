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
    NOISE_ROUND_PRECISION = 2

    # Noise sensor
    NOISE_SAMPLE_RATE = 44100  # Hz
    NOISE_CHUNK_SIZE = 1024  # samples
    NOISE_AVERAGE_WINDOW = 10  # number of chunks to average
    NOISE_STARTUP_DISCARD_CHUNKS = 5  # discard first N chunks to avoid "plop"
    # Calibration: maps RMS value to dB(A) using two-point calibration
    # For I2S microphone (adau7002), RMS values don't scale properly with sound pressure level
    # So we use a two-point calibration to create a proper mapping:
    # SPL = m * log10(filtered_rms) + b
    # Where m and b are determined by two calibration points
    #
    # Calibration points (from user logs):
    # - Quiet room: filtered_rms ≈ 0.010, SPL = 30 dB
    # - Loud music: filtered_rms ≈ 0.030, SPL = 77 dB
    #
    # This gives us: SPL = 98.5 * log10(filtered_rms) + 227.0
    # The calibration offset is then added as a fine-tuning adjustment:
    # SPL_final = two_point_calibration(RMS) + user_offset
    # Default offset is 0.0 (no adjustment), users can adjust via MQTT
    NOISE_CALIBRATION_OFFSET = 0.0  # dB offset for fine-tuning (default: 0.0 = no adjustment)
