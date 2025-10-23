#!/usr/bin/env python3
"""
ha-enviro-plus v0.1.0
Enviro+ → Home Assistant MQTT agent

- Publishes Temp/Humidity/Pressure/Lux and Gas (kΩ)
- Home Assistant MQTT Discovery (retained)
- Calibration via MQTT commands (retained offsets)
- Host telemetry (CPU temp/usage, RAM, uptime, hostname, ip)
- Rotating log file (default /var/log/ha-enviro-plus.log)

Configuration:
  /etc/default/ha-enviro-plus  (KEY=VALUE lines)

Environment variables (read from the file above):
  MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS, MQTT_DISCOVERY_PREFIX
  DEVICE_NAME, POLL_SEC
  TEMP_OFFSET_C, HUM_OFFSET_PC
  ROOT_TOPIC  (default: enviro_<hostname-without-dashes>)

Controls (MQTT commands):
  <root>/cmd/restart            → restart agent (systemd)
  <root>/cmd/reboot             → sudo reboot
  <root>/cmd/set_temp_offset    payload: float °C
  <root>/cmd/set_hum_offset     payload: float %
  <root>/cmd/identify           → publish a burst of state

Requires (inside Pimoroni venv or system Python):
  paho-mqtt, enviroplus, pimoroni-bme280, ltr559, psutil
"""
import os, json, time, socket, psutil, subprocess, logging, logging.handlers, shutil
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from bme280 import BME280
from ltr559 import LTR559
from enviroplus import gas

# ---------- CONFIG LOADING ----------
CFG_PATH = "/etc/default/ha-enviro-plus"

def _read_cfg(path):
    cfg = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line=line.strip()
                if not line or line.startswith("#") or "=" not in line: 
                    continue
                k,v = line.split("=",1)
                cfg[k.strip()] = v.strip().strip('"')
    return cfg

_cfg = _read_cfg(CFG_PATH)

MQTT_HOST             = _cfg.get("MQTT_HOST", "homeassistant.local")
MQTT_PORT             = int(_cfg.get("MQTT_PORT", "1883"))
MQTT_USER             = _cfg.get("MQTT_USER", "")
MQTT_PASS             = _cfg.get("MQTT_PASS", "")
MQTT_DISCOVERY_PREFIX = _cfg.get("MQTT_DISCOVERY_PREFIX", "homeassistant")
DEVICE_NAME           = _cfg.get("DEVICE_NAME", "Enviro+")
POLL_SEC              = float(_cfg.get("POLL_SEC", "2"))
TEMP_OFFSET_C         = float(_cfg.get("TEMP_OFFSET_C", "0.0"))
HUM_OFFSET_PC         = float(_cfg.get("HUM_OFFSET_PC", "0.0"))

hostname   = socket.gethostname()
root_topic = _cfg.get("ROOT_TOPIC", f"enviro_{hostname.replace('-', '')}")
availability_topic = f"{root_topic}/status"

# ---------- LOGGING ----------
LOG_PATH = _cfg.get("LOG_PATH", "/var/log/ha-enviro-plus.log")
logger = logging.getLogger("ha-enviro-plus")
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=262144, backupCount=5)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Also log a single line to stdout on start
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(formatter)
logger.addHandler(console)

logger.info("ha-enviro-plus starting (v0.1.0)")

# ---------- DISCOVERY ----------
SENSORS = {
    "bme280/temperature" : ("Temperature", "°C",  "temperature"),
    "bme280/humidity"    : ("Humidity",    "%",   "humidity"),
    "bme280/pressure"    : ("Pressure",    "hPa", "atmospheric_pressure"),
    "ltr559/lux"         : ("Illuminance", "lx",  "illuminance"),
    "gas/oxidising"      : ("Gas Oxidising (kΩ)", "kΩ", None),
    "gas/reducing"       : ("Gas Reducing (kΩ)",  "kΩ", None),
    "gas/nh3"            : ("Gas NH3 (kΩ)",       "kΩ", None),
    "host/cpu_temp"      : ("CPU Temp", "°C", "temperature"),
    "host/cpu_usage"     : ("CPU Usage", "%", "power_factor"),
    "host/ram_used"      : ("RAM Used", "MB", None),
    "host/ram_total"     : ("RAM Total", "MB", None),
    "host/uptime_min"    : ("Uptime", "min", None),
    "host/hostname"      : ("Host Name", None, None),
    "host/ip"            : ("Network Address", None, None),
    "meta/cal_temp"      : ("Temp Offset", "°C", None),
    "meta/cal_hum"       : ("Hum Offset", "%", None),
}

def discovery_payload(topic_tail, name, unit, device_class=None, state_class="measurement", icon=None, extra=None):
    cfg = {
        "name": f"{DEVICE_NAME} {name}" if name else DEVICE_NAME,
        "uniq_id": f"{root_topic}_{topic_tail.replace('/', '_')}",
        "state_topic": f"{root_topic}/{topic_tail}",
        "availability_topic": availability_topic,
        "device": {
            "identifiers": [root_topic],
            "name": DEVICE_NAME,
            "manufacturer": "Pimoroni",
            "model": "Enviro+ (no PMS5003)",
            "sw_version": "ha-enviro-plus 0.1.0"
        },
        "state_class": state_class
    }
    if unit: cfg["unit_of_measurement"] = unit
    if device_class: cfg["device_class"] = device_class
    if icon: cfg["icon"] = icon
    if extra: cfg.update(extra)
    return cfg

def publish_discovery(client):
    for topic_tail, (name, unit, dev_class) in SENSORS.items():
        obj = topic_tail.replace("/", "_")
        disc_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{root_topic}/{obj}/config"
        payload = discovery_payload(topic_tail, name, unit, device_class=dev_class)
        client.publish(disc_topic, json.dumps(payload), qos=1, retain=True)

# ---------- HELPERS ----------
def _cpu_temp():
    try:
        out = subprocess.check_output(["vcgencmd", "measure_temp"], text=True).strip()
        # temp=41.8'C
        return float(out.split("=")[1].split("'")[0])
    except Exception:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return float(f.read().strip()) / 1000.0
        except Exception:
            return float("nan")

def _ip():
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True).strip()
        return out.split()[0] if out else "unknown"
    except Exception:
        return "unknown"

def _hostname():
    return hostname

def read_sensors(bme, ltr, temp_offset, hum_offset):
    t = round(bme.get_temperature() + temp_offset, 2)
    h = round(bme.get_humidity() + hum_offset,    2)
    p = round(bme.get_pressure(),    2)
    lux = round(ltr.get_lux(),        2)
    g  = gas.read_all()
    ox   = round(g.oxidising / 1000.0, 2)
    red  = round(g.reducing  / 1000.0, 2)
    nh3  = round(g.nh3       / 1000.0, 2)
    ram = psutil.virtual_memory()
    uptime_min = round(time.time() / 60.0, 2)
    return {
        "bme280/temperature": t,
        "bme280/humidity":    h,
        "bme280/pressure":    p,
        "ltr559/lux":         lux,
        "gas/oxidising":      ox,
        "gas/reducing":       red,
        "gas/nh3":            nh3,
        "host/cpu_temp":      round(_cpu_temp(),2),
        "host/cpu_usage":     round(psutil.cpu_percent(interval=None),2),
        "host/ram_used":      round((ram.total-ram.available)/1024/1024,1),
        "host/ram_total":     round(ram.total/1024/1024,1),
        "host/uptime_min":    uptime_min,
        "host/hostname":      _hostname(),
        "host/ip":            _ip(),
        "meta/cal_temp":      temp_offset,
        "meta/cal_hum":       hum_offset,
    }

# ---------- MQTT ----------
def on_connect(client, userdata, flags, rc, properties=None):
    logger.info("MQTT connected rc=%s", rc)
    client.publish(availability_topic, "online", retain=True)
    # subscribe to commands
    client.subscribe(f"{root_topic}/cmd/#")

def on_message(client, userdata, msg):
    global TEMP_OFFSET_C, HUM_OFFSET_PC
    topic = msg.topic
    payload = (msg.payload or b"").decode("utf-8").strip()
    logger.info("MQTT cmd: %s -> %s", topic, payload)
    try:
        if topic.endswith("/cmd/restart"):
            client.publish(f"{root_topic}/meta/info", "restarting", retain=False)
            subprocess.Popen(["/bin/systemctl","restart","ha-enviro-plus.service"])
        elif topic.endswith("/cmd/reboot"):
            client.publish(f"{root_topic}/meta/info", "rebooting", retain=False)
            subprocess.Popen(["/sbin/reboot"])
        elif topic.endswith("/cmd/set_temp_offset"):
            TEMP_OFFSET_C = float(payload)
            _persist_offset("TEMP_OFFSET_C", TEMP_OFFSET_C)
        elif topic.endswith("/cmd/set_hum_offset"):
            HUM_OFFSET_PC = float(payload)
            _persist_offset("HUM_OFFSET_PC", HUM_OFFSET_PC)
        elif topic.endswith("/cmd/identify"):
            client.publish(f"{root_topic}/meta/identify", datetime.now(timezone.utc).isoformat(), retain=False)
        else:
            logger.warning("Unknown command topic: %s", topic)
    except Exception as e:
        logger.exception("Command error: %s", e)

def _persist_offset(key, val):
    # atomically update CFG_PATH
    lines = []
    seen = False
    if os.path.exists(CFG_PATH):
        with open(CFG_PATH) as f:
            for line in f:
                if line.startswith(f"{key}="):
                    lines.append(f'{key}="{val}"\n')
                    seen = True
                else:
                    lines.append(line)
    if not seen:
        lines.append(f'{key}="{val}"\n')
    tmp = CFG_PATH + ".tmp"
    with open(tmp,"w") as f:
        f.writelines(lines)
    os.replace(tmp, CFG_PATH)
    logger.info("Persisted %s=%s to %s", key, val, CFG_PATH)

def main():
    logger.info("Root topic: %s", root_topic)
    logger.info("Discovery prefix: %s", MQTT_DISCOVERY_PREFIX)
    logger.info("Poll interval: %ss", POLL_SEC)
    logger.info("Initial offsets: TEMP=%s°C HUM=%s%%", TEMP_OFFSET_C, HUM_OFFSET_PC)

    bme = BME280(i2c_addr=0x76)
    ltr = LTR559()

    client = mqtt.Client(client_id=root_topic, protocol=mqtt.MQTTv5)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.will_set(availability_topic, "offline", retain=True)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    publish_discovery(client)
    client.publish(availability_topic, "online", retain=True)

    try:
        while True:
            vals = read_sensors(bme, ltr, TEMP_OFFSET_C, HUM_OFFSET_PC)
            for topic_tail, value in vals.items():
                client.publish(f"{root_topic}/{topic_tail}", str(value), retain=True)
            client.publish(f"{root_topic}/meta/last_update", datetime.now(timezone.utc).isoformat(), retain=True)
            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        client.publish(availability_topic, "offline", retain=True)
        client.loop_stop()
        client.disconnect()
        logger.info("Stopped")

if __name__ == "__main__":
    main()
