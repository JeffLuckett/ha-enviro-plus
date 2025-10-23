#!/usr/bin/env bash
set -euo pipefail

APP_NAME="ha-enviro-plus"
APP_DIR="/opt/${APP_NAME}"
VENV_DIR="${APP_DIR}/.venv"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
DEFAULTS="/etc/default/${APP_NAME}"

# Detect the user that should own/run the service
RUN_AS="${SUDO_USER:-$(whoami)}"

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1"; exit 1; }; }

need_cmd sudo
need_cmd python3
need_cmd wget
need_cmd systemctl

echo "==> Installing ${APP_NAME}..."

# Ensure git for first install (your repo clones itself when using the wget installer)
if ! command -v git >/dev/null 2>&1; then
  echo "==> Installing git..."
  sudo apt-get update -y
  sudo apt-get install -y git
fi

# Fresh clone or update to main
if [ -d "${APP_DIR}/.git" ]; then
  echo "==> Updating existing checkout in ${APP_DIR}..."
  sudo git -C "${APP_DIR}" fetch --depth=1 origin main
  sudo git -C "${APP_DIR}" reset --hard origin/main
else
  echo "==> Cloning to ${APP_DIR}..."
  sudo rm -rf "${APP_DIR}"
  sudo git clone --depth=1 https://github.com/JeffLuckett/${APP_NAME}.git "${APP_DIR}"
fi

# Create venv (inside /opt so the service user can use it)
if [ ! -d "${VENV_DIR}" ]; then
  echo "==> Creating virtualenv..."
  sudo python3 -m venv "${VENV_DIR}"
  # Make sure the service user can read/execute it
  sudo chown -R "${RUN_AS}:${RUN_AS}" "${APP_DIR}"
fi

echo "==> Installing Python dependencies..."
sudo -u "${RUN_AS}" "${VENV_DIR}/bin/pip" install --upgrade pip
# Install directly (no requirements.txt dependency)
sudo -u "${RUN_AS}" "${VENV_DIR}/bin/pip" install \
  paho-mqtt==2.* psutil enviroplus

# Create defaults if missing (interactive; safe re-run preserves existing config)
if [ ! -f "${DEFAULTS}" ]; then
  echo "==> Creating new config..."
  read -r -p "MQTT host [homeassistant.local]: " MQTT_HOST
  MQTT_HOST=${MQTT_HOST:-homeassistant.local}
  read -r -p "MQTT port [1883]: " MQTT_PORT
  MQTT_PORT=${MQTT_PORT:-1883}
  read -r -p "MQTT username (blank for none): " MQTT_USER
  read -r -s -p "MQTT password (blank for none): " MQTT_PASS; echo
  read -r -p "MQTT discovery prefix [homeassistant]: " MQTT_DISCOVERY_PREFIX
  MQTT_DISCOVERY_PREFIX=${MQTT_DISCOVERY_PREFIX:-homeassistant}
  read -r -p "Poll interval seconds [2]: " POLL_SEC
  POLL_SEC=${POLL_SEC:-2}
  read -r -p "Initial temperature offset (°C) [0.0]: " TEMP_OFFSET
  TEMP_OFFSET=${TEMP_OFFSET:-0.0}
  read -r -p "Initial humidity offset (%) [0.0]: " HUM_OFFSET
  HUM_OFFSET=${HUM_OFFSET:-0.0}

  sudo tee "${DEFAULTS}" >/dev/null <<EOF
# ${APP_NAME} /etc/default
MQTT_HOST="${MQTT_HOST}"
MQTT_PORT=${MQTT_PORT}
MQTT_USER="${MQTT_USER}"
MQTT_PASS="${MQTT_PASS}"
MQTT_DISCOVERY_PREFIX="${MQTT_DISCOVERY_PREFIX}"
POLL_SEC=${POLL_SEC}
TEMP_OFFSET=${TEMP_OFFSET}
HUM_OFFSET=${HUM_OFFSET}
# Optional: LOG_TO_FILE=1 to write /var/log/${APP_NAME}.log (otherwise journald only)
LOG_TO_FILE=0
EOF
else
  echo "==> Preserving existing ${DEFAULTS}"
fi

echo "==> Writing systemd service..."
sudo tee "${SERVICE_FILE}" >/dev/null <<EOF
[Unit]
Description=Enviro+ → Home Assistant MQTT Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_AS}
Group=${RUN_AS}
EnvironmentFile=${DEFAULTS}
WorkingDirectory=${APP_DIR}
ExecStart=${VENV_DIR}/bin/python ${APP_DIR}/enviro_agent.py
Restart=on-failure
RestartSec=5
# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=false

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${APP_NAME}.service"

echo "==> Installation complete!

Start the service:
  sudo systemctl start ${APP_NAME}.service

Follow logs:
  journalctl -u ${APP_NAME} -f --no-pager
"
exit 0