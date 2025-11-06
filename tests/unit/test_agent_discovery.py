"""Unit tests for agent discovery payload and publishing."""

import json
import pytest
from unittest.mock import Mock, patch

from ha_enviro_plus.agent import disc_payload, publish_discovery, SENSORS
from ha_enviro_plus.system_info import get_device_info


class TestDiscoveryPayload:
    """Test discovery payload generation."""

    def test_disc_payload_basic(self, mock_device_id):
        """Test basic discovery payload."""
        from ha_enviro_plus.agent import APP_NAME, VERSION

        payload = disc_payload("test/sensor", "Test Sensor", "°C")

        assert payload["name"] == "Test Sensor"
        assert payload["uniq_id"] == "enviro_raspberrypi_test_sensor"
        assert payload["state_topic"] == "enviro_raspberrypi/test/sensor"
        assert payload["availability_topic"] == "enviro_raspberrypi/status"
        assert payload["unit_of_measurement"] == "°C"
        assert "device_class" not in payload
        assert payload["state_class"] == "measurement"
        device_info = get_device_info("", APP_NAME, VERSION)
        assert payload["device"] == device_info

    def test_disc_payload_with_device_class(self):
        """Test discovery payload with device class."""
        payload = disc_payload("test/temp", "Temperature", "°C", "temperature")

        assert payload["device_class"] == "temperature"
        assert payload["state_class"] == "measurement"

    def test_disc_payload_text_sensor(self):
        """Test discovery payload for text sensor (no unit)."""
        payload = disc_payload("test/hostname", "Hostname", None, state_class=None)

        assert "unit_of_measurement" not in payload
        assert "state_class" not in payload

    def test_disc_payload_with_icon(self):
        """Test discovery payload with icon."""
        payload = disc_payload("test/sensor", "Test Sensor", "°C", icon="mdi:thermometer")

        assert payload["icon"] == "mdi:thermometer"


class TestPublishDiscovery:
    """Test discovery publishing."""

    def test_publish_discovery_sensors(self, mock_mqtt_client, mocker):
        """Test publishing sensor discovery."""
        from ha_enviro_plus.config import Config

        client = mock_mqtt_client.return_value
        config = Config.from_env()
        mocker.patch("ha_enviro_plus.agent.Config.from_env", return_value=config)

        publish_discovery(client, config)

        # Should publish config for each sensor
        expected_calls = len(SENSORS)
        assert client.publish.call_count >= expected_calls

        # Check a few specific sensor configs
        calls = client.publish.call_args_list

        # Find temperature sensor config
        temp_config_call = None
        for call in calls:
            topic = call[0][0]
            if "bme280_temperature" in topic:
                temp_config_call = call
                break

        assert temp_config_call is not None
        config = json.loads(temp_config_call[0][1])
        assert config["name"] == "Temperature"
        assert config["unit_of_measurement"] == "°C"
        assert config["device_class"] == "temperature"

    def test_publish_discovery_buttons(self, mock_mqtt_client, mock_device_id, mocker):
        """Test publishing button discovery."""
        from ha_enviro_plus.config import Config

        client = mock_mqtt_client.return_value
        config = Config.from_env()
        mocker.patch("ha_enviro_plus.agent.Config.from_env", return_value=config)

        publish_discovery(client, config)

        calls = client.publish.call_args_list

        # Find reboot button config
        reboot_config_call = None
        for call in calls:
            topic = call[0][0]
            if "button" in topic and "reboot" in topic:
                reboot_config_call = call
                break

        assert reboot_config_call is not None
        config = json.loads(reboot_config_call[0][1])
        assert config["name"] == "Reboot Enviro Zero"
        assert config["cmd_t"] == "enviro_raspberrypi/cmd"
        assert config["pl_prs"] == "reboot"
        assert config["icon"] == "mdi:restart"

    def test_publish_discovery_numbers(self, mock_mqtt_client, mock_device_id, mocker):
        """Test publishing number entity discovery."""
        from ha_enviro_plus.config import Config

        client = mock_mqtt_client.return_value
        config = Config.from_env()
        mocker.patch("ha_enviro_plus.agent.Config.from_env", return_value=config)

        publish_discovery(client, config)

        calls = client.publish.call_args_list

        # Find temp offset number config
        temp_offset_config_call = None
        for call in calls:
            topic = call[0][0]
            if "number" in topic and "temp_offset" in topic:
                temp_offset_config_call = call
                break

        assert temp_offset_config_call is not None
        config = json.loads(temp_offset_config_call[0][1])
        assert config["name"] == "Temp Offset"
        assert config["cmd_t"] == "enviro_raspberrypi/set/temp_offset"
        assert config["stat_t"] == "enviro_raspberrypi/set/temp_offset"
        assert config["unit_of_measurement"] == "°C"
        assert config["min"] == -10
        assert config["max"] == 10
        assert config["step"] == 0.1
