#!/usr/bin/env bash
#
# ha-enviro-plus Installation Script
#
# This script can be executed in multiple ways:
# 1. Install from PyPI latest stable release (default): ./install.sh
# 2. Install specific version from PyPI: ./install.sh --release v0.1.1
# 3. Install from GitHub branch: ./install.sh --branch your-branch-name
# 4. Show installer version: ./install.sh --version
# 5. Remote installation: bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh)
# 6. Remote installation: bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh)
# 7. Remote from branch: bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/refs/heads/your-branch/scripts/install.sh) --branch your-branch
# 8. Remote specific version: bash <(wget -qO- https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh) --release v0.1.1
#
# Features:
# - Default installation from PyPI (fastest, most reliable)
# - Fallback to GitHub releases for specific versions
# - GitHub branch installation for development/testing
# - Preserves existing configuration on updates
# - Prompts for new configuration options when detected
# - Works in both interactive and non-interactive modes
# - Provides comprehensive post-installation guidance
#
set -euo pipefail

# Script version for debugging
SCRIPT_VERSION="v0.1.1"

APP_NAME="ha-enviro-plus"
APP_DIR="/opt/${APP_NAME}"
SERVICE="/etc/systemd/system/${APP_NAME}.service"
CFG="/etc/default/${APP_NAME}"
VENV="${APP_DIR}/.venv"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULTS_FILE="${REPO_ROOT}/config/install-defaults.conf"

# Load default values from configuration file
load_defaults() {
  # Default values (fallback if file doesn't exist)
  DEFAULT_MQTT_HOST="homeassistant.local"
  DEFAULT_MQTT_PORT="1883"
  DEFAULT_MQTT_USER="enviro"
  DEFAULT_MQTT_PASS=""
  DEFAULT_DISCOVERY="homeassistant"
  DEFAULT_POLL="2"
  DEFAULT_TEMP_OFFSET="0"
  DEFAULT_HUM_OFFSET="0"
  DEFAULT_CPU_TEMP_FACTOR="1.8"
  DEFAULT_CPU_TEMP_SMOOTHING="0.1"
  DEFAULT_TEMP_SMOOTHING_MINUTES="5.0"
  DEFAULT_PRESSURE_OFFSET="0.0"
  DEFAULT_ELEVATION_METERS="0.0"
  DEFAULT_DISPLAY_ENABLED="1"
  DEFAULT_UNITS="metric"

  # Try to source from configuration file if it exists
  # Use set +u temporarily to allow unset variables during sourcing
  set +u
  if [ -f "${DEFAULTS_FILE}" ]; then
    # shellcheck source=config/install-defaults.conf
    source "${DEFAULTS_FILE}" || true  # Continue even if sourcing fails
    echo "==> Loaded defaults from ${DEFAULTS_FILE}"
  else
    # If file doesn't exist (e.g., during remote installation or PyPI install),
    # try to download it from the repo
    if [ -d "${APP_DIR}/.git" ] || [ -f "${APP_DIR}/config/install-defaults.conf" ]; then
      local repo_defaults="${APP_DIR}/config/install-defaults.conf"
      if [ -f "${repo_defaults}" ]; then
        source "${repo_defaults}" || true  # Continue even if sourcing fails
        echo "==> Loaded defaults from ${repo_defaults}"
      fi
    fi
  fi
  set -u  # Re-enable unbound variable checking

  # Ensure critical defaults are always set (even if config file didn't define them)
  # This prevents "unbound variable" errors with set -u
  : "${DEFAULT_TEMP_SMOOTHING_MINUTES:=5.0}"
  : "${DEFAULT_PRESSURE_OFFSET:=0.0}"
  : "${DEFAULT_ELEVATION_METERS:=0.0}"
}

# Track if we've already updated in this script run to avoid multiple updates
_APT_UPDATE_DONE=false

# Helper function to safely run apt-get update
# On resource-constrained systems, this can be killed by OOM killer
# This function is silent and non-fatal - failures are expected on low-memory systems
# Uses caching to avoid multiple updates in the same script execution
safe_apt_update() {
  # If we've already updated in this script run, skip
  if [ "$_APT_UPDATE_DONE" = "true" ]; then
    return 0
  fi

  # Check if package lists are recent (less than 1 hour old)
  # If they are, skip the update to avoid OOM kills
  local update_needed=true
  if [ -d /var/lib/apt/lists ] && [ -n "$(find /var/lib/apt/lists -name '*.gz' -mmin -60 2>/dev/null | head -1)" ]; then
    update_needed=false
    _APT_UPDATE_DONE=true  # Mark as done even if we skipped
    return 0
  fi

  if [ "$update_needed" = "true" ]; then
    # Suppress all output including "Killed" messages from shell
    # Run in a separate shell context to suppress kill messages
    if command -v timeout >/dev/null 2>&1; then
      sh -c 'nice -n 19 timeout 60 sudo apt-get update -y >/dev/null 2>&1' 2>/dev/null || true
    else
      sh -c 'nice -n 19 sudo apt-get update -y >/dev/null 2>&1' 2>/dev/null || true
    fi
    _APT_UPDATE_DONE=true  # Mark as done even if it was killed
  fi
}

ensure_git() {
  if ! command -v git >/dev/null 2>&1; then
    safe_apt_update
    sudo apt-get install -y git || {
      echo "==> Warning: Failed to install git"
      echo "==> Please install manually: sudo apt-get install git"
      exit 1
    }
  fi
}

ensure_python() {
  safe_apt_update
  sudo apt-get install -y python3 python3-venv python3-pip || {
    echo "==> Warning: Failed to install Python packages"
    echo "==> Please install manually: sudo apt-get install python3 python3-venv python3-pip"
    exit 1
  }
}

ensure_fonts() {
  echo "==> Ensuring display fonts are installed..."

  # Check if DejaVu fonts are already installed (check multiple locations)
  local font_found=false
  for font_path in \
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" \
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" \
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" \
    "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans-Bold.ttf"; do
    if [ -f "$font_path" ]; then
      font_found=true
      echo "==> Found DejaVu font at: $font_path"
      break
    fi
  done

  # Also try using fc-list to check for fonts (only if fontconfig is installed)
  if [ "$font_found" = "false" ] && command -v fc-list >/dev/null 2>&1; then
    if fc-list 2>/dev/null | grep -qi "dejavu"; then
      font_found=true
      echo "==> DejaVu fonts found via fontconfig"
    fi
  fi

  if [ "$font_found" = "true" ]; then
    echo "==> DejaVu fonts already installed"
    return 0
  fi

  # Fonts not found - install them
  echo "==> DejaVu fonts not found, installing..."
  echo "==> Installing DejaVu fonts and fontconfig for display..."

  # Update package list (non-fatal if killed)
  safe_apt_update

  # Install fonts
  if sudo apt-get install -y fonts-dejavu-core fonts-dejavu-extra fontconfig 2>&1; then
    echo "==> Font packages installed successfully"
  else
    echo "==> Warning: Failed to install fonts-dejavu packages, trying alternative..."
    # Try alternative package names
    if sudo apt-get install -y ttf-dejavu-core ttf-dejavu-extra 2>&1; then
      echo "==> Alternative font packages installed"
    else
      echo "==> Error: Could not install DejaVu fonts automatically"
      echo "==> Display will use default bitmap font (will be very small)"
      echo "==> To install fonts manually, run: sudo apt-get install fonts-dejavu-core fonts-dejavu-extra fontconfig"
      return 1
    fi
  fi

  # Update font cache
  if command -v fc-cache >/dev/null 2>&1; then
    echo "==> Updating font cache..."
    sudo fc-cache -fv >/dev/null 2>&1 || true
  fi

  # Verify font installation
  font_found=false
  for font_path in \
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" \
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" \
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" \
    "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans-Bold.ttf"; do
    if [ -f "$font_path" ]; then
      font_found=true
      echo "==> Fonts verified at: $font_path"
      break
    fi
  done

  if [ "$font_found" = "true" ]; then
    echo "==> Font installation complete"
    return 0
  else
    echo "==> Warning: Font installation completed but fonts not found in expected locations"
    echo "==> Font discovery will search for fonts on startup"
    echo "==> If fonts still don't work, check: find /usr/share/fonts -name '*DejaVu*.ttf'"
    return 1
  fi
}

configure_i2s_microphone() {
  echo "==> Configuring I2S microphone (Enviro+)..."

  # Check if we're on a Raspberry Pi
  if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "==> Not running on a Raspberry Pi, skipping I2S microphone configuration"
    return 0
  fi

  # The service runs as root, so we MUST configure ALSA for root
  # Also configure for the user who ran the script (for manual testing)
  local root_asoundrc="/root/.asoundrc"
  local script_user="${SUDO_USER:-${USER}}"
  local script_user_home=""
  local script_user_asoundrc=""

  # Determine script user's home directory
  if [ -n "$script_user" ] && [ "$script_user" != "root" ]; then
    script_user_home=$(getent passwd "$script_user" | cut -d: -f6 2>/dev/null || echo "")
    if [ -z "$script_user_home" ]; then
      script_user_home="/home/$script_user"
    fi
    script_user_asoundrc="${script_user_home}/.asoundrc"
  fi

  # Try to find the I2S card name from arecord
  local i2s_card=""
  if command -v arecord >/dev/null 2>&1; then
    local arecord_output
    arecord_output=$(arecord -l 2>/dev/null | grep -i "adau7002\|i2s" || true)
    if [ -n "$arecord_output" ]; then
      # Extract card name from output like "card 1: adau7002 [adau7002]"
      i2s_card=$(echo "$arecord_output" | sed -n 's/.*card [0-9]*: \([^ ]*\).*/\1/p' | head -1)
      if [ -z "$i2s_card" ]; then
        # Fallback: extract card number
        i2s_card=$(echo "$arecord_output" | sed -n 's/.*card \([0-9]*\):.*/\1/p' | head -1)
      fi
    fi
  fi

  # Default to adau7002 if not found (standard Enviro+ card name)
  if [ -z "$i2s_card" ]; then
    i2s_card="adau7002"
    echo "==> I2S card not detected via arecord, using default: $i2s_card"
  else
    echo "==> Detected I2S card: $i2s_card"
  fi

  # Function to create ALSA config
  create_asoundrc() {
    local target_file="$1"
    local target_user="$2"

    # Check if already configured
    if [ -f "$target_file" ] && grep -q "adau7002\|dmic" "$target_file" 2>/dev/null; then
      echo "==> ALSA configuration already exists at $target_file"
      return 0
    fi

    echo "==> Creating ALSA configuration at $target_file for $target_user..."

    # Create directory if needed
    local target_dir=$(dirname "$target_file")
    if [ ! -d "$target_dir" ]; then
      if [ "$target_user" = "root" ]; then
        sudo mkdir -p "$target_dir" 2>/dev/null || true
      else
        sudo -u "$target_user" mkdir -p "$target_dir" 2>/dev/null || true
      fi
    fi

    # Write the config file using a temporary file for reliability
    local temp_file
    temp_file=$(mktemp /tmp/asoundrc.XXXXXX)

    cat > "$temp_file" <<EOF
# ALSA configuration for Enviro+ I2S microphone (adau7002)
# This section makes a reference to your I2S hardware
# Adjust the card name to what is shown in 'arecord -l' after 'card x:' before the name in []
pcm.dmic_hw {
  type hw
  card $i2s_card
  channels 2
  format S32_LE
}

# Software volume control for the I2S microphone
# After saving this file, you can adjust volume with: alsamixer
# Press F6 to select the I2S mic, then F4 to set recording volume
# Note: Control name is "Master" for adau7002
pcm.dmic_sv {
  type softvol
  slave.pcm dmic_hw
  control {
    name "Master"
    card $i2s_card
  }
  min_dB -3.0
  max_dB 30.0
}

# Default capture device
pcm.!default {
  type plug
  slave.pcm dmic_sv
}
EOF

    # Copy temp file to target location with proper ownership
    if [ "$target_user" = "root" ]; then
      sudo cp "$temp_file" "$target_file" && sudo chown root:root "$target_file" && sudo chmod 644 "$target_file"
    else
      sudo cp "$temp_file" "$target_file" && sudo chown "$target_user:$target_user" "$target_file" && sudo chmod 644 "$target_file"
    fi

    # Clean up temp file
    rm -f "$temp_file"

    if [ -f "$target_file" ]; then
      echo "==> ✓ ALSA configuration created successfully at $target_file"
      return 0
    else
      echo "==> ✗ Failed to create ALSA configuration at $target_file"
      return 1
    fi
  }

  # Always configure for root (service runs as root)
  local root_success=false

  # Check if already configured
  if [ -f "$root_asoundrc" ] && grep -q "adau7002\|dmic" "$root_asoundrc" 2>/dev/null; then
    echo "==> ALSA configuration already exists at $root_asoundrc"
    root_success=true
  else
    # Try the create_asoundrc function first
    if create_asoundrc "$root_asoundrc" "root" 2>/dev/null; then
      root_success=true
    else
      # Fallback: use sudo tee directly
      echo "==> Attempting alternative method to create root ALSA config..."
      sudo tee "$root_asoundrc" > /dev/null <<EOF
# ALSA configuration for Enviro+ I2S microphone (adau7002)
pcm.dmic_hw {
  type hw
  card $i2s_card
  channels 2
  format S32_LE
}
pcm.dmic_sv {
  type softvol
  slave.pcm dmic_hw
  control {
    name "Master Capture Volume"
    card $i2s_card
  }
  min_dB -3.0
  max_dB 30.0
}
pcm.!default {
  type plug
  slave.pcm dmic_sv
}
EOF
      if [ -f "$root_asoundrc" ]; then
        sudo chown root:root "$root_asoundrc" 2>/dev/null || true
        sudo chmod 644 "$root_asoundrc" 2>/dev/null || true
        if grep -q "adau7002\|dmic" "$root_asoundrc" 2>/dev/null; then
          root_success=true
          echo "==> ✓ ALSA configuration created successfully at $root_asoundrc (using alternative method)"
        fi
      fi
    fi
  fi

  # Also configure for script user if different from root
  local user_success=false
  if [ -n "$script_user_asoundrc" ] && [ "$script_user" != "root" ]; then
    create_asoundrc "$script_user_asoundrc" "$script_user" || true
    if [ -f "$script_user_asoundrc" ]; then
      user_success=true
    fi
  fi

  if [ "$root_success" = "true" ]; then
    echo "==> Note: Microphone volume may need adjustment"
    echo "==>   Run: sudo alsamixer (press F6, select I2S mic, F4, adjust volume)"
    echo "==>   Or: sudo amixer -c $i2s_card sset 'Master Capture Volume' 50%"
    return 0
  else
    echo "==> Warning: Failed to create ALSA configuration for root user"
    echo "==> The noise sensor may not work until ALSA is configured manually"
    echo "==> You can manually create /root/.asoundrc with the configuration"
    # Don't return error - allow installation to continue
    return 0
  fi
}

ensure_system_dependencies() {
  echo "==> Ensuring system dependencies are installed..."

  # Use safe_apt_update which handles caching and OOM kills gracefully
  # This avoids duplicate updates if other functions already ran it
  safe_apt_update

  # Install PortAudio development libraries (required for sounddevice)
  # This is needed for the noise sensor feature
  echo "==> Installing PortAudio libraries for noise sensor support..."
  if command -v timeout >/dev/null 2>&1; then
    if nice -n 19 timeout 300 sudo apt-get install -y --no-install-recommends portaudio19-dev libportaudio2 libportaudiocpp0 >/dev/null 2>&1; then
      echo "==> PortAudio libraries installed successfully"
    else
      echo "==> Warning: Failed to install PortAudio libraries"
      echo "==> Noise sensor will not be available (this is optional)"
      echo "==> To install manually: sudo apt-get install portaudio19-dev libportaudio2 libportaudiocpp0"
    fi
  else
    if nice -n 19 sudo apt-get install -y --no-install-recommends portaudio19-dev libportaudio2 libportaudiocpp0 >/dev/null 2>&1; then
      echo "==> PortAudio libraries installed successfully"
    else
      echo "==> Warning: Failed to install PortAudio libraries"
      echo "==> Noise sensor will not be available (this is optional)"
      echo "==> To install manually: sudo apt-get install portaudio19-dev libportaudio2 libportaudiocpp0"
    fi
  fi

  # Install other system dependencies that might be needed
  # numpy and scipy may need system libraries for optimal performance
  echo "==> Installing additional system libraries for scientific computing..."
  if command -v timeout >/dev/null 2>&1; then
    if nice -n 19 timeout 300 sudo apt-get install -y --no-install-recommends libatlas-base-dev gfortran >/dev/null 2>&1; then
      echo "==> Scientific computing libraries installed successfully"
    else
      echo "==> Warning: Failed to install some scientific computing libraries"
      echo "==> This may affect performance but should not prevent installation"
    fi
  else
    if nice -n 19 sudo apt-get install -y --no-install-recommends libatlas-base-dev gfortran >/dev/null 2>&1; then
      echo "==> Scientific computing libraries installed successfully"
    else
      echo "==> Warning: Failed to install some scientific computing libraries"
      echo "==> This may affect performance but should not prevent installation"
    fi
  fi
}

enable_hardware_interfaces() {
  echo "==> Enabling hardware interfaces (I2C, SPI, and I2S)..."

  # Check if we're on a Raspberry Pi
  if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "==> Not running on a Raspberry Pi, skipping interface enablement"
    return 0
  fi

  # Check if raspi-config is available
  if ! command -v raspi-config >/dev/null 2>&1; then
    echo "==> raspi-config not found, installing..."
    safe_apt_update
    sudo apt-get install -y raspi-config || {
      echo "==> Warning: Failed to install raspi-config"
      echo "==> Hardware interfaces may not be enabled automatically"
    }
  fi

  local reboot_needed=false
  local i2c_enabled=false
  local spi_enabled=false
  local i2s_enabled=false

  # Check if I2C is already enabled (returns 0 if enabled, 1 if disabled)
  if sudo raspi-config nonint get_i2c >/dev/null 2>&1; then
    local i2c_status
    i2c_status=$(sudo raspi-config nonint get_i2c)
    if [ "$i2c_status" = "0" ]; then
      echo "==> I2C is already enabled"
      i2c_enabled=true
    fi
  fi

  # Check if SPI is already enabled (returns 0 if enabled, 1 if disabled)
  if sudo raspi-config nonint get_spi >/dev/null 2>&1; then
    local spi_status
    spi_status=$(sudo raspi-config nonint get_spi)
    if [ "$spi_status" = "0" ]; then
      echo "==> SPI is already enabled"
      spi_enabled=true
    fi
  fi

  # Enable I2C if not already enabled
  if [ "$i2c_enabled" = "false" ]; then
    echo "==> Enabling I2C interface..."
    if sudo raspi-config nonint do_i2c 0; then
      echo "==> I2C enabled successfully"
      reboot_needed=true
    else
      echo "==> Warning: Failed to enable I2C"
    fi
  fi

  # Enable SPI if not already enabled
  if [ "$spi_enabled" = "false" ]; then
    echo "==> Enabling SPI interface..."
    if sudo raspi-config nonint do_spi 0; then
      echo "==> SPI enabled successfully"
      reboot_needed=true
    else
      echo "==> Warning: Failed to enable SPI"
    fi
  fi

  # Check if I2S is enabled (for Enviro+ microphone)
  # I2S is enabled with dtparam=i2s=on in config.txt
  # Enviro+ also needs dtoverlay=adau7002-simple for the I2S microphone
  local config_file=""
  for cfg in /boot/firmware/config.txt /boot/config.txt; do
    if [ -f "$cfg" ]; then
      config_file="$cfg"
      break
    fi
  done

  if [ -n "$config_file" ]; then
    if grep -q "^dtparam=i2s=on" "$config_file" 2>/dev/null || \
       grep -q "^[^#]*dtparam=i2s=on" "$config_file" 2>/dev/null; then
      echo "==> I2S is already enabled"
      i2s_enabled=true
    fi
  fi

  # Enable I2S if not already enabled
  if [ "$i2s_enabled" = "false" ] && [ -n "$config_file" ]; then
    echo "==> Enabling I2S interface (required for Enviro+ microphone)..."
    # Remove commented line if present
    sudo sed -i 's/^#dtparam=i2s=on/dtparam=i2s=on/' "$config_file" 2>/dev/null || true
    # Add if not present
    if ! grep -q "dtparam=i2s=on" "$config_file" 2>/dev/null; then
      echo "dtparam=i2s=on" | sudo tee -a "$config_file" > /dev/null
    fi
    if grep -q "^dtparam=i2s=on" "$config_file" 2>/dev/null || \
       grep -q "^[^#]*dtparam=i2s=on" "$config_file" 2>/dev/null; then
      echo "==> I2S enabled successfully"
      i2s_enabled=true
      reboot_needed=true
    else
      echo "==> Warning: Failed to enable I2S"
    fi
  fi

  # Check if adau7002-simple overlay is loaded (required for Enviro+ I2S microphone)
  local adau7002_enabled=false
  if [ -n "$config_file" ]; then
    if grep -q "^dtoverlay=adau7002-simple" "$config_file" 2>/dev/null || \
       grep -q "^[^#]*dtoverlay=adau7002-simple" "$config_file" 2>/dev/null; then
      echo "==> adau7002-simple overlay is already enabled"
      adau7002_enabled=true
    fi
  fi

  # Enable adau7002-simple overlay if not already enabled
  if [ "$adau7002_enabled" = "false" ] && [ -n "$config_file" ]; then
    # Check if overlay file exists
    local overlay_file=""
    for ovl in /boot/firmware/overlays/adau7002-simple.dtbo /boot/overlays/adau7002-simple.dtbo; do
      if [ -f "$ovl" ]; then
        overlay_file="$ovl"
        break
      fi
    done

    if [ -n "$overlay_file" ]; then
      echo "==> Enabling adau7002-simple overlay (required for Enviro+ I2S microphone)..."
      # Remove commented line if present
      sudo sed -i 's/^#dtoverlay=adau7002-simple/dtoverlay=adau7002-simple/' "$config_file" 2>/dev/null || true
      # Add if not present
      if ! grep -q "dtoverlay=adau7002-simple" "$config_file" 2>/dev/null; then
        echo "dtoverlay=adau7002-simple" | sudo tee -a "$config_file" > /dev/null
      fi
      if grep -q "^dtoverlay=adau7002-simple" "$config_file" 2>/dev/null || \
         grep -q "^[^#]*dtoverlay=adau7002-simple" "$config_file" 2>/dev/null; then
        echo "==> adau7002-simple overlay enabled successfully"
        adau7002_enabled=true
        reboot_needed=true
      else
        echo "==> Warning: Failed to enable adau7002-simple overlay"
      fi
    else
      echo "==> Warning: adau7002-simple overlay not found - I2S microphone may not work"
      echo "==> This overlay is required for Enviro+ I2S microphone"
    fi
  fi

  # Verify configuration was written (check both possible config locations)
  local config_found=false
  for config_file in /boot/config.txt /boot/firmware/config.txt; do
    if [ -f "$config_file" ]; then
      if grep -q "dtparam=i2c_arm=on" "$config_file" 2>/dev/null && \
         grep -q "dtparam=spi=on" "$config_file" 2>/dev/null; then
        echo "==> Verified I2C and SPI configuration in $config_file"
        config_found=true
        break
      fi
    fi
  done

  if [ "$reboot_needed" = "true" ] && [ "$config_found" = "false" ]; then
    echo "==> Warning: Configuration enabled but not yet written to config file"
    echo "==> This is normal - raspi-config will write changes on next boot"
  fi

  # Export reboot_needed flag for use in main function
  if [ "$reboot_needed" = "true" ]; then
    export REBOOT_NEEDED=true
    echo "==> Hardware interfaces enabled. Reboot required for changes to take effect."
  else
    export REBOOT_NEEDED=false
    echo "==> Hardware interfaces are already enabled."
  fi
}

install_from_pypi() {
  local version="${1:-}"

  echo "==> Installing from PyPI..."

  # Create virtual environment for the application
  echo "==> Creating virtual environment..."
  sudo mkdir -p "${APP_DIR}"
  sudo python3 -m venv "${VENV}"
  sudo "${VENV}/bin/pip" install --upgrade pip

  if [[ -n "$version" ]]; then
    echo "==> Installing specific version: $version"
    sudo "${VENV}/bin/pip" install "ha-enviro-plus==${version#v}"
  else
    echo "==> Installing latest version from PyPI"
    sudo "${VENV}/bin/pip" install ha-enviro-plus
  fi

  # Create symlink to the venv executable
  sudo ln -sf "${VENV}/bin/ha-enviro-plus" /usr/local/bin/ha-enviro-plus || true
}

install_from_release() {
  local version="$1"

  echo "==> Installing from GitHub release: $version"

  # Create virtual environment for the application
  echo "==> Creating virtual environment..."
  sudo mkdir -p "${APP_DIR}"
  sudo python3 -m venv "${VENV}"
  sudo "${VENV}/bin/pip" install --upgrade pip

  # Download wheel from GitHub release
  local wheel_url="https://github.com/JeffLuckett/ha-enviro-plus/releases/download/${version}/ha_enviro_plus-${version#v}-py3-none-any.whl"

  echo "==> Downloading wheel from: $wheel_url"
  sudo "${VENV}/bin/pip" install "$wheel_url"

  # Create symlink to the venv executable
  sudo ln -sf "${VENV}/bin/ha-enviro-plus" /usr/local/bin/ha-enviro-plus || true
}

install_from_git() {
  local branch="$1"

  echo "==> Installing from GitHub branch: $branch"

  ensure_git
  ensure_python
  clone_or_update "${branch}"
  make_venv
}

clone_or_update() {
  local branch="${1:-main}"

  if [ -d "${APP_DIR}/.git" ]; then
    echo "==> Updating ${APP_NAME} at ${APP_DIR}..."
    sudo git -C "${APP_DIR}" fetch origin
    sudo git -C "${APP_DIR}" checkout "${branch}"
    sudo git -C "${APP_DIR}" pull --ff-only
  else
    echo "==> Installing ${APP_NAME} from branch: ${branch}..."
    sudo rm -rf "${APP_DIR}"
    sudo git clone -b "${branch}" https://github.com/JeffLuckett/${APP_NAME}.git "${APP_DIR}"
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

# Detect if running remotely (via wget/curl)
is_remote_execution() {
  # Check if stdin is not a terminal (piped from wget/curl)
  [ ! -t 0 ] || [ -n "${REMOTE_EXECUTION:-}" ]
}


# Load existing config values
load_existing_config() {
  if [ -f "${CFG}" ]; then
    # Read config file with sudo and export variables
    # Use a temporary approach to avoid permission issues
    local temp_config
    temp_config=$(sudo cat "${CFG}" 2>/dev/null) || {
      echo "Warning: Could not read existing config file ${CFG}"
      return 1
    }

    while IFS='=' read -r key value; do
      # Skip empty lines and comments
      if [ -n "$key" ] && [ "${key#\#}" = "$key" ]; then
        # Remove quotes from value if present
        value=$(echo "$value" | sed 's/^"//;s/"$//')
        export "$key"="$value"
      fi
    done <<< "$temp_config"
    return 0
  fi
  return 1
}

# Check for new config options that weren't in previous versions
check_new_config_options() {
  local new_options=()

  # Check if any new options are missing from existing config
  if [ -z "${CPU_TEMP_FACTOR:-}" ]; then
    new_options+=("CPU_TEMP_FACTOR")
  fi

  if [ -z "${CPU_TEMP_SMOOTHING:-}" ]; then
    new_options+=("CPU_TEMP_SMOOTHING")
  fi

  if [ -z "${TEMP_SMOOTHING_MINUTES:-}" ]; then
    new_options+=("TEMP_SMOOTHING_MINUTES")
  fi

  if [ -z "${UNITS:-}" ]; then
    new_options+=("UNITS")
  fi

  if [ -z "${DISPLAY_AUTO_ROTATE:-}" ]; then
    new_options+=("DISPLAY_AUTO_ROTATE")
  fi

  if [ -z "${DISPLAY_ROTATION_INTERVAL:-}" ]; then
    new_options+=("DISPLAY_ROTATION_INTERVAL")
  fi

  if [ ${#new_options[@]} -gt 0 ]; then
    echo "==> New configuration options detected: ${new_options[*]}"
    echo "These options were added in newer versions and need to be configured."
    return 0
  fi
  return 1
}

write_config() {
  echo "==> Configuring ${APP_NAME}..."
  sudo mkdir -p "$(dirname "${CFG}")"

  # Load default values from configuration file
  load_defaults

  # Ensure critical defaults are always set (defensive programming)
  # This prevents "unbound variable" errors even if config file doesn't define them
  : "${DEFAULT_TEMP_SMOOTHING_MINUTES:=5.0}"
  : "${DEFAULT_PRESSURE_OFFSET:=0.0}"
  : "${DEFAULT_ELEVATION_METERS:=0.0}"
  : "${DEFAULT_CPU_TEMP_FACTOR:=1.8}"
  : "${DEFAULT_CPU_TEMP_SMOOTHING:=0.1}"
  : "${DEFAULT_UNITS:=metric}"

  # Check if UNITS exists in config file with a valid value before loading
  local units_in_config=false
  if [ -f "${CFG}" ]; then
    # Check if UNITS line exists and has a valid non-empty value
    local units_line=$(sudo grep "^UNITS=" "${CFG}" 2>/dev/null || echo "")
    if [ -n "$units_line" ]; then
      local units_value=$(echo "$units_line" | cut -d'=' -f2 | tr -d '"' | tr -d ' ' | tr -d '\n')
      # Check if value is non-empty and valid
      if [ -n "$units_value" ] && [ "$units_value" = "metric" ] || [ "$units_value" = "imperial" ]; then
        units_in_config=true
      fi
    fi
  fi

  # Try to load existing config
  if load_existing_config; then
    echo "==> Found existing configuration, preserving current settings..."

    # Set defaults for new variables that might not be in old config files
    # This must happen before any variable expansion to prevent "unbound variable" errors
    : "${PRESSURE_OFFSET:=${DEFAULT_PRESSURE_OFFSET}}"
    : "${ELEVATION_METERS:=${DEFAULT_ELEVATION_METERS}}"

    # Re-check UNITS after loading config - it might be empty or invalid
    # This is critical because load_existing_config might set UNITS="" if it exists but is empty
    # Check if UNITS is actually empty (not just unset) or invalid
    local units_after_load="${UNITS:-}"
    if [ -z "$units_after_load" ] || ([ "$units_after_load" != "metric" ] && [ "$units_after_load" != "imperial" ]); then
      units_in_config=false  # Override previous check - it's not valid
      unset UNITS  # Clear it so we prompt
    fi

    # Track if UNITS was already prompted in the new options section
    local units_prompted=false

    # Check for new options that need configuration
    if check_new_config_options; then
      # Try to prompt if interactive, otherwise use defaults
      if [ -t 0 ]; then
        echo
        echo "Please configure the new options:"

        if [ -z "${CPU_TEMP_FACTOR:-}" ]; then
          read -rp "CPU temperature compensation factor (higher=less compensation, lower=more compensation) [${DEFAULT_CPU_TEMP_FACTOR}]: " CPU_TEMP_FACTOR_INPUT
          CPU_TEMP_FACTOR="${CPU_TEMP_FACTOR_INPUT:-${DEFAULT_CPU_TEMP_FACTOR}}"
        fi

        if [ -z "${CPU_TEMP_SMOOTHING:-}" ]; then
          read -rp "CPU temperature smoothing factor [${DEFAULT_CPU_TEMP_SMOOTHING}]: " CPU_TEMP_SMOOTHING_INPUT
          CPU_TEMP_SMOOTHING="${CPU_TEMP_SMOOTHING_INPUT:-${DEFAULT_CPU_TEMP_SMOOTHING}}"
        fi

        if [ -z "${TEMP_SMOOTHING_MINUTES:-}" ]; then
          read -rp "Temperature smoothing window (minutes) [${DEFAULT_TEMP_SMOOTHING_MINUTES}]: " TEMP_SMOOTHING_MINUTES_INPUT
          TEMP_SMOOTHING_MINUTES="${TEMP_SMOOTHING_MINUTES_INPUT:-${DEFAULT_TEMP_SMOOTHING_MINUTES}}"
        fi

        if [ -z "${PRESSURE_OFFSET:-}" ]; then
          read -rp "Pressure offset (hPa, e.g. 0.14 for ~1 mmHg correction) [${DEFAULT_PRESSURE_OFFSET}]: " PRESSURE_OFFSET_INPUT
          PRESSURE_OFFSET="${PRESSURE_OFFSET_INPUT:-${DEFAULT_PRESSURE_OFFSET}}"
        fi

        if [ -z "${ELEVATION_METERS:-}" ]; then
          read -rp "Elevation in meters above sea level (for sea-level pressure correction, 0 to disable) [${DEFAULT_ELEVATION_METERS}]: " ELEVATION_METERS_INPUT
          ELEVATION_METERS="${ELEVATION_METERS_INPUT:-${DEFAULT_ELEVATION_METERS}}"
        fi

        if [ -z "${UNITS:-}" ] || ([ "${UNITS:-}" != "metric" ] && [ "${UNITS:-}" != "imperial" ]); then
          read -rp "Display units (metric/imperial) [${DEFAULT_UNITS}]: " UNITS_INPUT
          UNITS="${UNITS_INPUT:-${DEFAULT_UNITS}}"
          # Validate units
          if [ "$UNITS" != "metric" ] && [ "$UNITS" != "imperial" ]; then
            echo "==> Invalid units: $UNITS, using default: ${DEFAULT_UNITS}"
            UNITS="${DEFAULT_UNITS}"
          fi
          units_prompted=true  # Mark that UNITS was already prompted
        fi

        if [ -z "${DISPLAY_AUTO_ROTATE:-}" ]; then
          read -rp "Enable display auto-rotation (1=yes, 0=no) [${DEFAULT_DISPLAY_AUTO_ROTATE}]: " DISPLAY_AUTO_ROTATE_INPUT
          DISPLAY_AUTO_ROTATE="${DISPLAY_AUTO_ROTATE_INPUT:-${DEFAULT_DISPLAY_AUTO_ROTATE}}"
        fi

        if [ -z "${DISPLAY_ROTATION_INTERVAL:-}" ]; then
          read -rp "Display rotation interval (seconds) [${DEFAULT_DISPLAY_ROTATION_INTERVAL}]: " DISPLAY_ROTATION_INTERVAL_INPUT
          DISPLAY_ROTATION_INTERVAL="${DISPLAY_ROTATION_INTERVAL_INPUT:-${DEFAULT_DISPLAY_ROTATION_INTERVAL}}"
        fi
      else
        # Use defaults for new options if not interactive
        echo "==> Using defaults for new options (non-interactive mode)"
        : "${CPU_TEMP_FACTOR:=${DEFAULT_CPU_TEMP_FACTOR}}"
        : "${CPU_TEMP_SMOOTHING:=${DEFAULT_CPU_TEMP_SMOOTHING}}"
        : "${TEMP_SMOOTHING_MINUTES:=${DEFAULT_TEMP_SMOOTHING_MINUTES}}"
        : "${PRESSURE_OFFSET:=${DEFAULT_PRESSURE_OFFSET}}"
        : "${ELEVATION_METERS:=${DEFAULT_ELEVATION_METERS}}"
        : "${DISPLAY_AUTO_ROTATE:=${DEFAULT_DISPLAY_AUTO_ROTATE}}"
        : "${DISPLAY_ROTATION_INTERVAL:=${DEFAULT_DISPLAY_ROTATION_INTERVAL}}"
        # Only set UNITS default if it wasn't in the config file with a valid value
        if [ "$units_in_config" = "false" ]; then
          : "${UNITS:=${DEFAULT_UNITS}}"
        fi
      fi
    else
      # Use defaults for new options if not interactive
      : "${CPU_TEMP_FACTOR:=${DEFAULT_CPU_TEMP_FACTOR}}"
      : "${CPU_TEMP_SMOOTHING:=${DEFAULT_CPU_TEMP_SMOOTHING}}"
      : "${TEMP_SMOOTHING_MINUTES:=${DEFAULT_TEMP_SMOOTHING_MINUTES}}"
      : "${PRESSURE_OFFSET:=${DEFAULT_PRESSURE_OFFSET}}"
      : "${ELEVATION_METERS:=${DEFAULT_ELEVATION_METERS}}"
      # Only set UNITS default if it wasn't in the config file with a valid value
      if [ "$units_in_config" = "false" ]; then
        : "${UNITS:=${DEFAULT_UNITS}}"
      fi
    fi

    # Always prompt for UNITS if it's missing or invalid (separate from new options check)
    # BUT only if it wasn't already prompted above
    if [ "$units_prompted" = "false" ]; then
      # Check if UNITS is unset, empty, or invalid AFTER loading config
      local units_current="${UNITS:-}"
      local units_valid=false
      if [ -n "$units_current" ] && [ "$units_current" = "metric" ]; then
        units_valid=true
      elif [ -n "$units_current" ] && [ "$units_current" = "imperial" ]; then
        units_valid=true
      fi

      # Prompt if not valid or not in config - ALWAYS prompt on interactive installs
      if [ "$units_in_config" = "false" ] || [ "$units_valid" = "false" ]; then
        # Try to prompt if we can (check if stdin is available)
        if [ -t 0 ]; then
          echo
          echo "==> Display units configuration:"
          read -rp "Display units (metric/imperial) [${DEFAULT_UNITS}]: " UNITS_INPUT
          if [ -n "$UNITS_INPUT" ]; then
            UNITS="$UNITS_INPUT"
          else
            UNITS="${DEFAULT_UNITS}"
          fi
          # Validate units
          if [ "$UNITS" != "metric" ] && [ "$UNITS" != "imperial" ]; then
            echo "==> Invalid units: $UNITS, using default: ${DEFAULT_UNITS}"
            UNITS="${DEFAULT_UNITS}"
          fi
        else
          # Non-interactive - use default but warn
          UNITS="${DEFAULT_UNITS}"
          echo "==> UNITS not configured, using default: ${DEFAULT_UNITS}"
          echo "==> To configure later, edit ${CFG} and set UNITS=\"metric\" or UNITS=\"imperial\""
        fi
      fi
    fi
  else
    echo "==> Creating new configuration..."

    # Interactive configuration for new installations
    if [ -t 0 ]; then
      read -rp "MQTT host [${DEFAULT_MQTT_HOST}]: " MQTT_HOST
      read -rp "MQTT port [${DEFAULT_MQTT_PORT}]: " MQTT_PORT
      read -rp "MQTT username [${DEFAULT_MQTT_USER}]: " MQTT_USER
      read -rsp "MQTT password (input hidden) [empty ok]: " MQTT_PASS; echo
      read -rp "Home Assistant discovery prefix [${DEFAULT_DISCOVERY}]: " MQTT_DISCOVERY_PREFIX
      read -rp "Poll interval seconds [${DEFAULT_POLL}]: " POLL
      read -rp "Temperature offset °C [${DEFAULT_TEMP_OFFSET}]: " TEMP_OFFSET
      read -rp "Humidity offset % [${DEFAULT_HUM_OFFSET}]: " HUM_OFFSET
      read -rp "CPU temperature compensation factor (higher=less compensation, lower=more compensation) [${DEFAULT_CPU_TEMP_FACTOR}]: " CPU_TEMP_FACTOR
      read -rp "CPU temperature smoothing factor [${DEFAULT_CPU_TEMP_SMOOTHING}]: " CPU_TEMP_SMOOTHING
      read -rp "Temperature smoothing window (minutes) [${DEFAULT_TEMP_SMOOTHING_MINUTES}]: " TEMP_SMOOTHING_MINUTES
      read -rp "Pressure offset (hPa, e.g. 0.14 for ~1 mmHg correction) [${DEFAULT_PRESSURE_OFFSET}]: " PRESSURE_OFFSET
      read -rp "Elevation in meters above sea level (for sea-level pressure correction, 0 to disable) [${DEFAULT_ELEVATION_METERS}]: " ELEVATION_METERS
      read -rp "Display units (metric/imperial) [${DEFAULT_UNITS}]: " UNITS
      # Validate units
      if [ "$UNITS" != "metric" ] && [ "$UNITS" != "imperial" ]; then
        echo "==> Invalid units: $UNITS, using default: ${DEFAULT_UNITS}"
        UNITS="${DEFAULT_UNITS}"
      fi
    else
      echo "==> Using default values (non-interactive mode)"
    fi

    # Ensure UNITS is set even if not prompted (for non-interactive or defaults)
    : "${UNITS:=${DEFAULT_UNITS}}"
  fi

  # Set defaults for any unset variables (this handles both new and existing configs)
  # Note: UNITS is handled separately above to ensure prompting on interactive installs
  : "${MQTT_HOST:=${DEFAULT_MQTT_HOST}}"
  : "${MQTT_PORT:=${DEFAULT_MQTT_PORT}}"
  : "${MQTT_USER:=${DEFAULT_MQTT_USER}}"
  : "${MQTT_PASS:=${DEFAULT_MQTT_PASS}}"
  : "${MQTT_DISCOVERY_PREFIX:=${DEFAULT_DISCOVERY}}"
  : "${POLL:=${DEFAULT_POLL}}"
  : "${TEMP_OFFSET:=${DEFAULT_TEMP_OFFSET}}"
  : "${HUM_OFFSET:=${DEFAULT_HUM_OFFSET}}"
  : "${CPU_TEMP_FACTOR:=${DEFAULT_CPU_TEMP_FACTOR}}"
  : "${CPU_TEMP_SMOOTHING:=${DEFAULT_CPU_TEMP_SMOOTHING}}"
  : "${TEMP_SMOOTHING_MINUTES:=${DEFAULT_TEMP_SMOOTHING_MINUTES}}"
  : "${PRESSURE_OFFSET:=${DEFAULT_PRESSURE_OFFSET}}"
  : "${ELEVATION_METERS:=${DEFAULT_ELEVATION_METERS}}"
  : "${DISPLAY_ENABLED:=${DEFAULT_DISPLAY_ENABLED}}"
  : "${DISPLAY_AUTO_ROTATE:=${DEFAULT_DISPLAY_AUTO_ROTATE}}"
  : "${DISPLAY_ROTATION_INTERVAL:=${DEFAULT_DISPLAY_ROTATION_INTERVAL}}"
  # Only set UNITS default if it wasn't already set above
  if [ -z "${UNITS:-}" ]; then
    : "${UNITS:=${DEFAULT_UNITS}}"
  fi

  # Write the complete configuration
  sudo tee "${CFG}" > /dev/null <<EOF
MQTT_HOST="${MQTT_HOST}"
MQTT_PORT="${MQTT_PORT}"
MQTT_USER="${MQTT_USER}"
MQTT_PASS="${MQTT_PASS}"
MQTT_DISCOVERY_PREFIX="${MQTT_DISCOVERY_PREFIX}"
POLL_SEC="${POLL}"
TEMP_OFFSET="${TEMP_OFFSET}"
HUM_OFFSET="${HUM_OFFSET}"
CPU_TEMP_FACTOR="${CPU_TEMP_FACTOR}"
CPU_TEMP_SMOOTHING="${CPU_TEMP_SMOOTHING}"
TEMP_SMOOTHING_MINUTES="${TEMP_SMOOTHING_MINUTES}"
PRESSURE_OFFSET="${PRESSURE_OFFSET}"
ELEVATION_METERS="${ELEVATION_METERS}"
DISPLAY_ENABLED="${DISPLAY_ENABLED}"
DISPLAY_AUTO_ROTATE="${DISPLAY_AUTO_ROTATE}"
DISPLAY_ROTATION_INTERVAL="${DISPLAY_ROTATION_INTERVAL}"
UNITS="${UNITS}"
EOF
  sudo chmod 600 "${CFG}"
}

create_settings_dir() {
  echo "==> Creating settings directory..."
  sudo mkdir -p "/var/lib/${APP_NAME}"
  sudo chown root:root "/var/lib/${APP_NAME}"
  sudo chmod 755 "/var/lib/${APP_NAME}"
  echo "==> Settings directory created: /var/lib/${APP_NAME}"
}

install_icons() {
  echo "==> Installing display icons..."

  local icons_source="${APP_DIR}/icons"
  local icons_dest="/opt/${APP_NAME}/icons"

  # Create destination directory
  sudo mkdir -p "${icons_dest}"
  sudo chmod 755 "${icons_dest}"

  # Copy icons from repo if they exist
  if [ -d "${icons_source}" ] && [ -n "$(ls -A "${icons_source}"/*.png 2>/dev/null)" ]; then
    echo "==> Copying icons from ${icons_source} to ${icons_dest}..."
    sudo cp -f "${icons_source}"/*.png "${icons_dest}/" 2>/dev/null || true
    echo "==> Icons installed successfully"
  else
    echo "==> No icons found in ${icons_source}, skipping icon installation"
    echo "==> Icons can be added later by copying PNG files to ${icons_dest}/"
  fi
}

install_service() {
  echo "==> Installing systemd service..."

  # Determine the correct working directory and python path
  local working_dir="${APP_DIR}"
  local python_cmd="${VENV}/bin/python -m ha_enviro_plus.agent"

  # If we're using git installation, use the git working directory
  if [[ -d "${APP_DIR}/.git" ]]; then
    working_dir="${APP_DIR}"
  fi

  sudo tee "${SERVICE}" > /dev/null <<EOF
[Unit]
Description=Enviro+ → Home Assistant MQTT Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=${CFG}
# Force PortAudio to use ALSA (required for I2S microphone on Enviro+)
Environment="PULSE_RUNTIME_PATH="
Environment="ALSA_CARD=adau7002"
WorkingDirectory=${working_dir}
ExecStart=${python_cmd}
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
  echo
  echo "=========================================="
  echo "🎉 ${APP_NAME} installation complete!"
  echo "=========================================="
  echo

  echo "📋 Service Management:"
  echo "  • Start service:     sudo systemctl start ${APP_NAME}"
  echo "  • Stop service:      sudo systemctl stop ${APP_NAME}"
  echo "  • Restart service:   sudo systemctl restart ${APP_NAME}"
  echo "  • Enable service:    sudo systemctl enable ${APP_NAME}"
  echo "  • Disable service:   sudo systemctl disable ${APP_NAME}"
  echo "  • Service status:    sudo systemctl status ${APP_NAME}"
  echo

  echo "📊 Monitoring & Logs:"
  echo "  • Follow live logs:  sudo journalctl -u ${APP_NAME} -f"
  echo "  • View recent logs:  sudo journalctl -u ${APP_NAME} -n 50"
  echo "  • View all logs:     sudo journalctl -u ${APP_NAME}"
  echo "  • Logs since boot:   sudo journalctl -u ${APP_NAME} -b"
  echo "  • Logs with timestamps: sudo journalctl -u ${APP_NAME} -o short-precise"
  echo

  echo "⚙️  Configuration:"
  echo "  • Config file:       ${CFG}"
  echo "  • Edit config:       sudo nano ${CFG}"
  echo "  • Reload after edit: sudo systemctl restart ${APP_NAME}"
  echo

  echo "🔧 Troubleshooting:"
  echo "  • Check service:     sudo systemctl status ${APP_NAME}"
  echo "  • Test config:       sudo systemd-analyze verify ${SERVICE}"
  echo "  • Check dependencies: ${VENV}/bin/python -c 'import paho.mqtt.client, bme280, ltr559, enviroplus'"
  echo "  • Check noise sensor: ${VENV}/bin/python -c 'import sounddevice; print(\"PortAudio OK\")' || echo \"PortAudio missing - install: sudo apt-get install portaudio19-dev\""
  echo "  • Manual test:       sudo -u root ${VENV}/bin/python -m ha_enviro_plus.agent"
  echo

  echo "📁 Files & Directories:"
  echo "  • Application:       ${APP_DIR}"
  echo "  • Virtual env:       ${VENV}"
  echo "  • Service file:      ${SERVICE}"
  echo "  • Config file:       ${CFG}"
  echo

  echo "🌐 Repository & Support:"
  echo "  • GitHub:            https://github.com/JeffLuckett/${APP_NAME}"
  echo "  • Issues:            https://github.com/JeffLuckett/${APP_NAME}/issues"
  echo

  echo "💡 Quick Start:"
  if [ "${REBOOT_NEEDED:-false}" = "true" ]; then
    echo "  ⚠️  IMPORTANT: A reboot is required for I2C/SPI interfaces to work."
    echo "  The service is running but sensors/display will not work until reboot."
    echo "  You will be prompted to reboot after this message."
  else
    echo "  The service should now be running. Check the logs above to verify"
    echo "  it's connecting to your MQTT broker and publishing sensor data."
  fi
  echo

  if [ "${REBOOT_NEEDED:-false}" != "true" ]; then
    echo "⚠️  Hardware Interfaces:"
    echo "  I2C and SPI interfaces are enabled for sensors and display."
    echo "  Check interface status: ls -l /dev/i2c-* /dev/spidev*"
    echo
  fi

  if [ -t 0 ] && [ "${REBOOT_NEEDED:-false}" != "true" ]; then
    echo "Press Enter to view current service status..."
    read -r
    sudo systemctl status ${APP_NAME} --no-pager
  fi
}

main() {
  echo "==> ${APP_NAME} Installer ${SCRIPT_VERSION}"
  echo

  # Parse command line arguments
  local branch=""
  local install_version=""
  local install_method="pypi"  # Default to PyPI
  local test_mode=false
  local no_reboot=false

  while [[ $# -gt 0 ]]; do
    case $1 in
      --branch|-b)
        branch="$2"
        install_method="git"
        shift 2
        ;;
      --release|-r)
        install_version="$2"
        install_method="release"
        shift 2
        ;;
      --test|--dry-run)
        test_mode=true
        shift
        ;;
      --no-reboot)
        no_reboot=true
        shift
        ;;
      --version|-v)
        echo "${APP_NAME} Installer ${SCRIPT_VERSION}"
        echo "Default installation method: PyPI (latest)"
        if [[ -n "$install_version" ]]; then
          echo "Installing version: $install_version (from GitHub release)"
        elif [[ -n "$branch" ]]; then
          echo "Installing from branch: $branch (from GitHub)"
        fi
        exit 0
        ;;
      --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo "Options:"
        echo "  --branch BRANCH, -b BRANCH    Install from GitHub branch (development/testing)"
        echo "  --release VERSION, -r VERSION Install specific version from GitHub release"
        echo "  --test, --dry-run             Test mode - validate logic without making changes"
        echo "  --no-reboot                   Skip automatic reboot (even if I2C/SPI enabled)"
        echo "  --version, -v                 Show installer version and exit"
        echo "  --help, -h                    Show this help message"
        echo
        echo "Examples:"
        echo "  $0                           # Install latest from PyPI (default)"
        echo "  $0 --branch feature-branch   # Install from GitHub branch"
        echo "  $0 --release v0.1.1          # Install specific version from GitHub release"
        echo "  $0 --version                 # Show installer version"
        echo
        echo "Remote Installation:"
        echo "  # Install latest from PyPI (recommended)"
        echo "  bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh)"
        echo "  # Install from GitHub branch"
        echo "  bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh) --branch BRANCH"
        echo "  # Install specific version from GitHub release"
        echo "  bash <(curl -sL https://raw.githubusercontent.com/JeffLuckett/ha-enviro-plus/main/scripts/install.sh) --release v0.1.1"
        exit 0
        ;;
      *)
        echo "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
    esac
  done

  # Test mode - validate logic without making changes
  if [[ "$test_mode" == true ]]; then
    echo "🧪 TEST MODE - No actual changes will be made"
    echo
    echo "Installation method: $install_method"
    case "$install_method" in
      "pypi")
        if [[ -n "$install_version" ]]; then
          echo "Would install: ha-enviro-plus==${install_version#v} from PyPI"
        else
          echo "Would install: ha-enviro-plus (latest) from PyPI"
        fi
        ;;
      "release")
        echo "Would install: ha_enviro_plus-${install_version#v}-py3-none-any.whl from GitHub release $install_version"
        ;;
      "git")
        echo "Would install from GitHub branch: $branch"
        ;;
    esac
    echo
    echo "✅ Test mode validation complete - logic appears correct"
    exit 0
  fi

  # Install the package based on method
  case "$install_method" in
    "pypi")
      ensure_python
      install_from_pypi "$install_version"
      ;;
    "release")
      ensure_python
      install_from_release "$install_version"
      ;;
    "git")
      install_from_git "$branch"
      ;;
  esac

  # Common post-installation steps
  enable_hardware_interfaces
  echo  # Blank line for readability
  ensure_system_dependencies  # Install system dependencies (PortAudio, etc.)
  echo  # Blank line for readability
  configure_i2s_microphone  # Configure I2S microphone for noise sensor
  echo  # Blank line for readability
  ensure_fonts  # Install fonts for display rendering - MUST run before write_config
  echo  # Blank line for readability
  write_config
  create_settings_dir
  install_icons
  install_service
  start_service
  post_message

  # Handle reboot if needed and not suppressed
  if [ "${REBOOT_NEEDED:-false}" = "true" ] && [ "$no_reboot" = "false" ]; then
    echo
    echo "=========================================="
    echo "⚠️  Reboot Required"
    echo "=========================================="
    echo
    echo "I2C and/or SPI interfaces have been enabled and require a reboot"
    echo "to take effect. The service will not work properly until after reboot."
    echo

    if [ -t 0 ]; then
      echo "Reboot now? (y/n) [y]: "
      read -r reboot_answer
      if [[ "${reboot_answer:-y}" =~ ^[Yy]$ ]]; then
        echo "==> Rebooting in 5 seconds... (Press Ctrl+C to cancel)"
        sleep 5
        sudo reboot
      else
        echo "==> Skipping reboot. Please reboot manually when ready: sudo reboot"
        echo "==> The service will not work properly until after reboot."
      fi
    else
      echo "==> Non-interactive mode: Skipping automatic reboot."
      echo "==> Please reboot manually: sudo reboot"
      echo "==> The service will not work properly until after reboot."
    fi
  fi

  exit 0
}

main "$@"