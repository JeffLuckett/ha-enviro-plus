#!/usr/bin/env python3
"""
Unit tests for units setting in settings.py module
"""

import os
import sys
from unittest.mock import Mock, patch, mock_open
import pytest

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ha_enviro_plus.settings import SettingsManager


class TestUnitsSetting:
    """Test units setting functionality."""

    def test_default_units(self):
        """Test that default units is metric."""
        with patch("ha_enviro_plus.settings.Path") as mock_path_class:
            with patch("os.chmod"):
                with patch("builtins.open", mock_open()):
                    mock_path_instance = Mock()
                    mock_path_instance.mkdir = Mock()
                    mock_path_instance.exists.return_value = False
                    mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
                    mock_path_instance.with_suffix.return_value = mock_path_instance
                    mock_path_class.return_value = mock_path_instance

                    manager = SettingsManager()
                    assert manager.get_units() == "metric"

    def test_set_units_metric(self):
        """Test setting units to metric."""
        with patch("ha_enviro_plus.settings.Path") as mock_path_class:
            with patch("os.chmod"):
                with patch("builtins.open", mock_open()):
                    mock_path_instance = Mock()
                    mock_path_instance.mkdir = Mock()
                    mock_path_instance.exists.return_value = False
                    mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
                    mock_path_instance.with_suffix.return_value = mock_path_instance
                    mock_path_class.return_value = mock_path_instance

                    manager = SettingsManager()
                    manager.set_units("metric")
                    assert manager.get_units() == "metric"

    def test_set_units_imperial(self):
        """Test setting units to imperial."""
        with patch("ha_enviro_plus.settings.Path") as mock_path_class:
            with patch("os.chmod"):
                with patch("builtins.open", mock_open()):
                    mock_path_instance = Mock()
                    mock_path_instance.mkdir = Mock()
                    mock_path_instance.exists.return_value = False
                    mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
                    mock_path_instance.with_suffix.return_value = mock_path_instance
                    mock_path_class.return_value = mock_path_instance

                    manager = SettingsManager()
                    manager.set_units("imperial")
                    assert manager.get_units() == "imperial"

    def test_set_units_invalid(self):
        """Test setting invalid units value."""
        with patch("ha_enviro_plus.settings.Path") as mock_path_class:
            with patch("os.chmod"):
                with patch("builtins.open", mock_open()):
                    mock_path_instance = Mock()
                    mock_path_instance.mkdir = Mock()
                    mock_path_instance.exists.return_value = False
                    mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
                    mock_path_instance.with_suffix.return_value = mock_path_instance
                    mock_path_class.return_value = mock_path_instance

                    manager = SettingsManager()
                    original_units = manager.get_units()

                    # Try to set invalid units
                    manager.set_units("invalid")
                    # Should remain unchanged
                    assert manager.get_units() == original_units

    def test_units_in_get_all_settings(self):
        """Test that units is included in get_all_settings."""
        with patch("ha_enviro_plus.settings.Path") as mock_path_class:
            with patch("os.chmod"):
                with patch("builtins.open", mock_open()):
                    mock_path_instance = Mock()
                    mock_path_instance.mkdir = Mock()
                    mock_path_instance.exists.return_value = False
                    mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
                    mock_path_instance.with_suffix.return_value = mock_path_instance
                    mock_path_class.return_value = mock_path_instance

                    manager = SettingsManager()
                    settings = manager.get_all_settings()

                    assert "units" in settings
                    assert settings["units"] == "metric"

    def test_reset_to_defaults_includes_units(self):
        """Test that reset_to_defaults includes units."""
        with patch("ha_enviro_plus.settings.Path") as mock_path_class:
            with patch("os.chmod"):
                with patch("builtins.open", mock_open()):
                    mock_path_instance = Mock()
                    mock_path_instance.mkdir = Mock()
                    mock_path_instance.exists.return_value = False
                    mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
                    mock_path_instance.with_suffix.return_value = mock_path_instance
                    mock_path_class.return_value = mock_path_instance

                    manager = SettingsManager()
                    manager.set_units("imperial")
                    assert manager.get_units() == "imperial"

                    manager.reset_to_defaults()
                    assert manager.get_units() == "metric"
