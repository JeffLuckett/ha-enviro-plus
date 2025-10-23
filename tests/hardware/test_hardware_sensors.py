"""Hardware integration tests for real sensor functionality."""

import pytest
import time
from ha_enviro_plus.sensors import EnviroPlusSensors
from tests.conftest import hardware_available


@pytest.mark.hardware
@pytest.mark.skipif(not hardware_available(), reason="Hardware not detected")
class TestHardwareSensors:
    """Test real hardware sensor functionality."""

    def test_sensor_initialization(self):
        """Test that sensors can be initialized with real hardware."""
        sensors = EnviroPlusSensors()

        # Verify sensors were initialized
        assert sensors.bme280 is not None
        assert sensors.ltr559 is not None
        assert sensors.temp_offset == 0.0
        assert sensors.hum_offset == 0.0
        assert sensors.cpu_temp_factor == 1.8

    def test_temperature_readings(self):
        """Test temperature sensor readings."""
        sensors = EnviroPlusSensors()

        # Test raw temperature reading
        raw_temp = sensors.temp_raw()
        assert isinstance(raw_temp, float)
        assert -50.0 <= raw_temp <= 100.0  # Reasonable temperature range

        # Test compensated temperature reading
        temp = sensors.temp()
        assert isinstance(temp, float)
        assert -50.0 <= temp <= 100.0

        # Test CPU temperature reading
        cpu_temp = sensors._read_cpu_temp()
        assert isinstance(cpu_temp, float)
        assert 0.0 <= cpu_temp <= 100.0  # CPU should be warmer than ambient

    def test_humidity_readings(self):
        """Test humidity sensor readings."""
        sensors = EnviroPlusSensors()

        # Test raw humidity reading
        raw_humidity = sensors.humidity_raw()
        assert isinstance(raw_humidity, float)
        assert 0.0 <= raw_humidity <= 100.0

        # Test processed humidity reading
        humidity = sensors.humidity()
        assert isinstance(humidity, float)
        assert 0.0 <= humidity <= 100.0

        # Test humidity clamping
        sensors.hum_offset = -200.0  # Force negative humidity
        clamped_humidity = sensors.humidity()
        assert clamped_humidity == 0.0

        sensors.hum_offset = 200.0  # Force humidity > 100%
        clamped_humidity = sensors.humidity()
        assert clamped_humidity == 100.0

    def test_pressure_readings(self):
        """Test pressure sensor readings."""
        sensors = EnviroPlusSensors()

        # Test pressure reading
        pressure = sensors.pressure()
        assert isinstance(pressure, float)
        assert 800.0 <= pressure <= 1200.0  # Reasonable atmospheric pressure range

        # Test raw pressure reading
        raw_pressure = sensors.pressure_raw()
        assert isinstance(raw_pressure, float)
        assert 800.0 <= raw_pressure <= 1200.0

    def test_light_readings(self):
        """Test light sensor readings."""
        sensors = EnviroPlusSensors()

        # Test lux reading
        lux = sensors.lux()
        assert isinstance(lux, float)
        assert 0.0 <= lux <= 100000.0  # Reasonable lux range

        # Test raw lux reading
        raw_lux = sensors.lux_raw()
        assert isinstance(raw_lux, float)
        assert 0.0 <= raw_lux <= 100000.0

    def test_gas_sensor_readings(self):
        """Test gas sensor readings."""
        sensors = EnviroPlusSensors()

        # Test oxidising gas reading
        oxidising = sensors.gas_oxidising()
        assert isinstance(oxidising, float)
        assert 0.0 <= oxidising <= 1000.0  # Reasonable kΩ range

        oxidising_raw = sensors.gas_oxidising_raw()
        assert isinstance(oxidising_raw, float)
        assert 0.0 <= oxidising_raw <= 1000000.0  # Reasonable Ω range

        # Test reducing gas reading
        reducing = sensors.gas_reducing()
        assert isinstance(reducing, float)
        assert 0.0 <= reducing <= 1000.0

        reducing_raw = sensors.gas_reducing_raw()
        assert isinstance(reducing_raw, float)
        assert 0.0 <= reducing_raw <= 1000000.0

        # Test NH3 gas reading
        nh3 = sensors.gas_nh3()
        assert isinstance(nh3, float)
        assert 0.0 <= nh3 <= 1000.0

        nh3_raw = sensors.gas_nh3_raw()
        assert isinstance(nh3_raw, float)
        assert 0.0 <= nh3_raw <= 1000000.0

    def test_calibration_updates(self):
        """Test calibration updates with real hardware."""
        sensors = EnviroPlusSensors()

        # Test temperature offset
        original_temp = sensors.temp()
        sensors.update_calibration(temp_offset=2.0)
        assert sensors.temp_offset == 2.0

        # Temperature should change by offset amount
        new_temp = sensors.temp()
        assert abs(new_temp - original_temp - 2.0) < 0.1

        # Test humidity offset
        original_humidity = sensors.humidity()
        sensors.update_calibration(hum_offset=-5.0)
        assert sensors.hum_offset == -5.0

        # Humidity should change by offset amount
        new_humidity = sensors.humidity()
        assert abs(new_humidity - original_humidity + 5.0) < 0.1

        # Test CPU temperature factor
        sensors.update_calibration(cpu_temp_factor=2.0)
        assert sensors.cpu_temp_factor == 2.0

    def test_get_all_sensor_data(self):
        """Test getting all sensor data."""
        sensors = EnviroPlusSensors()

        data = sensors.get_all_sensor_data()

        # Verify all expected keys are present
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

        # Verify all values are reasonable
        assert isinstance(data["temperature"], float)
        assert isinstance(data["humidity"], float)
        assert isinstance(data["pressure"], float)
        assert isinstance(data["lux"], float)
        assert isinstance(data["gas_oxidising"], float)
        assert isinstance(data["gas_reducing"], float)
        assert isinstance(data["gas_nh3"], float)

        # Verify raw values are higher than processed values for gas sensors
        assert data["gas_oxidising_raw"] > data["gas_oxidising"]
        assert data["gas_reducing_raw"] > data["gas_reducing"]
        assert data["gas_nh3_raw"] > data["gas_nh3"]

    def test_sensor_stability(self):
        """Test sensor reading stability over time."""
        sensors = EnviroPlusSensors()

        # Take multiple readings
        temps = []
        humidities = []
        pressures = []

        for _ in range(5):
            temps.append(sensors.temp())
            humidities.append(sensors.humidity())
            pressures.append(sensors.pressure())
            time.sleep(0.1)  # Small delay between readings

        # Check that readings are reasonably stable
        temp_variance = max(temps) - min(temps)
        humidity_variance = max(humidities) - min(humidities)
        pressure_variance = max(pressures) - min(pressures)

        # Allow for some variation due to sensor noise
        assert temp_variance < 2.0  # Temperature should be stable within 2°C
        assert humidity_variance < 5.0  # Humidity should be stable within 5%
        assert pressure_variance < 10.0  # Pressure should be stable within 10 hPa

    def test_cpu_temperature_compensation(self):
        """Test CPU temperature compensation with real hardware."""
        sensors = EnviroPlusSensors()

        # Get raw temperature
        raw_temp = sensors.temp_raw()

        # Get CPU temperature
        cpu_temp = sensors._read_cpu_temp()

        # Apply compensation
        compensated_temp = sensors._apply_temp_compensation(raw_temp)

        # Compensated temperature should be different from raw
        assert compensated_temp != raw_temp

        # If CPU is warmer than ambient, compensated temp should be lower
        if cpu_temp > raw_temp:
            assert compensated_temp < raw_temp

        # Test with different CPU temperature factors
        sensors.cpu_temp_factor = 1.0
        compensated_temp_low_factor = sensors._apply_temp_compensation(raw_temp)

        sensors.cpu_temp_factor = 3.0
        compensated_temp_high_factor = sensors._apply_temp_compensation(raw_temp)

        # Different factors should produce different results
        assert compensated_temp_low_factor != compensated_temp_high_factor

    def test_sensor_error_handling(self):
        """Test sensor error handling with real hardware."""
        sensors = EnviroPlusSensors()

        # Test that sensors handle errors gracefully
        try:
            # This should work with real hardware
            temp = sensors.temp()
            assert isinstance(temp, float)
        except Exception as e:
            pytest.fail(f"Sensor reading failed: {e}")

        # Test CPU temperature reading failure simulation
        with pytest.raises(Exception):
            # This should fail if we can't read CPU temp
            sensors._read_cpu_temp()

        # But the sensor should still work
        temp = sensors.temp()
        assert isinstance(temp, float)

    def test_concurrent_sensor_access(self):
        """Test concurrent access to sensors."""
        import threading
        import time

        sensors = EnviroPlusSensors()
        results = []

        def read_sensors():
            for _ in range(10):
                data = sensors.get_all_sensor_data()
                results.append(data)
                time.sleep(0.01)

        # Start multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=read_sensors)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all readings were successful
        assert len(results) == 30  # 3 threads × 10 readings each

        for data in results:
            assert isinstance(data["temperature"], float)
            assert isinstance(data["humidity"], float)
            assert isinstance(data["pressure"], float)

    def test_sensor_initialization_with_custom_params(self):
        """Test sensor initialization with custom parameters."""
        # Test with custom offsets
        sensors = EnviroPlusSensors(temp_offset=5.0, hum_offset=-10.0, cpu_temp_factor=2.5)

        assert sensors.temp_offset == 5.0
        assert sensors.hum_offset == -10.0
        assert sensors.cpu_temp_factor == 2.5

        # Test that readings are affected by offsets
        temp = sensors.temp()
        humidity = sensors.humidity()

        assert isinstance(temp, float)
        assert isinstance(humidity, float)

        # Humidity should be clamped if offset makes it negative
        if humidity < 0:
            assert humidity == 0.0
        elif humidity > 100:
            assert humidity == 100.0


@pytest.mark.hardware
@pytest.mark.skipif(not hardware_available(), reason="Hardware not detected")
class TestHardwarePerformance:
    """Test hardware performance characteristics."""

    def test_sensor_reading_speed(self):
        """Test sensor reading speed."""
        sensors = EnviroPlusSensors()

        # Time multiple readings
        start_time = time.time()

        for _ in range(100):
            sensors.get_all_sensor_data()

        end_time = time.time()

        # Should be able to read sensors quickly
        total_time = end_time - start_time
        avg_time_per_reading = total_time / 100

        assert avg_time_per_reading < 0.1  # Should be under 100ms per reading

    def test_memory_usage(self):
        """Test memory usage with real hardware."""
        import psutil
        import os

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create multiple sensor instances
        sensors_list = []
        for _ in range(10):
            sensors = EnviroPlusSensors()
            sensors_list.append(sensors)

        # Get memory usage after creating sensors
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable
        assert memory_increase < 50 * 1024 * 1024  # Less than 50MB increase

        # Clean up
        del sensors_list

    def test_sensor_accuracy(self):
        """Test sensor accuracy with known conditions."""
        sensors = EnviroPlusSensors()

        # Test that readings are within expected ranges for indoor conditions
        temp = sensors.temp()
        humidity = sensors.humidity()
        pressure = sensors.pressure()

        # Indoor temperature should be reasonable
        assert 15.0 <= temp <= 35.0  # 15-35°C for indoor conditions

        # Indoor humidity should be reasonable
        assert 20.0 <= humidity <= 80.0  # 20-80% for indoor conditions

        # Atmospheric pressure should be reasonable
        assert 950.0 <= pressure <= 1050.0  # 950-1050 hPa for sea level

    def test_sensor_drift(self):
        """Test for sensor drift over time."""
        sensors = EnviroPlusSensors()

        # Take initial readings
        initial_temp = sensors.temp()
        initial_humidity = sensors.humidity()
        initial_pressure = sensors.pressure()

        # Wait a bit
        time.sleep(1.0)

        # Take final readings
        final_temp = sensors.temp()
        final_humidity = sensors.humidity()
        final_pressure = sensors.pressure()

        # Check for excessive drift
        temp_drift = abs(final_temp - initial_temp)
        humidity_drift = abs(final_humidity - initial_humidity)
        pressure_drift = abs(final_pressure - initial_pressure)

        # Drift should be minimal over short time periods
        assert temp_drift < 1.0  # Less than 1°C drift
        assert humidity_drift < 2.0  # Less than 2% drift
        assert pressure_drift < 5.0  # Less than 5 hPa drift
