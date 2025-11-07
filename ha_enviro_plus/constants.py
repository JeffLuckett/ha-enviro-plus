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
    # Formula: dB(A) = 20 * log10(filtered_rms) + NOISE_CALIBRATION_OFFSET
    # Using filtered RMS because raw RMS doesn't increase much during loud sounds
    # From logs: quiet filtered_rms ≈ 0.010, loud filtered_rms ≈ 0.030 (3x higher)
    # Calibrated to match phone SPL meter readings:
    # - Quiet room (30 dB) with filtered_rms ≈ 0.010: 30 = 20*log10(0.010) + offset → offset ≈ 70 dB
    # - Loud music (77 dB) with filtered_rms ≈ 0.030: 77 = 20*log10(0.030) + offset → offset ≈ 107 dB
    # Using 90 dB as default (middle ground) - users can adjust via MQTT
    NOISE_CALIBRATION_OFFSET = 90.0  # dB offset for I2S microphone calibration
