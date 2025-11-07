#!/usr/bin/env python3
"""
Enviro+ Sensor Data Management

This module provides a clean interface for reading and processing data from
Pimoroni Enviro+ sensors with proper separation of concerns.
"""

import subprocess
import logging
import time
import numpy as np
from typing import Dict, Any, Optional, Tuple, List, Union
from collections import deque

from .constants import Constants

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

# Noise sensor imports - only need scipy for A-weighting filter
# We use arecord (ALSA) directly, not PortAudio/sounddevice
try:
    from scipy.signal import lfilter, butter

    NOISE_SENSOR_AVAILABLE = True
except ImportError:
    # scipy not installed
    NOISE_SENSOR_AVAILABLE = False
    lfilter = None
    butter = None


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
        pressure_offset: float = 0.0,
        elevation_meters: float = 0.0,
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
            pressure_offset: Pressure calibration offset in hPa
            elevation_meters: Elevation in meters for sea-level pressure calculation (0.0 = no correction)
            logger: Optional logger instance
        """
        self.temp_offset = temp_offset
        self.hum_offset = hum_offset
        self.cpu_temp_factor = cpu_temp_factor
        self.cpu_temp_smoothing = cpu_temp_smoothing
        self.temp_smoothing_minutes = temp_smoothing_minutes
        self.pressure_offset = pressure_offset
        self.elevation_meters = elevation_meters
        self.logger = logger or logging.getLogger(__name__)

        # CPU temperature smoothing state
        # Initialize with typical Pi Zero CPU temperature
        self._cpu_temp_smoothed = Constants.DEFAULT_CPU_TEMP_CELSIUS
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
        self._noise_available = False

        # Noise sensor state
        self._noise_chunks_discarded = 0
        self._noise_chunk_buffer: deque[float] = deque(maxlen=Constants.NOISE_AVERAGE_WINDOW)
        self._a_weight_filter: Optional[Tuple[List[float], List[float]]] = None
        if NOISE_SENSOR_AVAILABLE:
            try:
                # Initialize A-weighting filter coefficients
                # A-weighting filter approximates IEC 61672:2003
                # Using second-order IIR filter approximation
                self._init_a_weight_filter()
                self.logger.debug("Noise sensor A-weighting filter initialized")
            except Exception as e:
                self.logger.debug("Failed to initialize A-weighting filter: %s", e)

        if HARDWARE_AVAILABLE:
            # Initialize BME280 (temperature, humidity, pressure)
            try:
                self.bme280 = BME280(i2c_addr=Constants.BME280_I2C_ADDR)
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

            # Check if noise sensor (microphone) is available
            # On Enviro+, we use arecord (ALSA) directly for I2S microphone (adau7002)
            if NOISE_SENSOR_AVAILABLE:
                try:
                    import tempfile
                    import os
                    from scipy.io import wavfile

                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                        test_wav = tmp_file.name

                    try:
                        # Test recording with arecord (1 second)
                        result = subprocess.run(
                            [
                                "arecord",
                                "-D",
                                "dmic_sv",
                                "-c",
                                "2",
                                "-r",
                                str(Constants.NOISE_SAMPLE_RATE),
                                "-f",
                                "S32_LE",
                                "-t",
                                "wav",
                                "-d",
                                "1",
                                test_wav,
                            ],
                            capture_output=True,
                            timeout=2.0,
                            check=False,
                        )

                        if result.returncode == 0 and os.path.exists(test_wav):
                            # Check if file has data
                            sample_rate, test_data = wavfile.read(test_wav)
                            if test_data is not None and len(test_data) > 0:
                                self._noise_available = True
                                self.logger.info(
                                    "Noise sensor (microphone) available - verified by arecord test recording"
                                )
                            else:
                                self.logger.warning(
                                    "arecord test recording returned no data - noise sensor will be unavailable"
                                )
                                self._noise_available = False
                        else:
                            stderr_msg = (
                                result.stderr.decode("utf-8", errors="ignore")
                                if result.stderr
                                else ""
                            )
                            self.logger.warning(
                                "arecord test failed: %s - noise sensor will be unavailable",
                                stderr_msg,
                            )
                            self._noise_available = False
                    finally:
                        try:
                            if os.path.exists(test_wav):
                                os.unlink(test_wav)
                        except Exception:
                            pass
                except Exception as e:
                    self.logger.warning(
                        "Noise sensor not available: %s - noise sensor will be unavailable", e
                    )
                    self._noise_available = False
            else:
                self.logger.warning(
                    "Noise sensor libraries not available (scipy) - noise sensor will be unavailable"
                )

            # Log summary of available sensors
            available = []
            if self.bme280:
                available.append("BME280")
            if self.ltr559:
                available.append("LTR559")
            if self._gas_available:
                available.append("gas")
            if self._noise_available:
                available.append("noise")
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
            sensor_name: Name of the sensor ("bme280", "ltr559", "gas", or "noise")

        Returns:
            True if sensor is available, False otherwise
        """
        if sensor_name == "bme280":
            return self.bme280 is not None
        elif sensor_name == "ltr559":
            return self.ltr559 is not None
        elif sensor_name == "gas":
            return self._gas_available
        elif sensor_name == "noise":
            return self._noise_available
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
                    Constants.DEFAULT_CPU_TEMP_CELSIUS,
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
            return round(float(raw_temp), Constants.TEMP_ROUND_PRECISION)
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
            return round(float(self.bme280.get_humidity()), Constants.HUMIDITY_ROUND_PRECISION)
        except Exception as e:
            self.logger.error("Failed to read raw humidity: %s", e)
            self.logger.info("Raw humidity will be reported as 0.0%")
            return 0.0

    # Pressure accessors
    def _calculate_sea_level_pressure(
        self, station_pressure_hpa: float, elevation_m: float, temp_c: float
    ) -> float:
        """
        Calculate sea-level pressure from station pressure using hypsometric equation.

        Args:
            station_pressure_hpa: Station pressure in hPa
            elevation_m: Elevation in meters above sea level
            temp_c: Temperature in Celsius (for altitude correction)

        Returns:
            Sea-level pressure in hPa
        """
        if elevation_m <= 0.0:
            return station_pressure_hpa

        # Convert temperature to Kelvin
        temp_k = temp_c + 273.15

        # Standard atmospheric constants
        # L = temperature lapse rate (K/m)
        L = 0.0065  # K/m
        # g = standard gravity (m/s²)
        g = 9.80665  # m/s²
        # M = molar mass of dry air (kg/mol)
        M = 0.0289644  # kg/mol
        # R = universal gas constant (J/(mol·K))
        R = 8.31447  # J/(mol·K)

        # Hypsometric equation: P_sea = P_station * (T / (T - L * h))^(g * M / (R * L))
        # where h is elevation, T is temperature in Kelvin
        # This formula converts station pressure at elevation to sea-level equivalent
        exponent = (g * M) / (R * L)
        denominator = temp_k - (L * elevation_m)

        if denominator <= 0.0:
            self.logger.warning(
                "Invalid temperature-elevation combination (%s K, %s m), using station pressure",
                temp_k,
                elevation_m,
            )
            return station_pressure_hpa

        pressure_ratio = temp_k / denominator
        sea_level_pressure = float(station_pressure_hpa * (pressure_ratio**exponent))

        self.logger.debug(
            "Sea-level pressure: %.2f hPa (station: %.2f hPa, elevation: %.1f m, temp: %.1f°C)",
            sea_level_pressure,
            station_pressure_hpa,
            elevation_m,
            temp_c,
        )

        return sea_level_pressure

    def pressure(self) -> float:
        """
        Get pressure reading with elevation correction and calibration offset applied.

        Returns:
            Pressure in hPa (sea-level pressure if elevation is set, plus offset)
        """
        if self.bme280 is None:
            self.logger.debug("Pressure unavailable: BME280 not initialized")
            return 0.0
        try:
            raw_pressure = float(self.bme280.get_pressure())

            # Apply elevation correction to get sea-level pressure
            if self.elevation_meters > 0.0:
                # Use current temperature for accurate sea-level calculation
                current_temp = self.temp()  # This uses all calibrations
                sea_level_pressure = self._calculate_sea_level_pressure(
                    raw_pressure, self.elevation_meters, current_temp
                )
            else:
                sea_level_pressure = raw_pressure

            # Apply user offset
            calibrated_pressure = sea_level_pressure + self.pressure_offset

            self.logger.debug(
                "Final pressure: %.2f hPa (raw=%.2f, sea-level=%.2f, offset=%.2f, elevation=%.1f m)",
                calibrated_pressure,
                raw_pressure,
                sea_level_pressure,
                self.pressure_offset,
                self.elevation_meters,
            )

            return round(calibrated_pressure, Constants.PRESSURE_ROUND_PRECISION)
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
            return round(float(self.bme280.get_pressure()), Constants.PRESSURE_ROUND_PRECISION)
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
            return round(float(self.ltr559.get_lux()), Constants.TEMP_ROUND_PRECISION)
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
            return round(float(self.ltr559.get_lux()), Constants.TEMP_ROUND_PRECISION)
        except Exception as e:
            self.logger.error("Failed to read raw lux: %s", e)
            self.logger.info("Raw lux will be reported as 0.0 lux")
            return 0.0

    def proximity(self) -> float:
        """
        Get proximity reading from LTR559.

        Returns:
            Proximity value (0-255, higher = closer), or 0.0 if unavailable
        """
        if self.ltr559 is None:
            self.logger.debug("Proximity unavailable: LTR559 not initialized")
            return 0.0
        try:
            prox = self.ltr559.get_proximity()
            return round(float(prox), 0)
        except Exception as e:
            self.logger.error("Failed to read proximity: %s", e)
            self.logger.info("Proximity will be reported as 0.0")
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
            return round(float(gas_data.oxidising), Constants.TEMP_ROUND_PRECISION)
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
            return round(float(gas_data.reducing), Constants.TEMP_ROUND_PRECISION)
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
            return round(float(gas_data.nh3), Constants.TEMP_ROUND_PRECISION)
        except Exception as e:
            self.logger.error("Failed to read raw NH3 gas: %s", e)
            self.logger.info("Raw NH3 gas will be reported as 0.0 Ω")
            return 0.0

    def _init_a_weight_filter(self) -> None:
        """
        Initialize A-weighting filter coefficients.

        A-weighting filter approximates IEC 61672:2003 standard for sound level measurement.
        Uses second-order IIR filter coefficients calculated at sample rate.
        """
        if not NOISE_SENSOR_AVAILABLE or butter is None or lfilter is None:
            return

        try:
            # A-weighting filter coefficients for 44.1kHz sample rate
            # These coefficients approximate the A-weighting curve
            # Based on standard A-weighting filter design
            fs = Constants.NOISE_SAMPLE_RATE

            # A-weighting filter design using bilinear transform
            # Frequency response matches IEC 61672:2003 A-weighting
            # Simplified approximation using Butterworth-like filter
            # This is a practical approximation suitable for real-time processing

            # High-pass filter to remove DC and very low frequencies
            # Cutoff around 20 Hz
            b_hp, a_hp = butter(2, 20.0 / (fs / 2), btype="high", analog=False)

            # Low-pass filter to remove high-frequency noise
            # Cutoff around 20 kHz
            b_lp, a_lp = butter(2, 20000.0 / (fs / 2), btype="low", analog=False)

            # Combine filters (simplified A-weighting approximation)
            # In practice, we'll use a single filter that approximates A-weighting
            # For simplicity, we use a bandpass filter that approximates A-weighting response
            b_a, a_a = butter(2, [100.0 / (fs / 2), 10000.0 / (fs / 2)], btype="band", analog=False)

            self._a_weight_filter = (b_a, a_a)
            self.logger.debug("A-weighting filter initialized for sample rate %d Hz", fs)
        except Exception as e:
            self.logger.warning("Failed to initialize A-weighting filter: %s", e)
            self._a_weight_filter = None

    def _read_noise_chunk(self) -> Optional[float]:
        """
        Read a chunk of audio data and return RMS level.

        Uses arecord (ALSA) directly for I2S microphones.

        Returns:
            RMS level of audio chunk, or None if unavailable
        """
        if not self._noise_available:
            return None

        # Use arecord exclusively - PortAudio doesn't work reliably with I2S mics
        return self._read_noise_chunk_arecord()

    def _read_noise_chunk_raw(self) -> Optional[np.ndarray]:
        """
        Read raw audio data (not RMS) for A-weighting.

        Uses arecord (ALSA) directly for I2S microphones.

        Returns:
            Raw audio data as numpy array, or None if unavailable
        """
        if not self._noise_available:
            return None

        # Use arecord exclusively - PortAudio doesn't work reliably with I2S mics
        return self._read_noise_chunk_raw_arecord()

    def _read_noise_chunk_raw_arecord(self) -> Optional[np.ndarray]:
        """
        Read raw audio using arecord fallback.

        Returns:
            Raw audio data as numpy array, or None if unavailable
        """
        if not self._noise_available:
            return None

        try:
            import tempfile
            import os
            from scipy.io import wavfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_wav = tmp_file.name

            try:
                # Calculate duration - arecord only accepts integer seconds
                # Record 1 second minimum and we'll use only the samples we need
                duration_sec = max(1.0, Constants.NOISE_CHUNK_SIZE / Constants.NOISE_SAMPLE_RATE)
                duration_str = str(int(duration_sec))  # Use integer seconds

                result = subprocess.run(
                    [
                        "arecord",
                        "-D",
                        "dmic_sv",
                        "-c",
                        "2",
                        "-r",
                        str(Constants.NOISE_SAMPLE_RATE),
                        "-f",
                        "S16_LE",
                        "-t",
                        "wav",
                        "-d",
                        duration_str,
                        tmp_wav,
                    ],
                    capture_output=True,
                    timeout=duration_sec + 1.0,
                    check=False,
                )

                if result.returncode != 0:
                    return None

                sample_rate, audio_data = wavfile.read(tmp_wav)

                # Convert to float32 in range [-1.0, 1.0]
                if audio_data.dtype == np.int16:
                    audio_data = audio_data.astype(np.float32) / 32768.0
                elif audio_data.dtype == np.int32:
                    audio_data = audio_data.astype(np.float32) / 2147483648.0
                else:
                    audio_data = audio_data.astype(np.float32)

                # Ensure mono
                if len(audio_data.shape) > 1:
                    audio_data = audio_data[:, 0]

                return audio_data
            finally:
                try:
                    if os.path.exists(tmp_wav):
                        os.unlink(tmp_wav)
                except Exception:
                    pass
        except Exception:
            return None

    def _read_noise_chunk_arecord(self) -> Optional[float]:
        """
        Read audio using arecord (ALSA).

        Uses arecord to record a WAV file, then reads it with scipy.io.wavfile.

        Returns:
            RMS level of audio chunk, or None if unavailable
        """
        if not self._noise_available:
            return None

        try:
            import tempfile
            import os
            from scipy.io import wavfile

            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_wav = tmp_file.name

            try:
                # Calculate duration - arecord only accepts integer seconds
                # Record 1 second minimum and we'll use only the samples we need
                duration_sec = max(1.0, Constants.NOISE_CHUNK_SIZE / Constants.NOISE_SAMPLE_RATE)
                duration_str = str(int(duration_sec))  # Use integer seconds

                # Record using arecord with ALSA device
                # Use mono channel, 32-bit signed LE (required by I2S microphone)
                result = subprocess.run(
                    [
                        "arecord",
                        "-D",
                        "dmic_sv",  # Use our ALSA PCM device
                        "-c",
                        "2",  # Stereo (required by I2S microphone)
                        "-r",
                        str(Constants.NOISE_SAMPLE_RATE),
                        "-f",
                        "S32_LE",  # 32-bit signed little-endian
                        "-t",
                        "wav",
                        "-d",
                        duration_str,
                        tmp_wav,
                    ],
                    capture_output=True,
                    timeout=duration_sec + 1.0,  # Add 1 second buffer
                    check=False,  # Don't raise on error
                )

                if result.returncode != 0:
                    stderr_msg = result.stderr.decode("utf-8", errors="ignore")
                    # Check if device is busy - if so, wait a bit and retry multiple times
                    if "busy" in stderr_msg.lower() or "resource busy" in stderr_msg.lower():
                        # Device busy - retry with increasing delays
                        max_retries = 3
                        for retry in range(max_retries):
                            delay = 0.2 * (retry + 1)  # 0.2s, 0.4s, 0.6s
                            self.logger.debug(
                                "Device busy, waiting %.1fs and retrying arecord (attempt %d/%d)...",
                                delay,
                                retry + 1,
                                max_retries,
                            )
                            time.sleep(delay)
                            # Retry
                            result = subprocess.run(
                                [
                                    "arecord",
                                    "-D",
                                    "dmic_sv",
                                    "-c",
                                    "1",
                                    "-r",
                                    str(Constants.NOISE_SAMPLE_RATE),
                                    "-f",
                                    "S16_LE",
                                    "-t",
                                    "wav",
                                    "-d",
                                    duration_str,
                                    tmp_wav,
                                ],
                                capture_output=True,
                                timeout=duration_sec + 1.0,
                                check=False,
                            )
                            if result.returncode == 0:
                                break  # Success!
                        if result.returncode != 0:
                            stderr_msg = result.stderr.decode("utf-8", errors="ignore")
                            self.logger.warning(
                                "arecord failed after %d retries (exit code %d): %s",
                                max_retries,
                                result.returncode,
                                stderr_msg,
                            )
                            return None
                    else:
                        self.logger.warning(
                            "arecord failed (exit code %d): %s", result.returncode, stderr_msg
                        )
                        return None

                # Read WAV file
                sample_rate, audio_data = wavfile.read(tmp_wav)

                # Convert to float32 in range [-1.0, 1.0]
                if audio_data.dtype == np.int16:
                    audio_data = audio_data.astype(np.float32) / 32768.0
                elif audio_data.dtype == np.int32:
                    audio_data = audio_data.astype(np.float32) / 2147483648.0
                else:
                    audio_data = audio_data.astype(np.float32)

                # Ensure mono (take first channel if stereo)
                if len(audio_data.shape) > 1:
                    audio_data = audio_data[:, 0]

                # Trim to only the samples we need (in case we recorded more)
                samples_needed = Constants.NOISE_CHUNK_SIZE
                if len(audio_data) > samples_needed:
                    audio_data = audio_data[:samples_needed]

                # Check if we got actual audio data (not all zeros)
                max_val = np.max(np.abs(audio_data))
                if max_val == 0.0:
                    self.logger.warning(
                        "arecord returned zeros (max_val=0.0) - microphone may not be recording"
                    )
                    return 0.0

                # Calculate RMS
                rms = np.sqrt(np.mean(audio_data**2))

                self.logger.info(
                    "arecord fallback succeeded: RMS=%.6f (max=%.6f, shape=%s, dtype=%s)",
                    rms,
                    max_val,
                    audio_data.shape,
                    audio_data.dtype,
                )
                return float(rms)

            finally:
                # Clean up temporary file
                try:
                    if os.path.exists(tmp_wav):
                        os.unlink(tmp_wav)
                except Exception:
                    pass

        except ImportError:
            # scipy.io.wavfile not available
            self.logger.debug("scipy.io.wavfile not available for arecord fallback")
            return None
        except Exception as e:
            self.logger.debug("Failed to read noise chunk with arecord: %s", e)
            return None

    def noise_spl_db(self) -> float:
        """
        Get A-weighted sound pressure level in dB(A).

        Uses streaming approach to handle microphone startup "plop" by discarding
        initial chunks. Applies A-weighting filter for accurate sound level measurement.

        Returns:
            Sound pressure level in dB(A), or 0.0 if unavailable
        """
        if not self._noise_available:
            self.logger.debug("Noise SPL unavailable: microphone not available")
            return 0.0

        if not NOISE_SENSOR_AVAILABLE or self._a_weight_filter is None:
            self.logger.debug("Noise SPL unavailable: noise sensor libraries not available")
            return 0.0

        try:
            # Read raw audio for A-weighting
            raw_audio = self._read_noise_chunk_raw()
            if raw_audio is None:
                return 0.0

            # Discard initial chunks to avoid microphone startup "plop"
            if self._noise_chunks_discarded < Constants.NOISE_STARTUP_DISCARD_CHUNKS:
                self._noise_chunks_discarded += 1
                max_val = np.max(np.abs(raw_audio))
                raw_rms = np.sqrt(np.mean(raw_audio**2))
                self.logger.debug(
                    "Discarding noise chunk %d/%d (startup plop, max=%.6f, rms=%.6f)",
                    self._noise_chunks_discarded,
                    Constants.NOISE_STARTUP_DISCARD_CHUNKS,
                    max_val,
                    raw_rms,
                )
                return 0.0

            # Apply A-weighting filter
            b, a = self._a_weight_filter
            filtered_audio = lfilter(b, a, raw_audio.flatten())

            # Calculate RMS of filtered audio
            rms = np.sqrt(np.mean(filtered_audio**2))

            # Get max value for logging
            max_val = np.max(np.abs(raw_audio))

            # Convert to dB(A)
            # For normalized audio (range -1 to 1), we need to account for:
            # 1. Microphone sensitivity (typically -40 to -60 dBV/Pa for I2S mics)
            # 2. Preamp gain
            # 3. ADC normalization (int32 to float32)
            # 4. A-weighting filter attenuation
            # We use a calibration offset to map RMS values to dB(A)
            # This offset is calibrated for I2S microphone (adau7002) based on typical quiet room (30 dB)
            # Formula: dB(A) = 20 * log10(filtered_rms) + calibration_offset
            # Calibrated for quiet room (30 dB) with raw RMS ~0.049
            # After A-weighting, filtered RMS is typically 10-20% of raw RMS
            if rms > 0:
                # Convert filtered RMS to dB using logarithmic scale
                # Add small epsilon to avoid log(0)
                spl_db = 20.0 * np.log10(rms + 1e-10)

                # Add calibration offset to map to actual dB(A) range
                # This offset accounts for microphone sensitivity, normalization, and A-weighting
                # Calibrated for quiet room (30 dB) - adjust if needed with reference SPL meter
                spl_db_calibrated = spl_db + Constants.NOISE_CALIBRATION_OFFSET

                # Only clamp maximum to prevent unrealistic high readings
                # Don't clamp minimum - report actual quiet readings accurately
                spl_db_final = min(100.0, spl_db_calibrated)

                self.logger.info(
                    "Noise SPL: %.1f dB(A) (raw rms=%.6f, filtered rms=%.6f, max=%.6f)",
                    spl_db_final,
                    np.sqrt(np.mean(raw_audio**2)),
                    rms,
                    max_val,
                )
                return float(round(spl_db_final, Constants.NOISE_ROUND_PRECISION))
            else:
                self.logger.debug("Noise SPL: rms is 0, returning 0.0")
                return 0.0

        except Exception as e:
            # PortAudio failed - try arecord fallback for raw audio
            self.logger.warning(
                "PortAudio failed in noise_spl_db: %s, trying arecord fallback...", e
            )
            try:
                raw_audio = self._read_noise_chunk_raw_arecord()
                if raw_audio is None:
                    self.logger.warning("arecord fallback also failed in noise_spl_db")
                    return 0.0

                # Apply A-weighting filter
                b, a = self._a_weight_filter
                filtered_audio = lfilter(b, a, raw_audio.flatten())

                # Calculate RMS of filtered audio
                rms = np.sqrt(np.mean(filtered_audio**2))
                max_val = np.max(np.abs(raw_audio))

                if rms > 0:
                    # Use same calibration as main path
                    spl_db = 20.0 * np.log10(rms + 1e-10)
                    spl_db_calibrated = spl_db + Constants.NOISE_CALIBRATION_OFFSET
                    spl_db_final = min(100.0, spl_db_calibrated)
                    self.logger.info(
                        "arecord fallback succeeded in noise_spl_db: %.1f dB(A) (raw rms=%.6f, filtered rms=%.6f, max=%.6f)",
                        spl_db_final,
                        np.sqrt(np.mean(raw_audio**2)),
                        rms,
                        max_val,
                    )
                    return float(round(spl_db_final, Constants.NOISE_ROUND_PRECISION))
                else:
                    return 0.0
            except Exception as fallback_error:
                self.logger.error(
                    "arecord fallback also failed in noise_spl_db: %s", fallback_error
                )
                return 0.0

    def noise_spl_raw(self) -> float:
        """
        Get raw sound pressure level (unweighted).

        Returns:
            Raw sound level (RMS), or 0.0 if unavailable
        """
        if not self._noise_available:
            self.logger.debug("Raw noise SPL unavailable: microphone not available")
            return 0.0

        if not NOISE_SENSOR_AVAILABLE:
            self.logger.debug("Raw noise SPL unavailable: noise sensor libraries not available")
            return 0.0

        try:
            rms = self._read_noise_chunk()
            if rms is not None:
                return round(rms, Constants.NOISE_ROUND_PRECISION)
            return 0.0
        except Exception as e:
            self.logger.error("Failed to read raw noise SPL: %s", e)
            self.logger.info("Raw noise SPL will be reported as 0.0")
            return 0.0

    def update_calibration(
        self,
        temp_offset: Optional[float] = None,
        hum_offset: Optional[float] = None,
        cpu_temp_factor: Optional[float] = None,
        cpu_temp_smoothing: Optional[float] = None,
        temp_smoothing_minutes: Optional[float] = None,
        pressure_offset: Optional[float] = None,
        elevation_meters: Optional[float] = None,
    ) -> None:
        """
        Update calibration parameters.

        Args:
            temp_offset: New temperature offset in °C
            hum_offset: New humidity offset in %
            cpu_temp_factor: New CPU temperature compensation factor (higher=less compensation, lower=more compensation)
            cpu_temp_smoothing: New CPU temperature smoothing factor (0.0-1.0, lower=more smoothing)
            temp_smoothing_minutes: New temperature smoothing window in minutes (0.0 = no smoothing)
            pressure_offset: New pressure offset in hPa
            elevation_meters: New elevation in meters for sea-level pressure calculation
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

        if temp_smoothing_minutes is not None:
            self.temp_smoothing_minutes = temp_smoothing_minutes
            # Clear history when smoothing window changes
            self._temp_history.clear()
            self.logger.info(
                "Updated temperature smoothing window to %s minutes", temp_smoothing_minutes
            )

        if pressure_offset is not None:
            self.pressure_offset = pressure_offset
            self.logger.info("Updated pressure offset to %s hPa", pressure_offset)

        if elevation_meters is not None:
            if elevation_meters < 0.0:
                self.logger.warning("Elevation cannot be negative, setting to 0.0")
                elevation_meters = 0.0
            self.elevation_meters = elevation_meters
            self.logger.info("Updated elevation to %s meters", elevation_meters)

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
            # Proximity
            "proximity": self.proximity(),
            # Gas sensors
            "gas_oxidising": self.gas_oxidising(),
            "gas_oxidising_raw": self.gas_oxidising_raw(),
            "gas_reducing": self.gas_reducing(),
            "gas_reducing_raw": self.gas_reducing_raw(),
            "gas_nh3": self.gas_nh3(),
            "gas_nh3_raw": self.gas_nh3_raw(),
            # Noise sensor
            "noise_spl_db": self.noise_spl_db(),
            "noise_spl_raw": self.noise_spl_raw(),
        }
