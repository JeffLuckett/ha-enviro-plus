#!/usr/bin/env bash
set -euo pipefail
APP_NAME="ha-enviro-plus"
REPO_URL="https://github.com/JeffLuckett/ha-enviro-plus.git"
APP_DIR="/opt/${APP_NAME}"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
CONFIG_FILE="/etc/default/${APP_NAME}"
LOG_FILE="/var/log/${APP_NAME}.log"
VENV_DIR="/home/${USER}/.virtualenvs/pimoroni"

# --- helper functions ---
say() { echo -e "\033[1;36m==> $*\033[0m"; }
warn() { echo -e "\033[1;33m⚠ $*\033[0m"; }
fail() { echo -e "\033[1;31m✖ $*\033[0m"; exit 1; }

sudo_cmd() { if [ "$(id -u)" -ne 0 ]; then sudo "$@"; else "$@"; fi; }

# --- sanity checks ---
cd ~ || fail "Cannot access home directory"
command -v git >/dev/null || sudo_cmd apt-get install -y git
command -v python3 >/dev/null || sudo_cmd apt-get install -y python3
command -v pip3 >/dev/null || sudo_cmd apt-get install -y python3-pip python3-venv

# --- clone or update repo ---
say "Installing ${APP_NAME}..."
if [ -d "$APP_DIR/.git" ]; then
  sudo_cmd git -C "$APP_DIR" pull --ff-only || warn "Could not update repo, continuing..."
else
  sudo_cmd rm -rf "$APP_DIR"
  sudo_cmd git clone "$REPO_URL" "$APP_DIR"
fi
sudo_cmd chown -R "$USER":"$USER" "$APP_DIR"

# --- ensure virtualenv ---
if [ ! -d "$VENV_DIR" ]; then
  say "Creating virtualenv in $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt" >/dev/null || warn "pip install warnings ignored"

# --- config file ---
if [ -f "$CONFIG_FILE" ]; then
  warn "Existing config found at $CONFIG_FILE — preserving."
else
  say "Creating new config..."
  read -rp "MQTT host [homeassistant.local]: " MQTT_HOST
  read -rp "MQTT user [enviro]: " MQTT_USER
  read -rp "MQTT pass [changeme]: " MQTT_PASS
  read -rp "Poll interval seconds [2]: " POLL_SEC
  read -rp "Temp offset (°C) [0.0]: " TEMP_OFFSET
  read -rp "Humidity offset (%) [0.0]: " HUM_OFFSET
  MQTT_HOST=${MQTT_HOST:-homeassistant.local}
  MQTT_USER=${MQTT_USER:-enviro}
  MQTT_PASS=${MQTT_PASS:-changeme}
  POLL_SEC=${POLL_SEC:-2}
  TEMP_OFFSET=${TEMP_OFFSET:-0.0}
  HUM_OFFSET=${HUM_OFFSET:-0.0}

  CFG=$(cat <<EOF
MQTT_HOST='${MQTT_HOST}'
MQTT_PORT='1883'
MQTT_USER='${MQTT_USER}'
MQTT_PASS='${MQTT_PASS}'
POLL_SEC='${POLL_SEC}'
TEMP_OFFSET='${TEMP_OFFSET}'
HUM_OFFSET='${HUM_OFFSET}'
EOF
)
  echo "$CFG" | sudo_cmd tee "$CONFIG_FILE" >/dev/null
fi

# --- systemd service ---
say "Installing systemd service..."
SERVICE_CONTENT="[Unit]
Description=Enviro+ → Home Assistant MQTT Agent
After=network.target

[Service]
User=${USER}
EnvironmentFile=${CONFIG_FILE}
ExecStart=${VENV_DIR}/bin/python ${APP_DIR}/enviro_agent.py
WorkingDirectory=${APP_DIR}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"
echo "$SERVICE_CONTENT" | sudo_cmd tee "$SERVICE_FILE" >/dev/null
sudo_cmd systemctl daemon-reload
sudo_cmd systemctl enable "${APP_NAME}.service"

# --- log file ---
sudo_cmd touch "$LOG_FILE"
sudo_cmd chown "$USER":"$USER" "$LOG_FILE"

say "Installation complete!"
echo
echo "Start the service:"
echo "  sudo systemctl start ${APP_NAME}.service"
echo
echo "Follow logs:"
echo "  tail -f ${LOG_FILE}"
echo
exit 0