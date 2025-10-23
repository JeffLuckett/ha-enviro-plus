#!/usr/bin/env bash
set -euo pipefail

APP_NAME="ha-enviro-plus"
REPO_URL="${REPO_URL:-https://raw.githubusercontent.com/jeffluckett/ha-enviro-plus/main}"
APP_DIR="/opt/${APP_NAME}"
CFG="/etc/default/${APP_NAME}"
SERVICE="/etc/systemd/system/${APP_NAME}.service"
LOG="/var/log/${APP_NAME}.log"

# Detect target user (who will own files and run the agent)
TARGET_USER="${SUDO_USER:-$(whoami)}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

echo "==> Installing ${APP_NAME} as ${TARGET_USER}"

# Ensure dependencies (runtime + tools)
echo "==> Installing OS dependencies"
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip \
  python3-psutil python3-paho-mqtt python3-numpy \
  git curl ca-certificates

# Prefer Pimoroni venv if present
PIMORONI_VENV="${TARGET_HOME}/.virtualenvs/pimoroni"
VENV="${PIMORONI_VENV}"
if [ ! -d "${VENV}" ]; then
  VENV="${TARGET_HOME}/.virtualenvs/${APP_NAME}"
  echo "==> Creating virtualenv at ${VENV}"
  sudo -u "${TARGET_USER}" python3 -m venv "${VENV}"
fi

PIP="${VENV}/bin/pip"
PY="${VENV}/bin/python"

# Install Python deps in the venv (safe if already satisfied)
echo "==> Installing Python dependencies into ${VENV}"
sudo -u "${TARGET_USER}" "${PIP}" install --upgrade pip
sudo -u "${TARGET_USER}" "${PIP}" install \
  paho-mqtt psutil enviroplus pimoroni-bme280 ltr559

# Create app directory
echo "==> Placing application files into ${APP_DIR}"
sudo mkdir -p "${APP_DIR}"
sudo chown -R "${TARGET_USER}:${TARGET_USER}" "${APP_DIR}"

# Fetch the agent (if running from GitHub), else copy local file if present
if curl -fsSL "${REPO_URL}/enviro_agent.py" -o "${APP_DIR}/enviro_agent.py"; then
  echo "==> Downloaded enviro_agent.py from ${REPO_URL}"
else
  # Fallback to local file (when installing from source)
  if [ -f "./enviro_agent.py" ]; then
    echo "==> Using local enviro_agent.py"
    sudo cp ./enviro_agent.py "${APP_DIR}/enviro_agent.py"
    sudo chown "${TARGET_USER}:${TARGET_USER}" "${APP_DIR}/enviro_agent.py"
  else
    echo "ERROR: Could not obtain enviro_agent.py"; exit 1
  fi
fi
sudo chmod +x "${APP_DIR}/enviro_agent.py"

# Create default config if missing
if [ ! -f "${CFG}" ]; then
  echo "==> Creating config at ${CFG}"
  sudo tee "${CFG}" >/dev/null <<EOF
# ${APP_NAME} configuration
MQTT_HOST="homeassistant.local"
MQTT_PORT="1883"
MQTT_USER="enviro"
MQTT_PASS="changeme"
MQTT_DISCOVERY_PREFIX="homeassistant"

DEVICE_NAME="Enviro+"
POLL_SEC="2.0"

# Calibration offsets
TEMP_OFFSET_C="0.0"
HUM_OFFSET_PC="0.0"

# Root topic (default enviro_<hostname> if empty)
# ROOT_TOPIC=""
# Log file
LOG_PATH="${LOG}"
EOF
fi

# Ensure log exists and is writable
sudo touch "${LOG}"
sudo chown "${TARGET_USER}:${TARGET_USER}" "${LOG}"
sudo chmod 644 "${LOG}"

# Create systemd service
echo "==> Installing systemd service"
sudo tee "${SERVICE}" >/dev/null <<EOF
[Unit]
Description=Enviro+ → Home Assistant MQTT Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${TARGET_USER}
EnvironmentFile=${CFG}
ExecStart=${VENV}/bin/python ${APP_DIR}/enviro_agent.py
Restart=on-failure
RestartSec=5
WorkingDirectory=${APP_DIR}

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${APP_NAME}.service
echo "==> Installation complete."
echo "Now run: sudo systemctl start ${APP_NAME}.service"
echo "Then check logs: tail -f ${LOG}"
