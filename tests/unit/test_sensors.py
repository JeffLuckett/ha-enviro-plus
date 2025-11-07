"""Unit tests for ha_enviro_plus.sensors module."""

import pytest
from unittest.mock import patch, Mock
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
        assert sensors.temp_smoothing_minutes == 5.0
        assert sensors.pressure_offset == 0.0
        assert sensors.elevation_meters == 0.0
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
            temp_smoothing_minutes=10.0,
            logger=logger,
        )

        assert sensors.temp_offset == 2.5
        assert sensors.hum_offset == -5.0
        assert sensors.cpu_temp_factor == 2.0
        assert sensors.cpu_temp_smoothing == 0.3
        assert sensors.temp_smoothing_minutes == 10.0
        assert sensors.pressure_offset == 0.0
        assert sensors.elevation_meters == 0.0
        assert sensors.logger == logger

    def test_init_with_pressure_calibration(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger
    ):
        """Test initialization with pressure calibration values."""
        sensors = EnviroPlusSensors(
            pressure_offset=0.14,
            elevation_meters=100.0,
        )

        assert sensors.pressure_offset == 0.14
        assert sensors.elevation_meters == 100.0

    def test_init_sensor_failure_graceful(self, mock_logger):
        """Test initialization gracefully handles sensor failures."""
        with patch("ha_enviro_plus.sensors.BME280") as mock_bme280:
            mock_bme280.side_effect = Exception("Sensor not found")
            # Mock LTR559 to succeed
            with patch("ha_enviro_plus.sensors.LTR559") as mock_ltr559:
                mock_ltr559_instance = Mock()
                mock_ltr559.return_value = mock_ltr559_instance
                # Should not raise - graceful failure
                sensors = EnviroPlusSensors()
                assert sensors.bme280 is None
                assert sensors.ltr559 is not None

    def test_init_partial_sensor_availability(self, mock_logger):
        """Test initialization with partial sensor availability."""
        with patch("ha_enviro_plus.sensors.BME280") as mock_bme280:
            mock_bme280.side_effect = Exception("BME280 not found")
            with patch("ha_enviro_plus.sensors.LTR559") as mock_ltr559:
                # BME280 fails, LTR559 succeeds
                sensors = EnviroPlusSensors()
                assert sensors.bme280 is None
                assert sensors.ltr559 is not None
                assert not sensors.has_sensor("bme280")
                assert sensors.has_sensor("ltr559")

    def test_has_sensor_method(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test has_sensor method."""
        sensors = EnviroPlusSensors()
        assert sensors.has_sensor("bme280")
        assert sensors.has_sensor("ltr559")
        # Gas sensor availability depends on test mock


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

        # Disable smoothing for this test
        sensors = EnviroPlusSensors(
            temp_offset=2.0, cpu_temp_factor=2.0, temp_smoothing_minutes=0.0
        )
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

    def test_temp_without_bme280(self, mock_logger):
        """Test temperature reading when BME280 is not available."""
        with patch("ha_enviro_plus.sensors.BME280") as mock_bme280:
            mock_bme280.side_effect = Exception("BME280 not found")
            with patch("ha_enviro_plus.sensors.LTR559"):
                sensors = EnviroPlusSensors()
                assert sensors.temp() == 0.0
                assert sensors.temp_raw() == 0.0

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
        # Disable smoothing for this test
        sensors = EnviroPlusSensors(temp_offset=offset, temp_smoothing_minutes=0.0)
        temp = sensors.temp()

        assert temp == expected


class TestTemperatureSmoothing:
    """Test temperature smoothing functionality."""

    def test_temp_smoothing_disabled(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test temperature smoothing when disabled (0 minutes)."""
        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=25.0'C\n"

        sensors = EnviroPlusSensors(temp_smoothing_minutes=0.0)
        temp1 = sensors.temp()
        temp2 = sensors.temp()

        # Without smoothing, should return the same value
        assert temp1 == pytest.approx(temp2, abs=0.01)

    def test_temp_smoothing_enabled(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test temperature smoothing with time-based window."""
        import time
        from unittest.mock import patch

        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=25.0'C\n"

        # Use a very short window (0.001 minutes = ~0.06 seconds) for testing
        sensors = EnviroPlusSensors(temp_smoothing_minutes=0.001)

        # First reading should be the actual value (no history yet)
        temp1 = sensors.temp()
        assert temp1 == pytest.approx(25.0, abs=0.1)

        # Second reading should be averaged with first
        temp2 = sensors.temp()
        assert temp2 == pytest.approx(25.0, abs=0.1)

        # Change the temperature significantly
        mock_bme280.get_temperature.return_value = 30.0

        # With a very short window, the average should shift toward new value quickly
        # But it will still be averaged with previous readings in the window
        temp3 = sensors.temp()
        # Should be between 25.0 and 30.0 (average of readings in window)
        assert 25.0 <= temp3 <= 30.0

    def test_temp_smoothing_history_cleanup(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test that old readings are removed from smoothing history."""
        import time

        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=25.0'C\n"

        # Use a very short window for testing (0.001 minutes = ~0.06 seconds)
        sensors = EnviroPlusSensors(temp_smoothing_minutes=0.001)

        # Take a reading
        sensors.temp()

        # Wait for window to expire (0.1 seconds > 0.06 seconds)
        time.sleep(0.1)

        # Change temperature
        mock_bme280.get_temperature.return_value = 30.0
        mock_subprocess.return_value = "temp=30.0'C\n"

        # New reading should be closer to 30.0 since old reading expired
        # Note: Temperature compensation may affect the result, so we check it's
        # at least closer to 30.0 than 25.0
        temp = sensors.temp()
        # Should be significantly closer to 30.0 than 25.0
        assert abs(temp - 30.0) < abs(temp - 25.0)

    def test_temp_smoothing_init_default(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test that temp_smoothing_minutes defaults to 5.0."""
        sensors = EnviroPlusSensors()
        assert sensors.temp_smoothing_minutes == 5.0

    def test_temp_smoothing_custom_value(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test setting custom temp_smoothing_minutes value."""
        sensors = EnviroPlusSensors(temp_smoothing_minutes=10.0)
        assert sensors.temp_smoothing_minutes == 10.0


class TestHumidityReadings:
    """Test humidity reading methods."""

    def test_humidity_with_offset(self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess):
        """Test humidity with offset and smoothing."""
        mock_bme280.get_temperature.return_value = 25.0
        mock_bme280.get_humidity.return_value = 45.0

        sensors = EnviroPlusSensors(hum_offset=5.0)
        humidity = sensors.humidity()

        # Expect: 45.0 (raw) + compensation + 5.0 (offset)
        # Compensation: with smoothing on first call, smoothed_error starts at 0.0
        # and is updated: smoothed = 0.1 * 9.44 + 0.9 * 0.0 = 0.944
        # First reading: 45.0 + (0.944 * 2.0) + 5.0 = 51.89
        assert humidity == pytest.approx(51.89, abs=0.1)

    def test_humidity_without_bme280(self, mock_logger):
        """Test humidity reading when BME280 is not available."""
        with patch("ha_enviro_plus.sensors.BME280") as mock_bme280:
            mock_bme280.side_effect = Exception("BME280 not found")
            with patch("ha_enviro_plus.sensors.LTR559"):
                sensors = EnviroPlusSensors()
                assert sensors.humidity() == 0.0
                assert sensors.humidity_raw() == 0.0

    def test_humidity_raw(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test raw humidity reading."""
        mock_bme280.get_humidity.return_value = 45.123456

        sensors = EnviroPlusSensors()
        humidity = sensors.humidity_raw()

        assert humidity == 45.12  # Rounded to 2 decimal places

    def test_humidity_clamping_upper(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test humidity clamping at upper bound."""
        mock_bme280.get_temperature.return_value = 25.0
        mock_bme280.get_humidity.return_value = 95.0

        sensors = EnviroPlusSensors(hum_offset=10.0)
        humidity = sensors.humidity()

        assert humidity == 100.0

    def test_humidity_clamping_lower(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test humidity clamping at lower bound."""
        mock_bme280.get_temperature.return_value = 25.0
        mock_bme280.get_humidity.return_value = 5.0

        sensors = EnviroPlusSensors(hum_offset=-10.0)
        humidity = sensors.humidity()

        # Compensation adds ~1.89 (first reading with smoothing), so 5.0 + 1.89 - 10.0 = -3.11, clamped to 0.0
        assert humidity == 0.0

    @pytest.mark.parametrize(
        "raw_humidity,offset,temp_offset,expected_range",
        [
            (45.0, 0.0, 0, [46, 48]),  # With smoothing compensation (first reading)
            (45.0, 5.0, 0, [51, 53]),  # With smoothing compensation + offset
            (45.0, -5.0, 0, [41, 43]),  # With smoothing compensation - offset
            (95.0, 10.0, 0, [100, 100]),  # Clamped
        ],
    )
    def test_humidity_various_values(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        raw_humidity,
        offset,
        temp_offset,
        expected_range,
    ):
        """Test humidity with various raw values and offsets."""
        mock_bme280.get_temperature.return_value = 25.0
        mock_bme280.get_humidity.return_value = raw_humidity

        sensors = EnviroPlusSensors(hum_offset=offset)
        humidity = sensors.humidity()

        assert expected_range[0] <= humidity <= expected_range[1]


class TestPressureReadings:
    """Test pressure reading methods."""

    def test_pressure_without_bme280(self, mock_logger):
        """Test pressure reading when BME280 is not available."""
        with patch("ha_enviro_plus.sensors.BME280") as mock_bme280:
            mock_bme280.side_effect = Exception("BME280 not found")
            with patch("ha_enviro_plus.sensors.LTR559"):
                sensors = EnviroPlusSensors()
                assert sensors.pressure() == 0.0
                assert sensors.pressure_raw() == 0.0

    def test_pressure(self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess):
        """Test pressure reading."""
        mock_bme280.get_pressure.return_value = 1013.123456
        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=25.0'C\n"

        sensors = EnviroPlusSensors()
        pressure = sensors.pressure()

        # Should return raw pressure when no calibration
        assert pressure == 1013.12  # Rounded to 2 decimal places

    def test_pressure_with_offset(self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess):
        """Test pressure reading with offset."""
        mock_bme280.get_pressure.return_value = 1013.25
        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=25.0'C\n"

        sensors = EnviroPlusSensors(pressure_offset=0.14)
        pressure = sensors.pressure()

        # Should apply offset: 1013.25 + 0.14 = 1013.39
        assert pressure == pytest.approx(1013.39, abs=0.01)

    def test_pressure_with_elevation(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test pressure reading with elevation correction."""
        mock_bme280.get_pressure.return_value = 1000.0  # Station pressure at elevation
        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=25.0'C\n"

        sensors = EnviroPlusSensors(elevation_meters=100.0)
        pressure = sensors.pressure()

        # Should apply sea-level correction (increases pressure)
        # At 100m elevation, sea-level pressure should be higher than station pressure
        assert pressure > 1000.0
        # Approximate calculation: at 100m, sea-level should be ~11-12 hPa higher
        assert pressure == pytest.approx(1011.0, abs=2.0)

    def test_pressure_with_elevation_and_offset(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test pressure reading with both elevation correction and offset."""
        mock_bme280.get_pressure.return_value = 1000.0
        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=25.0'C\n"

        sensors = EnviroPlusSensors(elevation_meters=100.0, pressure_offset=0.14)
        pressure = sensors.pressure()

        # Should apply elevation correction first, then offset
        sea_level_pressure = sensors._calculate_sea_level_pressure(1000.0, 100.0, 25.0)
        expected = sea_level_pressure + 0.14
        assert pressure == pytest.approx(expected, abs=0.01)

    def test_pressure_elevation_zero(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_subprocess
    ):
        """Test that elevation=0 does not apply correction."""
        mock_bme280.get_pressure.return_value = 1013.25
        mock_bme280.get_temperature.return_value = 25.0
        mock_subprocess.return_value = "temp=25.0'C\n"

        sensors = EnviroPlusSensors(elevation_meters=0.0, pressure_offset=0.14)
        pressure = sensors.pressure()

        # Should only apply offset, no elevation correction
        assert pressure == pytest.approx(1013.39, abs=0.01)

    def test_pressure_raw(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test raw pressure reading."""
        mock_bme280.get_pressure.return_value = 1013.123456

        sensors = EnviroPlusSensors()
        pressure = sensors.pressure_raw()

        assert pressure == 1013.12  # Rounded to 2 decimal places


class TestLightReadings:
    """Test light reading methods."""

    def test_lux_without_ltr559(self, mock_logger):
        """Test lux reading when LTR559 is not available."""
        with patch("ha_enviro_plus.sensors.LTR559") as mock_ltr559:
            mock_ltr559.side_effect = Exception("LTR559 not found")
            with patch("ha_enviro_plus.sensors.BME280"):
                sensors = EnviroPlusSensors()
                assert sensors.lux() == 0.0
                assert sensors.lux_raw() == 0.0

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

    def test_gas_without_availability(self, mock_bme280, mock_ltr559):
        """Test gas readings when gas sensor is not available (regular Enviro)."""
        with patch("ha_enviro_plus.sensors.gas.read_all") as mock_gas:
            mock_gas.side_effect = Exception("Gas sensor not available")
            sensors = EnviroPlusSensors()
            # Gas sensor should not be available
            assert not sensors.has_sensor("gas")
            assert sensors.gas_oxidising() == 0.0
            assert sensors.gas_oxidising_raw() == 0.0
            assert sensors.gas_reducing() == 0.0
            assert sensors.gas_reducing_raw() == 0.0
            assert sensors.gas_nh3() == 0.0
            assert sensors.gas_nh3_raw() == 0.0

    @pytest.mark.parametrize(
        "gas_type,method_name,raw_method_name,raw_value,expected_value",
        [
            ("oxidising", "gas_oxidising", "gas_oxidising_raw", 50000.0, 50.0),
            ("reducing", "gas_reducing", "gas_reducing_raw", 30000.0, 30.0),
            ("nh3", "gas_nh3", "gas_nh3_raw", 40000.0, 40.0),
        ],
    )
    def test_gas_reading(
        self,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        gas_type,
        method_name,
        raw_method_name,
        raw_value,
        expected_value,
    ):
        """Test gas reading in kΩ for all gas types."""
        sensors = EnviroPlusSensors()
        gas_value = getattr(sensors, method_name)()

        assert gas_value == expected_value, f"{gas_type} should be {expected_value} kΩ"

    @pytest.mark.parametrize(
        "gas_type,raw_method_name,raw_value",
        [
            ("oxidising", "gas_oxidising_raw", 50000.0),
            ("reducing", "gas_reducing_raw", 30000.0),
            ("nh3", "gas_nh3_raw", 40000.0),
        ],
    )
    def test_gas_reading_raw(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, gas_type, raw_method_name, raw_value
    ):
        """Test raw gas reading in Ω for all gas types."""
        sensors = EnviroPlusSensors()
        gas_value = getattr(sensors, raw_method_name)()

        assert gas_value == raw_value, f"{gas_type} raw should be {raw_value} Ω"


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

        # Should log initialization (sensor availability) + each update
        # Now includes sensor initialization logs (BME280, LTR559, gas, summary)
        assert mock_logger.info.call_count >= 5

    def test_update_calibration_pressure_offset(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger
    ):
        """Test updating pressure offset."""
        sensors = EnviroPlusSensors()
        sensors.update_calibration(pressure_offset=0.14)

        assert sensors.pressure_offset == 0.14

    def test_update_calibration_elevation(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger
    ):
        """Test updating elevation."""
        sensors = EnviroPlusSensors()
        sensors.update_calibration(elevation_meters=100.0)

        assert sensors.elevation_meters == 100.0

    def test_update_calibration_elevation_negative(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger
    ):
        """Test that negative elevation is clamped to 0."""
        sensors = EnviroPlusSensors()
        sensors.update_calibration(elevation_meters=-50.0)

        # Should be clamped to 0.0
        assert sensors.elevation_meters == 0.0

    def test_update_calibration_pressure_both(
        self, mock_bme280, mock_ltr559, mock_gas_sensor, mock_logger
    ):
        """Test updating both pressure offset and elevation."""
        sensors = EnviroPlusSensors()
        sensors.update_calibration(pressure_offset=0.14, elevation_meters=150.0)

        assert sensors.pressure_offset == 0.14
        assert sensors.elevation_meters == 150.0


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
            "proximity",
            "gas_oxidising",
            "gas_oxidising_raw",
            "gas_reducing",
            "gas_reducing_raw",
            "gas_nh3",
            "gas_nh3_raw",
            "noise_spl_db",
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


class TestProximitySensor:
    """Test proximity sensor reading methods."""

    def test_proximity_without_ltr559(self, mock_logger):
        """Test proximity reading when LTR559 is not available."""
        with patch("ha_enviro_plus.sensors.LTR559") as mock_ltr559:
            mock_ltr559.side_effect = Exception("LTR559 not found")
            with patch("ha_enviro_plus.sensors.BME280"):
                sensors = EnviroPlusSensors()
                assert sensors.proximity() == 0.0

    def test_proximity(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test proximity reading."""
        mock_ltr559.get_proximity.return_value = 75.5

        sensors = EnviroPlusSensors()
        proximity = sensors.proximity()

        assert proximity == 76.0  # Rounded to nearest integer

    def test_proximity_zero(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test proximity reading at zero."""
        mock_ltr559.get_proximity.return_value = 0.0

        sensors = EnviroPlusSensors()
        proximity = sensors.proximity()

        assert proximity == 0.0

    def test_proximity_max(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test proximity reading at maximum."""
        mock_ltr559.get_proximity.return_value = 255.0

        sensors = EnviroPlusSensors()
        proximity = sensors.proximity()

        assert proximity == 255.0


class TestNoiseSensor:
    """Test noise sensor reading methods."""

    def test_noise_sensor_not_available(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test noise sensor when microphone is not available."""
        with patch("ha_enviro_plus.sensors.NOISE_SENSOR_AVAILABLE", False):
            sensors = EnviroPlusSensors()
            assert not sensors.has_sensor("noise")
            assert sensors.noise_spl_db() == 0.0
            assert sensors.noise_spl_raw() == 0.0

    def test_noise_sensor_available_detection(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test noise sensor availability detection."""
        with patch("ha_enviro_plus.sensors.NOISE_SENSOR_AVAILABLE", True):
            import numpy as np

            # Mock scipy.io.wavfile module
            from unittest.mock import MagicMock

            # Mock scipy.io.wavfile module
            mock_wavfile_module = MagicMock()
            # Return audio data that looks like a real recording (enough samples)
            # Use a list instead of numpy array to ensure len() works correctly with mocks
            audio_data = [1000] * 44100  # 1 second at 44.1kHz
            mock_wavfile_module.read.return_value = (44100, audio_data)
            with (
                patch("subprocess.run") as mock_run,
                patch("scipy.io.wavfile", mock_wavfile_module),
            ):
                # Mock successful arecord test
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = b""
                with patch("os.path.exists", return_value=True):
                    sensors = EnviroPlusSensors()
                    assert sensors.has_sensor("noise") is True

    def test_noise_spl_db_not_available(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test noise SPL dB when microphone is not available."""
        sensors = EnviroPlusSensors()
        # Noise sensor not available by default in test environment
        assert sensors.noise_spl_db() == 0.0

    def test_noise_spl_raw_not_available(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test noise SPL raw when microphone is not available."""
        sensors = EnviroPlusSensors()
        # Noise sensor not available by default in test environment
        assert sensors.noise_spl_raw() == 0.0

    def test_noise_sensor_startup_discard(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test that initial noise chunks are discarded."""
        with patch("ha_enviro_plus.sensors.NOISE_SENSOR_AVAILABLE", True):
            import numpy as np

            # Mock scipy.io.wavfile module
            from unittest.mock import MagicMock

            mock_wavfile_module = MagicMock()
            mock_wavfile_module.read.return_value = (
                44100,
                np.array([100, 200, 300], dtype=np.int32),
            )

            # Mock successful arecord test during initialization
            with (
                patch("subprocess.run") as mock_run,
                patch("scipy.io.wavfile", mock_wavfile_module),
            ):
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = b""
                with patch("os.path.exists", return_value=True):
                    # Mock A-weighting filter
                    with patch("ha_enviro_plus.sensors.butter") as mock_butter:
                        mock_butter.return_value = ([1.0], [1.0])
                        sensors = EnviroPlusSensors()

                        # Mock arecord calls for noise reading - return audio data that will produce non-zero RMS
                        audio_data = np.array([1000] * 44100, dtype=np.int32)
                        mock_wavfile_module.read.return_value = (44100, audio_data)
                        mock_run.return_value.returncode = 0
                        with patch("os.path.exists", return_value=True):
                            # First few calls should return 0.0 (discarded)
                            for _ in range(5):
                                result = sensors.noise_spl_db()
                                assert result == 0.0

    def test_noise_sensor_in_get_all_sensor_data(self, mock_bme280, mock_ltr559, mock_gas_sensor):
        """Test that noise sensor data is included in get_all_sensor_data."""
        sensors = EnviroPlusSensors()
        data = sensors.get_all_sensor_data()

        # Should include noise sensor keys even if unavailable
        assert "noise_spl_db" in data
        # Should be 0.0 when unavailable
        assert data["noise_spl_db"] == 0.0
