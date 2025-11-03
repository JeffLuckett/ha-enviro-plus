#!/usr/bin/env bash
#
# ha-enviro-plus Installation Script
#
# This script can be executed in multiple ways:
# 1. Install from PyPI latest stable release (default): ./install.sh
# 2. Install specific version from PyPI: ./install.sh --release v0.1.1
# 3. Install from GitHub branch: ./install.sh --branch your-branch-name
# 4. Show installer version: ./install.sh --version
# 5. Remote installation: bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh)
# 6. Remote installation: bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh)
# 7. Remote from branch: bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/refs/heads/your-branch/scripts/install.sh) --branch your-branch
# 8. Remote specific version: bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh) --release v0.1.1
#
# Features:
# - Default installation from PyPI (fastest, most reliable)
# - Fallback to GitHub releases for specific versions
# - GitHub branch installation for development/testing
# - Preserves existing configuration on updates
# - Prompts for new configuration options when detected
# - Works in both interactive and non-interactive modes
# - Provides comprehensive post-installation guidance
#
set -euo pipefail

# Script version for debugging
SCRIPT_VERSION="v0.1.1"

APP_NAME="ha-enviro-plus"
APP_DIR="/opt/${APP_NAME}"
SERVICE="/etc/systemd/system/${APP_NAME}.service"
CFG="/etc/default/${APP_NAME}"
VENV="${APP_DIR}/.venv"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULTS_FILE="${REPO_ROOT}/config/install-defaults.conf"

# Load default values from configuration file
load_defaults() {
  # Default values (fallback if file doesn't exist)
  DEFAULT_MQTT_HOST="homeassistant.local"
  DEFAULT_MQTT_PORT="1883"
  DEFAULT_MQTT_USER="enviro"
  DEFAULT_MQTT_PASS=""
  DEFAULT_DISCOVERY="homeassistant"
  DEFAULT_POLL="2"
  DEFAULT_TEMP_OFFSET="0"
  DEFAULT_HUM_OFFSET="0"
  DEFAULT_CPU_TEMP_FACTOR="1.8"
  DEFAULT_CPU_TEMP_SMOOTHING="0.1"
  DEFAULT_DISPLAY_ENABLED="1"

  # Try to source from configuration file if it exists
  if [ -f "${DEFAULTS_FILE}" ]; then
    # shellcheck source=config/install-defaults.conf
    source "${DEFAULTS_FILE}"
    echo "==> Loaded defaults from ${DEFAULTS_FILE}"
  else
    # If file doesn't exist (e.g., during remote installation or PyPI install),
    # try to download it from the repo
    if [ -d "${APP_DIR}/.git" ] || [ -f "${APP_DIR}/config/install-defaults.conf" ]; then
      local repo_defaults="${APP_DIR}/config/install-defaults.conf"
      if [ -f "${repo_defaults}" ]; then
        source "${repo_defaults}"
        echo "==> Loaded defaults from ${repo_defaults}"
      fi
    fi
  fi
}

ensure_git() {
  if ! command -v git >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y git
  fi
}

ensure_python() {
  sudo apt-get update -y
  sudo apt-get install -y python3 python3-venv python3-pip
}

enable_hardware_interfaces() {
  echo "==> Enabling hardware interfaces (I2C and SPI)..."

  # Check if we're on a Raspberry Pi
  if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "==> Not running on a Raspberry Pi, skipping interface enablement"
    return 0
  fi

  # Check if raspi-config is available
  if ! command -v raspi-config >/dev/null 2>&1; then
    echo "==> raspi-config not found, installing..."
    sudo apt-get update -y
    sudo apt-get install -y raspi-config
  fi

  local reboot_needed=false
  local i2c_enabled=false
  local spi_enabled=false

  # Check if I2C is already enabled (returns 0 if enabled, 1 if disabled)
  if sudo raspi-config nonint get_i2c >/dev/null 2>&1; then
    local i2c_status
    i2c_status=$(sudo raspi-config nonint get_i2c)
    if [ "$i2c_status" = "0" ]; then
      echo "==> I2C is already enabled"
      i2c_enabled=true
    fi
  fi

  # Check if SPI is already enabled (returns 0 if enabled, 1 if disabled)
  if sudo raspi-config nonint get_spi >/dev/null 2>&1; then
    local spi_status
    spi_status=$(sudo raspi-config nonint get_spi)
    if [ "$spi_status" = "0" ]; then
      echo "==> SPI is already enabled"
      spi_enabled=true
    fi
  fi

  # Enable I2C if not already enabled
  if [ "$i2c_enabled" = "false" ]; then
    echo "==> Enabling I2C interface..."
    if sudo raspi-config nonint do_i2c 0; then
      echo "==> I2C enabled successfully"
      reboot_needed=true
    else
      echo "==> Warning: Failed to enable I2C"
    fi
  fi

  # Enable SPI if not already enabled
  if [ "$spi_enabled" = "false" ]; then
    echo "==> Enabling SPI interface..."
    if sudo raspi-config nonint do_spi 0; then
      echo "==> SPI enabled successfully"
      reboot_needed=true
    else
      echo "==> Warning: Failed to enable SPI"
    fi
  fi

  # Verify configuration was written (check both possible config locations)
  local config_found=false
  for config_file in /boot/config.txt /boot/firmware/config.txt; do
    if [ -f "$config_file" ]; then
      if grep -q "dtparam=i2c_arm=on" "$config_file" 2>/dev/null && \
         grep -q "dtparam=spi=on" "$config_file" 2>/dev/null; then
        echo "==> Verified I2C and SPI configuration in $config_file"
        config_found=true
        break
      fi
    fi
  done

  if [ "$reboot_needed" = "true" ] && [ "$config_found" = "false" ]; then
    echo "==> Warning: Configuration enabled but not yet written to config file"
    echo "==> This is normal - raspi-config will write changes on next boot"
  fi

  # Export reboot_needed flag for use in main function
  if [ "$reboot_needed" = "true" ]; then
    export REBOOT_NEEDED=true
    echo "==> Hardware interfaces enabled. Reboot required for changes to take effect."
  else
    export REBOOT_NEEDED=false
    echo "==> Hardware interfaces are already enabled."
  fi
}

install_from_pypi() {
  local version="${1:-}"

  echo "==> Installing from PyPI..."

  # Create virtual environment for the application
  echo "==> Creating virtual environment..."
  sudo mkdir -p "${APP_DIR}"
  sudo python3 -m venv "${VENV}"
  sudo "${VENV}/bin/pip" install --upgrade pip

  if [[ -n "$version" ]]; then
    echo "==> Installing specific version: $version"
    sudo "${VENV}/bin/pip" install "ha-enviro-plus==${version#v}"
  else
    echo "==> Installing latest version from PyPI"
    sudo "${VENV}/bin/pip" install ha-enviro-plus
  fi

  # Create symlink to the venv executable
  sudo ln -sf "${VENV}/bin/ha-enviro-plus" /usr/local/bin/ha-enviro-plus || true
}

install_from_release() {
  local version="$1"

  echo "==> Installing from GitHub release: $version"

  # Create virtual environment for the application
  echo "==> Creating virtual environment..."
  sudo mkdir -p "${APP_DIR}"
  sudo python3 -m venv "${VENV}"
  sudo "${VENV}/bin/pip" install --upgrade pip

  # Download wheel from GitHub release
  local wheel_url="https://github.com/JeffLuckett/ha-enviro-plus/releases/download/${version}/ha_enviro_plus-${version#v}-py3-none-any.whl"

  echo "==> Downloading wheel from: $wheel_url"
  sudo "${VENV}/bin/pip" install "$wheel_url"

  # Create symlink to the venv executable
  sudo ln -sf "${VENV}/bin/ha-enviro-plus" /usr/local/bin/ha-enviro-plus || true
}

install_from_git() {
  local branch="$1"

  echo "==> Installing from GitHub branch: $branch"

  ensure_git
  ensure_python
  clone_or_update "${branch}"
  make_venv
}

clone_or_update() {
  local branch="${1:-main}"

  if [ -d "${APP_DIR}/.git" ]; then
    echo "==> Updating ${APP_NAME} at ${APP_DIR}..."
    sudo git -C "${APP_DIR}" fetch origin
    sudo git -C "${APP_DIR}" checkout "${branch}"
    sudo git -C "${APP_DIR}" pull --ff-only
  else
    echo "==> Installing ${APP_NAME} from branch: ${branch}..."
    sudo rm -rf "${APP_DIR}"
    sudo git clone -b "${branch}" https://github.com/JeffLuckett/${APP_NAME}.git "${APP_DIR}"
  fi
}

make_venv() {
  sudo python3 -m venv "${VENV}"
  sudo "${VENV}/bin/pip" install --upgrade pip
  if [ -f "${APP_DIR}/requirements.txt" ]; then
    sudo "${VENV}/bin/pip" install -r "${APP_DIR}/requirements.txt" || echo "⚠ pip install warnings ignored"
  else
    echo "⚠ ${APP_DIR}/requirements.txt not found; skipping dependency install"
  fi
}

# Detect if running remotely (via wget/curl)
is_remote_execution() {
  # Check if stdin is not a terminal (piped from wget/curl)
  [ ! -t 0 ] || [ -n "${REMOTE_EXECUTION:-}" ]
}


# Load existing config values
load_existing_config() {
  if [ -f "${CFG}" ]; then
    # Read config file with sudo and export variables
    # Use a temporary approach to avoid permission issues
    local temp_config
    temp_config=$(sudo cat "${CFG}" 2>/dev/null) || {
      echo "Warning: Could not read existing config file ${CFG}"
      return 1
    }

    while IFS='=' read -r key value; do
      # Skip empty lines and comments
      if [ -n "$key" ] && [ "${key#\#}" = "$key" ]; then
        # Remove quotes from value if present
        value=$(echo "$value" | sed 's/^"//;s/"$//')
        export "$key"="$value"
      fi
    done <<< "$temp_config"
    return 0
  fi
  return 1
}

# Check for new config options that weren't in previous versions
check_new_config_options() {
  local new_options=()

  # Check if any new options are missing from existing config
  if [ -z "${CPU_TEMP_FACTOR:-}" ]; then
    new_options+=("CPU_TEMP_FACTOR")
  fi

  if [ -z "${CPU_TEMP_SMOOTHING:-}" ]; then
    new_options+=("CPU_TEMP_SMOOTHING")
  fi

  if [ ${#new_options[@]} -gt 0 ]; then
    echo "==> New configuration options detected: ${new_options[*]}"
    echo "These options were added in newer versions and need to be configured."
    return 0
  fi
  return 1
}

write_config() {
  echo "==> Configuring ${APP_NAME}..."
  sudo mkdir -p "$(dirname "${CFG}")"

  # Load default values from configuration file
  load_defaults

  # Try to load existing config
  if load_existing_config; then
    echo "==> Found existing configuration, preserving current settings..."

    # Check for new options that need configuration
    if check_new_config_options && [ -t 0 ]; then
      echo
      echo "Please configure the new options:"

      if [ -z "${CPU_TEMP_FACTOR:-}" ]; then
        read -rp "CPU temperature compensation factor (higher=less compensation, lower=more compensation) [${DEFAULT_CPU_TEMP_FACTOR}]: " CPU_TEMP_FACTOR_INPUT
        CPU_TEMP_FACTOR="${CPU_TEMP_FACTOR_INPUT:-${DEFAULT_CPU_TEMP_FACTOR}}"
      fi

      if [ -z "${CPU_TEMP_SMOOTHING:-}" ]; then
        read -rp "CPU temperature smoothing factor [${DEFAULT_CPU_TEMP_SMOOTHING}]: " CPU_TEMP_SMOOTHING_INPUT
        CPU_TEMP_SMOOTHING="${CPU_TEMP_SMOOTHING_INPUT:-${DEFAULT_CPU_TEMP_SMOOTHING}}"
      fi
    else
      # Use defaults for new options if not interactive
      : "${CPU_TEMP_FACTOR:=${DEFAULT_CPU_TEMP_FACTOR}}"
      : "${CPU_TEMP_SMOOTHING:=${DEFAULT_CPU_TEMP_SMOOTHING}}"
    fi
  else
    echo "==> Creating new configuration..."

    # Interactive configuration for new installations
    if [ -t 0 ]; then
      read -rp "MQTT host [${DEFAULT_MQTT_HOST}]: " MQTT_HOST
      read -rp "MQTT port [${DEFAULT_MQTT_PORT}]: " MQTT_PORT
      read -rp "MQTT username [${DEFAULT_MQTT_USER}]: " MQTT_USER
      read -rsp "MQTT password (input hidden) [empty ok]: " MQTT_PASS; echo
      read -rp "Home Assistant discovery prefix [${DEFAULT_DISCOVERY}]: " MQTT_DISCOVERY_PREFIX
      read -rp "Poll interval seconds [${DEFAULT_POLL}]: " POLL
      read -rp "Temperature offset °C [${DEFAULT_TEMP_OFFSET}]: " TEMP_OFFSET
      read -rp "Humidity offset % [${DEFAULT_HUM_OFFSET}]: " HUM_OFFSET
      read -rp "CPU temperature compensation factor (higher=less compensation, lower=more compensation) [${DEFAULT_CPU_TEMP_FACTOR}]: " CPU_TEMP_FACTOR
      read -rp "CPU temperature smoothing factor [${DEFAULT_CPU_TEMP_SMOOTHING}]: " CPU_TEMP_SMOOTHING
    else
      echo "==> Using default values (non-interactive mode)"
    fi
  fi

  # Set defaults for any unset variables (this handles both new and existing configs)
  : "${MQTT_HOST:=${DEFAULT_MQTT_HOST}}"
  : "${MQTT_PORT:=${DEFAULT_MQTT_PORT}}"
  : "${MQTT_USER:=${DEFAULT_MQTT_USER}}"
  : "${MQTT_PASS:=${DEFAULT_MQTT_PASS}}"
  : "${MQTT_DISCOVERY_PREFIX:=${DEFAULT_DISCOVERY}}"
  : "${POLL:=${DEFAULT_POLL}}"
  : "${TEMP_OFFSET:=${DEFAULT_TEMP_OFFSET}}"
  : "${HUM_OFFSET:=${DEFAULT_HUM_OFFSET}}"
  : "${CPU_TEMP_FACTOR:=${DEFAULT_CPU_TEMP_FACTOR}}"
  : "${CPU_TEMP_SMOOTHING:=${DEFAULT_CPU_TEMP_SMOOTHING}}"
  : "${DISPLAY_ENABLED:=${DEFAULT_DISPLAY_ENABLED}}"

  # Write the complete configuration
  sudo tee "${CFG}" > /dev/null <<EOF
MQTT_HOST="${MQTT_HOST}"
MQTT_PORT="${MQTT_PORT}"
MQTT_USER="${MQTT_USER}"
MQTT_PASS="${MQTT_PASS}"
MQTT_DISCOVERY_PREFIX="${MQTT_DISCOVERY_PREFIX}"
POLL_SEC="${POLL}"
TEMP_OFFSET="${TEMP_OFFSET}"
HUM_OFFSET="${HUM_OFFSET}"
CPU_TEMP_FACTOR="${CPU_TEMP_FACTOR}"
CPU_TEMP_SMOOTHING="${CPU_TEMP_SMOOTHING}"
DISPLAY_ENABLED="${DISPLAY_ENABLED}"
EOF
  sudo chmod 600 "${CFG}"
}

create_settings_dir() {
  echo "==> Creating settings directory..."
  sudo mkdir -p "/var/lib/${APP_NAME}"
  sudo chown root:root "/var/lib/${APP_NAME}"
  sudo chmod 755 "/var/lib/${APP_NAME}"
  echo "==> Settings directory created: /var/lib/${APP_NAME}"
}

install_service() {
  echo "==> Installing systemd service..."

  # Determine the correct working directory and python path
  local working_dir="${APP_DIR}"
  local python_cmd="${VENV}/bin/python -m ha_enviro_plus.agent"

  # If we're using git installation, use the git working directory
  if [[ -d "${APP_DIR}/.git" ]]; then
    working_dir="${APP_DIR}"
  fi

  sudo tee "${SERVICE}" > /dev/null <<EOF
[Unit]
Description=Enviro+ → Home Assistant MQTT Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=${CFG}
WorkingDirectory=${working_dir}
ExecStart=${python_cmd}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable ${APP_NAME}.service
}

start_service() {
  sudo systemctl restart ${APP_NAME}.service || sudo systemctl start ${APP_NAME}.service
}

post_message() {
  echo
  echo "=========================================="
  echo "🎉 ${APP_NAME} installation complete!"
  echo "=========================================="
  echo

  echo "📋 Service Management:"
  echo "  • Start service:     sudo systemctl start ${APP_NAME}"
  echo "  • Stop service:      sudo systemctl stop ${APP_NAME}"
  echo "  • Restart service:   sudo systemctl restart ${APP_NAME}"
  echo "  • Enable service:    sudo systemctl enable ${APP_NAME}"
  echo "  • Disable service:   sudo systemctl disable ${APP_NAME}"
  echo "  • Service status:    sudo systemctl status ${APP_NAME}"
  echo

  echo "📊 Monitoring & Logs:"
  echo "  • Follow live logs:  sudo journalctl -u ${APP_NAME} -f"
  echo "  • View recent logs:  sudo journalctl -u ${APP_NAME} -n 50"
  echo "  • View all logs:     sudo journalctl -u ${APP_NAME}"
  echo "  • Logs since boot:   sudo journalctl -u ${APP_NAME} -b"
  echo "  • Logs with timestamps: sudo journalctl -u ${APP_NAME} -o short-precise"
  echo

  echo "⚙️  Configuration:"
  echo "  • Config file:       ${CFG}"
  echo "  • Edit config:       sudo nano ${CFG}"
  echo "  • Reload after edit: sudo systemctl restart ${APP_NAME}"
  echo

  echo "🔧 Troubleshooting:"
  echo "  • Check service:     sudo systemctl status ${APP_NAME}"
  echo "  • Test config:       sudo systemd-analyze verify ${SERVICE}"
  echo "  • Check dependencies: ${VENV}/bin/python -c 'import paho.mqtt.client, bme280, ltr559, enviroplus'"
  echo "  • Manual test:       sudo -u root ${VENV}/bin/python -m ha_enviro_plus.agent"
  echo

  echo "📁 Files & Directories:"
  echo "  • Application:       ${APP_DIR}"
  echo "  • Virtual env:       ${VENV}"
  echo "  • Service file:      ${SERVICE}"
  echo "  • Config file:       ${CFG}"
  echo

  echo "🌐 Repository & Support:"
  echo "  • GitHub:            https://github.com/JeffLuckett/${APP_NAME}"
  echo "  • Issues:            https://github.com/JeffLuckett/${APP_NAME}/issues"
  echo

  echo "💡 Quick Start:"
  if [ "${REBOOT_NEEDED:-false}" = "true" ]; then
    echo "  ⚠️  IMPORTANT: A reboot is required for I2C/SPI interfaces to work."
    echo "  The service is running but sensors/display will not work until reboot."
    echo "  You will be prompted to reboot after this message."
  else
    echo "  The service should now be running. Check the logs above to verify"
    echo "  it's connecting to your MQTT broker and publishing sensor data."
  fi
  echo

  if [ "${REBOOT_NEEDED:-false}" != "true" ]; then
    echo "⚠️  Hardware Interfaces:"
    echo "  I2C and SPI interfaces are enabled for sensors and display."
    echo "  Check interface status: ls -l /dev/i2c-* /dev/spidev*"
    echo
  fi

  if [ -t 0 ] && [ "${REBOOT_NEEDED:-false}" != "true" ]; then
    echo "Press Enter to view current service status..."
    read -r
    sudo systemctl status ${APP_NAME} --no-pager
  fi
}

main() {
  echo "==> ${APP_NAME} Installer ${SCRIPT_VERSION}"
  echo

  # Parse command line arguments
  local branch=""
  local install_version=""
  local install_method="pypi"  # Default to PyPI
  local test_mode=false
  local no_reboot=false

  while [[ $# -gt 0 ]]; do
    case $1 in
      --branch|-b)
        branch="$2"
        install_method="git"
        shift 2
        ;;
      --release|-r)
        install_version="$2"
        install_method="release"
        shift 2
        ;;
      --test|--dry-run)
        test_mode=true
        shift
        ;;
      --no-reboot)
        no_reboot=true
        shift
        ;;
      --version|-v)
        echo "${APP_NAME} Installer ${SCRIPT_VERSION}"
        echo "Default installation method: PyPI (latest)"
        if [[ -n "$install_version" ]]; then
          echo "Installing version: $install_version (from GitHub release)"
        elif [[ -n "$branch" ]]; then
          echo "Installing from branch: $branch (from GitHub)"
        fi
        exit 0
        ;;
      --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo "Options:"
        echo "  --branch BRANCH, -b BRANCH    Install from GitHub branch (development/testing)"
        echo "  --release VERSION, -r VERSION Install specific version from GitHub release"
        echo "  --test, --dry-run             Test mode - validate logic without making changes"
        echo "  --no-reboot                   Skip automatic reboot (even if I2C/SPI enabled)"
        echo "  --version, -v                 Show installer version and exit"
        echo "  --help, -h                    Show this help message"
        echo
        echo "Examples:"
        echo "  $0                           # Install latest from PyPI (default)"
        echo "  $0 --branch feature-branch   # Install from GitHub branch"
        echo "  $0 --release v0.1.1          # Install specific version from GitHub release"
        echo "  $0 --version                 # Show installer version"
        echo
        echo "Remote Installation:"
        echo "  # Install latest from PyPI (recommended)"
        echo "  bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh)"
        echo "  # Install from GitHub branch"
        echo "  bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh) --branch BRANCH"
        echo "  # Install specific version from GitHub release"
        echo "  bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh) --release v0.1.1"
        exit 0
        ;;
      *)
        echo "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
    esac
  done

  # Test mode - validate logic without making changes
  if [[ "$test_mode" == true ]]; then
    echo "🧪 TEST MODE - No actual changes will be made"
    echo
    echo "Installation method: $install_method"
    case "$install_method" in
      "pypi")
        if [[ -n "$install_version" ]]; then
          echo "Would install: ha-enviro-plus==${install_version#v} from PyPI"
        else
          echo "Would install: ha-enviro-plus (latest) from PyPI"
        fi
        ;;
      "release")
        echo "Would install: ha_enviro_plus-${install_version#v}-py3-none-any.whl from GitHub release $install_version"
        ;;
      "git")
        echo "Would install from GitHub branch: $branch"
        ;;
    esac
    echo
    echo "✅ Test mode validation complete - logic appears correct"
    exit 0
  fi

  # Install the package based on method
  case "$install_method" in
    "pypi")
      ensure_python
      install_from_pypi "$install_version"
      ;;
    "release")
      ensure_python
      install_from_release "$install_version"
      ;;
    "git")
      install_from_git "$branch"
      ;;
  esac

  # Common post-installation steps
  enable_hardware_interfaces
  write_config
  create_settings_dir
  install_service
  start_service
  post_message

  # Handle reboot if needed and not suppressed
  if [ "${REBOOT_NEEDED:-false}" = "true" ] && [ "$no_reboot" = "false" ]; then
    echo
    echo "=========================================="
    echo "⚠️  Reboot Required"
    echo "=========================================="
    echo
    echo "I2C and/or SPI interfaces have been enabled and require a reboot"
    echo "to take effect. The service will not work properly until after reboot."
    echo

    if [ -t 0 ]; then
      echo "Reboot now? (y/n) [y]: "
      read -r reboot_answer
      if [[ "${reboot_answer:-y}" =~ ^[Yy]$ ]]; then
        echo "==> Rebooting in 5 seconds... (Press Ctrl+C to cancel)"
        sleep 5
        sudo reboot
      else
        echo "==> Skipping reboot. Please reboot manually when ready: sudo reboot"
        echo "==> The service will not work properly until after reboot."
      fi
    else
      echo "==> Non-interactive mode: Skipping automatic reboot."
      echo "==> Please reboot manually: sudo reboot"
      echo "==> The service will not work properly until after reboot."
    fi
  fi

  exit 0
}

main "$@"