# ha-enviro-plus (v0.1.0)

Enviro+ → Home Assistant MQTT agent for Raspberry Pi (Zero 2 W, 3/4/5).  
Publishes Enviro+ sensor data and Pi host stats, exposes calibration + control via MQTT.

## One‑line install

```bash
bash <(wget -qO- https://raw.githubusercontent.com/jeffluckett/ha-enviro-plus/main/install.sh)
sudo systemctl start ha-enviro-plus.service
tail -f /var/log/ha-enviro-plus.log
```

> The installer prefers the Pimoroni virtualenv at `~/.virtualenvs/pimoroni` if present; otherwise it creates `~/.virtualenvs/ha-enviro-plus`.

## Configuration

File: `/etc/default/ha-enviro-plus`

```ini
MQTT_HOST=homeassistant.local
MQTT_PORT=1883
MQTT_USER=enviro
MQTT_PASS=changeme
MQTT_DISCOVERY_PREFIX=homeassistant

DEVICE_NAME="Enviro+"
POLL_SEC=2.0

TEMP_OFFSET_C=0.0
HUM_OFFSET_PC=0.0

# Optional overrides
# ROOT_TOPIC=enviro_kitchen
# LOG_PATH=/var/log/ha-enviro-plus.log
```

Edit, then `sudo systemctl restart ha-enviro-plus`.

## MQTT Topics

Root: `enviro_<hostname-without-dashes>` by default.

- State topics (retained), e.g. `enviro_zero/bme280/temperature`, `.../ltr559/lux`, `.../gas/nh3`, `.../host/cpu_temp`, `.../meta/last_update`
- Availability: `enviro_zero/status` → `online` / `offline`
- Commands:
  - `.../cmd/restart` (no payload)
  - `.../cmd/reboot` (no payload)
  - `.../cmd/set_temp_offset` (float °C)
  - `.../cmd/set_hum_offset` (float %)
  - `.../cmd/identify` (no payload)

Offsets are persisted into `/etc/default/ha-enviro-plus`.

## Home Assistant

Enable the MQTT integration and make sure the agent can authenticate.  
Entities are auto‑created via MQTT Discovery (`homeassistant/sensor/.../config`).

## Logging

Logs to `/var/log/ha-enviro-plus.log` with rotation (5×256KB).

## Uninstall

```bash
bash <(wget -qO- https://raw.githubusercontent.com/jeffluckett/ha-enviro-plus/main/uninstall.sh)
```

## License

MIT
