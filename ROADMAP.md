# Roadmap

This document outlines the planned development roadmap for ha-enviro-plus, including upcoming features, improvements, and long-term goals.

## Version 0.1.1 (Current Release)

**Status**: ✅ Released

### Core Features
- ✅ Enviro+ sensor support (BME280, LTR559, Gas sensors, [PM sensor pending])
- ✅ MQTT integration with Home Assistant discovery
- ✅ System telemetry (CPU temperature, load, memory, disk)
- ✅ Home Assistant control entities (reboot, restart, shutdown)
- ✅ Configurable polling intervals and calibration offsets
- ✅ CPU temperature compensation for accurate readings
- ✅ Comprehensive test suite
- ✅ Graceful sensor degradation (hardware failures don't crash the app)
- ✅ Graceful shutdown handling (SIGTERM/SIGINT)
- ✅ Configuration validation on startup

### Documentation & Process
- ✅ Complete README with installation and configuration instructions
- ✅ Contributing guidelines and development setup
- ✅ API documentation with comprehensive docstrings
- ✅ Security policy and responsible disclosure guidelines
- ✅ Code of conduct
- ✅ Automated dependency updates (Dependabot)
- ✅ Cross-platform compatibility fixes

## Version 0.2.0 (Current Release)

**Status**: ✅ Released

### Core Features
- ✅ Enviro+ sensor support (BME280, LTR559, Gas sensors)
- ✅ MQTT integration with Home Assistant discovery
- ✅ System telemetry (CPU temperature, load, memory, disk)
- ✅ Home Assistant control entities (reboot, restart, shutdown)
- ✅ Configurable polling intervals and calibration offsets
- ✅ CPU temperature compensation for accurate readings
- ✅ Comprehensive test suite
- ✅ Graceful sensor degradation (hardware failures don't crash the app)
- ✅ Graceful shutdown handling (SIGTERM/SIGINT)
- ✅ Configuration validation on startup

### New Sensor Support

#### Noise Sensor (Microphone)
- ✅ A-weighted dB calculation for accurate sound pressure levels
- ✅ Streaming approach to handle microphone startup "plop"
- ✅ Configurable sampling rate and averaging window
- ✅ Graceful degradation if microphone hardware not available
- ✅ Sensors: `noise/spl_db` (dB(A)) and `noise/spl_raw` (raw RMS)

#### Proximity Sensor
- ✅ LTR559 proximity sensor support
- ✅ Tap detection for display navigation
- ✅ Debouncing logic for reliable tap detection

### LCD Display System

#### Display Features
- ✅ Boot splash screen with fade-out animation
- ✅ Individual sensor display screens (Temperature, Humidity, Pressure, Noise, Gas)
- ✅ Auto-rotating display with configurable timing
- ✅ Tap navigation using proximity sensor for manual screen paging
- ✅ Display plugin architecture with auto-discovery
- ✅ Error state messaging on LCD for critical issues
- ✅ Non-blocking display system with threaded display manager

#### Plugin Architecture
- ✅ Base Class: `DisplayPlugin` abstract class
- ✅ Auto-discovery: Automatic plugin loading from `ha_enviro_plus/plugins/`
- ✅ Individual plugins: TemperatureDisplayPlugin, HumidityDisplayPlugin, PressureDisplayPlugin, NoiseDisplayPlugin, GasDisplayPlugin
- ✅ Sensor display plugin with icon support and unit conversion (metric/imperial)

### Documentation & Process
- ✅ Complete README with installation and configuration instructions
- ✅ Contributing guidelines and development setup
- ✅ API documentation with comprehensive docstrings
- ✅ Security policy and responsible disclosure guidelines
- ✅ Code of conduct
- ✅ Automated dependency updates (Dependabot)
- ✅ Cross-platform compatibility fixes

## Version 0.3.0 (Future)

**Status**: 💭 Conceptual

### Enhanced Display Features
- Web-based calibration interface
- Remote display control via web UI
- Custom display themes and layouts
- Historical data visualization
- Alert thresholds and notifications

### New Sensor Support

#### PMS5003 Particulate Sensor
- **Features**:
  - PM1.0, PM2.5, and PM10 readings
  - Serial communication with error handling
  - Optional sensor detection (add-on device)
  - Graceful fallback if sensor not present
- **Sensors**:
  - `particulate/pm1` - PM1.0 (µg/m³)
  - `particulate/pm25` - PM2.5 (µg/m³)
  - `particulate/pm10` - PM10 (µg/m³)

### Advanced Sensor Features
- Sensor health monitoring and alerts
- Automatic calibration routines
- Data logging and export
- Integration with external weather services
- Multi-device support and coordination

### Performance & Reliability
- Configurable publish rates (separate from poll rates)
- Only publish changed values (with threshold)
- Batch MQTT publishes
- Circuit breaker patterns for unreliable sensors
- Retry logic with exponential backoff

### Developer Experience
- Plugin development tools and templates
- Enhanced debugging and diagnostics
- Performance profiling tools
- Docker support for development

## Version 1.0.0 (Stable Release)

**Status**: 🎯 Long-term Goal

### Production Readiness
- Full backward compatibility guarantees
- Long-term support (LTS) commitment
- Comprehensive documentation and tutorials
- Community plugin marketplace
- Professional support options

### Enterprise Features
- Multi-tenant support
- Advanced security features
- Audit logging and compliance
- Integration with enterprise monitoring systems
- Professional deployment tools

## Contributing to the Roadmap

We welcome community input on the roadmap! Please:

1. **Feature Requests**: Use [GitHub Issues](https://github.com/JeffLuckett/ha-enviro-plus/issues) with the `enhancement` label
2. **Discussion**: Use [GitHub Discussions](https://github.com/JeffLuckett/ha-enviro-plus/discussions) for broader feature discussions
3. **Contributions**: Submit pull requests for features you'd like to implement


## Dependencies & Requirements

### v0.2.0 Dependencies
- ✅ `sounddevice>=0.4.6` (for noise sensor)
- ✅ `scipy>=1.9.0` (for A-weighted filtering)
- ✅ `pillow>=10.0.0` (for display rendering)
- Additional hardware: Microphone (optional), LCD display (optional)

### Hardware Compatibility
- **Primary**: Raspberry Pi Zero 2 W + Enviro+ HAT
- **Secondary**: Any Raspberry Pi with Enviro+ compatibility

## Success Metrics

### v0.1.0 Success Criteria
- ✅ All critical issues resolved
- ✅ Release workflow successfully creates GitHub release
- ✅ Install script works on fresh Raspberry Pi OS
- ✅ All tests pass in CI/CD
- ✅ Documentation is accurate and complete

### v0.2.0 Success Criteria
- ✅ Noise sensor provides believable dB(A) readings (within realistic range, with calibration options for accuracy)
- ✅ Display system supports all planned modes (individual sensor screens, auto-rotation, tap navigation)
- ✅ Plugin system allows user extensions
- ✅ All new features have >=75% test coverage
- ✅ Documentation includes setup guides and examples
- ✅ Backward compatible with v0.1.0 configurations

---

*This roadmap is a living document and will be updated as development progresses and community feedback is incorporated.*
