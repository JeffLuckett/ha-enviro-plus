#!/usr/bin/env python3
"""
System information gathering utilities.

This module provides functions to gather system information like MAC address,
device ID, serial number, uptime, model, etc. All functions follow the
fail-safe pattern: never raise exceptions, always return fallback values.
"""

import logging
import os
import platform
import socket
from typing import Any, Dict, List, Optional

import psutil

from .constants import Constants

# Use module logger
_logger = logging.getLogger(__name__)


def get_mac_address() -> Optional[str]:
    """
    Get MAC address from primary network interface.

    Prefers wlan0, then eth0, then first non-loopback interface.

    Returns:
        MAC address string (XX:XX:XX:XX:XX:XX format), or None if unable to determine
    """
    try:
        addrs = psutil.net_if_addrs()
        # Prefer wlan0, then eth0
        for iface_name in Constants.PREFERRED_INTERFACES:
            if iface_name in addrs:
                mac = _extract_mac_from_addrs(addrs[iface_name])
                if mac:
                    _logger.debug("Using %s MAC address: %s", iface_name, mac)
                    return mac

        # Fallback: first non-loopback interface
        for iface_name, iface_addrs in addrs.items():
            if iface_name == "lo":
                continue
            mac = _extract_mac_from_addrs(iface_addrs)
            if mac:
                _logger.debug("Using %s MAC address: %s", iface_name, mac)
                return mac
    except Exception as e:
        _logger.debug("Failed to get MAC address: %s", e)
    return None


def _extract_mac_from_addrs(addrs: list) -> Optional[str]:
    """Extract MAC address from psutil address list."""
    for addr in addrs:
        mac = getattr(addr, "address", None)
        if _is_valid_mac(mac):
            return mac
    return None


def _is_valid_mac(mac: Optional[str]) -> bool:
    """Check if string is a valid MAC address."""
    return (
        mac is not None
        and isinstance(mac, str)
        and len(mac) == Constants.MAC_ADDRESS_LENGTH
        and Constants.MAC_ADDRESS_SEPARATOR in mac
    )


def get_serial() -> str:
    """
    Get device serial number from /proc/cpuinfo.

    Returns:
        Serial number string, or "unknown" if unable to read
    """
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("Serial"):
                    serial = line.split(":")[1].strip()
                    _logger.debug("Device serial: %s", serial)
                    return serial
        _logger.warning("Serial number not found in cpuinfo")
    except FileNotFoundError:
        _logger.error("CPU info file not found")
    except Exception as e:
        _logger.error("Failed to read device serial: %s", e)
    return "unknown"


def get_device_id() -> str:
    """
    Get unique device identifier using serial number (HA best practice).

    Falls back to hostname if serial is unavailable.

    Returns:
        Unique device ID string (e.g., "enviro_1234567890abcdef")
    """
    serial = get_serial()
    if serial and serial != "unknown":
        dev_id = f"enviro_{serial}"
        _logger.debug("Using serial number for device_id: %s", dev_id)
        return dev_id

    # Fallback to hostname
    hostname = socket.gethostname()
    dev_id = f"enviro_{hostname.replace('-', '')}"
    _logger.warning("Serial number unavailable, using hostname for device_id: %s", dev_id)
    return dev_id


def get_ipv4_prefer_wlan0() -> str:
    """
    Get IPv4 address with preference for wlan0 interface.

    Returns:
        IPv4 address string, or "unknown" if unable to determine
    """
    try:
        addrs = psutil.net_if_addrs()
        # Prefer wlan0
        if "wlan0" in addrs:
            ip = _extract_ipv4_from_addrs(addrs["wlan0"])
            if ip:
                _logger.debug("Using wlan0 IPv4 address: %s", ip)
                return ip

        # Fallback: first non-loopback IPv4
        for iface, iface_addrs in addrs.items():
            ip = _extract_ipv4_from_addrs(iface_addrs)
            if ip:
                _logger.debug("Using %s IPv4 address: %s", iface, ip)
                return ip
    except Exception as e:
        _logger.error("Failed to get network address: %s", e)
    return "unknown"


def _extract_ipv4_from_addrs(addrs: list) -> Optional[str]:
    """Extract IPv4 address from psutil address list."""
    for addr in addrs:
        if addr.family.name == "AF_INET" and not addr.address.startswith("127."):
            return str(addr.address)
    return None


def get_uptime_seconds() -> int:
    """
    Get system uptime in seconds from /proc/uptime.

    Returns:
        Uptime in seconds, or 0 if unable to read
    """
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            uptime_str = f.read().split()[0]
            uptime_seconds = int(float(uptime_str))
            _logger.debug("System uptime: %d seconds", uptime_seconds)
            return uptime_seconds
    except (FileNotFoundError, ValueError, IndexError) as e:
        _logger.error("Failed to read system uptime: %s", e)
    except Exception as e:
        _logger.error("Unexpected error reading uptime: %s", e)
    return 0


def get_model() -> str:
    """
    Get device model from /proc/device-tree/model.

    Returns:
        Device model string, or "Raspberry Pi" if unable to read
    """
    try:
        with open("/proc/device-tree/model", "rb") as f:
            model_bytes = f.read()
            model_str = model_bytes.decode(errors="ignore").strip("\x00")
            _logger.debug("Device model: %s", model_str)
            return model_str
    except FileNotFoundError:
        _logger.warning("Device model file not found, using default")
    except Exception as e:
        _logger.error("Failed to read device model: %s", e)
    return "Raspberry Pi"


def get_os_release() -> str:
    """
    Get OS release information from /etc/os-release or platform fallback.

    Returns:
        OS release string, or "unknown" if unable to determine
    """
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        os_name = line.split("=", 1)[1].strip().strip('"')
                        _logger.debug("OS release from os-release: %s", os_name)
                        return os_name

        # Fallback to platform info
        platform_info = platform.platform()
        _logger.debug("OS release from platform: %s", platform_info)
        return platform_info
    except FileNotFoundError:
        _logger.warning("OS release file not found, using platform fallback")
        try:
            return platform.platform()
        except Exception as e:
            _logger.error("Platform fallback failed: %s", e)
    except Exception as e:
        _logger.error("Failed to get OS release: %s", e)
    return "unknown"


def get_hostname() -> str:
    """
    Get system hostname.

    Returns:
        Hostname string
    """
    return socket.gethostname()


def get_device_info(
    device_location: str = "", app_name: str = "ha-enviro-plus", version: str = ""
) -> Dict[str, Any]:
    """
    Get device info for Home Assistant discovery.

    Args:
        device_location: Optional location/name for device
        app_name: Application name
        version: Application version

    Returns:
        Dictionary with device information including identifiers and connections
    """
    # Use serial number as primary identifier (HA best practice)
    serial = get_serial()
    identifiers = []
    if serial and serial != "unknown":
        identifiers.append(serial)
    else:
        # Fallback to device_id if serial unavailable
        identifiers.append(get_device_id())

    # Build device name with location if provided
    device_name = "Enviro+"
    if device_location:
        device_name = f"Enviro+ {device_location}"

    # Get MAC address for connections (HA best practice)
    connections_list: List[List[str]] = []
    mac_address = get_mac_address()
    if mac_address:
        connections_list.append(["mac", mac_address])

    device_info: Dict[str, Any] = {
        "identifiers": identifiers,
        "name": device_name,
        "manufacturer": "Pimoroni",
        "model": get_model(),
        "sw_version": f"{app_name} {version}",
        "configuration_url": "https://github.com/JeffLuckett/ha-enviro-plus",
    }

    if connections_list:
        device_info["connections"] = connections_list

    return device_info
