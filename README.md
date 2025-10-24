# ha-enviro-plus

[![Tests](https://github.com/JeffLuckett/ha-enviro-plus/workflows/Tests/badge.svg)](https://github.com/JeffLuckett/ha-enviro-plus/actions)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Latest Release](https://img.shields.io/github/v/release/JeffLuckett/ha-enviro-plus)](https://github.com/JeffLuckett/ha-enviro-plus/releases/latest)

**Enviro+ → Home Assistant MQTT Agent**
A lightweight Python agent for publishing Pimoroni Enviro+ sensor data (temperature, humidity, pressure, light, gas, and system metrics) to Home Assistant via MQTT with automatic discovery.

---

## 🚀 Overview

`ha-enviro-plus` turns a Raspberry Pi Zero 2 W (or any Pi running the Enviro+) into a self-contained Home Assistant satellite.

It reads data from:
- **BME280** (temperature, humidity, pressure)
- **LTR559** (ambient light)
- **Gas sensor** (oxidising, reducing, NH₃)
and publishes them to Home Assistant over MQTT using native **HA Discovery**.

Additional system telemetry is included:
- CPU temperature, load, and uptime
- Memory and disk utilisation
- Network info and hostname
- Service availability and reboot/restart controls

---

## 🧩 Features

- Plug-and-play Home Assistant discovery (no YAML setup)
- Fast, configurable polling (default 2 s)
- On-device temperature / humidity calibration offsets
- CPU temperature compensation for accurate readings (higher number lowers temp. output)
- Host metrics: uptime, CPU temp, load, RAM, disk
- MQTT availability and discovery payloads
- Home Assistant controls:
    - Reboot device
    - Restart service
    - Shutdown
    - Apply calibration offsets
    - Adjust CPU temperature compensation factor
- Structured logging (rotation-friendly)
- Graceful shutdown handling (SIGTERM/SIGINT)
- Startup configuration validation
- Safe installer/uninstaller with config preservation
- Versioned installation support (`--release`, `--branch` flags)
- Designed and tested with a Raspberry Pi Zero 2 W + Enviro+ HAT. Also supports the original Enviro HAT (fewer sensors) and runs on any hardware that supports these devices and the necessary libraries. (Testers welcome!)

---

## ⚙️ Quick Install

Run this command **on your Raspberry Pi**:

    bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh)

**Installation Options:**
- Install latest stable: `./install.sh`
- Install specific version: `./install.sh --release v0.1.0`
- Install from branch: `./install.sh --branch feature-branch`
- Show installer version: `./install.sh --version`

The installer will:
- Create `/opt/ha-enviro-plus` and a virtualenv
- Prompt for MQTT host, username, and password
- Prompt for poll interval and temperature / humidity offsets
- Install dependencies and a systemd service
- Start the agent immediately

Home Assistant should auto-discover the sensors within a few seconds.

---

## 🔧 Configuration

Configuration lives at:

    /etc/default/ha-enviro-plus

Edit values safely, then restart the service:

    sudo systemctl restart ha-enviro-plus

**Example config:**

    MQTT_HOST=homeassistant.local
    MQTT_PORT=1883
    MQTT_USER=enviro
    MQTT_PASS=<use_your_own>
    MQTT_DISCOVERY_PREFIX=homeassistant
    POLL_SEC=2
    TEMP_OFFSET=0.0
    HUM_OFFSET=0.0
    CPU_TEMP_FACTOR=1.8

---

## 🧰 Uninstall

Remove the agent and optionally keep the config:

    bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/uninstall.sh)

The uninstaller:
- Stops and disables the systemd service
- Removes `/opt/ha-enviro-plus`, log files, and settings directory
- Prompts to preserve `/etc/default/ha-enviro-plus` (interactive mode)
- Works in both interactive and non-interactive modes

---

## 🧪 Testing

This project includes comprehensive tests to ensure reliability and maintainability.

### Test Structure

- **Unit Tests**: Test individual components with mocked hardware
- **Integration Tests**: Test MQTT functionality and end-to-end workflows
- **Hardware Tests**: Test with real Enviro+ sensors (optional, requires hardware)

### Running Tests

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests (excluding hardware)
pytest tests/ -m "not hardware"

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run hardware tests (requires Enviro+ hardware)
pytest tests/hardware/

# Run with coverage
pytest tests/ --cov=ha_enviro_plus --cov-report=html
```

### Test Coverage

The project aims for >=75% test coverage. Coverage reports are generated in HTML format and available in the `htmlcov/` directory after running tests with coverage.

### Continuous Integration

Tests run automatically on every push and pull request via GitHub Actions, testing against Python 3.9, 3.10, 3.11, and 3.12.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/JeffLuckett/ha-enviro-plus.git
cd ha-enviro-plus

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -m "not hardware"
```

---

- **Temperature Compensation**: The temperature sensor runs warm due to CPU proximity. The agent now includes automatic CPU temperature compensation using a configurable factor (default 1.8). You can adjust this factor via Home Assistant or the config file for optimal accuracy.
- **Calibration**: Use the `TEMP_OFFSET` for fine-tuning individual installations, and `CPU_TEMP_FACTOR` to adjust the CPU compensation algorithm.
- Humidity readings depend on temperature calibration — adjust both together.
- Sound and particulate sensors are planned for v0.2.0; the agent functions fully without them.

---

## 🧪 Version

**v0.1.0 — Stable Release**

This version includes:
- Complete Enviro+ sensor support (BME280, LTR559, Gas sensors)
- MQTT integration with Home Assistant discovery
- System telemetry (CPU temperature, load, memory, disk)
- Home Assistant control entities (reboot, restart, shutdown)
- Configurable polling intervals and calibration offsets
- CPU temperature compensation for accurate readings
- Graceful shutdown handling and configuration validation
- Versioned installation support
- Comprehensive test suite with >=75% coverage

**Next milestone (v0.2.0):**
- Noise sensor (microphone to dB conversion)
- PMS5003 particulate sensor support
- 0.96" LCD display system with plugin architecture

---

## 📜 License

MIT © 2025 Jeff Luckett