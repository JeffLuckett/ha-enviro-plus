"""Unit tests for agent MQTT handlers."""

import pytest
from unittest.mock import Mock, patch

from ha_enviro_plus.agent import on_connect, on_message


class TestMQTTErrorScenarios:
    """Test MQTT error handling scenarios."""

    def test_on_message_decode_error(self, mocker, mock_device_id):
        """Test on_message when payload decode fails."""
        # Create a mock message with decode error
        mock_msg = Mock()
        mock_msg.payload.decode.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")
        mock_msg.topic = "enviro_raspberrypi/cmd"

        mock_client = Mock()
        mock_sensors = Mock()
        mock_logger = mocker.patch("ha_enviro_plus.agent.logger")

        # Should handle decode error gracefully
        on_message(mock_client, None, mock_msg, mock_sensors)

        # Should log the error using logger.exception
        assert mock_logger.exception.call_count > 0

    def test_on_message_invalid_json(self, mocker, mock_device_id):
        """Test on_message with malformed JSON in discovery."""
        # Create a mock message with invalid JSON
        mock_msg = Mock()
        mock_msg.payload.decode.return_value = "invalid json {"
        mock_msg.topic = "homeassistant/sensor/enviro_raspberrypi/test/config"

        mock_client = Mock()
        mock_sensors = Mock()
        mock_logger = mocker.patch("ha_enviro_plus.agent.logger")

        # Discovery messages are not processed by on_message, so no error should occur
        on_message(mock_client, None, mock_msg, mock_sensors)

        # No error should be logged since discovery messages are ignored
        assert mock_logger.exception.call_count == 0

    def test_on_message_unknown_command(self, mocker, mock_device_id):
        """Test on_message with unknown command."""
        mock_msg = Mock()
        mock_msg.payload.decode.return_value = "unknown_command"
        mock_msg.topic = "enviro_raspberrypi/cmd"

        mock_client = Mock()
        mock_sensors = Mock()
        mock_logger = mocker.patch("ha_enviro_plus.agent.logger")

        on_message(mock_client, None, mock_msg, mock_sensors)

        # Unknown commands are silently ignored, no logging
        assert mock_logger.info.call_count == 0
        assert mock_logger.warning.call_count == 0
        assert mock_logger.error.call_count == 0

    def test_on_message_unknown_calibration_setting(self, mocker, mock_device_id):
        """Test on_message with unknown calibration setting."""
        mock_msg = Mock()
        mock_msg.payload.decode.return_value = "5.0"
        mock_msg.topic = "enviro_raspberrypi/set/unknown_setting"

        mock_client = Mock()
        mock_sensors = Mock()
        mock_logger = mocker.patch("ha_enviro_plus.agent.logger")

        on_message(mock_client, None, mock_msg, mock_sensors)

        # Unknown settings should log a warning
        assert mock_logger.warning.call_count == 1
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Unknown calibration setting" in warning_call
        assert mock_logger.error.call_count == 0

    def test_on_message_invalid_calibration_value(self, mocker, mock_device_id):
        """Test on_message with invalid calibration value."""
        mock_msg = Mock()
        mock_msg.payload.decode.return_value = "not_a_number"
        mock_msg.topic = "enviro_raspberrypi/set/temp_offset"

        mock_client = Mock()
        mock_sensors = Mock()
        mock_logger = mocker.patch("ha_enviro_plus.agent.logger")

        on_message(mock_client, None, mock_msg, mock_sensors)

        # Invalid values should be logged as an error
        assert mock_logger.error.call_count > 0
        error_call = mock_logger.error.call_args[0][0]
        assert "Invalid value for" in error_call

    def test_mqtt_connection_failure(self, mocker, mock_device_id):
        """Test MQTT connection failure handling."""
        mock_client = Mock()
        mock_logger = mocker.patch("ha_enviro_plus.agent.logger")

        from ha_enviro_plus.config import Config

        config = Config.from_env()
        # Test connection failure (rc != 0)
        on_connect(mock_client, None, None, 1, config=config)  # rc=1 indicates connection failure

        # Should log the connection attempt with failure code
        assert mock_logger.info.call_count > 0
        # Check that it logged the connection attempt
        log_calls = [
            call for call in mock_logger.info.call_args_list if "Connected to MQTT" in str(call)
        ]
        assert len(log_calls) > 0

    def test_mqtt_connection_success(self, mocker, mock_device_id):
        """Test MQTT successful connection."""
        mock_client = Mock()
        mock_logger = mocker.patch("ha_enviro_plus.agent.logger")

        from ha_enviro_plus.config import Config

        config = Config.from_env()
        # Test successful connection (rc = 0)
        on_connect(mock_client, None, None, 0, config=config)

        # Should log successful connection and publish discovery
        assert mock_logger.info.call_count > 0
        # Should publish availability and discovery
        assert mock_client.publish.call_count > 0
        assert mock_client.subscribe.call_count > 0


class TestOnConnect:
    """Test MQTT on_connect handler."""

    def test_on_connect_basic(self, mock_mqtt_client, mock_device_id):
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
    """Test MQTT message handling."""

    def test_on_message_reboot_command(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
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
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
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
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
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
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
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
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
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
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
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

    def test_on_message_temp_smoothing_minutes_update(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test temperature smoothing window update via MQTT."""
        client = mock_mqtt_client.return_value

        msg = Mock()
        msg.topic = "enviro_raspberrypi/set/temp_smoothing_minutes"
        msg.payload.decode.return_value = "10.0"

        sensors = Mock()
        mock_settings = Mock()
        mock_settings.set_temp_smoothing_minutes = Mock()

        on_message(client, {"settings_manager": mock_settings}, msg, sensors)

        # Should update calibration
        sensors.update_calibration.assert_called_once_with(temp_smoothing_minutes=10.0)
        mock_settings.set_temp_smoothing_minutes.assert_called_once_with(10.0)
        # Should NOT publish back when value is valid (prevents infinite loop)
        # Only publishes back if value was clamped (outside valid range)
        assert client.publish.call_count == 0

    def test_on_message_temp_smoothing_minutes_clamped(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test temperature smoothing window update with value clamping."""
        client = mock_mqtt_client.return_value

        msg = Mock()
        msg.topic = "enviro_raspberrypi/set/temp_smoothing_minutes"
        msg.payload.decode.return_value = "70.0"  # Value outside valid range

        sensors = Mock()
        mock_settings = Mock()
        mock_settings.set_temp_smoothing_minutes = Mock()

        on_message(client, {"settings_manager": mock_settings}, msg, sensors)

        # Should update calibration with clamped value (60.0)
        sensors.update_calibration.assert_called_once_with(temp_smoothing_minutes=60.0)
        mock_settings.set_temp_smoothing_minutes.assert_called_once_with(60.0)
        # Should publish back when value was clamped (so HA shows corrected value)
        assert client.publish.call_count > 0
        # Verify the published value is the clamped value
        publish_calls = [
            call for call in client.publish.call_args_list if "temp_smoothing_minutes" in call[0][0]
        ]
        assert len(publish_calls) > 0
        assert publish_calls[0][0][1] == "60.0"

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

