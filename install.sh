#!/usr/bin/env bash
set -euo pipefail

APP_NAME="ha-enviro-plus"
APP_DIR="/opt/${APP_NAME}"
SERVICE="/etc/systemd/system/${APP_NAME}.service"
CFG="/etc/default/${APP_NAME}"
VENV="${APP_DIR}/.venv"

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "✖ Please run as root: sudo bash install.sh"
    exit 1
  fi
}

ensure_git() {
  if ! command -v git >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y git
  fi
}

ensure_python() {
  apt-get update -y
  apt-get install -y python3 python3-venv python3-pip
}

clone_or_update() {
  if [ -d "${APP_DIR}/.git" ]; then
    echo "==> Updating ${APP_NAME} at ${APP_DIR}..."
    git -C "${APP_DIR}" pull --ff-only
  else
    echo "==> Installing ${APP_NAME}..."
    rm -rf "${APP_DIR}"
    git clone https://github.com/JeffLuckett/${APP_NAME}.git "${APP_DIR}"
  fi
}

make_venv() {
  if [ ! -d "${VENV}" ]; then
    python3 -m venv "${VENV}"
  fi
  "${VENV}/bin/pip" install --upgrade pip
  # NOTE: requirements.txt (plural)
  if [ -f "${APP_DIR}/requirements.txt" ]; then
    "${VENV}/bin/pip" install -r "${APP_DIR}/requirements.txt" || echo "⚠ pip install warnings ignored"
  else
    echo "⚠ ${APP_DIR}/requirements.txt not found; skipping dependency install"
  fi
}

write_config() {
  echo "==> Creating new config..."
  mkdir -p "$(dirname "${CFG}")"

  # Defaults (non-interactive safe)
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

  # Interactive if stdin is a TTY
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

  cat > "${CFG}" <<EOF
# ${APP_NAME} configuration
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
  chmod 600 "${CFG}"
}

install_service() {
  echo "==> Installing systemd service..."
  cat > "${SERVICE}" <<EOF
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

# Log to journal; don't fight file perms
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable ${APP_NAME}.service
}

start_service() {
  systemctl restart ${APP_NAME}.service || systemctl start ${APP_NAME}.service
}

post_message() {
  echo "==> Installation complete!"
  echo
  echo "Start the service:"
  echo "  sudo systemctl start ${APP_NAME}.service"
  echo
  echo "Follow logs (journal):"
  echo "  sudo journalctl -u ${APP_NAME} -f"
  echo
  echo "Config file:"
  echo "  ${CFG}"
  echo
  echo "Repository:"
  echo "  https://github.com/JeffLuckett/${APP_NAME}"
}

main() {
  require_root
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