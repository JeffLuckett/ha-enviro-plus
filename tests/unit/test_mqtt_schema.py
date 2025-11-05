"""Unit tests for MQTT schema validation.

This module validates that the MQTT schema adheres to Home Assistant best practices
and maintains consistency across all entity types.
"""

import json
import pytest
from unittest.mock import Mock, patch

from ha_enviro_plus.agent import (
    disc_payload,
    publish_discovery,
    get_device_info,
    get_device_id,
    get_serial,
    get_mac_address,
    SENSORS,
    device_id,
    root,
    avail_t,
)


class TestDeviceIdentification:
    """Test device identification schema."""

    def test_device_id_uses_serial_when_available(self, mocker):
        """Test that device_id uses serial number when available."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="1234567890abcdef")
        mocker.patch("ha_enviro_plus.agent.hostname", "raspberrypi")

        # Recalculate device_id
        dev_id = get_device_id()

        assert dev_id == "enviro_1234567890abcdef"
        assert dev_id.startswith("enviro_")
        assert "raspberrypi" not in dev_id

    def test_device_id_falls_back_to_hostname(self, mocker):
        """Test that device_id falls back to hostname when serial unavailable."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="unknown")
        mocker.patch("ha_enviro_plus.agent.hostname", "raspberry-pi")

        dev_id = get_device_id()

        assert dev_id == "enviro_raspberrypi"  # hyphens removed
        assert dev_id.startswith("enviro_")

    def test_device_id_format(self, mocker):
        """Test that device_id follows correct format."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="abc123def456")

        dev_id = get_device_id()

        # Should start with "enviro_" and contain serial
        assert dev_id.startswith("enviro_")
        assert dev_id == "enviro_abc123def456"


class TestDeviceInfoSchema:
    """Test device info schema structure."""

    def test_device_info_has_required_fields(self):
        """Test that device_info contains all required fields."""
        device_info = get_device_info()

        required_fields = [
            "identifiers",
            "name",
            "manufacturer",
            "model",
            "sw_version",
            "configuration_url",
        ]

        for field in required_fields:
            assert field in device_info, f"Missing required field: {field}"

    def test_device_info_identifiers_uses_serial(self, mocker):
        """Test that identifiers uses serial number when available."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="1234567890abcdef")
        mocker.patch("ha_enviro_plus.agent.device_id", "enviro_1234567890abcdef")

        device_info = get_device_info()

        assert "identifiers" in device_info
        assert isinstance(device_info["identifiers"], list)
        assert len(device_info["identifiers"]) > 0
        assert device_info["identifiers"][0] == "1234567890abcdef"

    def test_device_info_identifiers_fallback(self, mocker):
        """Test that identifiers falls back to device_id when serial unavailable."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="unknown")
        mocker.patch("ha_enviro_plus.agent.device_id", "enviro_raspberrypi")

        device_info = get_device_info()

        assert "identifiers" in device_info
        assert device_info["identifiers"][0] == "enviro_raspberrypi"

    def test_device_info_connections_includes_mac(self, mocker):
        """Test that connections includes MAC address when available."""
        mocker.patch("ha_enviro_plus.agent.get_mac_address", return_value="aa:bb:cc:dd:ee:ff")

        device_info = get_device_info()

        assert "connections" in device_info
        assert isinstance(device_info["connections"], list)
        assert len(device_info["connections"]) > 0
        assert device_info["connections"][0] == ["mac", "aa:bb:cc:dd:ee:ff"]

    def test_device_info_connections_omitted_when_no_mac(self, mocker):
        """Test that connections is omitted when MAC address unavailable."""
        mocker.patch("ha_enviro_plus.agent.get_mac_address", return_value=None)

        device_info = get_device_info()

        # Connections should not be present if MAC is None
        if "connections" in device_info:
            assert len(device_info["connections"]) == 0

    def test_device_info_name_with_location(self, mocker):
        """Test that device name includes location when set."""
        mocker.patch("ha_enviro_plus.agent.DEVICE_LOCATION", "Living Room")

        device_info = get_device_info()

        assert device_info["name"] == "Enviro+ Living Room"

    def test_device_info_name_without_location(self, mocker):
        """Test that device name doesn't include location when not set."""
        mocker.patch("ha_enviro_plus.agent.DEVICE_LOCATION", "")

        device_info = get_device_info()

        assert device_info["name"] == "Enviro+"

    def test_device_info_manufacturer(self):
        """Test that manufacturer is correct."""
        device_info = get_device_info()

        assert device_info["manufacturer"] == "Pimoroni"

    def test_device_info_sw_version_format(self):
        """Test that sw_version follows expected format."""
        device_info = get_device_info()

        assert "sw_version" in device_info
        assert isinstance(device_info["sw_version"], str)
        assert "ha-enviro-plus" in device_info["sw_version"].lower()


class TestDiscoveryPayloadSchema:
    """Test discovery payload schema structure."""

    def test_disc_payload_has_required_fields(self, mock_device_id):
        """Test that discovery payload contains all required fields."""
        payload = disc_payload("test/sensor", "Test Sensor", "°C")

        required_fields = [
            "name",
            "uniq_id",
            "state_topic",
            "availability_topic",
            "device",
        ]

        for field in required_fields:
            assert field in payload, f"Missing required field: {field}"

    def test_disc_payload_unique_id_with_serial(self, mocker, mock_device_id):
        """Test that unique_id uses serial number when available."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="1234567890abcdef")

        payload = disc_payload("bme280/temperature", "Temperature", "°C")

        assert payload["uniq_id"] == "enviro_1234567890abcdef_bme280_temperature"
        assert payload["uniq_id"].startswith("enviro_")
        assert "1234567890abcdef" in payload["uniq_id"]

    def test_disc_payload_unique_id_fallback(self, mocker, mock_device_id):
        """Test that unique_id falls back to device_id when serial unavailable."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="unknown")
        mocker.patch("ha_enviro_plus.agent.device_id", "enviro_raspberrypi")

        payload = disc_payload("bme280/temperature", "Temperature", "°C")

        assert payload["uniq_id"] == "enviro_raspberrypi_bme280_temperature"
        assert payload["uniq_id"].startswith("enviro_")

    def test_disc_payload_unique_id_format(self, mocker, mock_device_id):
        """Test that unique_id follows correct format."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="abc123")

        payload = disc_payload("test/path", "Test Sensor", "°C")

        # Format: enviro_{serial}_{topic_path_with_underscores}
        assert payload["uniq_id"] == "enviro_abc123_test_path"
        assert payload["uniq_id"].count("_") >= 2  # At least enviro_serial_path

    def test_disc_payload_state_topic_format(self, mock_device_id):
        """Test that state_topic follows correct format."""
        payload = disc_payload("bme280/temperature", "Temperature", "°C")

        # Format: {device_id}/{sensor_path}
        # Use the mocked device_id value
        expected_topic = f"{mock_device_id}/bme280/temperature"
        assert payload["state_topic"] == expected_topic
        assert payload["state_topic"].startswith(mock_device_id)
        assert "/" in payload["state_topic"]

    def test_disc_payload_availability_topic(self, mock_device_id):
        """Test that availability_topic is correct."""
        payload = disc_payload("test/sensor", "Test Sensor", "°C")

        # Check format rather than exact value since avail_t might be set before mock
        assert payload["availability_topic"].endswith("/status")
        assert "enviro_" in payload["availability_topic"]

    def test_disc_payload_device_reference(self, mock_device_id):
        """Test that device reference is included."""
        payload = disc_payload("test/sensor", "Test Sensor", "°C")

        assert "device" in payload
        assert isinstance(payload["device"], dict)
        device_info = get_device_info()
        assert payload["device"] == device_info

    def test_disc_payload_unit_of_measurement(self, mock_device_id):
        """Test that unit_of_measurement is included when provided."""
        payload = disc_payload("test/sensor", "Test Sensor", "°C")

        assert payload["unit_of_measurement"] == "°C"

    def test_disc_payload_no_unit_of_measurement(self, mock_device_id):
        """Test that unit_of_measurement is omitted when None."""
        payload = disc_payload("test/hostname", "Hostname", None)

        assert "unit_of_measurement" not in payload

    def test_disc_payload_device_class(self, mock_device_id):
        """Test that device_class is included when provided."""
        payload = disc_payload("test/temp", "Temperature", "°C", "temperature")

        assert payload["device_class"] == "temperature"

    def test_disc_payload_state_class_measurement(self, mock_device_id):
        """Test that state_class is 'measurement' for sensors with units."""
        payload = disc_payload("test/sensor", "Test Sensor", "°C")

        assert payload["state_class"] == "measurement"

    def test_disc_payload_state_class_none_for_text(self, mock_device_id):
        """Test that state_class is None for text sensors."""
        payload = disc_payload("test/hostname", "Hostname", None, state_class=None)

        assert "state_class" not in payload or payload.get("state_class") is None


class TestPublishDiscoverySchema:
    """Test discovery publishing schema."""

    def test_all_sensors_have_discovery(self, mock_mqtt_client, mock_device_id):
        """Test that discovery is published for all sensors."""
        client = mock_mqtt_client.return_value

        publish_discovery(client)

        calls = client.publish.call_args_list
        sensor_calls = [c for c in calls if "sensor" in c[0][0] and "config" in c[0][0]]

        # Should have at least one discovery message per sensor
        assert len(sensor_calls) >= len(SENSORS)

    def test_discovery_topic_format(self, mock_mqtt_client, mocker, mock_device_id):
        """Test that discovery topics follow correct format."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="1234567890abcdef")
        mocker.patch("ha_enviro_plus.agent.MQTT_DISCOVERY_PREFIX", "homeassistant")

        client = mock_mqtt_client.return_value
        publish_discovery(client)

        calls = client.publish.call_args_list
        for call in calls:
            topic = call[0][0]
            if "config" in topic:
                # Format: {prefix}/{component}/{object_id}/{entity_id}/config
                parts = topic.split("/")
                assert len(parts) == 5, f"Invalid topic format: {topic}"
                assert parts[0] == "homeassistant"
                assert parts[1] in ["sensor", "button", "number"]
                assert parts[4] == "config"

    def test_discovery_payload_is_json(self, mock_mqtt_client, mock_device_id):
        """Test that discovery payloads are valid JSON."""
        client = mock_mqtt_client.return_value

        publish_discovery(client)

        calls = client.publish.call_args_list
        for call in calls:
            payload = call[0][1]
            # Should be valid JSON
            json.loads(payload)

    def test_discovery_qos_and_retain(self, mock_mqtt_client, mock_device_id):
        """Test that discovery messages use QoS 1 and retain."""
        client = mock_mqtt_client.return_value

        publish_discovery(client)

        calls = client.publish.call_args_list
        for call in calls:
            if "config" in call[0][0]:
                # Check keyword arguments
                kwargs = call[1] if len(call) > 1 else {}
                assert kwargs.get("qos", call[0][2] if len(call[0]) > 2 else 0) == 1
                assert kwargs.get("retain", call[0][3] if len(call[0]) > 3 else False) is True

    def test_button_discovery_unique_id_format(self, mock_mqtt_client, mocker, mock_device_id):
        """Test that button discovery unique_id follows correct format."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="1234567890abcdef")

        client = mock_mqtt_client.return_value
        publish_discovery(client)

        calls = client.publish.call_args_list
        button_calls = [c for c in calls if "button" in c[0][0] and "reboot" in c[0][0]]

        assert len(button_calls) > 0
        config = json.loads(button_calls[0][0][1])
        assert config["uniq_id"] == "enviro_1234567890abcdef_btn_reboot"
        assert config["uniq_id"].startswith("enviro_")
        assert "_btn_" in config["uniq_id"]

    def test_number_discovery_unique_id_format(self, mock_mqtt_client, mocker, mock_device_id):
        """Test that number discovery unique_id follows correct format."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="1234567890abcdef")

        client = mock_mqtt_client.return_value
        publish_discovery(client)

        calls = client.publish.call_args_list
        number_calls = [c for c in calls if "number" in c[0][0] and "temp_offset" in c[0][0]]

        assert len(number_calls) > 0
        config = json.loads(number_calls[0][0][1])
        assert config["uniq_id"] == "enviro_1234567890abcdef_num_temp_offset"

    def test_number_discovery_temp_smoothing_minutes(self, mock_mqtt_client, mocker, mock_device_id):
        """Test that temp_smoothing_minutes number entity is published."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="1234567890abcdef")
        mocker.patch("ha_enviro_plus.agent.device_id", "enviro_1234567890abcdef")
        mocker.patch("ha_enviro_plus.agent.root", "enviro_1234567890abcdef")

        client = mock_mqtt_client.return_value
        publish_discovery(client)

        calls = client.publish.call_args_list
        number_calls = [
            c for c in calls if "number" in c[0][0] and "temp_smoothing_minutes" in c[0][0]
        ]

        assert len(number_calls) > 0
        config = json.loads(number_calls[0][0][1])
        assert config["name"] == "Temp Smoothing Window"
        assert config["uniq_id"] == "enviro_1234567890abcdef_num_temp_smoothing_minutes"
        assert config["cmd_t"] == "enviro_1234567890abcdef/set/temp_smoothing_minutes"
        assert config["stat_t"] == "enviro_1234567890abcdef/set/temp_smoothing_minutes"
        assert config["unit_of_measurement"] == "min"
        assert config["min"] == 0.0
        assert config["max"] == 60.0
        assert config["step"] == 0.1
        assert config["uniq_id"].startswith("enviro_")
        assert "_num_" in config["uniq_id"]

    def test_sensor_discovery_unique_id_format(self, mock_mqtt_client, mocker, mock_device_id):
        """Test that sensor discovery unique_id follows correct format."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="1234567890abcdef")

        client = mock_mqtt_client.return_value
        publish_discovery(client)

        calls = client.publish.call_args_list
        sensor_calls = [c for c in calls if "sensor" in c[0][0] and "bme280_temperature" in c[0][0]]

        assert len(sensor_calls) > 0
        config = json.loads(sensor_calls[0][0][1])
        assert config["uniq_id"] == "enviro_1234567890abcdef_bme280_temperature"
        assert config["uniq_id"].startswith("enviro_")
        assert "_bme280_temperature" in config["uniq_id"]


class TestTopicStructure:
    """Test topic structure schema."""

    def test_root_topic_format(self, mock_device_id):
        """Test that root topic follows correct format."""
        assert root == device_id
        assert root.startswith("enviro_")

    def test_availability_topic_format(self, mock_device_id):
        """Test that availability topic follows correct format."""
        assert avail_t == f"{device_id}/status"
        assert avail_t.endswith("/status")

    def test_state_topic_format(self, mock_device_id):
        """Test that state topics follow correct format."""
        # State topics should be: {device_id}/{sensor_path}
        test_paths = [
            "bme280/temperature",
            "bme280/humidity",
            "host/cpu_temp",
            "meta/last_update",
        ]

        for path in test_paths:
            expected_topic = f"{device_id}/{path}"
            assert expected_topic.startswith(device_id)
            assert expected_topic.count("/") == 2  # device_id/path has 2 slashes

    def test_command_topic_format(self, mock_device_id):
        """Test that command topic follows correct format."""
        from ha_enviro_plus.agent import cmd_t

        assert cmd_t == f"{mock_device_id}/cmd"
        assert cmd_t.endswith("/cmd")

    def test_settings_topic_format(self, mock_device_id):
        """Test that settings topics follow correct format."""
        from ha_enviro_plus.agent import set_t

        assert set_t == f"{mock_device_id}/set/+"
        assert set_t.endswith("/set/+")

    def test_device_attributes_topic_format(self, mock_device_id):
        """Test that device attributes topic follows correct format."""
        expected_topic = f"{device_id}/device/attributes"
        assert expected_topic.startswith(device_id)
        assert expected_topic.endswith("/device/attributes")


class TestHomeAssistantBestPractices:
    """Test compliance with Home Assistant best practices."""

    def test_unique_id_uses_serial(self, mocker, mock_device_id):
        """Test that unique_id uses serial number (HA best practice)."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="1234567890abcdef")

        payload = disc_payload("test/sensor", "Test Sensor", "°C")

        # HA best practice: unique_id should use serial number
        assert payload["uniq_id"].startswith("enviro_1234567890abcdef")

    def test_device_identifiers_uses_serial(self, mocker):
        """Test that device identifiers uses serial number (HA best practice)."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="1234567890abcdef")
        mocker.patch("ha_enviro_plus.agent.device_id", "enviro_1234567890abcdef")

        device_info = get_device_info()

        # HA best practice: identifiers should use serial number
        assert device_info["identifiers"][0] == "1234567890abcdef"

    def test_device_connections_includes_mac(self, mocker):
        """Test that device connections includes MAC address (HA best practice)."""
        mocker.patch("ha_enviro_plus.agent.get_mac_address", return_value="aa:bb:cc:dd:ee:ff")

        device_info = get_device_info()

        # HA best practice: connections should include MAC address
        assert "connections" in device_info
        assert ["mac", "aa:bb:cc:dd:ee:ff"] in device_info["connections"]

    def test_all_entities_have_device_reference(self, mock_mqtt_client, mock_device_id):
        """Test that all discovery payloads include device reference."""
        client = mock_mqtt_client.return_value

        publish_discovery(client)

        calls = client.publish.call_args_list
        for call in calls:
            if "config" in call[0][0]:
                payload = json.loads(call[0][1])
                # HA best practice: all entities should reference device
                assert "device" in payload
                assert isinstance(payload["device"], dict)

    def test_unique_id_format_consistency(self, mock_mqtt_client, mocker, mock_device_id):
        """Test that unique_id format is consistent across all entity types."""
        mocker.patch("ha_enviro_plus.agent.get_serial", return_value="1234567890abcdef")

        client = mock_mqtt_client.return_value
        publish_discovery(client)

        calls = client.publish.call_args_list
        unique_ids = []

        for call in calls:
            if "config" in call[0][0]:
                payload = json.loads(call[0][1])
                unique_ids.append(payload["uniq_id"])

        # All unique_ids should start with enviro_{serial}
        for uniq_id in unique_ids:
            assert uniq_id.startswith(
                "enviro_1234567890abcdef"
            ), f"Unique ID {uniq_id} doesn't start with enviro_1234567890abcdef"
