#!/usr/bin/env python3
"""
Settings Persistence Module

This module handles persistent storage of user-supplied settings via MQTT.
Settings are stored in JSON format and survive device restarts and updates.
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path


class SettingsManager:
    """
    Manages persistent storage of user-supplied settings.

    Settings are stored in JSON format in /var/lib/ha-enviro-plus/settings.json
    and include calibration values that can be modified via MQTT.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the settings manager.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)

        # Settings file path
        self.settings_dir = Path("/var/lib/ha-enviro-plus")
        self.settings_file = self.settings_dir / "settings.json"

        # Default settings values
        self.default_settings = {
            "temp_offset": 0.0,
            "hum_offset": 0.0,
            "cpu_temp_factor": 1.8,
            "cpu_temp_smoothing": 0.1,
        }

        # Current settings cache
        self._settings_cache: Dict[str, Any] = {}

        # Ensure settings directory exists
        self._ensure_settings_dir()

        # Load existing settings
        self._load_settings()

    def _ensure_settings_dir(self) -> None:
        """Ensure the settings directory exists with proper permissions."""
        try:
            self.settings_dir.mkdir(parents=True, exist_ok=True)
            # Set permissions to be readable/writable by the service user
            os.chmod(self.settings_dir, 0o755)
            self.logger.debug("Settings directory ensured: %s", self.settings_dir)
        except Exception as e:
            self.logger.error("Failed to create settings directory %s: %s", self.settings_dir, e)
            raise

    def _load_settings(self) -> None:
        """Load settings from the settings file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    loaded_settings = json.load(f)

                # Merge with defaults to ensure all keys exist
                self._settings_cache = {**self.default_settings, **loaded_settings}
                self.logger.info(
                    "Loaded settings from %s: %s", self.settings_file, self._settings_cache
                )
            else:
                # Use defaults if file doesn't exist
                self._settings_cache = self.default_settings.copy()
                self.logger.info("No settings file found, using defaults: %s", self._settings_cache)
                # Save defaults to file
                self._save_settings()

        except (json.JSONDecodeError, IOError) as e:
            self.logger.error("Failed to load settings from %s: %s", self.settings_file, e)
            self.logger.info("Using default settings due to load error")
            self._settings_cache = self.default_settings.copy()
            # Try to save defaults
            try:
                self._save_settings()
            except Exception as save_error:
                self.logger.error("Failed to save default settings: %s", save_error)

    def _save_settings(self) -> None:
        """Save current settings to the settings file."""
        try:
            # Create a temporary file first for atomic write
            temp_file = self.settings_file.with_suffix(".tmp")

            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._settings_cache, f, indent=2, sort_keys=True)

            # Atomic move
            temp_file.replace(self.settings_file)

            # Set proper permissions
            os.chmod(self.settings_file, 0o644)

            self.logger.debug("Settings saved to %s: %s", self.settings_file, self._settings_cache)

        except Exception as e:
            self.logger.error("Failed to save settings to %s: %s", self.settings_file, e)
            raise

    def get_setting(self, key: str) -> Any:
        """
        Get a setting value.

        Args:
            key: Setting key name

        Returns:
            Setting value, or None if key doesn't exist
        """
        return self._settings_cache.get(key)

    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all current settings.

        Returns:
            Dictionary of all settings
        """
        return self._settings_cache.copy()

    def set_setting(self, key: str, value: Any) -> None:
        """
        Set a setting value and save to file.

        Args:
            key: Setting key name
            value: Setting value
        """
        if key not in self.default_settings:
            self.logger.warning("Unknown setting key: %s", key)
            return

        old_value = self._settings_cache.get(key)
        self._settings_cache[key] = value

        self.logger.info("Setting %s changed from %s to %s", key, old_value, value)

        try:
            self._save_settings()
        except Exception as e:
            self.logger.error("Failed to save setting %s=%s: %s", key, value, e)
            # Revert the change
            self._settings_cache[key] = old_value
            raise

    def reset_to_defaults(self) -> None:
        """Reset all settings to default values."""
        self.logger.info("Resetting all settings to defaults")

        old_settings = self._settings_cache.copy()
        self._settings_cache = self.default_settings.copy()

        try:
            self._save_settings()
            self.logger.info(
                "Settings reset successfully from %s to %s", old_settings, self._settings_cache
            )
        except Exception as e:
            self.logger.error("Failed to reset settings: %s", e)
            # Revert the change
            self._settings_cache = old_settings
            raise

    def get_temp_offset(self) -> float:
        """Get temperature offset setting."""
        return float(self.get_setting("temp_offset"))

    def get_hum_offset(self) -> float:
        """Get humidity offset setting."""
        return float(self.get_setting("hum_offset"))

    def get_cpu_temp_factor(self) -> float:
        """Get CPU temperature factor setting."""
        return float(self.get_setting("cpu_temp_factor"))

    def get_cpu_temp_smoothing(self) -> float:
        """Get CPU temperature smoothing setting."""
        return float(self.get_setting("cpu_temp_smoothing"))

    def set_temp_offset(self, value: float) -> None:
        """Set temperature offset setting."""
        self.set_setting("temp_offset", float(value))

    def set_hum_offset(self, value: float) -> None:
        """Set humidity offset setting."""
        self.set_setting("hum_offset", float(value))

    def set_cpu_temp_factor(self, value: float) -> None:
        """Set CPU temperature factor setting."""
        self.set_setting("cpu_temp_factor", float(value))

    def set_cpu_temp_smoothing(self, value: float) -> None:
        """Set CPU temperature smoothing setting."""
        self.set_setting("cpu_temp_smoothing", float(value))
