"""Unit tests for ha_enviro_plus.config module."""

import os
import pytest
from unittest.mock import patch

from ha_enviro_plus.config import Config


class TestConfig:
    """Test the Config class."""

    def test_default_values(self):
        """Test that default values are correct."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config.from_env()
            assert config.mqtt_host == "homeassistant.local"
            assert config.mqtt_port == 1883
            assert config.mqtt_user == ""
            assert config.mqtt_pass == ""
            assert config.poll_sec == 2.0
            assert config.temp_offset == 0.0
            assert config.hum_offset == 0.0
            assert config.cpu_temp_factor == 1.8
            assert config.cpu_temp_smoothing == 0.1
            assert config.temp_smoothing_minutes == 5.0
            assert config.display_enabled is True
            assert config.display_auto_rotate is True
            assert config.display_rotation_interval == 10.0
            assert config.units == "metric"

    def test_from_env(self):
        """Test loading from environment variables."""
        env_vars = {
            "MQTT_HOST": "test.local",
            "MQTT_PORT": "8883",
            "MQTT_USER": "user",
            "MQTT_PASS": "pass",
            "POLL_SEC": "5.0",
            "TEMP_OFFSET": "1.5",
            "HUM_OFFSET": "2.0",
            "CPU_TEMP_FACTOR": "2.0",
            "CPU_TEMP_SMOOTHING": "0.2",
            "TEMP_SMOOTHING_MINUTES": "10.0",
            "DISPLAY_ENABLED": "0",
            "DISPLAY_AUTO_ROTATE": "0",
            "DISPLAY_ROTATION_INTERVAL": "15.0",
            "UNITS": "imperial",
            "DEVICE_LOCATION": "Kitchen",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config.from_env()
            assert config.mqtt_host == "test.local"
            assert config.mqtt_port == 8883
            assert config.mqtt_user == "user"
            assert config.mqtt_pass == "pass"
            assert config.poll_sec == 5.0
            assert config.temp_offset == 1.5
            assert config.hum_offset == 2.0
            assert config.cpu_temp_factor == 2.0
            assert config.cpu_temp_smoothing == 0.2
            assert config.temp_smoothing_minutes == 10.0
            assert config.display_enabled is False
            assert config.display_auto_rotate is False
            assert config.display_rotation_interval == 15.0
            assert config.units == "imperial"
            assert config.device_location == "Kitchen"

    def test_validate_success(self):
        """Test successful validation."""
        config = Config(
            mqtt_host="test.local",
            mqtt_port=1883,
            poll_sec=2.0,
            units="metric",
        )
        # Should not raise
        config.validate()

    def test_validate_missing_host(self):
        """Test validation fails with missing host."""
        config = Config(mqtt_host="", mqtt_port=1883, poll_sec=2.0, units="metric")
        with pytest.raises(ValueError, match="MQTT_HOST is required"):
            config.validate()

    def test_validate_invalid_port(self):
        """Test validation fails with invalid port."""
        config = Config(mqtt_host="test.local", mqtt_port=0, poll_sec=2.0, units="metric")
        with pytest.raises(ValueError, match="MQTT_PORT must be"):
            config.validate()

        config = Config(mqtt_host="test.local", mqtt_port=70000, poll_sec=2.0, units="metric")
        with pytest.raises(ValueError, match="MQTT_PORT must be"):
            config.validate()

    def test_validate_invalid_poll_sec(self):
        """Test validation fails with invalid poll_sec."""
        config = Config(mqtt_host="test.local", mqtt_port=1883, poll_sec=-1.0, units="metric")
        with pytest.raises(ValueError, match="POLL_SEC must be positive"):
            config.validate()

    def test_validate_invalid_units(self):
        """Test validation fails with invalid units."""
        config = Config(mqtt_host="test.local", mqtt_port=1883, poll_sec=2.0, units="invalid")
        with pytest.raises(ValueError, match="UNITS must be"):
            config.validate()
