# ha-enviro-plus

**Enviro+ → Home Assistant MQTT Agent**
A lightweight Python agent for publishing Pimoroni Enviro+ sensor data (temperature, humidity, pressure, light, gas, and system metrics) to Home Assistant via MQTT with automatic discovery.

---

## 🚀 Overview

`ha-enviro-plus` turns a Raspberry Pi Zero 2 W (or any Pi running the Enviro+) into a self-contained Home Assistant satellite.

It reads data from:
- **BME280** (temperature, humidity, pressure)
- **LTR559** (ambient light)
- **Gas sensor** (oxidising, reducing, NH₃)
- Optional **sound** and **PMS5003 particulate** sensors
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
- Safe installer/uninstaller with config preservation
- Designed for Pi Zero 2 W + Enviro+ HAT, but works anywhere the libraries do

---

## ⚙️ Quick Install

Run this command **on your Raspberry Pi** (requires `sudo`):

    bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/install.sh)

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
    DEVICE_NAME="Enviro+ Satellite"

---

## 🧰 Uninstall

Remove the agent and optionally keep the config:

    wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/uninstall.sh | sudo bash

The uninstaller:
- Stops and disables the systemd service
- Removes `/opt/ha-enviro-plus` and log files
- Prompts to preserve `/etc/default/ha-enviro-plus`

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

The project aims for >90% test coverage. Coverage reports are generated in HTML format and available in the `htmlcov/` directory after running tests with coverage.

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
- Sound and particulate sensors are optional; the agent functions fully without them.

---

## 🧪 Version

**v0.1.0 — Experimental pre-release**

This version:
- Establishes the base framework
- Implements all major sensors and MQTT features
- Adds host telemetry and Home Assistant control entities

Next milestone:
- Versioned installer (`--version` flag)
- Web-based calibration adjustment
- Optional local REST API

---

## 📜 License

MIT © 2025 Jeff Luckett