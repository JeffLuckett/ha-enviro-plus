#!/usr/bin/env python3
"""
Enviro+ Sensor Data Management

This module provides a clean interface for reading and processing data from
Pimoroni Enviro+ sensors with proper separation of concerns.
"""

import subprocess
import logging
import time
from typing import Dict, Any, Optional

# Hardware imports with fallback for testing
try:
    from bme280 import BME280
    from ltr559 import LTR559
    from enviroplus import gas

    HARDWARE_AVAILABLE = True
except ImportError:
    # Mock hardware modules for testing environments
    from unittest.mock import MagicMock

    BME280 = None
    LTR559 = None
    gas = MagicMock()  # Keep gas as a mockable object
    HARDWARE_AVAILABLE = False


class EnviroPlusSensors:
    """
    Manages all Enviro+ sensor data with clean accessors for both raw and processed values.

    Provides temperature compensation, calibration offsets, and consistent data formatting.
    """

    def __init__(
        self,
        temp_offset: float = 0.0,
        hum_offset: float = 0.0,
        cpu_temp_factor: float = 1.8,
        cpu_temp_smoothing: float = 0.1,
        temp_smoothing_minutes: float = 5.0,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Enviro+ sensor manager.

        Args:
            temp_offset: Temperature calibration offset in °C
            hum_offset: Humidity calibration offset in %
            cpu_temp_factor: CPU temperature compensation factor (higher=less compensation, lower=more compensation)
            cpu_temp_smoothing: CPU temperature smoothing factor (0.0-1.0, lower=more smoothing)
            temp_smoothing_minutes: Temperature smoothing window in minutes (0.0 = no smoothing)
            logger: Optional logger instance
        """
        self.temp_offset = temp_offset
        self.hum_offset = hum_offset
        self.cpu_temp_factor = cpu_temp_factor
        self.cpu_temp_smoothing = cpu_temp_smoothing
        self.temp_smoothing_minutes = temp_smoothing_minutes
        self.logger = logger or logging.getLogger(__name__)

        # CPU temperature smoothing state
        # Initialize with typical Pi Zero CPU temperature (105°F = 40.6°C)
        self._cpu_temp_smoothed = 40.6
        self._cpu_temp_last_update = 0.0

        # Temperature smoothing history (list of (timestamp, temperature) tuples)
        self._temp_history: list[tuple[float, float]] = []

        # Humidity compensation temperature error smoothing state
        # Initialize to 0 (no error expected initially)
        self._hum_compensation_temp_error_smoothed = 0.0

        # Initialize sensor hardware individually to allow partial failures
        self.bme280 = None
        self.ltr559 = None
        self._gas_available = False

        if HARDWARE_AVAILABLE:
            # Initialize BME280 (temperature, humidity, pressure)
            try:
                self.bme280 = BME280(i2c_addr=0x76)
                self.logger.info("BME280 sensor initialized successfully")
            except Exception as e:
                self.logger.warning("Failed to initialize BME280 sensor: %s", e)
                self.logger.info("Temperature, humidity, and pressure sensors unavailable")

            # Initialize LTR559 (light/proximity)
            try:
                self.ltr559 = LTR559()
                self.logger.info("LTR559 sensor initialized successfully")
            except Exception as e:
                self.logger.warning("Failed to initialize LTR559 sensor: %s", e)
                self.logger.info("Light/proximity sensor unavailable")

            # Check if gas sensor is available (Enviro+ only)
            try:
                # Try to read gas sensor to verify availability
                gas.read_all()
                self._gas_available = True
                self.logger.info("Gas sensor available (Enviro+)")
            except Exception as e:
                self.logger.debug("Gas sensor not available (regular Enviro board): %s", e)
                self._gas_available = False

            # Log summary of available sensors
            available = []
            if self.bme280:
                available.append("BME280")
            if self.ltr559:
                available.append("LTR559")
            if self._gas_available:
                available.append("gas")
            if available:
                self.logger.info("Sensors initialized: %s", ", ".join(available))
            else:
                self.logger.warning(
                    "No sensors initialized - service will continue with system metrics only"
                )
        else:
            # Create mock sensors for testing environments
            self.logger.info("Enviro+ sensors initialized in test mode (no hardware)")

    def has_sensor(self, sensor_name: str) -> bool:
        """
        Check if a sensor is available.

        Args:
            sensor_name: Name of the sensor ("bme280", "ltr559", or "gas")

        Returns:
            True if sensor is available, False otherwise
        """
        if sensor_name == "bme280":
            return self.bme280 is not None
        elif sensor_name == "ltr559":
            return self.ltr559 is not None
        elif sensor_name == "gas":
            return self._gas_available
        else:
            return False

    def _read_cpu_temp(self) -> float:
        """
        Read CPU temperature using vcgencmd.

        Returns:
            CPU temperature in °C

        Raises:
            subprocess.CalledProcessError: If vcgencmd command fails
            ValueError: If temperature parsing fails
            Exception: For any other unexpected error
        """
        try:
            out = subprocess.check_output(["vcgencmd", "measure_temp"], text=True).strip()
            # Parse output: temp=42.0'C
            temp_str = out.split("=")[1].split("'")[0]
            temp_value = float(temp_str)
            self.logger.debug("CPU temperature: %.1f°C", temp_value)
            return temp_value
        except subprocess.CalledProcessError as e:
            self.logger.error("vcgencmd command failed (exit code %d): %s", e.returncode, e)
            raise
        except (ValueError, IndexError) as e:
            self.logger.error("Failed to parse CPU temperature from output '%s': %s", str(out), e)
            raise
        except Exception as e:
            self.logger.error("Unexpected error reading CPU temperature: %s", e)
            raise

    def _get_smoothed_cpu_temp(self) -> float:
        """
        Get smoothed CPU temperature using exponential moving average.

        Returns:
            Smoothed CPU temperature in °C

        Raises:
            Never raises - always returns a fallback value
        """
        try:
            current_time = time.time()
            raw_cpu_temp = self._read_cpu_temp()

            # If this is the first actual reading (last_update is 0), use it directly
            # but log that we're transitioning from the initialization value
            if self._cpu_temp_last_update == 0.0:
                self._cpu_temp_smoothed = raw_cpu_temp
                self._cpu_temp_last_update = current_time
                self.logger.debug(
                    "CPU temperature smoothing initialized: %.1f°C (was %.1f°C)",
                    raw_cpu_temp,
                    40.6,
                )
                return raw_cpu_temp

            # Apply exponential moving average
            # EMA = smoothing_factor * new_value + (1 - smoothing_factor) * previous_EMA
            self._cpu_temp_smoothed = (
                self.cpu_temp_smoothing * raw_cpu_temp
                + (1.0 - self.cpu_temp_smoothing) * self._cpu_temp_smoothed
            )
            self._cpu_temp_last_update = current_time

            self.logger.debug(
                "CPU temperature smoothing: raw=%.1f°C, smoothed=%.1f°C, factor=%.2f",
                raw_cpu_temp,
                self._cpu_temp_smoothed,
                self.cpu_temp_smoothing,
            )

            return self._cpu_temp_smoothed
        except Exception as e:
            self.logger.error("Failed to get smoothed CPU temperature: %s", e)
            # Return the last known smoothed value or fallback
            if self._cpu_temp_last_update > 0.0:
                # We have a real reading, use the last known smoothed value
                self.logger.info(
                    "Using last known smoothed CPU temperature: %.1f°C",
                    self._cpu_temp_smoothed,
                )
                return self._cpu_temp_smoothed
            else:
                # No real readings yet, return 0.0 to indicate no valid temperature
                self.logger.info("CPU temperature will be reported as 0.0°C")
                return 0.0

    def cpu_temp(self) -> float:
        """
        Get smoothed CPU temperature for reporting.

        Returns:
            Smoothed CPU temperature in °C
        """
        return self._get_smoothed_cpu_temp()

    def _apply_temp_compensation(self, raw_temp: float) -> float:
        """
        Apply CPU temperature compensation to raw temperature reading.

        Args:
            raw_temp: Raw temperature reading from BME280

        Returns:
            CPU-compensated temperature, or raw_temp if compensation fails

        Raises:
            Never raises - always returns a fallback value
        """
        try:
            cpu_temp = self._get_smoothed_cpu_temp()

            # If CPU temperature is 0.0 and we have no previous smoothed value, skip compensation
            if cpu_temp == 0.0 and self._cpu_temp_last_update == 0.0:
                self.logger.warning(
                    "CPU temperature compensation skipped: no valid CPU temperature"
                )
                self.logger.info("Using raw temperature reading: %.1f°C", raw_temp)
                return raw_temp

            # Apply Pimoroni compensation formula: raw_temp - ((cpu_temp - raw_temp) / factor)
            compensated_temp = raw_temp - ((cpu_temp - raw_temp) / self.cpu_temp_factor)
            self.logger.debug(
                "Temperature compensation: raw=%.1f°C, cpu_smoothed=%.1f°C, compensated=%.1f°C",
                raw_temp,
                cpu_temp,
                compensated_temp,
            )
            return compensated_temp
        except Exception as e:
            self.logger.warning("CPU temperature compensation failed: %s", e)
            self.logger.info("Using raw temperature reading: %.1f°C", raw_temp)
            return raw_temp

    def _get_smoothed_temp(self, compensated_temp: float) -> float:
        """
        Get smoothed temperature using time-based moving average.

        Args:
            compensated_temp: Compensated temperature reading (after CPU compensation and offset)

        Returns:
            Smoothed temperature in °C, or compensated_temp if smoothing disabled or insufficient history
        """
        # If smoothing is disabled (0 minutes), return the value as-is
        if self.temp_smoothing_minutes <= 0.0:
            return compensated_temp

        try:
            current_time = time.time()
            window_seconds = self.temp_smoothing_minutes * 60.0

            # Add current reading to history
            self._temp_history.append((current_time, compensated_temp))

            # Remove readings outside the time window
            cutoff_time = current_time - window_seconds
            self._temp_history = [
                (ts, temp) for ts, temp in self._temp_history if ts >= cutoff_time
            ]

            # If we don't have enough history, return the current value
            if len(self._temp_history) == 0:
                self.logger.debug(
                    "Temperature smoothing: insufficient history, using current value: %.2f°C",
                    compensated_temp,
                )
                return compensated_temp

            # Calculate average of readings within the window
            avg_temp = sum(temp for _, temp in self._temp_history) / len(self._temp_history)

            self.logger.debug(
                "Temperature smoothing: current=%.2f°C, smoothed=%.2f°C (window=%.1f min, samples=%d)",
                compensated_temp,
                avg_temp,
                self.temp_smoothing_minutes,
                len(self._temp_history),
            )

            return round(avg_temp, 2)
        except Exception as e:
            self.logger.error("Failed to get smoothed temperature: %s", e)
            self.logger.info("Using uncompensated temperature: %.2f°C", compensated_temp)
            return compensated_temp

    # Temperature accessors
    def temp(self) -> float:
        """
        Get compensated, calibrated, and smoothed temperature.

        Returns:
            Temperature in °C (compensated + offset + smoothed)

        Raises:
            Never raises - always returns a fallback value
        """
        if self.bme280 is None:
            self.logger.debug("Temperature unavailable: BME280 not initialized")
            return 0.0
        try:
            raw_temp = self.bme280.get_temperature()
            compensated_temp = self._apply_temp_compensation(raw_temp)
            final_temp = compensated_temp + self.temp_offset
            smoothed_temp = self._get_smoothed_temp(final_temp)
            self.logger.debug(
                "Final temperature: %.2f°C (raw=%.2f, compensated=%.2f, offset=%.2f, pre-smoothed=%.2f)",
                smoothed_temp,
                raw_temp,
                compensated_temp,
                self.temp_offset,
                final_temp,
            )
            return smoothed_temp
        except Exception as e:
            self.logger.error("Failed to read temperature: %s", e)
            self.logger.info("Temperature will be reported as 0.0°C")
            return 0.0

    def temp_raw(self) -> float:
        """
        Get raw temperature reading from BME280.

        Returns:
            Raw temperature in °C

        Raises:
            Never raises - always returns a fallback value
        """
        if self.bme280 is None:
            self.logger.debug("Raw temperature unavailable: BME280 not initialized")
            return 0.0
        try:
            raw_temp = self.bme280.get_temperature()
            return round(float(raw_temp), 2)
        except Exception as e:
            self.logger.error("Failed to read raw temperature: %s", e)
            self.logger.info("Raw temperature will be reported as 0.0°C")
            return 0.0

    def _apply_humidity_compensation(self, raw_humidity: float, raw_temp: float) -> float:
        """
        Apply CPU temperature compensation to humidity reading.

        Humidity sensors report relative humidity, which is temperature-
        dependent. If the BME280's internal temperature is elevated by CPU
        heating, it will report a lower RH% than actual. We compensate by
        adding back the error.

        The temperature error is smoothed to reduce jitter in the compensation.

        Args:
            raw_humidity: Raw humidity reading from BME280
            raw_temp: Raw temperature reading from BME280 (used for compensation calculation)

        Returns:
            CPU-compensated humidity in %
        """
        try:
            cpu_temp = self._get_smoothed_cpu_temp()

            # If CPU temperature is 0.0 and we have no previous smoothed value, skip compensation
            if cpu_temp == 0.0 and self._cpu_temp_last_update == 0.0:
                self.logger.debug("Humidity compensation skipped: no valid CPU temperature")
                return raw_humidity

            # Calculate temperature error due to CPU heating
            # This is the amount we compensated in temperature
            temp_error = (cpu_temp - raw_temp) / self.cpu_temp_factor

            # Apply smoothing to the temperature error to reduce jitter
            # Use the same smoothing factor as CPU temperature smoothing
            self._hum_compensation_temp_error_smoothed = (
                self.cpu_temp_smoothing * temp_error
                + (1 - self.cpu_temp_smoothing) * self._hum_compensation_temp_error_smoothed
            )

            # Compensate humidity: warmer sensor = lower RH%, so we add
            # The compensation factor is based on the smoothed temperature error
            # Empirical: large temp errors (10°C+) can cause 20+ percentage
            # point errors
            # 2% per °C error (empirical observation)
            compensated_humidity = raw_humidity + (self._hum_compensation_temp_error_smoothed * 2.0)

            self.logger.debug(
                "Humidity compensation: raw=%.1f%%, temp_error=%.1f°C, "
                "smoothed_error=%.1f°C, compensated=%.1f%%",
                raw_humidity,
                temp_error,
                self._hum_compensation_temp_error_smoothed,
                compensated_humidity,
            )
            return compensated_humidity
        except Exception as e:
            self.logger.warning("Humidity compensation failed: %s", e)
            return raw_humidity

    # Humidity accessors
    def humidity(self) -> float:
        """
        Get calibrated humidity reading with CPU compensation.

        Returns:
            Humidity in % (clamped to 0-100% range)
        """
        if self.bme280 is None:
            self.logger.debug("Humidity unavailable: BME280 not initialized")
            return 0.0
        try:
            raw_temp = self.bme280.get_temperature()
            raw_humidity = float(self.bme280.get_humidity())

            # Apply CPU temperature compensation
            compensated_humidity = self._apply_humidity_compensation(raw_humidity, raw_temp)

            # Apply user offset
            calibrated_humidity = compensated_humidity + self.hum_offset

            self.logger.debug(
                "Final humidity: %.2f%% (raw=%.2f%%, compensated=%.2f%%, " "offset=%.2f%%)",
                calibrated_humidity,
                raw_humidity,
                compensated_humidity,
                self.hum_offset,
            )

            return round(max(0.0, min(100.0, calibrated_humidity)), 2)
        except Exception as e:
            self.logger.error("Failed to read humidity: %s", e)
            self.logger.info("Humidity will be reported as 0.0%")
            return 0.0

    def humidity_raw(self) -> float:
        """
        Get raw humidity reading from BME280.

        Returns:
            Raw humidity in %
        """
        if self.bme280 is None:
            self.logger.debug("Raw humidity unavailable: BME280 not initialized")
            return 0.0
        try:
            return round(float(self.bme280.get_humidity()), 2)
        except Exception as e:
            self.logger.error("Failed to read raw humidity: %s", e)
            self.logger.info("Raw humidity will be reported as 0.0%")
            return 0.0

    # Pressure accessors
    def pressure(self) -> float:
        """
        Get pressure reading (no calibration applied).

        Returns:
            Pressure in hPa
        """
        if self.bme280 is None:
            self.logger.debug("Pressure unavailable: BME280 not initialized")
            return 0.0
        try:
            return round(float(self.bme280.get_pressure()), 2)
        except Exception as e:
            self.logger.error("Failed to read pressure: %s", e)
            self.logger.info("Pressure will be reported as 0.0 hPa")
            return 0.0

    def pressure_raw(self) -> float:
        """
        Get raw pressure reading from BME280.

        Returns:
            Raw pressure in hPa
        """
        if self.bme280 is None:
            self.logger.debug("Raw pressure unavailable: BME280 not initialized")
            return 0.0
        try:
            return round(float(self.bme280.get_pressure()), 2)
        except Exception as e:
            self.logger.error("Failed to read raw pressure: %s", e)
            self.logger.info("Raw pressure will be reported as 0.0 hPa")
            return 0.0

    # Light accessors
    def lux(self) -> float:
        """
        Get illuminance reading.

        Returns:
            Illuminance in lux
        """
        if self.ltr559 is None:
            self.logger.debug("Lux unavailable: LTR559 not initialized")
            return 0.0
        try:
            return round(float(self.ltr559.get_lux()), 2)
        except Exception as e:
            self.logger.error("Failed to read lux: %s", e)
            self.logger.info("Lux will be reported as 0.0 lux")
            return 0.0

    def lux_raw(self) -> float:
        """
        Get raw illuminance reading from LTR559.

        Returns:
            Raw illuminance in lux
        """
        if self.ltr559 is None:
            self.logger.debug("Raw lux unavailable: LTR559 not initialized")
            return 0.0
        try:
            return round(float(self.ltr559.get_lux()), 2)
        except Exception as e:
            self.logger.error("Failed to read raw lux: %s", e)
            self.logger.info("Raw lux will be reported as 0.0 lux")
            return 0.0

    # Gas sensor accessors
    def gas_oxidising(self) -> float:
        """
        Get oxidising gas reading in kΩ.

        Returns:
            Oxidising gas resistance in kΩ
        """
        if not self._gas_available:
            self.logger.debug("Oxidising gas unavailable: gas sensor not available (Enviro+ only)")
            return 0.0
        try:
            gas_data = gas.read_all()
            return round(float(gas_data.oxidising) / 1000.0, 2)
        except Exception as e:
            self.logger.error("Failed to read oxidising gas: %s", e)
            self.logger.info("Oxidising gas will be reported as 0.0 kΩ")
            return 0.0

    def gas_oxidising_raw(self) -> float:
        """
        Get raw oxidising gas reading in Ω.

        Returns:
            Raw oxidising gas resistance in Ω
        """
        if not self._gas_available:
            self.logger.debug(
                "Raw oxidising gas unavailable: gas sensor not available (Enviro+ only)"
            )
            return 0.0
        try:
            gas_data = gas.read_all()
            return round(float(gas_data.oxidising), 2)
        except Exception as e:
            self.logger.error("Failed to read raw oxidising gas: %s", e)
            self.logger.info("Raw oxidising gas will be reported as 0.0 Ω")
            return 0.0

    def gas_reducing(self) -> float:
        """
        Get reducing gas reading in kΩ.

        Returns:
            Reducing gas resistance in kΩ
        """
        if not self._gas_available:
            self.logger.debug("Reducing gas unavailable: gas sensor not available (Enviro+ only)")
            return 0.0
        try:
            gas_data = gas.read_all()
            return round(float(gas_data.reducing) / 1000.0, 2)
        except Exception as e:
            self.logger.error("Failed to read reducing gas: %s", e)
            self.logger.info("Reducing gas will be reported as 0.0 kΩ")
            return 0.0

    def gas_reducing_raw(self) -> float:
        """
        Get raw reducing gas reading in Ω.

        Returns:
            Raw reducing gas resistance in Ω
        """
        if not self._gas_available:
            self.logger.debug(
                "Raw reducing gas unavailable: gas sensor not available (Enviro+ only)"
            )
            return 0.0
        try:
            gas_data = gas.read_all()
            return round(float(gas_data.reducing), 2)
        except Exception as e:
            self.logger.error("Failed to read raw reducing gas: %s", e)
            self.logger.info("Raw reducing gas will be reported as 0.0 Ω")
            return 0.0

    def gas_nh3(self) -> float:
        """
        Get NH3 gas reading in kΩ.

        Returns:
            NH3 gas resistance in kΩ
        """
        if not self._gas_available:
            self.logger.debug("NH3 gas unavailable: gas sensor not available (Enviro+ only)")
            return 0.0
        try:
            gas_data = gas.read_all()
            return round(float(gas_data.nh3) / 1000.0, 2)
        except Exception as e:
            self.logger.error("Failed to read NH3 gas: %s", e)
            self.logger.info("NH3 gas will be reported as 0.0 kΩ")
            return 0.0

    def gas_nh3_raw(self) -> float:
        """
        Get raw NH3 gas reading in Ω.

        Returns:
            Raw NH3 gas resistance in Ω
        """
        if not self._gas_available:
            self.logger.debug("Raw NH3 gas unavailable: gas sensor not available (Enviro+ only)")
            return 0.0
        try:
            gas_data = gas.read_all()
            return round(float(gas_data.nh3), 2)
        except Exception as e:
            self.logger.error("Failed to read raw NH3 gas: %s", e)
            self.logger.info("Raw NH3 gas will be reported as 0.0 Ω")
            return 0.0

    def update_calibration(
        self,
        temp_offset: Optional[float] = None,
        hum_offset: Optional[float] = None,
        cpu_temp_factor: Optional[float] = None,
        cpu_temp_smoothing: Optional[float] = None,
    ) -> None:
        """
        Update calibration parameters.

        Args:
            temp_offset: New temperature offset in °C
            hum_offset: New humidity offset in %
            cpu_temp_factor: New CPU temperature compensation factor (higher=less compensation, lower=more compensation)
            cpu_temp_smoothing: New CPU temperature smoothing factor (0.0-1.0, lower=more smoothing)
        """
        if temp_offset is not None:
            self.temp_offset = temp_offset
            self.logger.info("Updated temperature offset to %s°C", temp_offset)

        if hum_offset is not None:
            self.hum_offset = hum_offset
            self.logger.info("Updated humidity offset to %s%%", hum_offset)

        if cpu_temp_factor is not None:
            self.cpu_temp_factor = cpu_temp_factor
            self.logger.info("Updated CPU temperature factor to %s", cpu_temp_factor)

        if cpu_temp_smoothing is not None:
            self.cpu_temp_smoothing = cpu_temp_smoothing
            self.logger.info("Updated CPU temperature smoothing to %s", cpu_temp_smoothing)

    def get_all_sensor_data(self) -> Dict[str, Any]:
        """
        Get all sensor readings in a structured format.

        Returns:
            Dictionary containing all sensor readings
        """
        return {
            # Temperature
            "temperature": self.temp(),
            "temperature_raw": self.temp_raw(),
            # Humidity
            "humidity": self.humidity(),
            "humidity_raw": self.humidity_raw(),
            # Pressure
            "pressure": self.pressure(),
            "pressure_raw": self.pressure_raw(),
            # Light
            "lux": self.lux(),
            "lux_raw": self.lux_raw(),
            # Gas sensors
            "gas_oxidising": self.gas_oxidising(),
            "gas_oxidising_raw": self.gas_oxidising_raw(),
            "gas_reducing": self.gas_reducing(),
            "gas_reducing_raw": self.gas_reducing_raw(),
            "gas_nh3": self.gas_nh3(),
            "gas_nh3_raw": self.gas_nh3_raw(),
        }
