"""Unit tests for ha_enviro_plus.system_info module."""

import pytest
from unittest.mock import patch, mock_open, MagicMock

from ha_enviro_plus.system_info import (
    get_mac_address,
    get_serial,
    get_device_id,
    get_ipv4_prefer_wlan0,
    get_uptime_seconds,
    get_model,
    get_os_release,
    get_hostname,
    get_device_info,
)


class TestSystemInfo:
    """Test system information functions."""

    @patch("ha_enviro_plus.system_info.psutil.net_if_addrs")
    def test_get_mac_address_wlan0(self, mock_net_if_addrs):
        """Test getting MAC address from wlan0."""
        mock_addr = MagicMock()
        mock_addr.address = "aa:bb:cc:dd:ee:ff"
        mock_net_if_addrs.return_value = {"wlan0": [mock_addr]}
        result = get_mac_address()
        assert result == "aa:bb:cc:dd:ee:ff"

    @patch("ha_enviro_plus.system_info.psutil.net_if_addrs")
    def test_get_mac_address_fallback(self, mock_net_if_addrs):
        """Test MAC address fallback to eth0."""
        mock_addr = MagicMock()
        mock_addr.address = "11:22:33:44:55:66"
        mock_net_if_addrs.return_value = {"eth0": [mock_addr]}
        result = get_mac_address()
        assert result == "11:22:33:44:55:66"

    @patch("builtins.open", new_callable=mock_open, read_data="Serial\t\t: 1234567890abcdef\n")
    def test_get_serial(self, mock_file):
        """Test getting serial number."""
        result = get_serial()
        assert result == "1234567890abcdef"

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_serial_not_found(self, mock_file):
        """Test getting serial when file not found."""
        result = get_serial()
        assert result == "unknown"

    @patch("ha_enviro_plus.system_info.get_serial")
    def test_get_device_id_from_serial(self, mock_get_serial):
        """Test device ID from serial number."""
        mock_get_serial.return_value = "1234567890abcdef"
        result = get_device_id()
        assert result == "enviro_1234567890abcdef"

    @patch("ha_enviro_plus.system_info.get_serial")
    @patch("ha_enviro_plus.system_info.socket.gethostname")
    def test_get_device_id_from_hostname(self, mock_hostname, mock_get_serial):
        """Test device ID fallback to hostname."""
        mock_get_serial.return_value = "unknown"
        mock_hostname.return_value = "raspberry-pi"
        result = get_device_id()
        assert result == "enviro_raspberrypi"

    @patch("ha_enviro_plus.system_info.psutil.net_if_addrs")
    def test_get_ipv4_prefer_wlan0(self, mock_net_if_addrs):
        """Test getting IPv4 address from wlan0."""
        mock_addr = MagicMock()
        mock_addr.family.name = "AF_INET"
        mock_addr.address = "192.168.1.100"
        mock_net_if_addrs.return_value = {"wlan0": [mock_addr]}
        result = get_ipv4_prefer_wlan0()
        assert result == "192.168.1.100"

    @patch("builtins.open", new_callable=mock_open, read_data="12345.67 98765.43\n")
    def test_get_uptime_seconds(self, mock_file):
        """Test getting uptime in seconds."""
        result = get_uptime_seconds()
        assert result == 12345

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_uptime_not_found(self, mock_file):
        """Test getting uptime when file not found."""
        result = get_uptime_seconds()
        assert result == 0

    @patch("builtins.open", new_callable=mock_open, read_data=b"Raspberry Pi Zero 2 W\x00")
    def test_get_model(self, mock_file):
        """Test getting device model."""
        result = get_model()
        assert result == "Raspberry Pi Zero 2 W"

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_model_not_found(self, mock_file):
        """Test getting model when file not found."""
        result = get_model()
        assert result == "Raspberry Pi"

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data='PRETTY_NAME="Raspberry Pi OS"\n')
    def test_get_os_release(self, mock_file, mock_exists):
        """Test getting OS release."""
        mock_exists.return_value = True
        result = get_os_release()
        assert result == "Raspberry Pi OS"

    @patch("os.path.exists")
    @patch("ha_enviro_plus.system_info.platform.platform")
    def test_get_os_release_fallback(self, mock_platform, mock_exists):
        """Test OS release fallback to platform."""
        mock_exists.return_value = False
        mock_platform.return_value = "Linux-5.10.0"
        result = get_os_release()
        assert result == "Linux-5.10.0"

    @patch("ha_enviro_plus.system_info.socket.gethostname")
    def test_get_hostname(self, mock_hostname):
        """Test getting hostname."""
        mock_hostname.return_value = "test-host"
        result = get_hostname()
        assert result == "test-host"

    @patch("ha_enviro_plus.system_info.get_serial")
    @patch("ha_enviro_plus.system_info.get_model")
    @patch("ha_enviro_plus.system_info.get_mac_address")
    def test_get_device_info(self, mock_mac, mock_model, mock_serial):
        """Test getting device info for HA discovery."""
        mock_serial.return_value = "1234567890abcdef"
        mock_model.return_value = "Raspberry Pi Zero 2 W"
        mock_mac.return_value = "aa:bb:cc:dd:ee:ff"
        result = get_device_info("Kitchen", "ha-enviro-plus", "1.0.0")
        assert result["name"] == "Enviro+ Kitchen"
        assert result["identifiers"] == ["1234567890abcdef"]
        assert result["model"] == "Raspberry Pi Zero 2 W"
        assert result["connections"] == [["mac", "aa:bb:cc:dd:ee:ff"]]
        assert result["sw_version"] == "ha-enviro-plus 1.0.0"

    @patch("ha_enviro_plus.system_info.get_serial")
    @patch("ha_enviro_plus.system_info.get_device_id")
    @patch("ha_enviro_plus.system_info.get_model")
    @patch("ha_enviro_plus.system_info.get_mac_address")
    def test_get_device_info_no_serial(self, mock_mac, mock_model, mock_device_id, mock_serial):
        """Test device info with no serial number."""
        mock_serial.return_value = "unknown"
        mock_device_id.return_value = "enviro_hostname"
        mock_model.return_value = "Raspberry Pi"
        mock_mac.return_value = None
        result = get_device_info("", "ha-enviro-plus", "1.0.0")
        assert result["name"] == "Enviro+"
        assert result["identifiers"] == ["enviro_hostname"]
        assert "connections" not in result
