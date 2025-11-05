#!/usr/bin/env python3
"""
Configuration management.

This module provides a clean configuration class that loads settings from
environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # MQTT Configuration
    mqtt_host: str = "homeassistant.local"
    mqtt_port: int = 1883
    mqtt_user: str = ""
    mqtt_pass: str = ""
    mqtt_discovery_prefix: str = "homeassistant"

    # Sensor Configuration
    poll_sec: float = 2.0
    temp_offset: float = 0.0
    hum_offset: float = 0.0
    cpu_temp_factor: float = 1.8
    cpu_temp_smoothing: float = 0.1
    temp_smoothing_minutes: float = 5.0

    # Display Configuration
    display_enabled: bool = True
    sensor_warmup_sec: float = 2.0
    units: str = "metric"
    device_location: str = ""

    # Logging Configuration
    log_to_file: bool = False
    log_path: Path = field(default_factory=lambda: Path("/var/log/ha-enviro-plus.log"))

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.

        Returns:
            Config instance with values from environment or defaults
        """

        def _get(key: str, default: str) -> str:
            """Get environment variable with default."""
            return os.getenv(key, default)

        return cls(
            # MQTT
            mqtt_host=_get("MQTT_HOST", "homeassistant.local"),
            mqtt_port=int(_get("MQTT_PORT", "1883")),
            mqtt_user=_get("MQTT_USER", ""),
            mqtt_pass=_get("MQTT_PASS", ""),
            mqtt_discovery_prefix=_get("MQTT_DISCOVERY_PREFIX", "homeassistant"),
            # Sensor
            poll_sec=float(_get("POLL_SEC", "2")),
            temp_offset=float(_get("TEMP_OFFSET", "0.0")),
            hum_offset=float(_get("HUM_OFFSET", "0.0")),
            cpu_temp_factor=float(_get("CPU_TEMP_FACTOR", "1.8")),
            cpu_temp_smoothing=float(_get("CPU_TEMP_SMOOTHING", "0.1")),
            temp_smoothing_minutes=float(_get("TEMP_SMOOTHING_MINUTES", "5.0")),
            # Display
            display_enabled=int(_get("DISPLAY_ENABLED", "1")) == 1,
            sensor_warmup_sec=float(_get("SENSOR_WARMUP_SEC", "2")),
            units=_get("UNITS", "metric"),
            device_location=_get("DEVICE_LOCATION", ""),
            # Logging
            log_to_file=int(_get("LOG_TO_FILE", "0")) == 1,
            log_path=Path(_get("LOG_PATH", "/var/log/ha-enviro-plus.log")),
        )

    def validate(self) -> None:
        """
        Validate configuration values.

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.mqtt_host:
            raise ValueError("MQTT_HOST is required but not set")

        if not (1 <= self.mqtt_port <= 65535):
            raise ValueError(f"MQTT_PORT must be 1-65535, got: {self.mqtt_port}")

        if self.poll_sec <= 0:
            raise ValueError(f"POLL_SEC must be positive, got: {self.poll_sec}")

        if self.units not in ("metric", "imperial"):
            raise ValueError(f"UNITS must be 'metric' or 'imperial', got: {self.units}")
