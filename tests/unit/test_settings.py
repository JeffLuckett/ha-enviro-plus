"""Unit tests for ha_enviro_plus.settings module."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from ha_enviro_plus.settings import SettingsManager


class TestSettingsManager:
    """Test the SettingsManager class."""

    def test_default_settings(self):
        """Test that default settings are correct."""
        with patch(
            "ha_enviro_plus.settings.Constants.SETTINGS_DIR", Path("/tmp/test-ha-enviro-plus")
        ):
            with patch("os.chmod"):
                with patch("builtins.open", mock_open()):
                    manager = SettingsManager()

                    assert manager.get_temp_offset() == 0.0
                    assert manager.get_hum_offset() == 0.0
                    assert manager.get_cpu_temp_factor() == 1.8
                    assert manager.get_cpu_temp_smoothing() == 0.1
                    assert manager.get_temp_smoothing_minutes() == 5.0
                    assert manager.get_units() == "metric"

    def test_set_and_get_settings(self, tmp_settings_dir):
        """Test setting and getting individual settings."""
        with patch("ha_enviro_plus.settings.Constants.SETTINGS_DIR", tmp_settings_dir):
            manager = SettingsManager()

            # Test property access
            assert manager.temp_offset == 0.0
            assert manager.hum_offset == 0.0
            assert manager.cpu_temp_factor == 1.8
            assert manager.cpu_temp_smoothing == 0.1
            assert manager.temp_smoothing_minutes == 5.0
            assert manager.units == "metric"

            # Test setters
            manager.set_temp_offset(1.5)
            manager.set_hum_offset(2.0)
            manager.set_cpu_temp_factor(2.5)
            manager.set_cpu_temp_smoothing(0.3)

            # Test getters
            assert manager.get_temp_offset() == 1.5
            assert manager.get_hum_offset() == 2.0
            assert manager.get_cpu_temp_factor() == 2.5
            assert manager.get_cpu_temp_smoothing() == 0.3

    def test_reset_to_defaults(self, tmp_settings_dir):
        """Test that reset_to_defaults works correctly."""
        with patch("ha_enviro_plus.settings.Constants.SETTINGS_DIR", tmp_settings_dir):
            manager = SettingsManager()

            # Set some custom values
            manager.set_temp_offset(5.0)
            manager.set_hum_offset(10.0)

            # Reset to defaults
            manager.reset_to_defaults()

            assert manager.get_temp_offset() == 0.0
            assert manager.get_hum_offset() == 0.0
            assert manager.get_cpu_temp_factor() == 1.8
            assert manager.get_cpu_temp_smoothing() == 0.1

    def test_get_all_settings(self, tmp_settings_dir):
        """Test that get_all_settings returns all current settings."""
        with patch("ha_enviro_plus.settings.Constants.SETTINGS_DIR", tmp_settings_dir):
            manager = SettingsManager()

            settings = manager.get_all_settings()

            expected_keys = {
                "temp_offset",
                "hum_offset",
                "cpu_temp_factor",
                "cpu_temp_smoothing",
                "temp_smoothing_minutes",
                "pressure_offset",
                "elevation_meters",
                "units",
            }
            assert set(settings.keys()) == expected_keys
            assert settings["temp_offset"] == 0.0
            assert settings["hum_offset"] == 0.0
            assert settings["cpu_temp_factor"] == 1.8
            assert settings["cpu_temp_smoothing"] == 0.1
            assert settings["temp_smoothing_minutes"] == 5.0
            assert settings["pressure_offset"] == 0.0
            assert settings["elevation_meters"] == 0.0
            assert settings["units"] == "metric"

    def test_set_setting_validates_key(self):
        """Test that setting an unknown key is handled gracefully."""
        with patch(
            "ha_enviro_plus.settings.Constants.SETTINGS_DIR", Path("/tmp/test-ha-enviro-plus")
        ):
            with patch("os.chmod"):
                with patch("builtins.open", mock_open()):
                    manager = SettingsManager()

                    # Should not raise an exception, just log a warning
                    manager.set_setting("unknown_key", 123)

    def test_file_operations_error_handling(self):
        """Test handling of file operation errors."""
        with patch("ha_enviro_plus.settings.Path") as mock_path_class:
            mock_path_instance = Mock()
            mock_path_instance.mkdir = Mock(side_effect=OSError("Cannot create directory"))
            mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
            mock_path_class.return_value = mock_path_instance

            with pytest.raises(OSError):
                SettingsManager()


class TestSettingsManagerIntegration:
    """Integration tests for SettingsManager with real file operations."""

    def test_settings_manager_functionality(self, tmp_settings_dir):
        """Test core settings manager functionality without file operations."""
        with patch("ha_enviro_plus.settings.Constants.SETTINGS_DIR", tmp_settings_dir):
            manager = SettingsManager()

            # Test basic functionality
            assert manager.get_temp_offset() == 0.0
            manager.set_temp_offset(2.5)
            assert manager.get_temp_offset() == 2.5

            # Test reset
            manager.reset_to_defaults()
            assert manager.get_temp_offset() == 0.0
