#!/usr/bin/env bash
set -euo pipefail

# ========== COLORS ==========
if [ -t 1 ]; then
  C_RESET="\033[0m"; C_BOLD="\033[1m"
  C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"; C_BLUE="\033[34m"
else
  C_RESET=""; C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BLUE=""
fi
info(){ echo -e "${C_BLUE}➜${C_RESET} $*"; }
good(){ echo -e "${C_GREEN}✔${C_RESET} $*"; }
warn(){ echo -e "${C_YELLOW}⚠${C_RESET} $*"; }
err(){  echo -e "${C_RED}✖${C_RESET} $*"; }

# ========== META ==========
APP_NAME="ha-enviro-plus"
REPO_URL="https://github.com/JeffLuckett/${APP_NAME}.git"
APP_DIR="/opt/${APP_NAME}"
VENV_DIR="${APP_DIR}/.venv"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
DEFAULTS_FILE="/etc/default/${APP_NAME}"
LOG_FILE="/var/log/${APP_NAME}.log"
LOGROTATE_FILE="/etc/logrotate.d/${APP_NAME}"
VERSION="v0.1.0"
SELECTED_VERSION="${1:-latest}"

# ========== PRECHECKS ==========
if [ "${EUID}" -ne 0 ]; then
  err "Please run as root: sudo bash install.sh"
  exit 1
fi

command -v git >/dev/null 2>&1 || { apt-get update -y && apt-get install -y git; }
command -v python3 >/dev/null 2>&1 || { apt-get install -y python3 python3-venv python3-pip; }

mkdir -p /tmp/${APP_NAME}
cd /tmp/${APP_NAME}

# ========== FETCH SOURCE ==========
info "Fetching ${APP_NAME} source..."
if [ "${SELECTED_VERSION}" = "--version" ]; then
  shift
  SELECTED_VERSION="${1:-latest}"
fi

# Determine branch/tag
TAG_TO_CLONE="main"
if [ "${SELECTED_VERSION}" != "latest" ]; then
  TAG_TO_CLONE="${SELECTED_VERSION}"
else
  LATEST_TAG=$(git ls-remote --tags --sort=v:refname ${REPO_URL} | tail -n1 | sed 's/.*\///')
  TAG_TO_CLONE="${LATEST_TAG:-main}"
fi

info "Installing ${C_BOLD}${APP_NAME}${C_RESET} ${C_YELLOW}${TAG_TO_CLONE}${C_RESET}"

rm -rf ${APP_DIR}
git clone --depth 1 --branch "${TAG_TO_CLONE}" "${REPO_URL}" "${APP_DIR}" >/dev/null 2>&1
cd "${APP_DIR}"

# ========== BACKUP CONFIG IF PRESENT ==========
if [ -f "${DEFAULTS_FILE}" ]; then
  TS=$(date +%Y%m%d-%H%M%S)
  cp "${DEFAULTS_FILE}" "${DEFAULTS_FILE}.bak.${TS}"
  good "Existing config backed up (${TS})"
  EXISTING_CONFIG=1
else
  EXISTING_CONFIG=0
fi

# ========== INTERACTIVE CONFIG CREATION ==========
if [ "${EXISTING_CONFIG}" -eq 0 ]; then
  echo
  echo -e "${C_BOLD}ha-enviro-plus setup${C_RESET}"

  prompt() {
    local var="$1" prompt="$2" def="$3" secret="${4:-0}"
    local val
    if [ "$secret" = "1" ]; then
      read -rp "$(echo -e "${C_BOLD}${prompt}${C_RESET} [default: ${def}]: ")" -s val; echo
    else
      read -rp "$(echo -e "${C_BOLD}${prompt}${C_RESET} [default: ${def}]: ")" val
    fi
    val="${val:-$def}"
    printf "%s" "$val"
  }

  MQTT_HOST=$(prompt MQTT_HOST "MQTT host" "homeassistant.local")
  MQTT_PORT=$(prompt MQTT_PORT "MQTT port" "1883")
  MQTT_USER=$(prompt MQTT_USER "MQTT username" "enviro")
  MQTT_PASS=$(prompt MQTT_PASS "MQTT password" "" 1)
  DISCOVERY=$(prompt MQTT_DISC "MQTT discovery prefix" "homeassistant")
  DEVICE_NAME=$(prompt DEVICE_NAME "Device name (shown in HA)" "Enviro+")
  POLL_SEC=$(prompt POLL_SEC "Poll interval seconds" "2")
  TEMP_OFFSET=$(prompt TEMP_OFFSET "Initial temperature offset (°C)" "0.0")
  HUM_OFFSET=$(prompt HUM_OFFSET "Initial humidity offset (%)" "0.0")
  CPU_CORR=$(prompt CPU_CORR "Enable CPU-temp correction? (y/n)" "y")
  CPU_CORR_ALPHA=$(prompt CPU_ALPHA "CPU correction alpha (0.0–1.0)" "0.2")

  if [[ "$CPU_CORR" =~ ^[Yy]$ ]]; then CPU_CORR="1"; else CPU_CORR="0"; fi

  info "Writing config to ${DEFAULTS_FILE}"
  cat > "${DEFAULTS_FILE}" <<EOF
MQTT_HOST="${MQTT_HOST}"
MQTT_PORT="${MQTT_PORT}"
MQTT_USER="${MQTT_USER}"
MQTT_PASS="${MQTT_PASS}"
MQTT_DISCOVERY_PREFIX="${DISCOVERY}"
DEVICE_NAME="${DEVICE_NAME}"
POLL_SEC="${POLL_SEC}"
TEMP_OFFSET="${TEMP_OFFSET}"
HUM_OFFSET="${HUM_OFFSET}"
CPU_CORR_ENABLED="${CPU_CORR}"
CPU_CORR_ALPHA="${CPU_CORR_ALPHA}"
EOF
  chmod 600 "${DEFAULTS_FILE}"
else
  warn "Existing configuration preserved."
fi

# ========== PYTHON ENV ==========
info "Setting up Python environment..."
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip >/dev/null
pip install --no-cache-dir enviroplus paho-mqtt psutil >/dev/null
deactivate
good "Python venv ready."

# ========== LOG ROTATION ==========
if [ ! -f "${LOGROTATE_FILE}" ]; then
  info "Configuring log rotation..."
  cat > "${LOGROTATE_FILE}" <<EOF
${LOG_FILE} {
  weekly
  rotate 4
  compress
  missingok
  notifempty
  copytruncate
}
EOF
fi

# ========== SYSTEMD SERVICE ==========
info "Creating systemd service..."
cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Enviro+ → Home Assistant MQTT Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=${DEFAULTS_FILE}
WorkingDirectory=${APP_DIR}
ExecStart=${VENV_DIR}/bin/python ${APP_DIR}/enviro_agent.py
Restart=on-failure
RestartSec=5
StandardOutput=append:${LOG_FILE}
StandardError=append:${LOG_FILE}
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${APP_NAME}.service" >/dev/null

# ========== RESTART SERVICE ==========
if systemctl is-active --quiet "${APP_NAME}.service"; then
  info "Restarting service..."
  systemctl restart "${APP_NAME}.service"
else
  info "Starting service..."
  systemctl start "${APP_NAME}.service"
fi

good "${APP_NAME} ${TAG_TO_CLONE} installed successfully!"
info "Logs: sudo journalctl -u ${APP_NAME} -n 50 --no-pager"
info "Config: ${DEFAULTS_FILE}"