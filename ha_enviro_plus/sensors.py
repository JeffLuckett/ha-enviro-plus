#!/usr/bin/env python3
"""
Enviro+ Sensor Data Management

This module provides a clean interface for reading and processing data from
Pimoroni Enviro+ sensors with proper separation of concerns.
"""

import subprocess
import logging
from typing import Dict, Any, Optional

# Hardware imports with fallback for testing
try:
    from bme280 import BME280
    from ltr559 import LTR559
    from enviroplus import gas

    HARDWARE_AVAILABLE = True
except ImportError:
    # Mock hardware modules for testing environments
    BME280 = None
    LTR559 = None
    gas = None
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
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Enviro+ sensor manager.

        Args:
            temp_offset: Temperature calibration offset in °C
            hum_offset: Humidity calibration offset in %
            cpu_temp_factor: CPU temperature compensation factor
            logger: Optional logger instance
        """
        self.temp_offset = temp_offset
        self.hum_offset = hum_offset
        self.cpu_temp_factor = cpu_temp_factor
        self.logger = logger or logging.getLogger(__name__)

        # Initialize sensor hardware
        try:
            self.bme280 = BME280(i2c_addr=0x76)
            self.ltr559 = LTR559()
            self.logger.info("Enviro+ sensors initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize Enviro+ sensors: %s", e)
            raise

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
            self.logger.error("Failed to parse CPU temperature from output '%s': %s", out, e)
            raise
        except Exception as e:
            self.logger.error("Unexpected error reading CPU temperature: %s", e)
            raise

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
            cpu_temp = self._read_cpu_temp()
            # Apply Pimoroni compensation formula: raw_temp - ((cpu_temp - raw_temp) / factor)
            compensated_temp = raw_temp - ((cpu_temp - raw_temp) / self.cpu_temp_factor)
            self.logger.debug(
                "Temperature compensation: raw=%.1f°C, cpu=%.1f°C, compensated=%.1f°C",
                raw_temp,
                cpu_temp,
                compensated_temp,
            )
            return compensated_temp
        except Exception as e:
            self.logger.warning("CPU temperature compensation failed: %s", e)
            self.logger.info("Using raw temperature reading: %.1f°C", raw_temp)
            return raw_temp

    # Temperature accessors
    def temp(self) -> float:
        """
        Get compensated and calibrated temperature.

        Returns:
            Temperature in °C (compensated + offset)

        Raises:
            Never raises - always returns a fallback value
        """
        try:
            raw_temp = self.bme280.get_temperature()
            compensated_temp = self._apply_temp_compensation(raw_temp)
            final_temp = round(compensated_temp + self.temp_offset, 2)
            self.logger.debug(
                "Final temperature: %.2f°C (raw=%.2f, offset=%.2f)",
                final_temp,
                raw_temp,
                self.temp_offset,
            )
            return final_temp
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
        try:
            raw_temp = self.bme280.get_temperature()
            return round(float(raw_temp), 2)
        except Exception as e:
            self.logger.error("Failed to read raw temperature: %s", e)
            self.logger.info("Raw temperature will be reported as 0.0°C")
            return 0.0

    # Humidity accessors
    def humidity(self) -> float:
        """
        Get calibrated humidity reading.

        Returns:
            Humidity in % (clamped to 0-100% range)
        """
        raw_humidity = float(self.bme280.get_humidity())
        calibrated_humidity = raw_humidity + self.hum_offset
        return round(max(0.0, min(100.0, calibrated_humidity)), 2)

    def humidity_raw(self) -> float:
        """
        Get raw humidity reading from BME280.

        Returns:
            Raw humidity in %
        """
        return round(float(self.bme280.get_humidity()), 2)

    # Pressure accessors
    def pressure(self) -> float:
        """
        Get pressure reading (no calibration applied).

        Returns:
            Pressure in hPa
        """
        return round(float(self.bme280.get_pressure()), 2)

    def pressure_raw(self) -> float:
        """
        Get raw pressure reading from BME280.

        Returns:
            Raw pressure in hPa
        """
        return round(float(self.bme280.get_pressure()), 2)

    # Light accessors
    def lux(self) -> float:
        """
        Get illuminance reading.

        Returns:
            Illuminance in lux
        """
        return round(float(self.ltr559.get_lux()), 2)

    def lux_raw(self) -> float:
        """
        Get raw illuminance reading from LTR559.

        Returns:
            Raw illuminance in lux
        """
        return round(float(self.ltr559.get_lux()), 2)

    # Gas sensor accessors
    def gas_oxidising(self) -> float:
        """
        Get oxidising gas reading in kΩ.

        Returns:
            Oxidising gas resistance in kΩ
        """
        gas_data = gas.read_all()
        return round(float(gas_data.oxidising) / 1000.0, 2)

    def gas_oxidising_raw(self) -> float:
        """
        Get raw oxidising gas reading in Ω.

        Returns:
            Raw oxidising gas resistance in Ω
        """
        gas_data = gas.read_all()
        return round(float(gas_data.oxidising), 2)

    def gas_reducing(self) -> float:
        """
        Get reducing gas reading in kΩ.

        Returns:
            Reducing gas resistance in kΩ
        """
        gas_data = gas.read_all()
        return round(float(gas_data.reducing) / 1000.0, 2)

    def gas_reducing_raw(self) -> float:
        """
        Get raw reducing gas reading in Ω.

        Returns:
            Raw reducing gas resistance in Ω
        """
        gas_data = gas.read_all()
        return round(float(gas_data.reducing), 2)

    def gas_nh3(self) -> float:
        """
        Get NH3 gas reading in kΩ.

        Returns:
            NH3 gas resistance in kΩ
        """
        gas_data = gas.read_all()
        return round(float(gas_data.nh3) / 1000.0, 2)

    def gas_nh3_raw(self) -> float:
        """
        Get raw NH3 gas reading in Ω.

        Returns:
            Raw NH3 gas resistance in Ω
        """
        gas_data = gas.read_all()
        return round(float(gas_data.nh3), 2)

    def update_calibration(
        self,
        temp_offset: Optional[float] = None,
        hum_offset: Optional[float] = None,
        cpu_temp_factor: Optional[float] = None,
    ) -> None:
        """
        Update calibration parameters.

        Args:
            temp_offset: New temperature offset in °C
            hum_offset: New humidity offset in %
            cpu_temp_factor: New CPU temperature compensation factor
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
