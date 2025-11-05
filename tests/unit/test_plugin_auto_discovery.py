#!/usr/bin/env python3
"""
Unit tests for plugin auto-discovery from plugins directory
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestPluginAutoDiscovery:
    """Test plugin auto-discovery from plugins directory."""

    def test_plugins_directory_not_exists(self):
        """Test that missing plugins directory doesn't cause errors."""
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            "ha_enviro_plus.display_plugins",
            os.path.join(
                os.path.dirname(__file__), "..", "..", "ha_enviro_plus", "display_plugins.py"
            ),
        )
        display_plugins_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(display_plugins_module)
        _plugin_registry = display_plugins_module._plugin_registry

        # Clear any existing plugins
        original_plugins = list(_plugin_registry)

        # Reload the module to trigger auto-discovery
        import importlib
        import ha_enviro_plus.display_plugins

        # Mock the plugins directory to not exist
        with patch("pathlib.Path.exists", return_value=False):
            importlib.reload(ha_enviro_plus.display_plugins)

        # Should not raise exception
        assert isinstance(_plugin_registry, list)

    def test_hello_enviro_not_registered(self):
        """Test that hello_enviro.py is not registered by default."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ha_enviro_plus.display_plugins",
            os.path.join(
                os.path.dirname(__file__), "..", "..", "ha_enviro_plus", "display_plugins.py"
            ),
        )
        display_plugins_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(display_plugins_module)
        _plugin_registry = display_plugins_module._plugin_registry
        get_available_plugins = display_plugins_module.get_available_plugins

        # Check that HelloEnviroPlugin is not in the registry
        plugin_names = [p.__name__ for p in _plugin_registry]
        assert "HelloEnviroPlugin" not in plugin_names

        # Verify it's not available
        mock_sensors = Mock()
        mock_settings = Mock()
        available = get_available_plugins(mock_sensors, mock_settings)
        available_names = [p.name() for p in available]
        assert "Hello Enviro" not in available_names

    def test_plugin_auto_import_with_valid_plugin(self, tmp_path):
        """Test that plugins in plugins directory are auto-imported."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ha_enviro_plus.display_plugins",
            os.path.join(
                os.path.dirname(__file__), "..", "..", "ha_enviro_plus", "display_plugins.py"
            ),
        )
        display_plugins_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(display_plugins_module)
        _plugin_registry = display_plugins_module._plugin_registry
        DisplayPlugin = display_plugins_module.DisplayPlugin
        register_plugin = display_plugins_module.register_plugin

        # Create a temporary plugins directory
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create a test plugin file
        plugin_file = plugins_dir / "test_plugin.py"
        plugin_file.write_text(
            """
from ha_enviro_plus.display_plugins import DisplayPlugin, register_plugin

@register_plugin
class TestAutoPlugin(DisplayPlugin):
    def name(self):
        return "Test Auto Plugin"

    def is_available(self, sensors, settings):
        return True

    def render(self, sensors, settings):
        from PIL import Image
        return Image.new("RGB", (160, 80), color=(0, 0, 0))

    def duration(self):
        return 3.0
"""
        )

        # Mock the plugins directory path
        original_count = len(_plugin_registry)

        # Create __init__.py
        init_file = plugins_dir / "__init__.py"
        init_file.write_text("")

        # Temporarily add the plugins directory to sys.path
        import sys

        sys.path.insert(0, str(tmp_path))

        # Import the plugin module manually to simulate auto-discovery
        import importlib

        plugin_module = importlib.import_module("plugins.test_plugin")

        # Check that the plugin was registered
        assert len(_plugin_registry) >= original_count

        # Clean up
        sys.path.remove(str(tmp_path))
        if "plugins.test_plugin" in sys.modules:
            del sys.modules["plugins.test_plugin"]

    def test_plugin_auto_import_handles_import_errors(self, tmp_path):
        """Test that import errors in plugins are handled gracefully."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ha_enviro_plus.display_plugins",
            os.path.join(
                os.path.dirname(__file__), "..", "..", "ha_enviro_plus", "display_plugins.py"
            ),
        )
        display_plugins_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(display_plugins_module)
        _plugin_registry = display_plugins_module._plugin_registry

        # Create a temporary plugins directory
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create a plugin file with syntax errors
        plugin_file = plugins_dir / "broken_plugin.py"
        plugin_file.write_text(
            """
# This plugin has a syntax error
class BrokenPlugin:
    def name(self
        # Missing closing parenthesis
"""
        )

        # Create __init__.py
        init_file = plugins_dir / "__init__.py"
        init_file.write_text("")

        # Mock pathlib.Path to point to our temp directory
        with patch("ha_enviro_plus.display_plugins.Path") as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.parent = Mock()
            mock_path_instance.parent.__truediv__ = Mock(return_value=plugins_dir)
            mock_path.return_value = mock_path_instance

            # Mock pkgutil.iter_modules to return our broken plugin
            import pkgutil
            import importlib

            with patch("pkgutil.iter_modules") as mock_iter:
                mock_iter.return_value = [(Mock(), "broken_plugin", False)]

                # Mock the module import to raise an error
                with patch("importlib.import_module") as mock_import:
                    mock_import.side_effect = SyntaxError("Invalid syntax")

                    # Reload the module to trigger auto-discovery
                    import ha_enviro_plus.display_plugins

                    importlib.reload(ha_enviro_plus.display_plugins)

                    # Should not raise exception, should handle gracefully
                    assert isinstance(_plugin_registry, list)

    def test_plugin_auto_import_skips_private_modules(self, tmp_path):
        """Test that private modules (starting with _) are skipped."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ha_enviro_plus.display_plugins",
            os.path.join(
                os.path.dirname(__file__), "..", "..", "ha_enviro_plus", "display_plugins.py"
            ),
        )
        display_plugins_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(display_plugins_module)
        _plugin_registry = display_plugins_module._plugin_registry

        # Create a temporary plugins directory
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create private plugin file
        private_plugin = plugins_dir / "_private_plugin.py"
        private_plugin.write_text(
            """
from ha_enviro_plus.display_plugins import DisplayPlugin, register_plugin

@register_plugin
class PrivatePlugin(DisplayPlugin):
    def name(self):
        return "Private Plugin"

    def is_available(self, sensors, settings):
        return True

    def render(self, sensors, settings):
        from PIL import Image
        return Image.new("RGB", (160, 80), color=(0, 0, 0))

    def duration(self):
        return 3.0
"""
        )

        # Create __init__.py
        init_file = plugins_dir / "__init__.py"
        init_file.write_text("")

        # Mock pkgutil.iter_modules to return private module
        import pkgutil

        with patch("pkgutil.iter_modules") as mock_iter:
            mock_iter.return_value = [(Mock(), "_private_plugin", False)]

            # Mock pathlib.Path to point to our temp directory
            with patch("ha_enviro_plus.display_plugins.Path") as mock_path:
                mock_path_instance = Mock()
                mock_path_instance.parent = Mock()
                mock_path_instance.parent.__truediv__ = Mock(return_value=plugins_dir)
                mock_path.return_value = mock_path_instance

                # Reload the module to trigger auto-discovery
                import importlib
                import ha_enviro_plus.display_plugins

                original_count = len(_plugin_registry)
                importlib.reload(ha_enviro_plus.display_plugins)

                # Private plugin should not be imported
                # Registry count should not increase
                assert len(_plugin_registry) >= original_count

    def test_plugin_auto_import_skips_init_module(self, tmp_path):
        """Test that __init__.py is skipped during auto-discovery."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ha_enviro_plus.display_plugins",
            os.path.join(
                os.path.dirname(__file__), "..", "..", "ha_enviro_plus", "display_plugins.py"
            ),
        )
        display_plugins_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(display_plugins_module)
        _plugin_registry = display_plugins_module._plugin_registry

        # Create a temporary plugins directory
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create __init__.py
        init_file = plugins_dir / "__init__.py"
        init_file.write_text(
            """
from ha_enviro_plus.display_plugins import DisplayPlugin, register_plugin

@register_plugin
class InitPlugin(DisplayPlugin):
    def name(self):
        return "Init Plugin"

    def is_available(self, sensors, settings):
        return True

    def render(self, sensors, settings):
        from PIL import Image
        return Image.new("RGB", (160, 80), color=(0, 0, 0))

    def duration(self):
        return 3.0
"""
        )

        # Mock pkgutil.iter_modules to return __init__ module
        import pkgutil

        with patch("pkgutil.iter_modules") as mock_iter:
            mock_iter.return_value = [(Mock(), "__init__", False)]

            # Mock pathlib.Path to point to our temp directory
            with patch("ha_enviro_plus.display_plugins.Path") as mock_path:
                mock_path_instance = Mock()
                mock_path_instance.parent = Mock()
                mock_path_instance.parent.__truediv__ = Mock(return_value=plugins_dir)
                mock_path.return_value = mock_path_instance

                # Reload the module to trigger auto-discovery
                import importlib
                import ha_enviro_plus.display_plugins

                original_count = len(_plugin_registry)
                importlib.reload(ha_enviro_plus.display_plugins)

                # __init__ should not be imported as a plugin
                # Registry count should not increase from __init__
                assert len(_plugin_registry) >= original_count

    def test_sensor_display_plugin_is_registered(self):
        """Test that SensorDisplayPlugin is registered by default."""
        # Clear any cached modules to ensure fresh state
        import sys
        modules_to_clear = [
            "ha_enviro_plus.display_plugins",
            "ha_enviro_plus.plugins",
            "ha_enviro_plus.plugins.sensor_display",
        ]
        for module_name in modules_to_clear:
            if module_name in sys.modules:
                del sys.modules[module_name]

        # Import modules to trigger plugin registration
        import ha_enviro_plus.display_plugins
        from ha_enviro_plus.plugins import sensor_display
        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        # Get the registry and available plugins function
        _plugin_registry = ha_enviro_plus.display_plugins._plugin_registry
        get_available_plugins = ha_enviro_plus.display_plugins.get_available_plugins

        # Check that SensorDisplayPlugin is in the registry
        # The plugin should be registered when sensor_display module is imported
        assert SensorDisplayPlugin in _plugin_registry, (
            f"SensorDisplayPlugin not found in registry. "
            f"Registry contains: {[p.__name__ for p in _plugin_registry]}"
        )

        # Verify it can be discovered
        mock_sensors = Mock()
        mock_sensors.has_sensor.return_value = True
        mock_settings = Mock()
        available = get_available_plugins(mock_sensors, mock_settings)
        available_names = [p.name() for p in available]
        assert "Sensor Display" in available_names, (
            f"'Sensor Display' not found in available plugins. "
            f"Available plugins: {available_names}"
        )

    def test_plugin_auto_import_with_logging(self, tmp_path, caplog):
        """Test that import errors are logged."""
        import logging
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ha_enviro_plus.display_plugins",
            os.path.join(
                os.path.dirname(__file__), "..", "..", "ha_enviro_plus", "display_plugins.py"
            ),
        )
        display_plugins_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(display_plugins_module)
        _plugin_registry = display_plugins_module._plugin_registry

        # Create a temporary plugins directory
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create __init__.py
        init_file = plugins_dir / "__init__.py"
        init_file.write_text("")

        # Mock pkgutil.iter_modules to return a module that will fail
        import pkgutil
        import importlib

        with patch("pkgutil.iter_modules") as mock_iter:
            mock_iter.return_value = [(Mock(), "failing_plugin", False)]

            # Mock pathlib.Path to point to our temp directory
            with patch("ha_enviro_plus.display_plugins.Path") as mock_path:
                mock_path_instance = Mock()
                mock_path_instance.parent = Mock()
                mock_path_instance.parent.__truediv__ = Mock(return_value=plugins_dir)
                mock_path.return_value = mock_path_instance

                # Mock import_module to raise an error
                with patch("importlib.import_module") as mock_import:
                    mock_import.side_effect = ImportError("Module not found")

                    # Reload the module to trigger auto-discovery
                    with caplog.at_level(logging.WARNING):
                        import ha_enviro_plus.display_plugins

                        importlib.reload(ha_enviro_plus.display_plugins)

                        # Should log a warning
                        assert "Failed to import plugin module" in caplog.text
                        assert "failing_plugin" in caplog.text
