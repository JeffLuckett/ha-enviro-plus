"""Unit tests for ha_enviro_plus.sensors module."""

import pytest
from unittest.mock import patch
import logging

from ha_enviro_plus.sensors import EnviroPlusSensors


class TestEnviroPlusSensorsInit:
    """Test EnviroPlusSensors initialization."""

    def test_init_default_values(self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger):
        """Test initialization with default values."""
        sensors = EnviroPlusSensors()

        assert sensors.temp_offset == 0.0
        assert sensors.hum_offset == 0.0
        assert sensors.cpu_temp_factor == 1.8
        assert sensors.cpu_temp_smoothing == 0.1
        assert sensors.logger is not None
        assert sensors.bme280 is not None
        assert sensors.ltr559 is not None

    def test_init_custom_values(self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger):
        """Test initialization with custom values."""
        logger = logging.getLogger("test")
        sensors = EnviroPlusSensors(
            temp_offset=2.5,
            hum_offset=-5.0,
            cpu_temp_factor=2.0,
            cpu_temp_smoothing=0.3,
            logger=logger,
        )

        assert sensors.temp_offset == 2.5
        assert sensors.hum_offset == -5.0
        assert sensors.cpu_temp_factor == 2.0
        assert sensors.cpu_temp_smoothing == 0.3
        assert sensors.logger == logger

    def test_init_sensor_failure(self, mock_logger):
        """Test initialization failure when sensors can't be initialized."""
        with patch("ha_enviro_plus.sensors.BME280") as mock_bme280:
            mock_bme280.side_effect = Exception("Sensor not found")

            with pytest.raises(Exception, match="Sensor not found"):
                EnviroPlusSensors()


class TestCpuTemperature:
    """Test CPU temperature reading."""

    def test_read_cpu_temp_success(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test successful CPU temperature reading."""
        mock_subprocess.return_value = "temp=42.5'C\n"  # Return string, not bytes

        sensors = EnviroPlusSensors()
        temp = sensors._read_cpu_temp()

        assert temp == 42.5
        mock_subprocess.assert_called_once_with(["vcgencmd", "measure_temp"], text=True)

    def test_read_cpu_temp_failure(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test CPU temperature reading failure."""
        mock_subprocess.side_effect = Exception("Command failed")

        sensors = EnviroPlusSensors()

        with pytest.raises(Exception, match="Command failed"):
            sensors._read_cpu_temp()

    def test_read_cpu_temp_malformed_output(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test CPU temperature reading with malformed output."""
        mock_subprocess.return_value = "invalid output"

        sensors = EnviroPlusSensors()

        with pytest.raises(IndexError):
            sensors._read_cpu_temp()


class TestCpuTemperatureSmoothing:
    """Test CPU temperature smoothing functionality."""

    def test_init_with_smoothing_factor(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger
    ):
        """Test initialization with CPU temperature smoothing factor."""
        sensors = EnviroPlusSensors(cpu_temp_smoothing=0.2)

        assert sensors.cpu_temp_smoothing == 0.2
        assert sensors._cpu_temp_smoothed == 40.6  # Initialized with Pi Zero temp
        assert sensors._cpu_temp_last_update == 0.0

    def test_get_smoothed_cpu_temp_first_reading(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test smoothed CPU temperature on first reading."""
        mock_subprocess.return_value = "temp=45.0'C\n"

        sensors = EnviroPlusSensors(cpu_temp_smoothing=0.1)
        temp = sensors._get_smoothed_cpu_temp()

        assert temp == 45.0
        assert sensors._cpu_temp_smoothed == 45.0
        assert sensors._cpu_temp_last_update > 0.0

    def test_get_smoothed_cpu_temp_subsequent_readings(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test smoothed CPU temperature on subsequent readings."""
        # First reading: 45.0°C (replaces initialization value)
        mock_subprocess.return_value = "temp=45.0'C\n"
        sensors = EnviroPlusSensors(cpu_temp_smoothing=0.2)
        first_temp = sensors._get_smoothed_cpu_temp()

        assert first_temp == 45.0
        assert sensors._cpu_temp_smoothed == 45.0

        # Second reading: 50.0°C
        mock_subprocess.return_value = "temp=50.0'C\n"
        second_temp = sensors._get_smoothed_cpu_temp()

        # EMA calculation: 0.2 * 50.0 + 0.8 * 45.0 = 10.0 + 36.0 = 46.0
        expected = 0.2 * 50.0 + 0.8 * 45.0
        assert second_temp == pytest.approx(expected, abs=0.01)
        assert sensors._cpu_temp_smoothed == pytest.approx(expected, abs=0.01)

    def test_get_smoothed_cpu_temp_multiple_readings(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test smoothed CPU temperature with multiple readings."""
        sensors = EnviroPlusSensors(cpu_temp_smoothing=0.3)

        # Simulate multiple readings
        readings = [40.0, 45.0, 50.0, 48.0, 52.0]
        expected_smoothed = []

        for reading in readings:
            mock_subprocess.return_value = f"temp={reading}'C\n"
            smoothed = sensors._get_smoothed_cpu_temp()
            expected_smoothed.append(smoothed)

        # First reading should be exact (replaces initialization value)
        assert expected_smoothed[0] == 40.0

        # Subsequent readings should be smoothed
        # Second: 0.3 * 45.0 + 0.7 * 40.0 = 13.5 + 28.0 = 41.5
        assert expected_smoothed[1] == pytest.approx(41.5, abs=0.01)

        # Third: 0.3 * 50.0 + 0.7 * 41.5 = 15.0 + 29.05 = 44.05
        assert expected_smoothed[2] == pytest.approx(44.05, abs=0.01)

    def test_get_smoothed_cpu_temp_failure_fallback(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test smoothed CPU temperature fallback on failure."""
        # First successful reading
        mock_subprocess.return_value = "temp=45.0'C\n"
        sensors = EnviroPlusSensors(cpu_temp_smoothing=0.1)
        first_temp = sensors._get_smoothed_cpu_temp()

        assert first_temp == 45.0

        # Subsequent failure
        mock_subprocess.side_effect = Exception("Command failed")
        fallback_temp = sensors._get_smoothed_cpu_temp()

        # Should return last known smoothed value
        assert fallback_temp == 45.0

    def test_get_smoothed_cpu_temp_failure_no_previous_value(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test smoothed CPU temperature fallback when no previous value."""
        mock_subprocess.side_effect = Exception("Command failed")

        sensors = EnviroPlusSensors(cpu_temp_smoothing=0.1)
        temp = sensors._get_smoothed_cpu_temp()

        # Should return 0.0 when no previous reading (indicates no valid temperature)
        assert temp == 0.0

    def test_cpu_temp_public_method(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test public cpu_temp method."""
        mock_subprocess.return_value = "temp=42.0'C\n"

        sensors = EnviroPlusSensors(cpu_temp_smoothing=0.1)
        temp = sensors.cpu_temp()

        assert temp == 42.0

    def test_smoothing_factor_boundaries(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test CPU temperature smoothing with different smoothing factors."""
        mock_subprocess.return_value = "temp=50.0'C\n"

        # Test with smoothing factor = 1.0 (no smoothing)
        sensors_no_smooth = EnviroPlusSensors(cpu_temp_smoothing=1.0)
        # First reading replaces initialization value
        sensors_no_smooth._get_smoothed_cpu_temp()  # This sets it to 50.0
        temp_no_smooth = sensors_no_smooth._get_smoothed_cpu_temp()

        # Should be exactly the new reading
        assert temp_no_smooth == 50.0

        # Test with smoothing factor = 0.0 (maximum smoothing)
        sensors_max_smooth = EnviroPlusSensors(cpu_temp_smoothing=0.0)
        # First reading replaces initialization value
        sensors_max_smooth._get_smoothed_cpu_temp()  # This sets it to 50.0
        temp_max_smooth = sensors_max_smooth._get_smoothed_cpu_temp()

        # Should remain the previous value
        assert temp_max_smooth == 50.0


class TestTemperatureCompensation:
    """Test temperature compensation calculations."""

    def test_apply_temp_compensation(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test temperature compensation formula with smoothed CPU temp."""
        mock_subprocess.return_value = "temp=50.0'C\n"  # CPU temp

        sensors = EnviroPlusSensors(cpu_temp_factor=2.0)
        raw_temp = 25.0

        compensated = sensors._apply_temp_compensation(raw_temp)

        # Formula: raw_temp - ((cpu_temp_smoothed - raw_temp) / factor)
        # First reading: smoothed = raw = 50.0
        # 25.0 - ((50.0 - 25.0) / 2.0) = 25.0 - 12.5 = 12.5
        expected = 25.0 - ((50.0 - 25.0) / 2.0)
        assert compensated == expected

    def test_apply_temp_compensation_cpu_failure(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test temperature compensation when CPU temp reading fails."""
        mock_subprocess.side_effect = Exception("CPU temp failed")

        sensors = EnviroPlusSensors()
        raw_temp = 25.0

        compensated = sensors._apply_temp_compensation(raw_temp)

        # Should return raw temp when CPU temp fails (no previous smoothed value)
        assert compensated == raw_temp


class TestTemperatureReadings:
    """Test temperature reading methods."""

    def test_temp_with_compensation_and_offset(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test compensated temperature with offset."""
        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=50.0'C\n"

        sensors = EnviroPlusSensors(temp_offset=2.0, cpu_temp_factor=2.0)
        temp = sensors.temp()

        # Raw: 25.0, Compensated: 25.0 - ((50.0 - 25.0) / 2.0) = 12.5, Final: 12.5 + 2.0 = 14.5
        expected = 12.5 + 2.0
        assert temp == pytest.approx(expected, abs=0.01)

    def test_temp_raw(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test raw temperature reading."""
        mock_bme280.get_temperature.return_value = 25.123456

        sensors = EnviroPlusSensors()
        temp = sensors.temp_raw()

        assert temp == 25.12  # Rounded to 2 decimal places

    @pytest.mark.parametrize(
        "offset,expected",
        [
            (0.0, 25.5),
            (2.0, 27.5),
            (-3.0, 22.5),
            (10.0, 35.5),
        ],
    )
    def test_temp_with_various_offsets(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess, offset, expected
    ):
        """Test temperature with various offset values."""
        mock_bme280.get_temperature.return_value = 25.5
        mock_subprocess.return_value = "temp=25.5'C\n"  # Same as raw temp

        sensors = EnviroPlusSensors(temp_offset=offset)
        temp = sensors.temp()

        assert temp == expected


class TestHumidityReadings:
    """Test humidity reading methods."""

    def test_humidity_with_offset(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test humidity with offset."""
        mock_bme280.get_humidity.return_value = 45.0

        sensors = EnviroPlusSensors(hum_offset=5.0)
        humidity = sensors.humidity()

        assert humidity == 50.0

    def test_humidity_raw(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test raw humidity reading."""
        mock_bme280.get_humidity.return_value = 45.123456

        sensors = EnviroPlusSensors()
        humidity = sensors.humidity_raw()

        assert humidity == 45.12  # Rounded to 2 decimal places

    def test_humidity_clamping_upper(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test humidity clamping at upper bound."""
        mock_bme280.get_humidity.return_value = 95.0

        sensors = EnviroPlusSensors(hum_offset=10.0)
        humidity = sensors.humidity()

        assert humidity == 100.0

    def test_humidity_clamping_lower(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test humidity clamping at lower bound."""
        mock_bme280.get_humidity.return_value = 5.0

        sensors = EnviroPlusSensors(hum_offset=-10.0)
        humidity = sensors.humidity()

        assert humidity == 0.0

    @pytest.mark.parametrize(
        "raw_humidity,offset,expected",
        [
            (45.0, 0.0, 45.0),
            (45.0, 5.0, 50.0),
            (45.0, -5.0, 40.0),
            (95.0, 10.0, 100.0),  # Clamped
            (5.0, -10.0, 0.0),  # Clamped
        ],
    )
    def test_humidity_various_values(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, raw_humidity, offset, expected
    ):
        """Test humidity with various raw values and offsets."""
        mock_bme280.get_humidity.return_value = raw_humidity

        sensors = EnviroPlusSensors(hum_offset=offset)
        humidity = sensors.humidity()

        assert humidity == expected


class TestPressureReadings:
    """Test pressure reading methods."""

    def test_pressure(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test pressure reading."""
        mock_bme280.get_pressure.return_value = 1013.123456

        sensors = EnviroPlusSensors()
        pressure = sensors.pressure()

        assert pressure == 1013.12  # Rounded to 2 decimal places

    def test_pressure_raw(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test raw pressure reading."""
        mock_bme280.get_pressure.return_value = 1013.123456

        sensors = EnviroPlusSensors()
        pressure = sensors.pressure_raw()

        assert pressure == 1013.12  # Rounded to 2 decimal places


class TestLightReadings:
    """Test light reading methods."""

    def test_lux(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test lux reading."""
        mock_ltr559.get_lux.return_value = 150.123456

        sensors = EnviroPlusSensors()
        lux = sensors.lux()

        assert lux == 150.12  # Rounded to 2 decimal places

    def test_lux_raw(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test raw lux reading."""
        mock_ltr559.get_lux.return_value = 150.123456

        sensors = EnviroPlusSensors()
        lux = sensors.lux_raw()

        assert lux == 150.12  # Rounded to 2 decimal places


class TestGasReadings:
    """Test gas sensor reading methods."""

    def test_gas_oxidising(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test oxidising gas reading in kΩ."""
        sensors = EnviroPlusSensors()
        gas_value = sensors.gas_oxidising()

        assert gas_value == 50.0  # Converted to kΩ

    def test_gas_oxidising_raw(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test raw oxidising gas reading in Ω."""
        sensors = EnviroPlusSensors()
        gas_value = sensors.gas_oxidising_raw()

        assert gas_value == 50000.0  # Raw value in Ω

    def test_gas_reducing(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test reducing gas reading in kΩ."""
        sensors = EnviroPlusSensors()
        gas_value = sensors.gas_reducing()

        assert gas_value == 30.0  # Converted to kΩ

    def test_gas_reducing_raw(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test raw reducing gas reading in Ω."""
        sensors = EnviroPlusSensors()
        gas_value = sensors.gas_reducing_raw()

        assert gas_value == 30000.0  # Raw value in Ω

    def test_gas_nh3(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test NH3 gas reading in kΩ."""
        sensors = EnviroPlusSensors()
        gas_value = sensors.gas_nh3()

        assert gas_value == 40.0  # Converted to kΩ

    def test_gas_nh3_raw(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test raw NH3 gas reading in Ω."""
        sensors = EnviroPlusSensors()
        gas_value = sensors.gas_nh3_raw()

        assert gas_value == 40000.0  # Raw value in Ω


class TestCalibration:
    """Test calibration update methods."""

    def test_update_calibration_temp_offset(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger
    ):
        """Test updating temperature offset."""
        sensors = EnviroPlusSensors()

        sensors.update_calibration(temp_offset=2.5)

        assert sensors.temp_offset == 2.5
        mock_logger.info.assert_called_with("Updated temperature offset to %s°C", 2.5)

    def test_update_calibration_hum_offset(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger
    ):
        """Test updating humidity offset."""
        sensors = EnviroPlusSensors()

        sensors.update_calibration(hum_offset=-3.0)

        assert sensors.hum_offset == -3.0
        mock_logger.info.assert_called_with("Updated humidity offset to %s%%", -3.0)

    def test_update_calibration_cpu_factor(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger
    ):
        """Test updating CPU temperature factor."""
        sensors = EnviroPlusSensors()

        sensors.update_calibration(cpu_temp_factor=2.5)

        assert sensors.cpu_temp_factor == 2.5
        mock_logger.info.assert_called_with("Updated CPU temperature factor to %s", 2.5)

    def test_update_calibration_cpu_smoothing(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger
    ):
        """Test updating CPU temperature smoothing factor."""
        sensors = EnviroPlusSensors()

        sensors.update_calibration(cpu_temp_smoothing=0.3)

        assert sensors.cpu_temp_smoothing == 0.3
        mock_logger.info.assert_called_with("Updated CPU temperature smoothing to %s", 0.3)

    def test_update_calibration_multiple(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger
    ):
        """Test updating multiple calibration values."""
        sensors = EnviroPlusSensors()

        sensors.update_calibration(
            temp_offset=1.5, hum_offset=-2.0, cpu_temp_factor=2.0, cpu_temp_smoothing=0.2
        )

        assert sensors.temp_offset == 1.5
        assert sensors.hum_offset == -2.0
        assert sensors.cpu_temp_factor == 2.0
        assert sensors.cpu_temp_smoothing == 0.2

        # Should log initialization + each update
        assert mock_logger.info.call_count == 5


class TestGetAllSensorData:
    """Test get_all_sensor_data method."""

    def test_get_all_sensor_data(self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess):
        """Test getting all sensor data."""
        # Set up mock return values
        mock_bme280.get_temperature.return_value = 25.5
        mock_bme280.get_humidity.return_value = 45.0
        mock_bme280.get_pressure.return_value = 1013.25
        mock_ltr559.get_lux.return_value = 150.0
        mock_subprocess.return_value = "temp=42.0'C\n"

        sensors = EnviroPlusSensors(temp_offset=1.0, hum_offset=2.0)
        data = sensors.get_all_sensor_data()

        # Verify structure
        expected_keys = {
            "temperature",
            "temperature_raw",
            "humidity",
            "humidity_raw",
            "pressure",
            "pressure_raw",
            "lux",
            "lux_raw",
            "gas_oxidising",
            "gas_oxidising_raw",
            "gas_reducing",
            "gas_reducing_raw",
            "gas_nh3",
            "gas_nh3_raw",
        }

        assert set(data.keys()) == expected_keys

        # Verify some values
        assert data["temperature_raw"] == 25.5
        assert data["humidity_raw"] == 45.0
        assert data["pressure_raw"] == 1013.25
        assert data["lux_raw"] == 150.0
        assert data["gas_oxidising_raw"] == 50000.0
        assert data["gas_reducing_raw"] == 30000.0
        assert data["gas_nh3_raw"] == 40000.0

        # Verify processed values
        assert data["gas_oxidising"] == 50.0  # Converted to kΩ
        assert data["gas_reducing"] == 30.0
        assert data["gas_nh3"] == 40.0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_extreme_cpu_temperature(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test with extreme CPU temperature."""
        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=100.0'C\n"  # Very hot CPU

        sensors = EnviroPlusSensors(cpu_temp_factor=1.0)
        temp = sensors.temp()

        # Should handle extreme values gracefully
        assert isinstance(temp, float)
        assert temp < 25.0  # Should be compensated down

    def test_negative_temperature_offset(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test with negative temperature offset."""
        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=25.0'C\n"

        sensors = EnviroPlusSensors(temp_offset=-10.0)
        temp = sensors.temp()

        assert temp == 15.0  # 25.0 - 10.0

    def test_zero_cpu_temp_factor(self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess):
        """Test with zero CPU temperature factor (should not divide by zero)."""
        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=50.0'C\n"

        sensors = EnviroPlusSensors(cpu_temp_factor=0.0)

        # Should handle division by zero gracefully by returning raw temp
        compensated = sensors._apply_temp_compensation(25.0)
        assert compensated == 25.0
