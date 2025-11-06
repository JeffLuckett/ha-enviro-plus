"""Unit tests for agent system info and network functions."""

import pytest
from unittest.mock import Mock, patch, mock_open

from ha_enviro_plus.system_info import (
    get_ipv4_prefer_wlan0,
    get_uptime_seconds,
    get_model,
    get_serial,
    get_os_release,
)


class TestNetworkFunctions:
    """Test network-related utility functions."""

    def test_get_ipv4_prefer_wlan0_wlan0_available(self, mock_network_interfaces):
        """Test getting IPv4 address with wlan0 preference."""
        ip = get_ipv4_prefer_wlan0()
        assert ip == "192.168.1.100"

    def test_get_ipv4_prefer_wlan0_no_wlan0(self, mocker, mock_device_id):
        """Test getting IPv4 address when wlan0 is not available."""
        mock_addrs = {
            "eth0": [Mock(family=Mock(name="AF_INET"), address="10.0.0.5")],
            "lo": [Mock(family=Mock(name="AF_INET"), address="127.0.0.1")],
        }

        # Fix the family.name attribute
        for interface_addrs in mock_addrs.values():
            for addr in interface_addrs:
                addr.family.name = "AF_INET"

        mock_psutil = mocker.patch("ha_enviro_plus.system_info.psutil.net_if_addrs")
        mock_psutil.return_value = mock_addrs

        ip = get_ipv4_prefer_wlan0()
        assert ip == "10.0.0.5"

    def test_get_ipv4_prefer_wlan0_no_non_loopback(self, mocker):
        """Test getting IPv4 address when only loopback is available."""
        mock_addrs = {"lo": [Mock(family=Mock(name="AF_INET"), address="127.0.0.1")]}

        mock_psutil = mocker.patch("ha_enviro_plus.system_info.psutil.net_if_addrs")
        mock_psutil.return_value = mock_addrs

        ip = get_ipv4_prefer_wlan0()
        assert ip == "unknown"

    def test_get_ipv4_prefer_wlan0_exception(self, mocker):
        """Test getting IPv4 address when exception occurs."""
        mock_psutil = mocker.patch("ha_enviro_plus.system_info.psutil.net_if_addrs")
        mock_psutil.side_effect = Exception("Network error")

        ip = get_ipv4_prefer_wlan0()
        assert ip == "unknown"


class TestSystemInfoFunctions:
    """
    Test system info functions.

    NOTE: These functions have been moved to ha_enviro_plus.system_info.
    These tests are kept here for backward compatibility but test the
    functions in their new location.
    """

    def test_get_uptime_seconds_success(self, mock_file_operations):
        """Test successful uptime reading."""
        uptime = get_uptime_seconds()
        assert uptime == 12345

    def test_get_uptime_seconds_file_error(self, mocker):
        """Test uptime reading when file doesn't exist."""
        mocker.patch("builtins.open", side_effect=FileNotFoundError)

        uptime = get_uptime_seconds()
        assert uptime == 0

    def test_get_model_success(self, mock_file_operations):
        """Test successful model reading."""
        model = get_model()
        assert model == "Raspberry Pi Zero 2 W Rev 1.0"

    def test_get_model_file_error(self, mocker):
        """Test model reading when file doesn't exist."""
        mocker.patch("builtins.open", side_effect=FileNotFoundError)

        model = get_model()
        assert model == "Raspberry Pi"

    def test_get_serial_success(self, mock_file_operations):
        """Test successful serial reading."""
        serial = get_serial()
        assert serial == "1234567890abcdef"

    def test_get_serial_file_error(self, mocker):
        """Test serial reading when file doesn't exist."""
        mocker.patch("builtins.open", side_effect=FileNotFoundError)

        serial = get_serial()
        assert serial == "unknown"

    def test_get_serial_no_serial_line(self, mocker):
        """Test serial reading when Serial line is not found."""
        cpuinfo_content = """processor	: 0
model name	: ARMv7 Processor rev 3 (v7l)
"""
        cpuinfo_mock = mocker.mock_open(read_data=cpuinfo_content)
        mocker.patch("builtins.open", cpuinfo_mock)

        serial = get_serial()
        assert serial == "unknown"

    def test_get_os_release_success(self, mock_file_operations):
        """Test successful OS release reading."""
        os_release = get_os_release()
        assert os_release == "Raspberry Pi OS Lite (64-bit)"

    def test_get_os_release_file_error(self, mock_file_operations_no_os_release, mock_platform):
        """Test OS release reading when file doesn't exist."""
        # Don't patch builtins.open here, let the fixture handle it
        # The fixture already raises FileNotFoundError for unknown files

        os_release = get_os_release()
        assert os_release == "Linux-5.15.0-rpi4-aarch64-with-glibc2.31"

    def test_get_os_release_no_pretty_name(self, mocker, mock_platform):
        """Test OS release reading when PRETTY_NAME is not found."""
        os_release_content = """NAME="Raspberry Pi OS Lite"
VERSION_ID="12"
"""
        os_release_mock = mocker.mock_open(read_data=os_release_content)
        mocker.patch("builtins.open", os_release_mock)

        os_release = get_os_release()
        assert os_release == "Linux-5.15.0-rpi4-aarch64-with-glibc2.31"

    def test_get_ipv4_prefer_wlan0_exception_handling(self, mocker):
        """Test IPv4 address detection when psutil raises an exception."""
        # Mock psutil to raise an exception
        mocker.patch(
            "ha_enviro_plus.system_info.psutil.net_if_addrs", side_effect=Exception("Network error")
        )

        ip = get_ipv4_prefer_wlan0()
        assert ip == "unknown"

    def test_get_uptime_seconds_malformed_file(self, mocker):
        """Test uptime reading with malformed /proc/uptime."""
        # Mock file with malformed content
        mocker.patch("builtins.open", mock_open(read_data="invalid uptime data"))

        uptime = get_uptime_seconds()
        assert uptime == 0

    def test_get_model_file_not_found(self, mocker):
        """Test model detection when /proc/device-tree/model doesn't exist."""
        # Mock file not found
        mocker.patch("builtins.open", side_effect=FileNotFoundError("File not found"))

        model = get_model()
        assert model == "Raspberry Pi"

    def test_get_serial_file_not_found(self, mocker):
        """Test serial detection when /proc/cpuinfo doesn't exist."""
        # Mock file not found
        mocker.patch("builtins.open", side_effect=FileNotFoundError("File not found"))

        serial = get_serial()
        assert serial == "unknown"

    def test_get_os_release_file_not_found(self, mocker):
        """Test OS release when /etc/os-release doesn't exist."""
        # Mock file not found and platform fallback
        mocker.patch("builtins.open", side_effect=FileNotFoundError("File not found"))
        mocker.patch(
            "ha_enviro_plus.system_info.platform.platform", return_value="Linux-5.15.0-rpi4-aarch64"
        )

        os_release = get_os_release()
        assert os_release == "Linux-5.15.0-rpi4-aarch64"

    def test_get_os_release_exception_handling(self, mocker):
        """Test OS release when both file read and platform fail."""
        # Mock both file read and platform to fail
        mocker.patch("builtins.open", side_effect=Exception("File error"))
        mocker.patch(
            "ha_enviro_plus.system_info.platform.platform", side_effect=Exception("Platform error")
        )

        os_release = get_os_release()
        assert os_release == "unknown"
