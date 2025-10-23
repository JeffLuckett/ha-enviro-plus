#!/usr/bin/env bash
set -euo pipefail

APP_NAME="ha-enviro-plus"
SERVICE="/etc/systemd/system/${APP_NAME}.service"
CFG="/etc/default/${APP_NAME}"
APP_DIR="/opt/${APP_NAME}"
LOG="/var/log/${APP_NAME}.log"

# Stop and disable the service if it exists
sudo systemctl disable --now "${APP_NAME}.service" >/dev/null 2>&1 || true
sudo rm -f "${SERVICE}" || true
sudo systemctl daemon-reload || true

# Decide whether to keep or remove the config file
if [[ -t 0 ]]; then
  # Interactive shell: ask user
  echo -n "Leave config at ${CFG}? (y/N): "
  read -r keepcfg || keepcfg="N"
else
  # Non-interactive (e.g., wget | bash): default to keep unless KEEP_CONFIG=N
  keepcfg="${KEEP_CONFIG:-Y}"
fi

if [[ "${keepcfg,,}" == "n" ]]; then
  echo "Removing ${CFG}"
  sudo rm -f "${CFG}" || true
else
  echo "Preserving ${CFG}"
fi

sudo rm -rf "${APP_DIR}" || true
sudo rm -f "${LOG}" || true

echo "✅ Uninstalled ${APP_NAME}"