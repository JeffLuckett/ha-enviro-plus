#!/usr/bin/env bash
set -euo pipefail
APP_NAME="ha-enviro-plus"
SERVICE="/etc/systemd/system/${APP_NAME}.service"
CFG="/etc/default/${APP_NAME}"
APP_DIR="/opt/${APP_NAME}"
LOG="/var/log/${APP_NAME}.log"

INTERACTIVE=0
if [[ "${1:-}" == "--interactive" ]]; then
  INTERACTIVE=1
fi

sudo systemctl disable --now "${APP_NAME}.service" || true
sudo rm -f "${SERVICE}"
sudo systemctl daemon-reload

KEEP=1
if [[ $INTERACTIVE -eq 1 ]]; then
  echo -n "Preserve ${CFG}? [Y/n]: "
  read -r ans || true
  if [[ "${ans,,}" == "n" ]]; then KEEP=0; fi
fi

if [[ $KEEP -eq 1 ]]; then
  echo "Preserving ${CFG}"
else
  sudo rm -f "${CFG}"
fi

sudo rm -rf "${APP_DIR}"
sudo rm -f "${LOG}" || true

echo "✅ Uninstalled ${APP_NAME}"