# Roadmap

This document outlines the planned development roadmap for ha-enviro-plus, including upcoming features, improvements, and long-term goals.

## Version 0.1.0 (Current Release)

**Status**: ✅ Ready for Release

### Core Features
- ✅ Enviro+ sensor support (BME280, LTR559, Gas sensors)
- ✅ MQTT integration with Home Assistant discovery
- ✅ System telemetry (CPU temperature, load, memory, disk)
- ✅ Home Assistant control entities (reboot, restart, shutdown)
- ✅ Configurable polling intervals and calibration offsets
- ✅ CPU temperature compensation for accurate readings
- ✅ Comprehensive test suite with >90% coverage
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

## Version 0.2.0 (Next Major Release)

**Status**: 🚧 In Planning

### New Sensor Support

#### Noise Sensor (Microphone)
- **Reference**: [Northcliff SPL Monitor](https://github.com/roscoe81/northcliff_spl_monitor)
- **Features**:
  - A-weighted dB calculation for accurate sound pressure levels
  - Calibration parameters for microphone sensitivity
  - Streaming approach to handle microphone startup "plop"
  - Configurable sampling rate and averaging window
  - Graceful degradation if microphone hardware not available
- **Sensors**:
  - `noise/spl_db` - Sound Pressure Level in dB(A)
  - `noise/spl_raw` - Raw sound level
  - Possibly frequency band analysis

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

### LCD Display System

#### Hardware Support
- **Display**: 0.96" IPS Color LCD (160x80 pixels)
- **Control**: LTR-559 proximity sensor for tap detection

#### Display Modes
- `off` - Display disabled
- `splash` - Boot splash screen with .gif animation
- `dashboard` - Multi-sensor summary layout
- `temp` - Temperature scrolling graph
- `humidity` - Humidity scrolling graph
- `pressure` - Pressure scrolling graph
- `lux` - Light level scrolling graph
- `gas` - Gas sensor readings
- `noise` - Sound level graph (if available)
- `particulate` - PM readings (if available)
- `message` - Scrolling custom message
- `auto` - Rotate through all enabled displays
- `custom_*` - User-provided plugins

#### Plugin Architecture
- **Base Class**: `BaseDisplay` abstract class
- **Plugin Directory**: `/opt/ha-enviro-plus/displays/custom/`
- **Auto-discovery**: Automatic plugin loading
- **Interface**: Simple render() method returning PIL Image

#### MQTT Controls
- `display/mode` - Set specific display mode
- `display/rotation` - Enable/disable auto-rotation
- `display/interval` - Set rotation interval (seconds)
- `display/message` - Set custom message text
- `display/message_colors` - Set text/background colors

#### Error State Messaging
- **Critical Errors**: Take over display for important issues
- **Error Types**: WiFi loss, MQTT connection failure, misconfiguration
- **Access Method**: Double-tap proximity sensor for error state access

## Version 0.3.0 (Future)

**Status**: 💭 Conceptual

### Enhanced Display Features
- Web-based calibration interface
- Remote display control via web UI
- Custom display themes and layouts
- Historical data visualization
- Alert thresholds and notifications

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
- Automated testing with real hardware
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

## Release Schedule

- **v0.1.0**: January 2025 (Ready for release)
- **v0.2.0**: Q2 2025 (Target: April-June)
- **v0.3.0**: Q4 2025 (Target: October-December)
- **v1.0.0**: 2026 (Long-term goal)

*Note: Release dates are estimates and may change based on development progress and community feedback.*

## Dependencies & Requirements

### v0.2.0 Dependencies
- `sounddevice==0.3.15` (for noise sensor)
- `scipy` (for A-weighted filtering)
- `waveform_analysis` (for advanced audio processing)
- PIL/Pillow (for display rendering)
- Additional hardware: Microphone, PMS5003 sensor, LCD display

### Hardware Compatibility
- **Primary**: Raspberry Pi Zero 2 W + Enviro+ HAT
- **Secondary**: Any Raspberry Pi with Enviro+ compatibility
- **Optional**: PMS5003 particulate sensor, I2S microphone, 0.96" LCD

## Success Metrics

### v0.1.0 Success Criteria
- ✅ All critical issues resolved
- ✅ Release workflow successfully creates GitHub release
- ✅ Install script works on fresh Raspberry Pi OS
- ✅ All tests pass in CI/CD
- ✅ Documentation is accurate and complete

### v0.2.0 Success Criteria
- ✅ Noise sensor provides believable dB(A) readings (within realistic range, with calibration options for accuracy)
- ✅ PM sensor works when present, gracefully disabled when absent
- ✅ Display system supports all planned modes
- ✅ Plugin system allows user extensions
- ✅ All new features have >=75% test coverage
- ✅ Documentation includes setup guides and examples
- ✅ Backward compatible with v0.1.0 configurations

---

*This roadmap is a living document and will be updated as development progresses and community feedback is incorporated.*
