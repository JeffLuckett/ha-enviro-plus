"""Shared pytest fixtures for ha-enviro-plus tests."""

import pytest
from unittest.mock import Mock

# Mock hardware modules at import time
import sys
from unittest.mock import MagicMock

# Mock the hardware modules that can't be imported on macOS
sys.modules["bme280"] = MagicMock()
sys.modules["ltr559"] = MagicMock()
sys.modules["enviroplus"] = MagicMock()
sys.modules["enviroplus.gas"] = MagicMock()
sys.modules["gpiod"] = MagicMock()
sys.modules["spidev"] = MagicMock()


@pytest.fixture
def mock_bme280(mocker):
    """Mock BME280 sensor with realistic data."""
    mock = mocker.patch("ha_enviro_plus.sensors.BME280")
    instance = Mock()
    instance.get_temperature.return_value = 25.5
    instance.get_humidity.return_value = 45.0
    instance.get_pressure.return_value = 1013.25
    mock.return_value = instance
    return instance


@pytest.fixture
def mock_ltr559(mocker):
    """Mock LTR559 light sensor with realistic data."""
    mock = mocker.patch("ha_enviro_plus.sensors.LTR559")
    instance = Mock()
    instance.get_lux.return_value = 150.0
    mock.return_value = instance
    return instance


@pytest.fixture
def mock_gas_sensor(mocker):
    """Mock gas sensor with realistic data."""
    mock = mocker.patch("ha_enviro_plus.sensors.gas.read_all")

    # Create mock gas data object
    gas_data = Mock()
    gas_data.oxidising = 50000.0  # 50kΩ
    gas_data.reducing = 30000.0  # 30kΩ
    gas_data.nh3 = 40000.0  # 40kΩ

    mock.return_value = gas_data
    return gas_data


@pytest.fixture
def mock_subprocess(mocker):
    """Mock subprocess for CPU temperature reading."""
    mock = mocker.patch("ha_enviro_plus.sensors.subprocess.check_output")
    mock.return_value = "temp=42.0'C\n"  # Return string, not bytes
    return mock


@pytest.fixture
def mock_device_id(mocker):
    """Mock device ID and related topic variables for consistent testing."""
    mocker.patch("ha_enviro_plus.agent.device_id", "enviro_raspberrypi")
    mocker.patch("ha_enviro_plus.agent.root", "enviro_raspberrypi")
    mocker.patch("ha_enviro_plus.agent.avail_t", "enviro_raspberrypi/status")
    mocker.patch("ha_enviro_plus.agent.cmd_t", "enviro_raspberrypi/cmd")
    mocker.patch("ha_enviro_plus.agent.set_t", "enviro_raspberrypi/set/+")
    return "enviro_raspberrypi"


@pytest.fixture
def mock_logger(mocker):
    """Mock logger for testing."""
    mock = mocker.patch("ha_enviro_plus.sensors.logging.getLogger")
    logger = Mock()
    mock.return_value = logger
    return logger


@pytest.fixture
def mock_mqtt_client(mocker):
    """Mock MQTT client for testing."""
    mock = mocker.patch("ha_enviro_plus.agent.mqtt.Client")
    client = Mock()
    mock.return_value = client
    return client


@pytest.fixture
def mock_psutil(mocker):
    """Mock psutil for system metrics."""
    mock_vm = mocker.patch("ha_enviro_plus.agent.psutil.virtual_memory")
    vm = Mock()
    vm.percent = 45.2
    vm.total = 8 * 1024 * 1024 * 1024  # 8GB
    mock_vm.return_value = vm

    mock_cpu = mocker.patch("ha_enviro_plus.agent.psutil.cpu_percent")
    mock_cpu.return_value = 12.5

    return {"vm": vm, "cpu": mock_cpu}


@pytest.fixture
def mock_file_operations(mocker):
    """Mock file operations for system info functions."""

    def mock_open_side_effect(filename, mode="r", **kwargs):
        if filename == "/proc/uptime":
            return mocker.mock_open(read_data="12345.67 98765.43")()
        elif filename == "/proc/device-tree/model":
            return mocker.mock_open(read_data=b"Raspberry Pi Zero 2 W Rev 1.0\x00")()
        elif filename == "/proc/cpuinfo":
            cpuinfo_content = """processor	: 0
model name	: ARMv7 Processor rev 3 (v7l)
Serial		: 1234567890abcdef
"""
            return mocker.mock_open(read_data=cpuinfo_content)()
        elif filename == "/etc/os-release":
            os_release_content = """PRETTY_NAME="Raspberry Pi OS Lite (64-bit)"
NAME="Raspberry Pi OS Lite"
VERSION_ID="12"
"""
            return mocker.mock_open(read_data=os_release_content)()
        elif filename == "/System/Library/CoreServices/SystemVersion.plist":
            # macOS fallback
            raise FileNotFoundError(
                "No such file or directory: '/System/Library/CoreServices/SystemVersion.plist'"
            )
        else:
            raise FileNotFoundError(f"No mock for {filename}")

    def mock_exists_side_effect(path):
        if path == "/etc/os-release":
            return True
        return True

    mocker.patch("builtins.open", side_effect=mock_open_side_effect)
    mocker.patch("os.path.exists", side_effect=mock_exists_side_effect)

    return {
        "uptime": "12345.67 98765.43",
        "model": "Raspberry Pi Zero 2 W Rev 1.0",
        "cpuinfo": "Serial\t\t: 1234567890abcdef",
        "os_release": 'PRETTY_NAME="Raspberry Pi OS Lite (64-bit)"',
    }


@pytest.fixture
def mock_file_operations_no_os_release(mocker):
    """Mock file operations without /etc/os-release."""

    def mock_open_side_effect(filename, mode="r", **kwargs):
        if filename == "/proc/uptime":
            return mocker.mock_open(read_data="12345.67 98765.43")()
        elif filename == "/proc/device-tree/model":
            return mocker.mock_open(read_data=b"Raspberry Pi Zero 2 W Rev 1.0\x00")()
        elif filename == "/proc/cpuinfo":
            cpuinfo_content = """processor	: 0
model name	: ARMv7 Processor rev 3 (v7l)
Serial		: 1234567890abcdef
"""
            return mocker.mock_open(read_data=cpuinfo_content)()
        elif filename == "/etc/os-release":
            raise FileNotFoundError("No such file or directory: '/etc/os-release'")
        else:
            raise FileNotFoundError(f"No mock for {filename}")

    def mock_exists_side_effect(path):
        if path == "/etc/os-release":
            return False
        return True

    mocker.patch("builtins.open", side_effect=mock_open_side_effect)
    mocker.patch("os.path.exists", side_effect=mock_exists_side_effect)

    return {
        "uptime": "12345.67 98765.43",
        "model": "Raspberry Pi Zero 2 W Rev 1.0",
        "cpuinfo": "Serial\t\t: 1234567890abcdef",
    }


@pytest.fixture
def mock_network_interfaces(mocker):
    """Mock network interface detection."""
    mock_addrs = {
        "wlan0": [
            Mock(family=Mock(name="AF_INET"), address="192.168.1.100"),
            Mock(family=Mock(name="AF_INET6"), address="fe80::1234"),
        ],
        "eth0": [Mock(family=Mock(name="AF_INET"), address="10.0.0.5")],
        "lo": [Mock(family=Mock(name="AF_INET"), address="127.0.0.1")],
    }

    # Fix the family.name attribute
    for interface_addrs in mock_addrs.values():
        for addr in interface_addrs:
            addr.family.name = "AF_INET"

    mock_psutil = mocker.patch("ha_enviro_plus.agent.psutil.net_if_addrs")
    mock_psutil.return_value = mock_addrs

    return mock_addrs


@pytest.fixture
def sample_sensor_data():
    """Sample sensor data for testing."""
    return {
        "temperature": 25.5,
        "temperature_raw": 25.5,
        "humidity": 45.0,
        "humidity_raw": 45.0,
        "pressure": 1013.25,
        "pressure_raw": 1013.25,
        "lux": 150.0,
        "lux_raw": 150.0,
        "gas_oxidising": 50.0,
        "gas_oxidising_raw": 50000.0,
        "gas_reducing": 30.0,
        "gas_reducing_raw": 30000.0,
        "gas_nh3": 40.0,
        "gas_nh3_raw": 40000.0,
    }


@pytest.fixture
def sample_system_data():
    """Sample system data for testing."""
    return {
        "cpu_temp": 42.0,
        "cpu_usage": 12.5,
        "mem_usage": 45.2,
        "mem_size": 8.0,
        "uptime": 12345,
        "hostname": "raspberrypi",
        "network": "192.168.1.100",
        "os_release": "Raspberry Pi OS Lite (64-bit)",
    }


def hardware_available():
    """Check if hardware is available for testing."""
    try:
        from bme280 import BME280

        BME280(i2c_addr=0x76)
        return True
    except Exception:
        return False


@pytest.fixture
def hardware_skipif():
    """Skipif marker for hardware tests."""
    return pytest.mark.skipif(not hardware_available(), reason="Hardware not detected")


@pytest.fixture
def mock_env_vars(mocker):
    """Mock environment variables."""
    env_vars = {
        "MQTT_HOST": "test-broker.local",
        "MQTT_PORT": "1883",
        "MQTT_USER": "testuser",
        "MQTT_PASS": "testpass",
        "MQTT_DISCOVERY_PREFIX": "homeassistant",
        "POLL_SEC": "2",
        "TEMP_OFFSET": "0.0",
        "HUM_OFFSET": "0.0",
        "CPU_TEMP_FACTOR": "1.8",
        "LOG_TO_FILE": "0",
    }

    mocker.patch.dict("os.environ", env_vars)
    return env_vars


@pytest.fixture
def mock_socket(mocker):
    """Mock socket operations."""
    mock_gethostname = mocker.patch("ha_enviro_plus.agent.socket.gethostname")
    mock_gethostname.return_value = "raspberrypi"
    return mock_gethostname


@pytest.fixture
def mock_platform(mocker):
    """Mock platform operations."""
    mock_platform = mocker.patch("ha_enviro_plus.agent.platform.platform")
    mock_platform.return_value = "Linux-5.15.0-rpi4-aarch64-with-glibc2.31"
    return mock_platform
