#!/usr/bin/env bash
set -euo pipefail

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
  if [ -d "${APP_DIR}/.git" ]; then
    echo "==> Updating ${APP_NAME} at ${APP_DIR}..."
    sudo git -C "${APP_DIR}" pull --ff-only
  else
    echo "==> Installing ${APP_NAME}..."
    sudo rm -rf "${APP_DIR}"
    sudo git clone https://github.com/JeffLuckett/${APP_NAME}.git "${APP_DIR}"
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

write_config() {
  echo "==> Creating new config..."
  sudo mkdir -p "$(dirname "${CFG}")"

  DEFAULT_MQTT_HOST="homeassistant.local"
  DEFAULT_MQTT_PORT="1883"
  DEFAULT_MQTT_USER="enviro"
  DEFAULT_MQTT_PASS=""
  DEFAULT_DISCOVERY="homeassistant"
  DEFAULT_POLL="2"
  DEFAULT_TEMP_OFFSET="0"
  DEFAULT_HUM_OFFSET="0"
  DEFAULT_CPU_ALPHA="0.8"
  DEFAULT_CPU_CORR="1.5"

  if [ -t 0 ]; then
    read -rp "MQTT host [${DEFAULT_MQTT_HOST}]: " MQTT_HOST
    read -rp "MQTT port [${DEFAULT_MQTT_PORT}]: " MQTT_PORT
    read -rp "MQTT username [${DEFAULT_MQTT_USER}]: " MQTT_USER
    read -rsp "MQTT password (input hidden) [empty ok]: " MQTT_PASS; echo
    read -rp "Home Assistant discovery prefix [${DEFAULT_DISCOVERY}]: " MQTT_DISCOVERY_PREFIX
    read -rp "Poll interval seconds [${DEFAULT_POLL}]: " POLL
    read -rp "Temperature offset °C [${DEFAULT_TEMP_OFFSET}]: " TEMP_OFFSET
    read -rp "Humidity offset % [${DEFAULT_HUM_OFFSET}]: " HUM_OFFSET
    read -rp "CPU alpha (0-1) [${DEFAULT_CPU_ALPHA}]: " CPU_ALPHA
    read -rp "CPU correction factor [${DEFAULT_CPU_CORR}]: " CPU_CORR
  fi

  : "${MQTT_HOST:=${DEFAULT_MQTT_HOST}}"
  : "${MQTT_PORT:=${DEFAULT_MQTT_PORT}}"
  : "${MQTT_USER:=${DEFAULT_MQTT_USER}}"
  : "${MQTT_PASS:=${DEFAULT_MQTT_PASS}}"
  : "${MQTT_DISCOVERY_PREFIX:=${DEFAULT_DISCOVERY}}"
  : "${POLL:=${DEFAULT_POLL}}"
  : "${TEMP_OFFSET:=${DEFAULT_TEMP_OFFSET}}"
  : "${HUM_OFFSET:=${DEFAULT_HUM_OFFSET}}"
  : "${CPU_ALPHA:=${DEFAULT_CPU_ALPHA}}"
  : "${CPU_CORR:=${DEFAULT_CPU_CORR}}"

  sudo tee "${CFG}" > /dev/null <<EOF
MQTT_HOST="${MQTT_HOST}"
MQTT_PORT="${MQTT_PORT}"
MQTT_USER="${MQTT_USER}"
MQTT_PASS="${MQTT_PASS}"
MQTT_DISCOVERY_PREFIX="${MQTT_DISCOVERY_PREFIX}"
POLL_SEC="${POLL}"
TEMP_OFFSET="${TEMP_OFFSET}"
HUM_OFFSET="${HUM_OFFSET}"
CPU_ALPHA="${CPU_ALPHA}"
CPU_CORRECTION="${CPU_CORR}"
EOF
  sudo chmod 600 "${CFG}"
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
ExecStart=${VENV}/bin/python ${APP_DIR}/enviro_agent.py
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
  echo "==> Installation complete!"
  echo
  echo "Start the service (already running):"
  echo "  sudo systemctl restart ${APP_NAME}.service"
  echo
  echo "Follow logs:"
  echo "  sudo journalctl -u ${APP_NAME} -f"
  echo
  echo "Repository:"
  echo "  https://github.com/JeffLuckett/${APP_NAME}"
}

main() {
  ensure_git
  ensure_python
  clone_or_update
  make_venv
  write_config
  install_service
  start_service
  post_message
  exit 0
}

main "$@"