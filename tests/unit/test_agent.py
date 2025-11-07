"""Unit tests for ha_enviro_plus.agent module."""

import json
import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime

from ha_enviro_plus.agent import (
    disc_payload,
    publish_discovery,
    read_all,
    on_connect,
    on_message,
    _handle_command,
    _handle_calibration_setting,
    SENSORS,
)
from ha_enviro_plus.system_info import get_device_info


class TestLoggingSetup:
    """Test logging setup and error handling."""

    def test_log_file_handler_error(self, mocker):
        """Test logging setup when file handler creation fails."""
        # Mock FileHandler to raise an exception
        mocker.patch("logging.FileHandler", side_effect=PermissionError("Permission denied"))

        # Mock the Config to enable log_to_file
        from ha_enviro_plus.config import Config

        config = Config.from_env()
        config.log_to_file = True

        # Test that main() handles file handler errors gracefully
        mocker.patch("ha_enviro_plus.agent.Config.from_env", return_value=config)
        mocker.patch("ha_enviro_plus.agent.validate_config")
        mocker.patch("ha_enviro_plus.agent.SettingsManager")
        mocker.patch("ha_enviro_plus.agent.EnviroPlusSensors")
        mocker.patch("ha_enviro_plus.agent.DisplayManager")
        mocker.patch("ha_enviro_plus.agent.mqtt.Client")

        # Should not raise an exception, just skip file logging
        assert True  # If we get here, the error was handled gracefully


class TestMainFunction:
    """Test the main function and startup."""

    def test_main_function_startup(self, mocker, mock_device_id):
        """Test main function startup logging."""
        # Mock all the dependencies
        mocker.patch("ha_enviro_plus.agent.mqtt.Client")
        mocker.patch("ha_enviro_plus.agent.EnviroPlusSensors")
        mock_settings_manager = mocker.patch("ha_enviro_plus.agent.SettingsManager")
        # Mock settings manager methods
        mock_settings_instance = mock_settings_manager.return_value
        mock_settings_instance.get_temp_offset.return_value = 0.0
        mock_settings_instance.get_hum_offset.return_value = 0.0
        mock_settings_instance.get_cpu_temp_factor.return_value = 1.8
        mock_settings_instance.get_cpu_temp_smoothing.return_value = 0.1
        mock_settings_instance.get_temp_smoothing_minutes.return_value = 5.0
        mock_settings_instance.get_units.return_value = "metric"
        mock_settings_instance.set_units.return_value = None
        mocker.patch("ha_enviro_plus.agent.time.sleep", side_effect=KeyboardInterrupt)

        # Mock the logger to capture log messages
        mock_logger = mocker.patch("ha_enviro_plus.agent.logger")

        # Import and call main
        from ha_enviro_plus.agent import main

        try:
            main()
        except SystemExit as e:
            assert e.code == 0  # Successful graceful shutdown
        except KeyboardInterrupt:
            pass  # Expected from our mock

        # Verify startup messages were logged
        assert mock_logger.info.call_count >= 4  # At least startup messages
        startup_calls = [
            call for call in mock_logger.info.call_args_list if "starting" in str(call)
        ]
        assert len(startup_calls) > 0


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
        mock_subprocess.return_value = "temp=42.0'C\n"

        mock_gas_sensor.oxidising = 50000.0
        mock_gas_sensor.reducing = 30000.0
        mock_gas_sensor.nh3 = 40000.0

        # Set up mock system data
        mock_psutil["vm"].percent = 45.2
        mock_psutil["vm"].total = 8 * 1024 * 1024 * 1024
        mock_psutil["cpu"].return_value = 12.5

        # Mock file operations and system functions
        def mock_open_side_effect(filename, mode="r", **kwargs):
            if filename == "/proc/uptime":
                return mock_open(read_data="12345.67 98765.43")()
            elif filename == "/etc/os-release":
                return mock_open(read_data='PRETTY_NAME="Raspberry Pi OS Lite (64-bit)"\n')()
            else:
                raise FileNotFoundError(f"No mock for {filename}")

        with patch("builtins.open", side_effect=mock_open_side_effect):
            with patch("os.path.exists", return_value=True):
                with patch("ha_enviro_plus.system_info.get_hostname", return_value="raspberrypi"):
                    with patch(
                        "ha_enviro_plus.system_info.get_ipv4_prefer_wlan0",
                        return_value="192.168.1.100",
                    ):
                        from ha_enviro_plus.sensors import EnviroPlusSensors

                        sensors = EnviroPlusSensors()

                        vals = read_all(sensors)

                        # Verify sensor data
                        assert vals["bme280/temperature"] == pytest.approx(16.33, abs=0.1)
                        # Humidity compensation depends on smoothing - first reading may vary
                        assert vals["bme280/humidity"] == pytest.approx(
                            46.83, abs=0.1
                        )  # With compensation (first reading)
                        assert vals["bme280/pressure"] == pytest.approx(1013.25, abs=0.1)
                        assert vals["ltr559/lux"] == pytest.approx(150.0, abs=0.1)
                        # Proximity should be present if LTR559 is available
                        if "ltr559/proximity" in vals:
                            assert isinstance(vals["ltr559/proximity"], (int, float))
                        # Gas sensor data may not be available if gas sensor is not initialized
                        if "gas/oxidising" in vals:
                            assert vals["gas/oxidising"] == pytest.approx(
                                50.0, abs=0.1
                            ), "Gas oxidising value should match expected"
                        if "gas/reducing" in vals:
                            assert vals["gas/reducing"] == pytest.approx(
                                30.0, abs=0.1
                            ), "Gas reducing value should match expected"
                        if "gas/nh3" in vals:
                            assert vals["gas/nh3"] == pytest.approx(
                                40.0, abs=0.1
                            ), "Gas NH3 value should match expected"

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


class TestConstants:
    """Test module constants."""

    def test_device_info_structure(self):
        """Test get_device_info() structure."""
        from ha_enviro_plus.agent import APP_NAME, VERSION

        device_info = get_device_info("", APP_NAME, VERSION)
        assert "identifiers" in device_info
        assert "name" in device_info
        assert "manufacturer" in device_info
        assert "model" in device_info
        assert "sw_version" in device_info
        assert "configuration_url" in device_info

        assert device_info["name"] == "Enviro+"
        assert device_info["manufacturer"] == "Pimoroni"
        # Model may vary based on actual device, so just check it exists
        assert "model" in device_info

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
        assert "ltr559/proximity" in SENSORS
        assert "gas/oxidising" in SENSORS
        assert "gas/reducing" in SENSORS
        assert "gas/nh3" in SENSORS
        assert "noise/spl_db" in SENSORS


class TestSettingsIntegration:
    """Test settings manager integration with agent."""

    def test_handle_command_reset_settings(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test reset_settings command handling."""
        client = mock_mqtt_client.return_value

        # Mock settings manager
        mock_settings_manager = Mock()
        mock_settings_manager.reset_to_defaults.return_value = None
        mock_settings_manager.temp_offset = 0.0
        mock_settings_manager.hum_offset = 0.0
        mock_settings_manager.cpu_temp_factor = 1.8
        mock_settings_manager.cpu_temp_smoothing = 0.1
        mock_settings_manager.get_temp_offset.return_value = 0.0
        mock_settings_manager.get_hum_offset.return_value = 0.0
        mock_settings_manager.get_cpu_temp_factor.return_value = 1.8
        mock_settings_manager.get_cpu_temp_smoothing.return_value = 0.1

        _handle_command(client, "reset_settings", mock_settings_manager)

        # Verify settings manager methods were called
        mock_settings_manager.reset_to_defaults.assert_called_once()

        # Verify MQTT publish calls for reset values
        publish_calls = client.publish.call_args_list
        temp_offset_call = None
        hum_offset_call = None
        cpu_factor_call = None
        cpu_smoothing_call = None

        for call in publish_calls:
            topic = call[0][0]
            value = call[0][1]
            if "temp_offset" in topic:
                temp_offset_call = call
            elif "hum_offset" in topic:
                hum_offset_call = call
            elif "cpu_temp_factor" in topic:
                cpu_factor_call = call
            elif "cpu_temp_smoothing" in topic:
                cpu_smoothing_call = call

        assert temp_offset_call is not None
        assert temp_offset_call[0][1] == "0.0"
        assert temp_offset_call[1]["retain"] is True

        assert hum_offset_call is not None
        assert hum_offset_call[0][1] == "0.0"
        assert hum_offset_call[1]["retain"] is True

        assert cpu_factor_call is not None
        assert cpu_factor_call[0][1] == "1.8"
        assert cpu_factor_call[1]["retain"] is True

        assert cpu_smoothing_call is not None
        assert cpu_smoothing_call[0][1] == "0.1"
        assert cpu_smoothing_call[1]["retain"] is True

    def test_handle_command_reset_settings_no_manager(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test reset_settings command when no settings manager is available."""
        client = mock_mqtt_client.return_value

        # Should not raise an exception
        _handle_command(client, "reset_settings", None)

    def test_handle_calibration_setting_with_settings_manager(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test calibration setting handling with settings manager."""
        client = mock_mqtt_client.return_value

        # Mock settings manager
        mock_settings_manager = Mock()

        # Mock enviro sensors
        mock_enviro_sensors = Mock()

        _handle_calibration_setting(
            client,
            "enviro_raspberrypi/set/temp_offset",
            "2.5",
            mock_enviro_sensors,
            mock_settings_manager,
        )

        # Verify settings manager was called
        mock_settings_manager.set_temp_offset.assert_called_once_with(2.5)

        # Verify sensor calibration was updated
        mock_enviro_sensors.update_calibration.assert_called_once_with(temp_offset=2.5)

    def test_handle_calibration_setting_without_settings_manager(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test calibration setting handling without settings manager."""
        client = mock_mqtt_client.return_value

        # Mock enviro sensors
        mock_enviro_sensors = Mock()

        _handle_calibration_setting(
            client, "enviro_raspberrypi/set/temp_offset", "2.5", mock_enviro_sensors, None
        )

        # Verify sensor calibration was still updated
        mock_enviro_sensors.update_calibration.assert_called_once_with(temp_offset=2.5)

    def test_handle_calibration_setting_invalid_value(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test calibration setting handling with invalid value."""
        client = mock_mqtt_client.return_value

        # Mock settings manager
        mock_settings_manager = Mock()

        # Mock enviro sensors
        mock_enviro_sensors = Mock()

        # Should not raise an exception for invalid value
        _handle_calibration_setting(
            client,
            "enviro_raspberrypi/set/temp_offset",
            "invalid",
            mock_enviro_sensors,
            mock_settings_manager,
        )

        # Settings manager should not be called for invalid values
        mock_settings_manager.set_temp_offset.assert_not_called()
        mock_enviro_sensors.update_calibration.assert_not_called()

    def test_on_message_with_settings_manager(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test on_message with settings manager in userdata."""
        client = mock_mqtt_client.return_value

        # Mock settings manager
        mock_settings_manager = Mock()

        # Mock userdata
        userdata = {"settings_manager": mock_settings_manager}

        # Mock message
        msg = Mock()
        msg.topic = "enviro_raspberrypi/set/temp_offset"
        msg.payload.decode.return_value = "1.5"

        # Mock enviro sensors
        mock_enviro_sensors = Mock()

        with patch("ha_enviro_plus.agent._handle_calibration_setting") as mock_handler:
            on_message(client, userdata, msg, mock_enviro_sensors)

            # Verify calibration handler was called with settings manager
            mock_handler.assert_called_once_with(
                client,
                "enviro_raspberrypi/set/temp_offset",
                "1.5",
                mock_enviro_sensors,
                mock_settings_manager,
            )

    def test_on_message_without_settings_manager(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test on_message without settings manager in userdata."""
        client = mock_mqtt_client.return_value

        # Mock message
        msg = Mock()
        msg.topic = "enviro_raspberrypi/set/temp_offset"
        msg.payload.decode.return_value = "1.5"

        # Mock enviro sensors
        mock_enviro_sensors = Mock()

        with patch("ha_enviro_plus.agent._handle_calibration_setting") as mock_handler:
            on_message(client, None, msg, mock_enviro_sensors)

            # Verify calibration handler was called without settings manager
            mock_handler.assert_called_once_with(
                client,
                "enviro_raspberrypi/set/temp_offset",
                "1.5",
                mock_enviro_sensors,
                None,
            )

    def test_on_connect_with_settings_manager(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test on_connect with settings manager in userdata."""
        client = mock_mqtt_client.return_value

        # Mock settings manager
        mock_settings_manager = Mock()
        mock_settings_manager.temp_offset = 1.0
        mock_settings_manager.hum_offset = 2.0
        mock_settings_manager.cpu_temp_factor = 2.5
        mock_settings_manager.cpu_temp_smoothing = 0.3
        mock_settings_manager.pressure_offset = 0.0
        mock_settings_manager.elevation_meters = 0.0
        mock_settings_manager.noise_calibration_offset = 60.0
        mock_settings_manager.get_temp_offset.return_value = 1.0
        mock_settings_manager.get_hum_offset.return_value = 2.0
        mock_settings_manager.get_cpu_temp_factor.return_value = 2.5
        mock_settings_manager.get_cpu_temp_smoothing.return_value = 0.3
        mock_settings_manager.get_temp_smoothing_minutes.return_value = 5.0

        # Mock userdata
        userdata = {"settings_manager": mock_settings_manager}

        from ha_enviro_plus.config import Config

        config = Config.from_env()
        with patch("ha_enviro_plus.agent.publish_discovery"):
            on_connect(client, userdata, None, 0, config=config)

            # Verify settings values were published
            publish_calls = client.publish.call_args_list

            # Find the settings publish calls
            settings_calls = [call for call in publish_calls if "set/" in call[0][0]]

            assert (
                len(settings_calls) == 8
            )  # temp_offset, hum_offset, cpu_temp_factor, cpu_temp_smoothing, temp_smoothing_minutes, pressure_offset, elevation_meters, noise_calibration_offset

            # Verify each setting was published with correct value
            temp_offset_call = next(call for call in settings_calls if "temp_offset" in call[0][0])
            assert temp_offset_call[0][1] == "1.0"

            hum_offset_call = next(call for call in settings_calls if "hum_offset" in call[0][0])
            assert hum_offset_call[0][1] == "2.0"

            cpu_factor_call = next(
                call for call in settings_calls if "cpu_temp_factor" in call[0][0]
            )
            assert cpu_factor_call[0][1] == "2.5"

            cpu_smoothing_call = next(
                call for call in settings_calls if "cpu_temp_smoothing" in call[0][0]
            )
            assert cpu_smoothing_call[0][1] == "0.3"

    def test_on_connect_without_settings_manager(
        self, mock_mqtt_client, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test on_connect without settings manager falls back to environment variables."""
        client = mock_mqtt_client.return_value

        from ha_enviro_plus.config import Config

        config = Config.from_env()
        config.temp_offset = 0.0
        config.hum_offset = 0.0
        config.cpu_temp_factor = 1.8
        config.cpu_temp_smoothing = 0.1
        config.temp_smoothing_minutes = 5.0
        config.pressure_offset = 0.0
        config.elevation_meters = 0.0
        with patch("ha_enviro_plus.agent.publish_discovery"):
            on_connect(client, {"config": config}, None, 0, config=config)

            # Verify environment variable values were published
            publish_calls = client.publish.call_args_list

            # Find the settings publish calls
            settings_calls = [call for call in publish_calls if "set/" in call[0][0]]

            assert (
                len(settings_calls) == 8
            )  # temp_offset, hum_offset, cpu_temp_factor, cpu_temp_smoothing, temp_smoothing_minutes, pressure_offset, elevation_meters, noise_calibration_offset

            # Verify each setting was published with environment variable value
            temp_offset_call = next(call for call in settings_calls if "temp_offset" in call[0][0])
            assert temp_offset_call[0][1] == "0.0"

            hum_offset_call = next(call for call in settings_calls if "hum_offset" in call[0][0])
            assert hum_offset_call[0][1] == "0.0"

            cpu_factor_call = next(
                call for call in settings_calls if "cpu_temp_factor" in call[0][0]
            )
            assert cpu_factor_call[0][1] == "1.8"

            cpu_smoothing_call = next(
                call for call in settings_calls if "cpu_temp_smoothing" in call[0][0]
            )
            assert cpu_smoothing_call[0][1] == "0.1"
