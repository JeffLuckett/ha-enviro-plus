"""Unit tests for display_plugins.py module."""

from unittest.mock import Mock, patch, MagicMock

import pytest


class TestUnitConversions:
    """Test unit conversion helper functions."""

    def test_celsius_to_fahrenheit(self):
        """Test Celsius to Fahrenheit conversion."""
        from ha_enviro_plus.display_plugins import celsius_to_fahrenheit

        # Test freezing point
        assert celsius_to_fahrenheit(0.0) == 32.0

        # Test boiling point
        assert celsius_to_fahrenheit(100.0) == 212.0

        # Test room temperature
        assert abs(celsius_to_fahrenheit(25.0) - 77.0) < 0.1

        # Test negative temperature
        assert abs(celsius_to_fahrenheit(-40.0) - (-40.0)) < 0.1

    def test_hpa_to_inhg(self):
        """Test hPa to inHg conversion."""
        from ha_enviro_plus.display_plugins import hpa_to_inhg

        # Test standard atmospheric pressure
        result = hpa_to_inhg(1013.25)
        assert abs(result - 29.92) < 0.1

        # Test sea level pressure
        result = hpa_to_inhg(1013.0)
        assert result > 0

        # Test low pressure
        result = hpa_to_inhg(980.0)
        assert result > 0
        assert result < 30.0


class TestDisplayPlugin:
    """Test DisplayPlugin base class."""

    def test_display_plugin_abstract(self):
        """Test that DisplayPlugin is abstract."""
        from ha_enviro_plus.display_plugins import DisplayPlugin

        # Cannot instantiate abstract class
        with pytest.raises(TypeError):
            DisplayPlugin()

    def test_display_plugin_implementation(self):
        """Test that a concrete plugin can be created."""
        from ha_enviro_plus.display_plugins import DisplayPlugin

        # Create a concrete implementation
        class TestPlugin(DisplayPlugin):
            def name(self):
                return "Test Plugin"

            def is_available(self, sensors, settings):
                return True

            def render(self, sensors, settings):
                from PIL import Image

                return Image.new("RGB", (160, 80), color=(0, 0, 0))

            def duration(self):
                return 5.0

        plugin = TestPlugin()
        assert plugin.name() == "Test Plugin"
        assert plugin.duration() == 5.0
        assert plugin.is_available(Mock(), Mock()) is True

    def test_error_message_generation(self):
        """Test error message generation."""
        from ha_enviro_plus.display_plugins import DisplayPlugin

        class TestPlugin(DisplayPlugin):
            def name(self):
                return "Test Plugin"

            def is_available(self, sensors, settings):
                return True

            def render(self, sensors, settings):
                from PIL import Image

                return Image.new("RGB", (160, 80), color=(0, 0, 0))

            def duration(self):
                return 5.0

        plugin = TestPlugin()
        error = Exception("Test error")
        message = plugin.error_message(error)
        assert "Test Plugin" in message
        assert "Test error" in message


class TestPluginRegistry:
    """Test plugin registry and discovery system."""

    def test_register_plugin(self):
        """Test plugin registration."""
        from ha_enviro_plus.display_plugins import (
            DisplayPlugin,
            register_plugin,
            get_available_plugins,
            _plugin_registry,
        )

        # Clear registry for testing
        original_count = len(_plugin_registry)

        class TestPlugin(DisplayPlugin):
            def name(self):
                return "Test Plugin"

            def is_available(self, sensors, settings):
                return True

            def render(self, sensors, settings):
                from PIL import Image

                return Image.new("RGB", (160, 80), color=(0, 0, 0))

            def duration(self):
                return 5.0

        # Register plugin
        registered = register_plugin(TestPlugin)
        assert registered == TestPlugin
        assert TestPlugin in _plugin_registry

        # Test discovery
        mock_sensors = Mock()
        mock_settings = Mock()
        available = get_available_plugins(mock_sensors, mock_settings)
        assert len(available) >= original_count + 1

        # Clean up
        _plugin_registry.remove(TestPlugin)

    def test_get_available_plugins_filters_unavailable(self):
        """Test that unavailable plugins are filtered out."""
        from ha_enviro_plus.display_plugins import (
            DisplayPlugin,
            register_plugin,
            get_available_plugins,
            _plugin_registry,
        )

        # Clear registry for testing
        original_plugins = list(_plugin_registry)

        class UnavailablePlugin(DisplayPlugin):
            def name(self):
                return "Unavailable Plugin"

            def is_available(self, sensors, settings):
                return False

            def render(self, sensors, settings):
                from PIL import Image

                return Image.new("RGB", (160, 80), color=(0, 0, 0))

            def duration(self):
                return 5.0

        # Register plugin
        register_plugin(UnavailablePlugin)

        # Test discovery - should not include unavailable plugin
        mock_sensors = Mock()
        mock_settings = Mock()
        available = get_available_plugins(mock_sensors, mock_settings)

        # Should not include unavailable plugin
        unavailable_names = [p.name() for p in available if p.name() == "Unavailable Plugin"]
        assert len(unavailable_names) == 0

        # Clean up
        _plugin_registry.remove(UnavailablePlugin)

    def test_get_available_plugins_handles_errors(self):
        """Test that plugin errors are handled gracefully."""
        from ha_enviro_plus.display_plugins import (
            DisplayPlugin,
            register_plugin,
            get_available_plugins,
            _plugin_registry,
        )

        # Clear registry for testing
        class ErrorPlugin(DisplayPlugin):
            def name(self):
                return "Error Plugin"

            def is_available(self, sensors, settings):
                raise Exception("Plugin error")

            def render(self, sensors, settings):
                from PIL import Image

                return Image.new("RGB", (160, 80), color=(0, 0, 0))

            def duration(self):
                return 5.0

        # Register plugin
        register_plugin(ErrorPlugin)

        # Test discovery - should handle errors gracefully
        mock_sensors = Mock()
        mock_settings = Mock()
        # Should not raise exception
        available = get_available_plugins(mock_sensors, mock_settings)
        assert isinstance(available, list)

        # Clean up
        _plugin_registry.remove(ErrorPlugin)


class TestSensorDisplayPlugin:
    """Test SensorDisplayPlugin implementation."""

    @pytest.fixture
    def mock_sensors(self):
        """Create mock sensors."""
        sensors = Mock()
        sensors.has_sensor.return_value = True
        sensors.temp.return_value = 25.5
        sensors.humidity.return_value = 45.0
        sensors.pressure.return_value = 1013.25
        return sensors

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.get_units.return_value = "metric"
        return settings

    def test_sensor_plugin_name(self):
        """Test plugin name."""
        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        plugin = SensorDisplayPlugin()
        assert plugin.name() == "Sensor Display"

    def test_sensor_plugin_duration(self):
        """Test plugin duration."""
        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        plugin = SensorDisplayPlugin()
        assert plugin.duration() == 0.1  # Continuous update mode

    def test_sensor_plugin_is_available_with_bme280(self, mock_sensors, mock_settings):
        """Test plugin availability with BME280 sensor."""
        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        plugin = SensorDisplayPlugin()
        assert plugin.is_available(mock_sensors, mock_settings) is True

    def test_sensor_plugin_is_available_without_bme280(self, mock_settings):
        """Test plugin availability without BME280 sensor."""
        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        mock_sensors = Mock()
        mock_sensors.has_sensor.return_value = False

        plugin = SensorDisplayPlugin()
        assert plugin.is_available(mock_sensors, mock_settings) is False

    def test_sensor_plugin_is_available_handles_errors(self, mock_settings):
        """Test plugin availability error handling."""
        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        mock_sensors = Mock()
        mock_sensors.has_sensor.side_effect = Exception("Sensor error")

        plugin = SensorDisplayPlugin()
        assert plugin.is_available(mock_sensors, mock_settings) is False

    @patch("ha_enviro_plus.plugins.sensor_display.PIL_AVAILABLE", True)
    def test_sensor_plugin_render_metric(self, mock_sensors, mock_settings):
        """Test plugin rendering with metric units."""
        import ha_enviro_plus.plugins.sensor_display as sensor_display_module
        from unittest.mock import MagicMock

        # Set up PIL mocks in the module
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()

        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(side_effect=OSError("Font not found"))
        mock_font.load_default = Mock(return_value=mock_font_instance)

        # Set the module attributes
        sensor_display_module.Image = mock_image
        sensor_display_module.ImageDraw = mock_draw
        sensor_display_module.ImageFont = mock_font

        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        plugin = SensorDisplayPlugin()
        result = plugin.render(mock_sensors, mock_settings)

        # Verify image was created
        mock_image.new.assert_called_once()
        assert result == mock_img_instance

        # Verify settings were checked for units
        mock_settings.get_units.assert_called_once()

    @patch("ha_enviro_plus.plugins.sensor_display.PIL_AVAILABLE", True)
    def test_sensor_plugin_render_imperial(self, mock_sensors, mock_settings):
        """Test plugin rendering with imperial units."""
        import ha_enviro_plus.plugins.sensor_display as sensor_display_module
        from unittest.mock import MagicMock

        # Setup mocks
        mock_settings.get_units.return_value = "imperial"

        # Set up PIL mocks in the module
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()

        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(side_effect=OSError("Font not found"))
        mock_font.load_default = Mock(return_value=mock_font_instance)

        # Set the module attributes
        sensor_display_module.Image = mock_image
        sensor_display_module.ImageDraw = mock_draw
        sensor_display_module.ImageFont = mock_font

        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        plugin = SensorDisplayPlugin()
        result = plugin.render(mock_sensors, mock_settings)

        # Verify image was created
        mock_image.new.assert_called_once()
        assert result == mock_img_instance

    @patch("ha_enviro_plus.plugins.sensor_display.PIL_AVAILABLE", False)
    def test_sensor_plugin_render_no_pil(self, mock_sensors, mock_settings):
        """Test plugin rendering when PIL is not available."""
        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        plugin = SensorDisplayPlugin()
        with pytest.raises(RuntimeError, match="PIL/Pillow not available"):
            plugin.render(mock_sensors, mock_settings)

    @patch("ha_enviro_plus.plugins.sensor_display.PIL_AVAILABLE", True)
    def test_sensor_plugin_render_handles_sensor_errors(self, mock_settings):
        """Test plugin rendering handles sensor errors gracefully."""
        import ha_enviro_plus.plugins.sensor_display as sensor_display_module
        from unittest.mock import MagicMock

        # Setup mocks
        mock_sensors = Mock()
        mock_sensors.has_sensor.return_value = True
        mock_sensors.temp.side_effect = Exception("Sensor read error")

        # Set up PIL mocks in the module
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()

        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(side_effect=OSError("Font not found"))
        mock_font.load_default = Mock(return_value=mock_font_instance)

        # Set the module attributes
        sensor_display_module.Image = mock_image
        sensor_display_module.ImageDraw = mock_draw
        sensor_display_module.ImageFont = mock_font

        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        plugin = SensorDisplayPlugin()
        # Should not raise exception, should handle gracefully
        result = plugin.render(mock_sensors, mock_settings)
        assert result == mock_img_instance

    @patch("ha_enviro_plus.plugins.sensor_display.PIL_AVAILABLE", True)
    def test_sensor_plugin_render_temperature_conversion(self, mock_sensors, mock_settings):
        """Test temperature conversion in rendering."""
        import ha_enviro_plus.plugins.sensor_display as sensor_display_module
        from unittest.mock import MagicMock

        # Setup mocks
        mock_settings.get_units.return_value = "imperial"
        mock_sensors.temp.return_value = 25.0  # 25°C = 77°F

        # Set up PIL mocks in the module
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()

        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(return_value=mock_font_instance)
        mock_font.load_default = Mock(return_value=mock_font_instance)

        # Set the module attributes
        sensor_display_module.Image = mock_image
        sensor_display_module.ImageDraw = mock_draw
        sensor_display_module.ImageFont = mock_font

        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        plugin = SensorDisplayPlugin()
        plugin.render(mock_sensors, mock_settings)

        # Verify temperature was read
        mock_sensors.temp.assert_called()

        # Verify text was drawn (should include converted temperature)
        assert mock_draw_instance.text.called

    @patch("ha_enviro_plus.plugins.sensor_display.PIL_AVAILABLE", True)
    def test_sensor_plugin_render_pressure_conversion(self, mock_sensors, mock_settings):
        """Test pressure conversion in rendering."""
        import ha_enviro_plus.plugins.sensor_display as sensor_display_module
        from unittest.mock import MagicMock

        # Setup mocks
        mock_settings.get_units.return_value = "imperial"
        mock_sensors.pressure.return_value = 1013.25  # Standard atmospheric pressure

        # Set up PIL mocks in the module
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()

        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(return_value=mock_font_instance)
        mock_font.load_default = Mock(return_value=mock_font_instance)

        # Set the module attributes
        sensor_display_module.Image = mock_image
        sensor_display_module.ImageDraw = mock_draw
        sensor_display_module.ImageFont = mock_font

        from ha_enviro_plus.plugins.sensor_display import SensorDisplayPlugin

        plugin = SensorDisplayPlugin()
        plugin.render(mock_sensors, mock_settings)

        # Verify pressure was read
        mock_sensors.pressure.assert_called()

        # Verify text was drawn (should include converted pressure)
        assert mock_draw_instance.text.called


class TestIndividualDisplayPlugins:
    """Test individual sensor display plugins."""

    @pytest.fixture
    def mock_sensors_bme280(self):
        """Create mock sensors with BME280."""
        sensors = Mock()
        sensors.has_sensor.return_value = True
        sensors.temp.return_value = 25.5
        sensors.humidity.return_value = 45.0
        sensors.pressure.return_value = 1013.25
        return sensors

    @pytest.fixture
    def mock_sensors_noise(self):
        """Create mock sensors with noise sensor."""
        sensors = Mock()
        sensors.has_sensor.return_value = True
        sensors.noise_spl_db.return_value = 65.5
        return sensors

    @pytest.fixture
    def mock_sensors_gas(self):
        """Create mock sensors with gas sensor."""
        sensors = Mock()
        sensors.has_sensor.return_value = True
        sensors.gas_oxidising.return_value = 50.0
        sensors.gas_reducing.return_value = 30.0
        sensors.gas_nh3.return_value = 40.0
        return sensors

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.get_units.return_value = "metric"
        return settings

    @patch("ha_enviro_plus.plugins.temperature_display.PIL_AVAILABLE", True)
    def test_temperature_display_plugin(self, mock_sensors_bme280, mock_settings):
        """Test TemperatureDisplayPlugin."""
        import ha_enviro_plus.plugins.temperature_display as temp_module
        from unittest.mock import MagicMock

        # Setup PIL mocks
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()

        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw_instance.textbbox = Mock(
            return_value=(0, 0, 50, 20)
        )  # (left, top, right, bottom)
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(side_effect=OSError("Font not found"))
        mock_font.load_default = Mock(return_value=mock_font_instance)

        temp_module.Image = mock_image
        temp_module.ImageDraw = mock_draw
        temp_module.ImageFont = mock_font

        from ha_enviro_plus.plugins.temperature_display import TemperatureDisplayPlugin

        plugin = TemperatureDisplayPlugin()
        assert plugin.name() == "Temperature"
        assert plugin.duration() == 5.0
        assert plugin.is_available(mock_sensors_bme280, mock_settings) is True

        result = plugin.render(mock_sensors_bme280, mock_settings)
        assert result == mock_img_instance
        mock_sensors_bme280.temp.assert_called()

    @patch("ha_enviro_plus.plugins.humidity_display.PIL_AVAILABLE", True)
    def test_humidity_display_plugin(self, mock_sensors_bme280, mock_settings):
        """Test HumidityDisplayPlugin."""
        import ha_enviro_plus.plugins.humidity_display as hum_module
        from unittest.mock import MagicMock

        # Setup PIL mocks
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()

        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw_instance.textbbox = Mock(
            return_value=(0, 0, 50, 20)
        )  # (left, top, right, bottom)
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(side_effect=OSError("Font not found"))
        mock_font.load_default = Mock(return_value=mock_font_instance)

        hum_module.Image = mock_image
        hum_module.ImageDraw = mock_draw
        hum_module.ImageFont = mock_font

        from ha_enviro_plus.plugins.humidity_display import HumidityDisplayPlugin

        plugin = HumidityDisplayPlugin()
        assert plugin.name() == "Humidity"
        assert plugin.is_available(mock_sensors_bme280, mock_settings) is True

        result = plugin.render(mock_sensors_bme280, mock_settings)
        assert result == mock_img_instance
        mock_sensors_bme280.humidity.assert_called()

    @patch("ha_enviro_plus.plugins.pressure_display.PIL_AVAILABLE", True)
    def test_pressure_display_plugin(self, mock_sensors_bme280, mock_settings):
        """Test PressureDisplayPlugin."""
        import ha_enviro_plus.plugins.pressure_display as press_module
        from unittest.mock import MagicMock

        # Setup PIL mocks
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()

        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw_instance.textbbox = Mock(
            return_value=(0, 0, 50, 20)
        )  # (left, top, right, bottom)
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(side_effect=OSError("Font not found"))
        mock_font.load_default = Mock(return_value=mock_font_instance)

        press_module.Image = mock_image
        press_module.ImageDraw = mock_draw
        press_module.ImageFont = mock_font

        from ha_enviro_plus.plugins.pressure_display import PressureDisplayPlugin

        plugin = PressureDisplayPlugin()
        assert plugin.name() == "Pressure"
        assert plugin.is_available(mock_sensors_bme280, mock_settings) is True

        result = plugin.render(mock_sensors_bme280, mock_settings)
        assert result == mock_img_instance
        mock_sensors_bme280.pressure.assert_called()

    @patch("ha_enviro_plus.plugins.noise_display.PIL_AVAILABLE", True)
    def test_noise_display_plugin(self, mock_sensors_noise, mock_settings):
        """Test NoiseDisplayPlugin."""
        import ha_enviro_plus.plugins.noise_display as noise_module
        from unittest.mock import MagicMock

        # Setup PIL mocks
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()

        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw_instance.textbbox = Mock(
            return_value=(0, 0, 50, 20)
        )  # (left, top, right, bottom)
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(side_effect=OSError("Font not found"))
        mock_font.load_default = Mock(return_value=mock_font_instance)

        noise_module.Image = mock_image
        noise_module.ImageDraw = mock_draw
        noise_module.ImageFont = mock_font

        from ha_enviro_plus.plugins.noise_display import NoiseDisplayPlugin

        plugin = NoiseDisplayPlugin()
        assert plugin.name() == "Noise"
        assert plugin.is_available(mock_sensors_noise, mock_settings) is True

        result = plugin.render(mock_sensors_noise, mock_settings)
        assert result == mock_img_instance
        mock_sensors_noise.noise_spl_db.assert_called()

    @patch("ha_enviro_plus.plugins.gas_display.PIL_AVAILABLE", True)
    def test_gas_display_plugin(self, mock_sensors_gas, mock_settings):
        """Test GasDisplayPlugin."""
        import ha_enviro_plus.plugins.gas_display as gas_module
        from unittest.mock import MagicMock

        # Setup PIL mocks
        mock_image = MagicMock()
        mock_draw = MagicMock()
        mock_font = MagicMock()

        mock_img_instance = Mock()
        mock_image.new = Mock(return_value=mock_img_instance)
        mock_draw_instance = Mock()
        mock_draw_instance.textbbox = Mock(
            return_value=(0, 0, 50, 20)
        )  # (left, top, right, bottom)
        mock_draw.Draw = Mock(return_value=mock_draw_instance)
        mock_font_instance = Mock()
        mock_font.truetype = Mock(side_effect=OSError("Font not found"))
        mock_font.load_default = Mock(return_value=mock_font_instance)

        gas_module.Image = mock_image
        gas_module.ImageDraw = mock_draw
        gas_module.ImageFont = mock_font

        from ha_enviro_plus.plugins.gas_display import GasDisplayPlugin

        plugin = GasDisplayPlugin()
        assert plugin.name() == "Gas"
        assert plugin.is_available(mock_sensors_gas, mock_settings) is True

        result = plugin.render(mock_sensors_gas, mock_settings)
        assert result == mock_img_instance
        mock_sensors_gas.gas_oxidising.assert_called()
        mock_sensors_gas.gas_reducing.assert_called()
        mock_sensors_gas.gas_nh3.assert_called()

    def test_individual_plugins_not_available(self, mock_settings):
        """Test that plugins return False when sensors are not available."""
        from ha_enviro_plus.plugins.temperature_display import TemperatureDisplayPlugin
        from ha_enviro_plus.plugins.humidity_display import HumidityDisplayPlugin
        from ha_enviro_plus.plugins.pressure_display import PressureDisplayPlugin
        from ha_enviro_plus.plugins.noise_display import NoiseDisplayPlugin
        from ha_enviro_plus.plugins.gas_display import GasDisplayPlugin

        mock_sensors = Mock()
        mock_sensors.has_sensor.return_value = False

        temp_plugin = TemperatureDisplayPlugin()
        assert temp_plugin.is_available(mock_sensors, mock_settings) is False

        hum_plugin = HumidityDisplayPlugin()
        assert hum_plugin.is_available(mock_sensors, mock_settings) is False

        press_plugin = PressureDisplayPlugin()
        assert press_plugin.is_available(mock_sensors, mock_settings) is False

        noise_plugin = NoiseDisplayPlugin()
        assert noise_plugin.is_available(mock_sensors, mock_settings) is False

        gas_plugin = GasDisplayPlugin()
        assert gas_plugin.is_available(mock_sensors, mock_settings) is False
