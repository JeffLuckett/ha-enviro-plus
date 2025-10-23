"""Unit tests for ha_enviro_plus.agent module."""

import json
import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime

from ha_enviro_plus.agent import (
    get_ipv4_prefer_wlan0,
    get_uptime_seconds,
    get_model,
    get_serial,
    get_os_release,
    disc_payload,
    publish_discovery,
    read_all,
    on_connect,
    on_message,
    DEVICE_INFO,
    SENSORS,
)


class TestNetworkFunctions:
    """Test network-related utility functions."""

    def test_get_ipv4_prefer_wlan0_wlan0_available(self, mock_network_interfaces):
        """Test getting IPv4 address with wlan0 preference."""
        ip = get_ipv4_prefer_wlan0()
        assert ip == "192.168.1.100"

    def test_get_ipv4_prefer_wlan0_no_wlan0(self, mocker):
        """Test getting IPv4 address when wlan0 is not available."""
        mock_addrs = {
            "eth0": [Mock(family=Mock(name="AF_INET"), address="10.0.0.5")],
            "lo": [Mock(family=Mock(name="AF_INET"), address="127.0.0.1")],
        }

        mock_psutil = mocker.patch("ha_enviro_plus.agent.psutil.net_if_addrs")
        mock_psutil.return_value = mock_addrs

        ip = get_ipv4_prefer_wlan0()
        assert ip == "10.0.0.5"

    def test_get_ipv4_prefer_wlan0_no_non_loopback(self, mocker):
        """Test getting IPv4 address when only loopback is available."""
        mock_addrs = {"lo": [Mock(family=Mock(name="AF_INET"), address="127.0.0.1")]}

        mock_psutil = mocker.patch("ha_enviro_plus.agent.psutil.net_if_addrs")
        mock_psutil.return_value = mock_addrs

        ip = get_ipv4_prefer_wlan0()
        assert ip == "unknown"

    def test_get_ipv4_prefer_wlan0_exception(self, mocker):
        """Test getting IPv4 address when exception occurs."""
        mock_psutil = mocker.patch("ha_enviro_plus.agent.psutil.net_if_addrs")
        mock_psutil.side_effect = Exception("Network error")

        ip = get_ipv4_prefer_wlan0()
        assert ip == "unknown"


class TestSystemInfoFunctions:
    """Test system information utility functions."""

    def test_get_uptime_seconds_success(self, mock_file_operations):
        """Test successful uptime reading."""
        uptime = get_uptime_seconds()
        assert uptime == 12345

    def test_get_uptime_seconds_file_error(self, mocker):
        """Test uptime reading when file doesn't exist."""
        mocker.patch("builtins.open", side_effect=FileNotFoundError)

        uptime = get_uptime_seconds()
        assert uptime == 0

    def test_get_model_success(self, mock_file_operations):
        """Test successful model reading."""
        model = get_model()
        assert model == "Raspberry Pi Zero 2 W Rev 1.0"

    def test_get_model_file_error(self, mocker):
        """Test model reading when file doesn't exist."""
        mocker.patch("builtins.open", side_effect=FileNotFoundError)

        model = get_model()
        assert model == "Raspberry Pi"

    def test_get_serial_success(self, mock_file_operations):
        """Test successful serial reading."""
        serial = get_serial()
        assert serial == "1234567890abcdef"

    def test_get_serial_file_error(self, mocker):
        """Test serial reading when file doesn't exist."""
        mocker.patch("builtins.open", side_effect=FileNotFoundError)

        serial = get_serial()
        assert serial == "unknown"

    def test_get_serial_no_serial_line(self, mocker):
        """Test serial reading when Serial line is not found."""
        cpuinfo_content = """processor	: 0
model name	: ARMv7 Processor rev 3 (v7l)
"""
        cpuinfo_mock = mocker.mock_open(read_data=cpuinfo_content)
        mocker.patch("builtins.open", cpuinfo_mock)

        serial = get_serial()
        assert serial == "unknown"

    def test_get_os_release_success(self, mock_file_operations):
        """Test successful OS release reading."""
        os_release = get_os_release()
        assert os_release == "Raspberry Pi OS Lite (64-bit)"

    def test_get_os_release_file_error(self, mocker, mock_platform):
        """Test OS release reading when file doesn't exist."""
        mocker.patch("builtins.open", side_effect=FileNotFoundError)

        os_release = get_os_release()
        assert os_release == "Linux-5.15.0-rpi4-aarch64-with-glibc2.31"

    def test_get_os_release_no_pretty_name(self, mocker, mock_platform):
        """Test OS release reading when PRETTY_NAME is not found."""
        os_release_content = """NAME="Raspberry Pi OS Lite"
VERSION_ID="12"
"""
        os_release_mock = mocker.mock_open(read_data=os_release_content)
        mocker.patch("builtins.open", os_release_mock)

        os_release = get_os_release()
        assert os_release == "Linux-5.15.0-rpi4-aarch64-with-glibc2.31"


class TestDiscoveryPayload:
    """Test discovery payload generation."""

    def test_disc_payload_basic(self):
        """Test basic discovery payload."""
        payload = disc_payload("test/sensor", "Test Sensor", "°C")

        assert payload["name"] == "Test Sensor"
        assert payload["uniq_id"] == "enviro_raspberrypi_test_sensor"
        assert payload["state_topic"] == "enviro_raspberrypi/test/sensor"
        assert payload["availability_topic"] == "enviro_raspberrypi/status"
        assert payload["unit_of_measurement"] == "°C"
        assert payload["device_class"] is None
        assert payload["state_class"] == "measurement"
        assert payload["device"] == DEVICE_INFO

    def test_disc_payload_with_device_class(self):
        """Test discovery payload with device class."""
        payload = disc_payload("test/temp", "Temperature", "°C", "temperature")

        assert payload["device_class"] == "temperature"
        assert payload["state_class"] == "measurement"

    def test_disc_payload_text_sensor(self):
        """Test discovery payload for text sensor (no unit)."""
        payload = disc_payload("test/hostname", "Hostname", None)

        assert payload["unit_of_measurement"] is None
        assert payload["state_class"] is None

    def test_disc_payload_with_icon(self):
        """Test discovery payload with icon."""
        payload = disc_payload("test/sensor", "Test Sensor", "°C", icon="mdi:thermometer")

        assert payload["icon"] == "mdi:thermometer"


class TestPublishDiscovery:
    """Test discovery publishing."""

    def test_publish_discovery_sensors(self, mock_mqtt_client):
        """Test publishing sensor discovery."""
        client = mock_mqtt_client.return_value

        publish_discovery(client)

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

    def test_publish_discovery_buttons(self, mock_mqtt_client):
        """Test publishing button discovery."""
        client = mock_mqtt_client.return_value

        publish_discovery(client)

        calls = client.publish.call_args_list

        # Find reboot button config
        reboot_config_call = None
        for call in calls:
            topic = call[0][0]
            if "btn_reboot" in topic:
                reboot_config_call = call
                break

        assert reboot_config_call is not None
        config = json.loads(reboot_config_call[0][1])
        assert config["name"] == "Reboot Enviro Zero"
        assert config["cmd_t"] == "enviro_raspberrypi/cmd"
        assert config["pl_prs"] == "reboot"
        assert config["icon"] == "mdi:restart"

    def test_publish_discovery_numbers(self, mock_mqtt_client):
        """Test publishing number entity discovery."""
        client = mock_mqtt_client.return_value

        publish_discovery(client)

        calls = client.publish.call_args_list

        # Find temp offset number config
        temp_offset_config_call = None
        for call in calls:
            topic = call[0][0]
            if "num_temp_offset" in topic:
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


class TestReadAll:
    """Test read_all function."""

    def test_read_all_complete_data(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        mock_psutil,
        mock_socket,
        mock_platform,
    ):
        """Test reading all sensor and system data."""
        # Set up mock sensor data
        mock_bme280.get_temperature.return_value = 25.5
        mock_bme280.get_humidity.return_value = 45.0
        mock_bme280.get_pressure.return_value = 1013.25
        mock_ltr559.get_lux.return_value = 150.0
        mock_subprocess.return_value = b"temp=42.0'C\n"

        mock_gas_sensor.oxidising = 50000.0
        mock_gas_sensor.reducing = 30000.0
        mock_gas_sensor.nh3 = 40000.0

        # Set up mock system data
        mock_psutil["vm"].percent = 45.2
        mock_psutil["vm"].total = 8 * 1024 * 1024 * 1024
        mock_psutil["cpu"].return_value = 12.5

        # Mock file operations
        with patch("builtins.open", mock_open(read_data="12345.67 98765.43")):
            from ha_enviro_plus.sensors import EnviroPlusSensors

            sensors = EnviroPlusSensors()

            vals = read_all(sensors)

        # Verify sensor data
        assert vals["bme280/temperature"] == pytest.approx(25.5, abs=0.1)
        assert vals["bme280/humidity"] == pytest.approx(45.0, abs=0.1)
        assert vals["bme280/pressure"] == pytest.approx(1013.25, abs=0.1)
        assert vals["ltr559/lux"] == pytest.approx(150.0, abs=0.1)
        assert vals["gas/oxidising"] == pytest.approx(50.0, abs=0.1)
        assert vals["gas/reducing"] == pytest.approx(30.0, abs=0.1)
        assert vals["gas/nh3"] == pytest.approx(40.0, abs=0.1)

        # Verify system data
        assert vals["host/cpu_temp"] == 42.0
        assert vals["host/cpu_usage"] == 12.5
        assert vals["host/mem_usage"] == 45.2
        assert vals["host/mem_size"] == 8.0
        assert vals["host/uptime"] == 12345
        assert vals["host/hostname"] == "raspberrypi"
        assert vals["host/network"] == "192.168.1.100"
        assert vals["host/os_release"] == "Raspberry Pi OS Lite (64-bit)"

        # Verify metadata
        assert "meta/last_update" in vals
        # Should be ISO format timestamp
        datetime.fromisoformat(vals["meta/last_update"].replace("Z", "+00:00"))


class TestOnConnect:
    """Test MQTT on_connect handler."""

    def test_on_connect_basic(self, mock_mqtt_client):
        """Test basic on_connect functionality."""
        client = mock_mqtt_client.return_value

        on_connect(client, None, None, 0)

        # Should publish availability
        calls = client.publish.call_args_list
        availability_call = None
        for call in calls:
            if "status" in call[0][0]:
                availability_call = call
                break

        assert availability_call is not None
        assert availability_call[0][1] == "online"
        assert availability_call[1]["retain"] is True

        # Should subscribe to commands and settings
        subscribe_calls = client.subscribe.call_args_list
        assert len(subscribe_calls) == 1
        assert subscribe_calls[0][0][0] == [
            ("enviro_raspberrypi/cmd", 1),
            ("enviro_raspberrypi/set/+", 1),
        ]

    def test_on_connect_publishes_offsets(self, mock_mqtt_client, mock_env_vars):
        """Test on_connect publishes current offset values."""
        client = mock_mqtt_client.return_value

        on_connect(client, None, None, 0)

        calls = client.publish.call_args_list

        # Find offset publications
        temp_offset_call = None
        hum_offset_call = None
        cpu_factor_call = None

        for call in calls:
            topic = call[0][0]
            if "set/temp_offset" in topic:
                temp_offset_call = call
            elif "set/hum_offset" in topic:
                hum_offset_call = call
            elif "set/cpu_temp_factor" in topic:
                cpu_factor_call = call

        assert temp_offset_call is not None
        assert temp_offset_call[0][1] == "0.0"
        assert temp_offset_call[1]["retain"] is True

        assert hum_offset_call is not None
        assert hum_offset_call[0][1] == "0.0"
        assert hum_offset_call[1]["retain"] is True

        assert cpu_factor_call is not None
        assert cpu_factor_call[0][1] == "1.8"
        assert cpu_factor_call[1]["retain"] is True


class TestOnMessage:
    """Test MQTT on_message handler."""

    def test_on_message_reboot_command(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor
    ):
        """Test reboot command handling."""
        client = mock_mqtt_client.return_value

        # Create mock message
        msg = Mock()
        msg.topic = "enviro_raspberrypi/cmd"
        msg.payload.decode.return_value = "reboot"

        with patch("ha_enviro_plus.agent.subprocess.Popen") as mock_popen:
            on_message(client, None, msg, Mock())

            # Should publish offline status
            calls = client.publish.call_args_list
            offline_call = None
            for call in calls:
                if "status" in call[0][0] and call[0][1] == "offline":
                    offline_call = call
                    break

            assert offline_call is not None

            # Should call reboot command
            mock_popen.assert_called_once_with(["sudo", "reboot"])

    def test_on_message_shutdown_command(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor
    ):
        """Test shutdown command handling."""
        client = mock_mqtt_client.return_value

        msg = Mock()
        msg.topic = "enviro_raspberrypi/cmd"
        msg.payload.decode.return_value = "shutdown"

        with patch("ha_enviro_plus.agent.subprocess.Popen") as mock_popen:
            on_message(client, None, msg, Mock())

            # Should call shutdown command
            mock_popen.assert_called_once_with(["sudo", "shutdown", "-h", "now"])

    def test_on_message_restart_service_command(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor
    ):
        """Test restart service command handling."""
        client = mock_mqtt_client.return_value

        msg = Mock()
        msg.topic = "enviro_raspberrypi/cmd"
        msg.payload.decode.return_value = "restart_service"

        with patch("ha_enviro_plus.agent.subprocess.Popen") as mock_popen:
            on_message(client, None, msg, Mock())

            # Should call restart service command
            mock_popen.assert_called_once_with(
                ["sudo", "systemctl", "restart", "ha-enviro-plus.service"]
            )

    def test_on_message_temp_offset_update(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor
    ):
        """Test temperature offset update."""
        client = mock_mqtt_client.return_value

        msg = Mock()
        msg.topic = "enviro_raspberrypi/set/temp_offset"
        msg.payload.decode.return_value = "2.5"

        sensors = Mock()
        on_message(client, None, msg, sensors)

        # Should update calibration
        sensors.update_calibration.assert_called_once_with(temp_offset=2.5)

    def test_on_message_hum_offset_update(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor
    ):
        """Test humidity offset update."""
        client = mock_mqtt_client.return_value

        msg = Mock()
        msg.topic = "enviro_raspberrypi/set/hum_offset"
        msg.payload.decode.return_value = "-3.0"

        sensors = Mock()
        on_message(client, None, msg, sensors)

        # Should update calibration
        sensors.update_calibration.assert_called_once_with(hum_offset=-3.0)

    def test_on_message_cpu_factor_update(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor
    ):
        """Test CPU temperature factor update."""
        client = mock_mqtt_client.return_value

        msg = Mock()
        msg.topic = "enviro_raspberrypi/set/cpu_temp_factor"
        msg.payload.decode.return_value = "2.5"

        sensors = Mock()
        on_message(client, None, msg, sensors)

        # Should update calibration
        sensors.update_calibration.assert_called_once_with(cpu_temp_factor=2.5)

    def test_on_message_invalid_command(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor
    ):
        """Test handling of invalid command."""
        client = mock_mqtt_client.return_value

        msg = Mock()
        msg.topic = "enviro_raspberrypi/cmd"
        msg.payload.decode.return_value = "invalid_command"

        sensors = Mock()
        on_message(client, None, msg, sensors)

        # Should not call any system commands
        assert not sensors.update_calibration.called

    def test_on_message_invalid_topic(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor
    ):
        """Test handling of invalid topic."""
        client = mock_mqtt_client.return_value

        msg = Mock()
        msg.topic = "invalid/topic"
        msg.payload.decode.return_value = "some_value"

        sensors = Mock()
        on_message(client, None, msg, sensors)

        # Should not do anything
        assert not sensors.update_calibration.called

    def test_on_message_exception_handling(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor
    ):
        """Test exception handling in on_message."""
        client = mock_mqtt_client.return_value

        msg = Mock()
        msg.topic = "enviro_raspberrypi/cmd"
        msg.payload.decode.side_effect = Exception("Decode error")

        sensors = Mock()

        # Should not raise exception
        on_message(client, None, msg, sensors)

        # Should not call any methods
        assert not sensors.update_calibration.called


class TestConstants:
    """Test module constants."""

    def test_device_info_structure(self):
        """Test DEVICE_INFO structure."""
        assert "identifiers" in DEVICE_INFO
        assert "name" in DEVICE_INFO
        assert "manufacturer" in DEVICE_INFO
        assert "model" in DEVICE_INFO
        assert "sw_version" in DEVICE_INFO
        assert "configuration_url" in DEVICE_INFO

        assert DEVICE_INFO["name"] == "Enviro+"
        assert DEVICE_INFO["manufacturer"] == "Pimoroni"
        assert DEVICE_INFO["model"] == "Enviro+ (no PMS5003)"

    def test_sensors_structure(self):
        """Test SENSORS structure."""
        assert len(SENSORS) > 0

        # Check that all sensors have required fields
        for sensor_key, (name, unit, device_class) in SENSORS.items():
            assert isinstance(name, str)
            assert unit is None or isinstance(unit, str)
            assert device_class is None or isinstance(device_class, str)

        # Check specific sensors exist
        assert "bme280/temperature" in SENSORS
        assert "bme280/humidity" in SENSORS
        assert "bme280/pressure" in SENSORS
        assert "ltr559/lux" in SENSORS
        assert "gas/oxidising" in SENSORS
        assert "gas/reducing" in SENSORS
        assert "gas/nh3" in SENSORS
