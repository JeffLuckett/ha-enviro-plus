"""Unit tests for units setting in settings.py module."""

import pytest
from pathlib import Path
from unittest.mock import patch

from ha_enviro_plus.settings import SettingsManager


class TestUnitsSetting:
    """Test units setting functionality."""

    def test_default_units(self, tmp_settings_dir):
        """Test that default units is metric."""
        with patch("ha_enviro_plus.settings.Constants.SETTINGS_DIR", tmp_settings_dir):
            manager = SettingsManager()
            assert manager.get_units() == "metric"

    def test_set_units_metric(self, tmp_settings_dir):
        """Test setting units to metric."""
        with patch("ha_enviro_plus.settings.Constants.SETTINGS_DIR", tmp_settings_dir):
            manager = SettingsManager()
            manager.set_units("metric")
            assert manager.get_units() == "metric"

    def test_set_units_imperial(self, tmp_settings_dir):
        """Test setting units to imperial."""
        with patch("ha_enviro_plus.settings.Constants.SETTINGS_DIR", tmp_settings_dir):
            manager = SettingsManager()
            manager.set_units("imperial")
            assert manager.get_units() == "imperial"

    def test_set_units_invalid(self, tmp_settings_dir):
        """Test setting invalid units value."""
        with patch("ha_enviro_plus.settings.Constants.SETTINGS_DIR", tmp_settings_dir):
            manager = SettingsManager()
            original_units = manager.get_units()

            # Try to set invalid units
            manager.set_units("invalid")
            # Should remain unchanged
            assert manager.get_units() == original_units

    def test_units_in_get_all_settings(self, tmp_settings_dir):
        """Test that units is included in get_all_settings."""
        with patch("ha_enviro_plus.settings.Constants.SETTINGS_DIR", tmp_settings_dir):
            manager = SettingsManager()
            settings = manager.get_all_settings()

            assert "units" in settings
            assert settings["units"] == "metric"

    def test_reset_to_defaults_includes_units(self, tmp_settings_dir):
        """Test that reset_to_defaults includes units."""
        with patch("ha_enviro_plus.settings.Constants.SETTINGS_DIR", tmp_settings_dir):
            manager = SettingsManager()
            manager.set_units("imperial")
            assert manager.get_units() == "imperial"

            manager.reset_to_defaults()
            assert manager.get_units() == "metric"
