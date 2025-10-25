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

### Recommended: Install Script (PyPI-first)

Run this command **on your Raspberry Pi**:

    bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh)

**Installation Methods:**
- **Latest stable (PyPI)**: `./install.sh` *(default)*
- **Specific version (PyPI)**: `./install.sh --release v0.1.1`
- **Development branch**: `./install.sh --branch feature-branch`
- **Test mode**: `./install.sh --test` *(validate without changes)*
- **Show installer info**: `./install.sh --version`

The installer automatically:
- **Prioritizes PyPI** for stable releases (faster, more reliable)
- **Falls back to GitHub** for development branches or specific versions
- Creates `/opt/ha-enviro-plus` and installs dependencies
- Prompts for MQTT host, username, and password
- Prompts for poll interval and temperature / humidity offsets
- Installs and starts the systemd service

### Alternative: Direct PyPI Install

For advanced users who prefer manual installation:

    pip install ha-enviro-plus

Then manually configure and start the service (see [Manual Setup](#manual-setup)).

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

## 🔧 Manual Setup

If you installed via `pip install ha-enviro-plus`, you'll need to manually configure the service:

### 1. Create Configuration File

    sudo mkdir -p /etc/default
    sudo tee /etc/default/ha-enviro-plus > /dev/null <<EOF
    MQTT_HOST=homeassistant.local
    MQTT_PORT=1883
    MQTT_USER=enviro
    MQTT_PASS=<use_your_own>
    MQTT_DISCOVERY_PREFIX=homeassistant
    POLL_SEC=2
    TEMP_OFFSET=0.0
    HUM_OFFSET=0.0
    CPU_TEMP_FACTOR=1.8
    EOF

### 2. Create Settings Directory

    sudo mkdir -p /var/lib/ha-enviro-plus
    sudo chown pi:pi /var/lib/ha-enviro-plus

### 3. Install Systemd Service

    sudo tee /etc/systemd/system/ha-enviro-plus.service > /dev/null <<EOF
    [Unit]
    Description=Enviro+ → Home Assistant MQTT Agent
    After=network-online.target
    Wants=network-online.target

    [Service]
    Type=simple
    EnvironmentFile=/etc/default/ha-enviro-plus
    WorkingDirectory=/opt/ha-enviro-plus
    ExecStart=python3 -m ha_enviro_plus.agent
    Restart=on-failure
    RestartSec=5
    StandardOutput=journal
    StandardError=journal

    [Install]
    WantedBy=multi-user.target
    EOF

### 4. Start Service

    sudo systemctl daemon-reload
    sudo systemctl enable ha-enviro-plus.service
    sudo systemctl start ha-enviro-plus.service

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

# Option 1: Install in development mode (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .

# Option 2: Install from PyPI for testing
pip install ha-enviro-plus

# Option 3: Use the install script for development
./scripts/install.sh --branch main

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

**v0.1.1 — Stable Release**

This version includes:
- Complete Enviro+ sensor support (BME280, LTR559, Gas sensors)
- MQTT integration with Home Assistant discovery
- System telemetry (CPU temperature, load, memory, disk)
- Home Assistant control entities (reboot, restart, shutdown)
- Configurable polling intervals and calibration offsets
- CPU temperature compensation for accurate readings
- Graceful shutdown handling and configuration validation
- **PyPI installation support** (pip install ha-enviro-plus)
- **Enhanced install script** with PyPI-first approach
- **Test mode** for safe installation validation
- Comprehensive test suite with >=75% coverage

**Next milestone (v0.2.0):**
- Noise sensor (microphone to dB conversion)
- PMS5003 particulate sensor support
- 0.96" LCD display system with plugin architecture

---

## 📜 License

MIT © 2025 Jeff Luckett