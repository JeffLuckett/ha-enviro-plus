# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Features
- (Features will be added here as they are implemented)

## [0.2.0] - 2025-01-XX

### Features
- **Noise sensor** with A-weighted dB(A) conversion for accurate sound pressure level measurements
- **Proximity sensor** support using LTR559 for tap detection and display navigation
- **Individual sensor display screens** - dedicated screens for Temperature, Humidity, Pressure, Noise, and Gas sensors
- **Auto-rotating display** - configured screens automatically rotate with configurable timing
- **Tap navigation** - tap proximity sensor to manually page through display screens
- **Display plugin architecture** for custom display modules with auto-discovery
- **Boot splash screen** with fade-out animation
- **Error state messaging** on LCD for critical issues
- **Sensor display plugin** with icon support and unit conversion (metric/imperial)
- **Non-blocking display system** with threaded display manager

### Technical
- Noise sensor implementation with `sounddevice` and `scipy` for A-weighting filter
- Proximity sensor tap detection with debouncing logic
- Individual display plugins: TemperatureDisplayPlugin, HumidityDisplayPlugin, PressureDisplayPlugin, NoiseDisplayPlugin, GasDisplayPlugin
- Display plugin system with auto-discovery
- Plugin rendering with error handling
- Thread-safe display queue system
- Graceful display hardware degradation
- Graceful noise sensor degradation (works without microphone)

## [0.1.1] - 2025-01-XX

### Features
- **PyPI installation support** - Package now available via `pip install ha-enviro-plus`
- **Enhanced install script** with PyPI-first approach for faster, more reliable installations
- **Test mode** (`--test` flag) for safe installation validation without system changes
- **Improved installation methods** - automatic fallback from PyPI to GitHub releases/branches
- **Boot splash screen** displaying ha-enviro-plus banner on startup
- **Sensor warm-up period** (2 seconds default, configurable via SENSOR_WARMUP_SEC) to eliminate spurious readings
- **ST7735 LCD display integration** with graceful hardware failure handling
- **Configurable display** via DISPLAY_ENABLED environment variable (1=ON, 0=OFF)
- **Fade-out animation** (2 seconds) for smooth display transition
- **Display plugin architecture** with auto-discovery and sensor display plugin

### Improvements
- **Installation reliability** - PyPI packages are more stable than git clones
- **Better user experience** - clearer installation options and error messages
- **Enhanced documentation** - comprehensive manual setup guide for PyPI installations

### Technical
- **Dynamic service configuration** - installer adapts to PyPI vs git installations
- **Cross-platform compatibility** - improved script compatibility across systems
- **Release automation** - automated PyPI uploads via GitHub Actions
- PIL/Pillow integration for image loading and manipulation
- Display hardware abstraction with graceful degradation
- Non-blocking splash screen that doesn't delay sensor initialization

## [0.1.0] - 2025-01-XX

### Features
- Initial release with Enviro+ sensor support
- MQTT integration with Home Assistant discovery
- Temperature, humidity, pressure, light, and gas sensor readings
- System telemetry (CPU temperature, load, memory, disk)
- Home Assistant control entities (reboot, restart, shutdown)
- Configurable polling intervals and calibration offsets
- CPU temperature compensation for accurate readings
- Comprehensive test suite with >=75% coverage covering all critical paths and edge cases

### Documentation
- Complete README with installation and configuration instructions
- Contributing guidelines and development setup
- API documentation with comprehensive docstrings

### CI/CD
- GitHub Actions workflow for testing across Python 3.9-3.12
- Automated linting, formatting, and type checking
- Coverage reporting with GitHub Actions artifacts
- Security scanning with Safety and Bandit