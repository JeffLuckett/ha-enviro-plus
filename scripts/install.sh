#!/usr/bin/env bash
#
# ha-enviro-plus Installation Script
#
# This script can be executed in multiple ways:
# 1. Interactive installation: ./install.sh
# 2. Install from specific branch: ./install.sh --branch your-branch-name
# 3. Install specific version: ./install.sh --release v0.1.0
# 4. Show installer version: ./install.sh --version
# 5. Remote installation: bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh)
# 6. Remote installation: bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh)
# 7. Remote from branch: bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/refs/heads/your-branch/scripts/install.sh) --branch your-branch
# 8. Remote specific version: bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh) --release v0.1.0
#
# Features:
# - Preserves existing configuration on updates
# - Prompts for new configuration options when detected
# - Works in both interactive and non-interactive modes
# - Provides comprehensive post-installation guidance
#
set -euo pipefail

# Script version for debugging
SCRIPT_VERSION="v0.1.0"

APP_NAME="ha-enviro-plus"
APP_DIR="/opt/${APP_NAME}"
SERVICE="/etc/systemd/system/${APP_NAME}.service"
CFG="/etc/default/${APP_NAME}"
VENV="${APP_DIR}/.venv"

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

  # Default values
  DEFAULT_MQTT_HOST="homeassistant.local"
  DEFAULT_MQTT_PORT="1883"
  DEFAULT_MQTT_USER="enviro"
  DEFAULT_MQTT_PASS=""
  DEFAULT_DISCOVERY="homeassistant"
  DEFAULT_POLL="2"
  DEFAULT_TEMP_OFFSET="0"
  DEFAULT_HUM_OFFSET="0"
  DEFAULT_CPU_TEMP_FACTOR="1.8"

  # Try to load existing config
  if load_existing_config; then
    echo "==> Found existing configuration, preserving current settings..."

    # Check for new options that need configuration
    if check_new_config_options && [ -t 0 ]; then
      echo
      echo "Please configure the new options:"

      if [ -z "${CPU_TEMP_FACTOR:-}" ]; then
        read -rp "CPU temperature compensation factor (higher number lowers temp output) [${DEFAULT_CPU_TEMP_FACTOR}]: " CPU_TEMP_FACTOR_INPUT
        CPU_TEMP_FACTOR="${CPU_TEMP_FACTOR_INPUT:-${DEFAULT_CPU_TEMP_FACTOR}}"
      fi
    else
      # Use defaults for new options if not interactive
      : "${CPU_TEMP_FACTOR:=${DEFAULT_CPU_TEMP_FACTOR}}"
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
      read -rp "CPU temperature compensation factor (higher number lowers temp output) [${DEFAULT_CPU_TEMP_FACTOR}]: " CPU_TEMP_FACTOR
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
  sudo tee "${SERVICE}" > /dev/null <<EOF
[Unit]
Description=Enviro+ → Home Assistant MQTT Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=${CFG}
WorkingDirectory=${APP_DIR}
ExecStart=${VENV}/bin/python -m ha_enviro_plus.agent
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
  echo "  The service should now be running. Check the logs above to verify"
  echo "  it's connecting to your MQTT broker and publishing sensor data."
  echo

  if [ -t 0 ]; then
    echo "Press Enter to view current service status..."
    read -r
    sudo systemctl status ${APP_NAME} --no-pager
  fi
}

main() {
  echo "==> ${APP_NAME} Installer ${SCRIPT_VERSION}"
  echo

  # Parse command line arguments
  local branch="main"
  local install_version=""

  while [[ $# -gt 0 ]]; do
    case $1 in
      --branch|-b)
        branch="$2"
        shift 2
        ;;
      --release|-r)
        install_version="$2"
        shift 2
        ;;
      --version|-v)
        echo "${APP_NAME} Installer ${SCRIPT_VERSION}"
        echo "Installing from branch: $branch"
        if [[ -n "$install_version" ]]; then
          echo "Installing version: $install_version"
        fi
        exit 0
        ;;
      --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo "Options:"
        echo "  --branch BRANCH, -b BRANCH    Install from specific branch (default: main)"
        echo "  --release VERSION, -r VERSION Install specific version (e.g., v0.1.0)"
        echo "  --version, -v                 Show installer version and exit"
        echo "  --help, -h                    Show this help message"
        echo
        echo "Examples:"
        echo "  $0                           # Install from main branch"
        echo "  $0 --branch feature-branch   # Install from specific branch"
        echo "  $0 --release v0.1.0          # Install specific version"
        echo "  $0 --version                 # Show installer version"
        echo
        echo "Remote Installation:"
        echo "  # Install from specific branch (recommended)"
        echo "  bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/refs/heads/BRANCH/scripts/install.sh) --branch BRANCH"
        echo "  # Install specific version"
        echo "  bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh) --release v0.1.0"
        exit 0
        ;;
      *)
        echo "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
    esac
  done

  # Determine what to install
  if [[ -n "$install_version" ]]; then
    echo "==> Installing version: $install_version"
    branch="tags/$install_version"
  else
    echo "==> Installing from branch: $branch"
  fi

  ensure_git
  ensure_python
  clone_or_update "${branch}"
  make_venv
  write_config
  create_settings_dir
  install_service
  start_service
  post_message
  exit 0
}

main "$@"