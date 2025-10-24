#!/usr/bin/env bash
#
# ha-enviro-plus Uninstallation Script
#
# This script can be executed in multiple ways:
# 1. Interactive uninstallation: ./uninstall.sh
# 2. Non-interactive uninstallation: ./uninstall.sh --non-interactive
# 3. Remote uninstallation: bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/uninstall.sh)
# 4. Remote uninstallation: bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/uninstall.sh)
#
# Features:
# - Preserves existing configuration by default (with option to remove)
# - Works in both interactive and non-interactive modes
# - Provides comprehensive post-uninstallation guidance
# - Safe removal with confirmation prompts
#
set -euo pipefail

# Script version for debugging
SCRIPT_VERSION="v0.1.0"

APP_NAME="ha-enviro-plus"
SERVICE="/etc/systemd/system/${APP_NAME}.service"
CFG="/etc/default/${APP_NAME}"
APP_DIR="/opt/${APP_NAME}"
LOG="/var/log/${APP_NAME}.log"
SETTINGS_DIR="/var/lib/${APP_NAME}"

# Default to interactive mode
INTERACTIVE=1

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --interactive|-i)
      INTERACTIVE=1
      shift
      ;;
    --non-interactive|-n)
      INTERACTIVE=0
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo "Options:"
      echo "  --interactive, -i     Interactive mode with prompts (default)"
      echo "  --non-interactive, -n Non-interactive mode (preserves config by default)"
      echo "  --help, -h            Show this help message"
      echo
      echo "Examples:"
      echo "  $0                    # Interactive uninstallation"
      echo "  $0 --non-interactive  # Non-interactive uninstallation"
      echo
      echo "Remote Uninstallation:"
      echo "  # Interactive uninstallation"
      echo "  bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/uninstall.sh)"
      echo
      echo "  # Non-interactive uninstallation"
      echo "  bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/uninstall.sh) --non-interactive"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Check if running as root
check_root() {
  if [[ $EUID -eq 0 ]]; then
    echo "⚠️  Warning: Running as root. This script will use sudo internally."
    echo "   Consider running as a regular user for better security."
    if [[ $INTERACTIVE -eq 1 ]]; then
      echo -n "Continue anyway? [y/N]: "
      read -r ans || true
      if [[ "${ans,,}" != "y" ]]; then
        echo "Aborted."
        exit 1
      fi
    fi
  fi
}

# Stop and disable service
stop_service() {
  echo "==> Stopping and disabling ${APP_NAME} service..."
  if sudo systemctl is-active --quiet "${APP_NAME}.service" 2>/dev/null; then
    sudo systemctl stop "${APP_NAME}.service" || echo "⚠️  Service stop failed (may not be running)"
  fi

  if sudo systemctl is-enabled --quiet "${APP_NAME}.service" 2>/dev/null; then
    sudo systemctl disable "${APP_NAME}.service" || echo "⚠️  Service disable failed"
  fi

  echo "==> Service stopped and disabled"
}

# Remove systemd service file
remove_service() {
  echo "==> Removing systemd service file..."
  if [[ -f "${SERVICE}" ]]; then
    sudo rm -f "${SERVICE}"
    sudo systemctl daemon-reload
    echo "==> Service file removed: ${SERVICE}"
  else
    echo "==> Service file not found: ${SERVICE}"
  fi
}

# Handle configuration file
handle_config() {
  local keep_config=1

  if [[ $INTERACTIVE -eq 1 ]]; then
    if [[ -f "${CFG}" ]]; then
      echo
      echo "==> Configuration file found: ${CFG}"
      echo "   This file contains your MQTT settings and calibration values."
      echo -n "   Preserve configuration file? [Y/n]: "
      read -r ans || true
      if [[ "${ans,,}" == "n" ]]; then
        keep_config=0
      fi
    else
      echo "==> No configuration file found: ${CFG}"
    fi
  else
    echo "==> Non-interactive mode: preserving configuration file by default"
  fi

  if [[ $keep_config -eq 1 ]]; then
    echo "==> Preserving configuration file: ${CFG}"
    echo "   You can manually remove it later with: sudo rm ${CFG}"
  else
    echo "==> Removing configuration file..."
    sudo rm -f "${CFG}"
    echo "==> Configuration file removed: ${CFG}"
  fi
}

# Remove application directory
remove_app_directory() {
  echo "==> Removing application directory..."
  if [[ -d "${APP_DIR}" ]]; then
    sudo rm -rf "${APP_DIR}"
    echo "==> Application directory removed: ${APP_DIR}"
  else
    echo "==> Application directory not found: ${APP_DIR}"
  fi
}

# Remove log files
remove_logs() {
  echo "==> Removing log files..."
  if [[ -f "${LOG}" ]]; then
    sudo rm -f "${LOG}"
    echo "==> Log file removed: ${LOG}"
  else
    echo "==> Log file not found: ${LOG}"
  fi
}

# Remove settings directory
remove_settings_directory() {
  echo "==> Removing settings directory..."
  if [[ -d "${SETTINGS_DIR}" ]]; then
    sudo rm -rf "${SETTINGS_DIR}"
    echo "==> Settings directory removed: ${SETTINGS_DIR}"
  else
    echo "==> Settings directory not found: ${SETTINGS_DIR}"
  fi
}

# Post-uninstall message
post_message() {
  echo
  echo "=========================================="
  echo "✅ ${APP_NAME} uninstallation complete!"
  echo "=========================================="
  echo

  echo "📋 What was removed:"
  echo "  • Systemd service:     ${SERVICE}"
  echo "  • Application files:   ${APP_DIR}"
  echo "  • Log files:           ${LOG}"
  echo "  • Settings directory:  ${SETTINGS_DIR}"
  echo

  if [[ -f "${CFG}" ]]; then
    echo "📁 Preserved files:"
    echo "  • Configuration:      ${CFG}"
    echo "  • Remove manually:    sudo rm ${CFG}"
    echo
  fi

  echo "🔧 Next steps:"
  echo "  • If you want to remove the config file: sudo rm ${CFG}"
  echo "  • If you want to reinstall: run the install script again"
  echo "  • Check for any remaining files: sudo find /opt /etc /var -name '*${APP_NAME}*' 2>/dev/null"
  echo

  echo "🌐 Repository & Support:"
  echo "  • GitHub:              https://github.com/JeffLuckett/${APP_NAME}"
  echo "  • Issues:              https://github.com/JeffLuckett/${APP_NAME}/issues"
  echo

  if [[ $INTERACTIVE -eq 1 ]]; then
    echo "Press Enter to continue..."
    read -r
  fi
}

main() {
  echo "==> ${APP_NAME} Uninstaller ${SCRIPT_VERSION}"
  echo

  check_root

  echo "==> This will remove ${APP_NAME} and all its files."
  if [[ $INTERACTIVE -eq 1 ]]; then
    echo -n "Continue with uninstallation? [Y/n]: "
    read -r ans || true
    if [[ "${ans,,}" == "n" ]]; then
      echo "Uninstallation cancelled."
      exit 0
    fi
  fi

  stop_service
  remove_service
  handle_config
  remove_app_directory
  remove_logs
  remove_settings_directory
  post_message

  exit 0
}

main "$@"