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
    # Calibration: maps RMS value to dB(A)
    # For I2S microphone (adau7002), calibrated based on typical quiet room (30 dB)
    # This is an empirical calibration - adjust based on reference SPL meter
    # Formula: dB(A) = 20 * log10(raw_rms) + NOISE_CALIBRATION_OFFSET
    # Using raw RMS instead of filtered RMS because A-weighting reduces signal too much
    # Calibrated to cover full dynamic range:
    # - Quiet room (30 dB) with raw RMS ~0.049: 30 = 20*log10(0.049) + offset = -26 + offset → offset ≈ 56 dB
    # - Loud music (80 dB) with raw RMS ~1.0: 80 = 20*log10(1.0) + offset = 0 + offset → offset = 80 dB
    # Using 80 dB as default to allow full dynamic range (users can adjust via MQTT)
    NOISE_CALIBRATION_OFFSET = 80.0  # dB offset for I2S microphone calibration
