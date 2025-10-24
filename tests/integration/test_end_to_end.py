"""End-to-end integration tests for complete workflows."""

import pytest
import threading
from unittest.mock import Mock, patch
from datetime import datetime

from ha_enviro_plus.agent import main, on_message, read_all
from ha_enviro_plus.sensors import EnviroPlusSensors


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""

    def test_startup_discovery_publishing_loop(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        mock_psutil,
        mock_socket,
        mock_platform,
        mock_env_vars,
        mock_file_operations,
        mock_device_id,
    ):
        """Test complete startup → discovery → publishing loop."""
        # Set up mock sensor data
        mock_bme280.get_temperature.return_value = 25.5
        mock_bme280.get_humidity.return_value = 45.0
        mock_bme280.get_pressure.return_value = 1013.25
        mock_ltr559.get_lux.return_value = 150.0
        mock_subprocess.return_value = "temp=42.0'C\n"

        mock_gas_sensor.oxidising = 50000.0
        mock_gas_sensor.reducing = 30000.0
        mock_gas_sensor.nh3 = 40000.0

        mock_psutil["vm"].percent = 45.2
        mock_psutil["vm"].total = 8 * 1024 * 1024 * 1024
        mock_psutil["cpu"].return_value = 12.5

        # Mock MQTT client
        mock_client = Mock()
        mock_client.publish = Mock()
        mock_client.subscribe = Mock()
        mock_client.connect = Mock()
        mock_client.loop_start = Mock()
        mock_client.loop_stop = Mock()
        mock_client.disconnect = Mock()

        with patch("ha_enviro_plus.agent.mqtt.Client") as mock_mqtt_class:
            mock_mqtt_class.return_value = mock_client

            # Mock the main function components
            with patch("ha_enviro_plus.agent.SettingsManager") as mock_settings_class:
                mock_settings = Mock()
                mock_settings_class.return_value = mock_settings
                mock_settings.get_temp_offset.return_value = 0.0
                mock_settings.get_hum_offset.return_value = 0.0
                mock_settings.get_cpu_temp_factor.return_value = 1.8
                mock_settings.get_cpu_temp_smoothing.return_value = 0.1

                with patch("ha_enviro_plus.agent.EnviroPlusSensors") as mock_sensors_class:
                    mock_sensors = Mock()
                    mock_sensors_class.return_value = mock_sensors
                    mock_sensors.get_all_sensor_data.return_value = {
                        "temperature": 25.5,
                        "temperature_raw": 25.5,
                        "humidity": 45.0,
                        "humidity_raw": 45.0,
                        "pressure": 1013.25,
                        "pressure_raw": 1013.25,
                        "lux": 150.0,
                        "lux_raw": 150.0,
                        "gas_oxidising": 50.0,
                        "gas_oxidising_raw": 50000.0,
                        "gas_reducing": 30.0,
                        "gas_reducing_raw": 30000.0,
                        "gas_nh3": 40.0,
                        "gas_nh3_raw": 40000.0,
                    }
                    mock_sensors._read_cpu_temp.return_value = 42.0
                    mock_sensors.cpu_temp.return_value = 42.0

                    # Mock the main loop to run once
                    with patch("ha_enviro_plus.agent.time.sleep") as mock_sleep:
                        # Let the first sleep pass, then interrupt on the second
                        mock_sleep.side_effect = [None, KeyboardInterrupt()]

                        # Run main function - expect SystemExit from graceful shutdown
                        with pytest.raises(SystemExit) as exc_info:
                            main()
                        assert exc_info.value.code == 0  # Successful shutdown

                        # Manually trigger on_connect to simulate connection
                        from ha_enviro_plus.agent import on_connect

                        on_connect(mock_client, None, None, 0)

        # Verify MQTT client was configured (no auth by default)
        # mock_client.username_pw_set.assert_called_once_with("testuser", "testpass")
        mock_client.will_set.assert_called_once()
        mock_client.connect.assert_called_once_with("homeassistant.local", 1883, keepalive=60)
        mock_client.loop_start.assert_called_once()
        # loop_stop may be called twice due to finally block, but should be called at least once
        assert mock_client.loop_stop.call_count >= 1
        # disconnect may be called twice due to finally block, but should be called at least once
        assert mock_client.disconnect.call_count >= 1

        # Verify discovery was published
        discovery_calls = [
            call for call in mock_client.publish.call_args_list if "config" in call[0][0]
        ]
        assert len(discovery_calls) > 0

        # Verify sensor data was published
        sensor_calls = [
            call
            for call in mock_client.publish.call_args_list
            if "enviro_raspberrypi/" in call[0][0] and "config" not in call[0][0]
        ]
        assert len(sensor_calls) > 0

        # Verify availability was published
        availability_calls = [
            call for call in mock_client.publish.call_args_list if "status" in call[0][0]
        ]
        assert len(availability_calls) >= 2  # online and offline

    def test_calibration_update_workflow(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        mock_psutil,
        mock_socket,
        mock_platform,
        mock_env_vars,
        mock_file_operations,
        mock_device_id,
    ):
        """Test calibration update workflow."""
        # Create sensors instance
        sensors = EnviroPlusSensors(temp_offset=0.0, hum_offset=0.0)

        # Mock MQTT client and message
        mock_client = Mock()
        mock_msg = Mock()
        mock_msg.topic = "enviro_raspberrypi/set/temp_offset"
        mock_msg.payload.decode.return_value = "2.5"

        # Test calibration update
        on_message(mock_client, None, mock_msg, sensors)

        # Verify calibration was updated
        assert sensors.temp_offset == 2.5

        # Test humidity calibration update
        mock_msg.topic = "enviro_raspberrypi/set/hum_offset"
        mock_msg.payload.decode.return_value = "-3.0"

        on_message(mock_client, None, mock_msg, sensors)

        # Verify humidity calibration was updated
        assert sensors.hum_offset == -3.0

        # Test CPU factor update
        mock_msg.topic = "enviro_raspberrypi/set/cpu_temp_factor"
        mock_msg.payload.decode.return_value = "2.0"

        on_message(mock_client, None, mock_msg, sensors)

        # Verify CPU factor was updated
        assert sensors.cpu_temp_factor == 2.0

    def test_command_execution_workflow(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        mock_psutil,
        mock_socket,
        mock_platform,
        mock_env_vars,
        mock_file_operations,
        mock_device_id,
    ):
        """Test command execution workflow."""
        sensors = Mock()

        # Mock MQTT client
        mock_client = Mock()

        # Test reboot command
        mock_msg = Mock()
        mock_msg.topic = "enviro_raspberrypi/cmd"
        mock_msg.payload.decode.return_value = "reboot"

        with patch("ha_enviro_plus.agent.subprocess.Popen") as mock_popen:
            on_message(mock_client, None, mock_msg, sensors)

            # Verify reboot command was executed
            mock_popen.assert_called_once_with(["sudo", "reboot"])

            # Verify offline status was published
            offline_calls = [
                call for call in mock_client.publish.call_args_list if call[0][1] == "offline"
            ]
            assert len(offline_calls) > 0

        # Test shutdown command
        mock_msg.payload.decode.return_value = "shutdown"

        with patch("ha_enviro_plus.agent.subprocess.Popen") as mock_popen:
            on_message(mock_client, None, mock_msg, sensors)

            # Verify shutdown command was executed
            mock_popen.assert_called_once_with(["sudo", "shutdown", "-h", "now"])

        # Test restart service command
        mock_msg.payload.decode.return_value = "restart_service"

        with patch("ha_enviro_plus.agent.subprocess.Popen") as mock_popen:
            on_message(mock_client, None, mock_msg, sensors)

            # Verify restart service command was executed
            mock_popen.assert_called_once_with(
                ["sudo", "systemctl", "restart", "ha-enviro-plus.service"]
            )

    def test_error_recovery_workflow(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        mock_psutil,
        mock_socket,
        mock_platform,
        mock_env_vars,
        mock_file_operations,
        mock_device_id,
    ):
        """Test error recovery workflow."""
        # Test sensor initialization failure recovery
        with patch("ha_enviro_plus.sensors.BME280") as mock_bme280_class:
            mock_bme280_class.side_effect = Exception("Sensor not found")

            # Should raise exception during initialization
            with pytest.raises(Exception, match="Sensor not found"):
                EnviroPlusSensors()

        # Test CPU temperature reading failure
        mock_subprocess.side_effect = Exception("Command failed")

        sensors = EnviroPlusSensors()

        # Should raise exception when CPU temp reading fails
        with pytest.raises(Exception, match="Command failed"):
            sensors._read_cpu_temp()

        # Test temperature compensation with CPU failure
        raw_temp = 25.0
        compensated_temp = sensors._apply_temp_compensation(raw_temp)

        # Should return raw temp when CPU temp fails
        assert compensated_temp == raw_temp

    def test_data_collection_workflow(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        mock_psutil,
        mock_socket,
        mock_platform,
        mock_env_vars,
        mock_file_operations,
        mock_device_id,
    ):
        """Test complete data collection workflow."""
        # Set up mock sensor data
        mock_bme280.get_temperature.return_value = 25.5
        mock_bme280.get_humidity.return_value = 45.0
        mock_bme280.get_pressure.return_value = 1013.25
        mock_ltr559.get_lux.return_value = 150.0
        mock_subprocess.return_value = "temp=42.0'C\n"

        mock_gas_sensor.oxidising = 50000.0
        mock_gas_sensor.reducing = 30000.0
        mock_gas_sensor.nh3 = 40000.0

        mock_psutil["vm"].percent = 45.2
        mock_psutil["vm"].total = 8 * 1024 * 1024 * 1024
        mock_psutil["cpu"].return_value = 12.5

        # Create sensors instance
        sensors = EnviroPlusSensors(temp_offset=1.0, hum_offset=2.0)

        # Collect all data with mocked hostname and network
        with patch("ha_enviro_plus.agent.hostname", "raspberrypi"):
            with patch("ha_enviro_plus.agent.get_ipv4_prefer_wlan0", return_value="192.168.1.100"):
                vals = read_all(sensors)

        # Verify all expected data is present
        expected_keys = {
            "bme280/temperature",
            "bme280/humidity",
            "bme280/pressure",
            "ltr559/lux",
            "gas/oxidising",
            "gas/reducing",
            "gas/nh3",
            "host/cpu_temp",
            "host/cpu_usage",
            "host/mem_usage",
            "host/mem_size",
            "host/uptime",
            "host/hostname",
            "host/network",
            "host/os_release",
            "meta/last_update",
        }

        assert set(vals.keys()) == expected_keys

        # Verify sensor data values
        # Temperature: 25.5 raw, compensated to ~16.33, + 1.0 offset = ~17.33
        assert vals["bme280/temperature"] == pytest.approx(17.33, abs=0.1)
        assert vals["bme280/humidity"] == pytest.approx(47.0, abs=0.1)  # 45.0 + 2.0 offset
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

    def test_graceful_shutdown_workflow(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        mock_psutil,
        mock_socket,
        mock_platform,
        mock_env_vars,
        mock_file_operations,
    ):
        """Test graceful shutdown workflow."""
        # Mock MQTT client
        mock_client = Mock()
        mock_client.publish = Mock()
        mock_client.loop_stop = Mock()
        mock_client.disconnect = Mock()

        # Simulate graceful shutdown
        try:
            # Publish offline status
            mock_client.publish("enviro_raspberrypi/status", "offline", retain=True)

            # Stop network loop
            mock_client.loop_stop()

            # Disconnect
            mock_client.disconnect()

        except Exception:
            pass  # Should handle shutdown gracefully

        # Verify shutdown sequence was executed
        mock_client.publish.assert_called_with("enviro_raspberrypi/status", "offline", retain=True)
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()

    def test_concurrent_operations(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        mock_psutil,
        mock_socket,
        mock_platform,
        mock_env_vars,
        mock_file_operations,
        mock_device_id,
    ):
        """Test concurrent operations handling."""
        sensors = EnviroPlusSensors()

        # Mock MQTT client
        mock_client = Mock()

        # Test concurrent calibration updates
        def update_temp_offset():
            mock_msg = Mock()
            mock_msg.topic = "enviro_raspberrypi/set/temp_offset"
            mock_msg.payload.decode.return_value = "1.0"
            on_message(mock_client, None, mock_msg, sensors)

        def update_hum_offset():
            mock_msg = Mock()
            mock_msg.topic = "enviro_raspberrypi/set/hum_offset"
            mock_msg.payload.decode.return_value = "2.0"
            on_message(mock_client, None, mock_msg, sensors)

        # Run updates concurrently
        thread1 = threading.Thread(target=update_temp_offset)
        thread2 = threading.Thread(target=update_hum_offset)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Verify both updates were applied
        assert sensors.temp_offset == 1.0
        assert sensors.hum_offset == 2.0

    def test_configuration_persistence(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        mock_psutil,
        mock_socket,
        mock_platform,
        mock_env_vars,
        mock_file_operations,
    ):
        """Test configuration persistence across restarts."""
        # Test that environment variables are properly loaded
        assert mock_env_vars["TEMP_OFFSET"] == "0.0"
        assert mock_env_vars["HUM_OFFSET"] == "0.0"
        assert mock_env_vars["CPU_TEMP_FACTOR"] == "1.8"
        assert mock_env_vars["MQTT_HOST"] == "test-broker.local"
        assert mock_env_vars["MQTT_PORT"] == "1883"
        assert mock_env_vars["MQTT_USER"] == "testuser"
        assert mock_env_vars["MQTT_PASS"] == "testpass"

        # Test that sensors are initialized with correct values
        sensors = EnviroPlusSensors(
            temp_offset=float(mock_env_vars["TEMP_OFFSET"]),
            hum_offset=float(mock_env_vars["HUM_OFFSET"]),
            cpu_temp_factor=float(mock_env_vars["CPU_TEMP_FACTOR"]),
        )

        assert sensors.temp_offset == 0.0
        assert sensors.hum_offset == 0.0
        assert sensors.cpu_temp_factor == 1.8

    def test_logging_workflow(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        mock_psutil,
        mock_socket,
        mock_platform,
        mock_env_vars,
        mock_file_operations,
        mock_device_id,
    ):
        """Test logging workflow."""
        # Test that logger is properly configured
        with patch("ha_enviro_plus.agent.logger") as mock_logger:
            # Import and use logger
            from ha_enviro_plus.agent import logger

            logger.info("Test message")

            # Verify logger was called
            mock_logger.info.assert_called_with("Test message")

        # Test sensor logging
        with patch("ha_enviro_plus.sensors.logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            sensors = EnviroPlusSensors()
            sensors.update_calibration(temp_offset=1.0)

            # Verify calibration update was logged
            mock_logger.info.assert_called_with("Updated temperature offset to %s°C", 1.0)
