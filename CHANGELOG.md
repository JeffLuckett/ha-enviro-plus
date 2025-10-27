# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Features
- Dashboard display with temperature, humidity, pressure, and light metrics
- Individual sensor displays with scrolling graphs
- Custom scrolling message display
- Display rotation modes (auto-rotation, manual via proximity sensor tap)
- Plugin architecture for custom display modules
- Noise sensor support with A-weighted dB(A) conversion
- PMS5003 particulate matter sensor support (PM1.0, PM2.5, PM10)

### Improvements
- Enhanced display system with multiple modes
- Error state messaging on LCD for critical issues
- LTR-559 proximity sensor tap detection for display navigation

## [0.2.0] - 2025-01-XX

### Features
- **Boot splash screen** displaying ha-enviro-plus banner on startup
- **Sensor warm-up period** (5 seconds) to eliminate spurious readings
- **ST7735 LCD display integration** with graceful hardware failure handling
- **Configurable display** via DISPLAY_ENABLED environment variable (1=ON, 0=OFF)
- **Fade-out animation** (2 seconds) for smooth display transition

### Technical
- PIL/Pillow integration for image loading and manipulation
- Display hardware abstraction with graceful degradation
- Non-blocking splash screen that doesn't delay sensor initialization

## [0.1.1] - 2025-01-XX

### Features
- **PyPI installation support** - Package now available via `pip install ha-enviro-plus`
- **Enhanced install script** with PyPI-first approach for faster, more reliable installations
- **Test mode** (`--test` flag) for safe installation validation without system changes
- **Improved installation methods** - automatic fallback from PyPI to GitHub releases/branches

### Improvements
- **Installation reliability** - PyPI packages are more stable than git clones
- **Better user experience** - clearer installation options and error messages
- **Enhanced documentation** - comprehensive manual setup guide for PyPI installations

### Technical
- **Dynamic service configuration** - installer adapts to PyPI vs git installations
- **Cross-platform compatibility** - improved script compatibility across systems
- **Release automation** - automated PyPI uploads via GitHub Actions

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
- Hardware tests for real Enviro+ devices