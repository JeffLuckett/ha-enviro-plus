#!/usr/bin/env bash
set -euo pipefail
APP_NAME="ha-enviro-plus"
SERVICE="/etc/systemd/system/${APP_NAME}.service"
CFG="/etc/default/${APP_NAME}"
APP_DIR="/opt/${APP_NAME}"
LOG="/var/log/${APP_NAME}.log"

sudo systemctl disable --now ${APP_NAME}.service || true
sudo rm -f "${SERVICE}"
sudo systemctl daemon-reload

echo "Leave config at ${CFG}? (y/N)"
read -r keepcfg || true
if [ "${keepcfg:-N}" != "y" ]; then
  sudo rm -f "${CFG}"
fi

sudo rm -rf "${APP_DIR}"
sudo rm -f "${LOG}"

echo "Uninstalled ${APP_NAME}"
