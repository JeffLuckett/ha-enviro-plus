#!/usr/bin/env python3
"""
ha-enviro-plus v0.1.0
Enviro+ → Home Assistant over MQTT, with HA discovery and control entities.

Sensors:
- BME280: temperature (°C), humidity (%), pressure (hPa)
- LTR559: illuminance (lx)
- Gas (MOX): oxidising/reducing/NH3 in kΩ

Controls/Numbers (HA MQTT Discovery):
- number: temp_offset (°C), hum_offset (%), cpu_alpha (0.0–1.0)
- switch: cpu_correction (on/off)
- button: reboot / restart_service / shutdown

Config via /etc/default/ha-enviro-plus (or env vars).
"""

import os, json, time, socket, logging, subprocess, re, sys
from datetime import datetime, timezone

import psutil
import paho.mqtt.client as mqtt

# Pimoroni libs (installed via enviroplus meta-package)
from bme280 import BME280
from ltr559 import LTR559
from enviroplus import gas

VERSION = "0.1.0"

# ---------- config helpers ----------
def getenv(name, default=None):
    v = os.getenv(name, default)
    return v

MQTT_HOST = getenv("MQTT_HOST", "homeassistant.local")
MQTT_PORT = int(getenv("MQTT_PORT", "1883"))
MQTT_USER = getenv("MQTT_USER", "")
MQTT_PASS = getenv("MQTT_PASS", "")
DISCOVERY = getenv("MQTT_DISCOVERY_PREFIX", "homeassistant")
DEVICE_NAME = getenv("DEVICE_NAME", "Enviro+")
POLL_SEC = float(getenv("POLL_SEC", "2"))

TEMP_OFFSET = float(getenv("TEMP_OFFSET", "0.0"))
HUM_OFFSET  = float(getenv("HUM_OFFSET",  "0.0"))

CPU_CORR_ENABLED = getenv("CPU_CORR_ENABLED", "1") in ("1","true","True","yes","Y","on")
CPU_CORR_ALPHA   = float(getenv("CPU_CORR_ALPHA", "0.20"))

HOSTNAME = socket.gethostname()
ROOT_TOPIC = f"enviro_{re.sub(r'[^0-9A-Za-z]', '', HOSTNAME)}"
AVAIL_TOPIC = f"{ROOT_TOPIC}/status"

DEFAULTS_FILE = "/etc/default/ha-enviro-plus"

# ---------- logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ha-enviro-plus")

# ---------- utilities ----------
def save_defaults(updates: dict):
    """Persist config changes back to /etc/default/ha-enviro-plus."""
    try:
        with open(DEFAULTS_FILE, "r") as f:
            lines = f.readlines()
        kv = {}
        for ln in lines:
            m = re.match(r'^([A-Z0-9_]+)=(.*)$', ln.strip())
            if m:
                kv[m.group(1)] = m.group(2)
        for k, v in updates.items():
            kv[k] = f"\"{v}\"" if isinstance(v, str) else str(v)
        out = []
        for k in sorted(kv.keys()):
            out.append(f"{k}={kv[k]}\n")
        with open(DEFAULTS_FILE, "w") as f:
            f.writelines(out)
        log.info("Saved config updates to %s", DEFAULTS_FILE)
        return True
    except Exception as e:
        log.warning("Failed to save config: %s", e)
        return False

def get_ip():
    # Robust local IPv4 without extra deps
    try:
        import socket as s
        sock = s.socket(s.AF_INET, s.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "unknown"

def cpu_temp_c():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp","r") as f:
            milli = int(f.read().strip())
        return milli / 1000.0
    except Exception:
        return None

# ---------- HA discovery ----------
def disc_sensor(topic_tail, name, unit, device_class=None, state_class="measurement", icon=None, extra=None):
    obj = topic_tail.replace("/", "_")
    cfg = {
        "name": f"{DEVICE_NAME} {name}",
        "uniq_id": f"{ROOT_TOPIC}_{obj}",
        "state_topic": f"{ROOT_TOPIC}/{topic_tail}",
        "availability_topic": AVAIL_TOPIC,
        "device": {
            "identifiers": [ROOT_TOPIC],
            "name": DEVICE_NAME,
            "manufacturer": "Pimoroni",
            "model": "Enviro+",
            "sw_version": f"ha-enviro-plus {VERSION}"
        },
        "unit_of_measurement": unit,
        "state_class": state_class
    }
    if device_class: cfg["device_class"] = device_class
    if icon: cfg["icon"] = icon
    if extra: cfg.update(extra)
    return ("sensor", obj, cfg)

def disc_number(obj, name, unit, minv, maxv, step, state_topic, cmd_topic, icon=None):
    cfg = {
        "name": f"{DEVICE_NAME} {name}",
        "uniq_id": f"{ROOT_TOPIC}_{obj}",
        "availability_topic": AVAIL_TOPIC,
        "state_topic": state_topic,
        "command_topic": cmd_topic,
        "unit_of_measurement": unit,
        "min": minv, "max": maxv, "step": step,
        "device": {
            "identifiers": [ROOT_TOPIC],
            "name": DEVICE_NAME
        }
    }
    if icon: cfg["icon"] = icon
    return ("number", obj, cfg)

def disc_switch(obj, name, state_topic, cmd_topic, icon=None):
    cfg = {
        "name": f"{DEVICE_NAME} {name}",
        "uniq_id": f"{ROOT_TOPIC}_{obj}",
        "availability_topic": AVAIL_TOPIC,
        "state_topic": state_topic,
        "command_topic": cmd_topic,
        "device": {
            "identifiers": [ROOT_TOPIC],
            "name": DEVICE_NAME
        }
    }
    if icon: cfg["icon"] = icon
    return ("switch", obj, cfg)

def disc_button(obj, name, cmd_topic, icon=None):
    cfg = {
        "name": f"{DEVICE_NAME} {name}",
        "uniq_id": f"{ROOT_TOPIC}_{obj}",
        "availability_topic": AVAIL_TOPIC,
        "command_topic": cmd_topic,
        "device": {
            "identifiers": [ROOT_TOPIC],
            "name": DEVICE_NAME
        }
    }
    if icon: cfg["icon"] = icon
    return ("button", obj, cfg)

def publish_discovery(client: mqtt.Client):
    items = []
    # Sensors
    items += [disc_sensor("bme280/temperature", "Temperature", "°C", "temperature")]
    items += [disc_sensor("bme280/humidity",    "Humidity",    "%",   "humidity")]
    items += [disc_sensor("bme280/pressure",    "Pressure",    "hPa", "atmospheric_pressure")]
    items += [disc_sensor("ltr559/lux",         "Illuminance", "lx",  "illuminance")]
    items += [disc_sensor("gas/oxidising",      "Gas Oxidising", "kΩ")]
    items += [disc_sensor("gas/reducing",       "Gas Reducing",  "kΩ")]
    items += [disc_sensor("gas/nh3",            "Gas NH3",       "kΩ")]
    # Meta
    items += [disc_sensor("meta/up_time",       "Up Time", "s")]
    items += [disc_sensor("meta/processor_temp","CPU Temp", "°C", "temperature")]
    items += [disc_sensor("meta/memory_usage",  "Memory Used", "%")]
    items += [disc_sensor("meta/host_name",     "Host Name", None)]
    items += [disc_sensor("meta/network_address","Network Address", None)]
    items += [disc_sensor("meta/os_release",    "OS Release", None)]

    # Controls
    items += [disc_number("temp_offset", "Temp Offset", "°C", -10, 10, 0.1,
                          f"{ROOT_TOPIC}/cfg/temp_offset/state",
                          f"{ROOT_TOPIC}/cfg/temp_offset/set", "mdi:thermometer")]
    items += [disc_number("hum_offset", "Hum Offset", "%", -20, 20, 0.5,
                          f"{ROOT_TOPIC}/cfg/hum_offset/state",
                          f"{ROOT_TOPIC}/cfg/hum_offset/set", "mdi:water-percent")]
    items += [disc_number("cpu_alpha", "CPU Alpha", None, 0.0, 1.0, 0.01,
                          f"{ROOT_TOPIC}/cfg/cpu_alpha/state",
                          f"{ROOT_TOPIC}/cfg/cpu_alpha/set", "mdi:tune")]
    items += [disc_switch("cpu_correction", "CPU Correction",
                          f"{ROOT_TOPIC}/cfg/cpu_correction/state",
                          f"{ROOT_TOPIC}/cfg/cpu_correction/set", "mdi:chip")]

    items += [disc_button("reboot", "Reboot", f"{ROOT_TOPIC}/cmd/reboot", "mdi:restart")]
    items += [disc_button("restart_service", "Restart Agent", f"{ROOT_TOPIC}/cmd/restart_service", "mdi:update")]
    items += [disc_button("shutdown", "Shutdown", f"{ROOT_TOPIC}/cmd/shutdown", "mdi:power")]

    for comp, obj, payload in items:
        topic = f"{DISCOVERY}/{comp}/{ROOT_TOPIC}/{obj}/config"
        client.publish(topic, json.dumps(payload), qos=1, retain=True)

# ---------- MQTT ----------
client = None

def on_connect(client, userdata, flags, reason_code, properties=None):
    log.info("Connected to MQTT (%s:%s) RC=%s", MQTT_HOST, MQTT_PORT, reason_code)
    client.publish(AVAIL_TOPIC, "online", retain=True)
    # subscribe to controls
    subs = [
        f"{ROOT_TOPIC}/cfg/temp_offset/set",
        f"{ROOT_TOPIC}/cfg/hum_offset/set",
        f"{ROOT_TOPIC}/cfg/cpu_alpha/set",
        f"{ROOT_TOPIC}/cfg/cpu_correction/set",
        f"{ROOT_TOPIC}/cmd/reboot",
        f"{ROOT_TOPIC}/cmd/restart_service",
        f"{ROOT_TOPIC}/cmd/shutdown",
    ]
    for t in subs: client.subscribe(t)
    # publish discovery + current config states
    publish_discovery(client)
    publish_config_state()

def publish_config_state():
    client.publish(f"{ROOT_TOPIC}/cfg/temp_offset/state", f"{TEMP_OFFSET}", retain=True)
    client.publish(f"{ROOT_TOPIC}/cfg/hum_offset/state",  f"{HUM_OFFSET}",  retain=True)
    client.publish(f"{ROOT_TOPIC}/cfg/cpu_alpha/state",   f"{CPU_CORR_ALPHA}", retain=True)
    client.publish(f"{ROOT_TOPIC}/cfg/cpu_correction/state", "ON" if CPU_CORR_ENABLED else "OFF", retain=True)

def on_message(client, userdata, msg):
    global TEMP_OFFSET, HUM_OFFSET, CPU_CORR_ALPHA, CPU_CORR_ENABLED
    topic = msg.topic; payload = (msg.payload or b"").decode().strip()
    log.info("MQTT cmd: %s = %s", topic, payload)
    try:
      if topic.endswith("/cfg/temp_offset/set"):
          TEMP_OFFSET = float(payload)
          save_defaults({"TEMP_OFFSET": TEMP_OFFSET})
          client.publish(f"{ROOT_TOPIC}/cfg/temp_offset/state", f"{TEMP_OFFSET}", retain=True)

      elif topic.endswith("/cfg/hum_offset/set"):
          HUM_OFFSET = float(payload)
          save_defaults({"HUM_OFFSET": HUM_OFFSET})
          client.publish(f"{ROOT_TOPIC}/cfg/hum_offset/state", f"{HUM_OFFSET}", retain=True)

      elif topic.endswith("/cfg/cpu_alpha/set"):
          CPU_CORR_ALPHA = max(0.0, min(1.0, float(payload)))
          save_defaults({"CPU_CORR_ALPHA": CPU_CORR_ALPHA})
          client.publish(f"{ROOT_TOPIC}/cfg/cpu_alpha/state", f"{CPU_CORR_ALPHA}", retain=True)

      elif topic.endswith("/cfg/cpu_correction/set"):
          CPU_CORR_ENABLED = payload.upper() in ("ON","TRUE","1","YES")
          save_defaults({"CPU_CORR_ENABLED": "1" if CPU_CORR_ENABLED else "0"})
          client.publish(f"{ROOT_TOPIC}/cfg/cpu_correction/state", "ON" if CPU_CORR_ENABLED else "OFF", retain=True)

      elif topic.endswith("/cmd/reboot"):
          client.publish(AVAIL_TOPIC, "offline", retain=True)
          subprocess.Popen(["/sbin/reboot"])

      elif topic.endswith("/cmd/restart_service"):
          client.publish(AVAIL_TOPIC, "offline", retain=True)
          subprocess.Popen(["/bin/systemctl", "restart", "ha-enviro-plus"])

      elif topic.endswith("/cmd/shutdown"):
          client.publish(AVAIL_TOPIC, "offline", retain=True)
          subprocess.Popen(["/sbin/poweroff"])
    except Exception as e:
      log.warning("Command failed: %s", e)

# ---------- main loop ----------
def main():
    log.info("ha-enviro-plus starting (v%s)", VERSION)
    log.info("Root topic: %s", ROOT_TOPIC)
    log.info("Discovery prefix: %s", DISCOVERY)
    log.info("Poll interval: %ss", POLL_SEC)
    log.info("Initial offsets: TEMP=%s°C HUM=%s%%", TEMP_OFFSET, HUM_OFFSET)

    # init sensors
    bme = BME280(i2c_addr=0x76)
    ltr = LTR559()

    # mqtt
    global client
    client = mqtt.Client(client_id=ROOT_TOPIC, protocol=mqtt.MQTTv5)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.will_set(AVAIL_TOPIC, "offline", retain=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    # Publish discovery & initial states quickly
    time.sleep(1.0)
    publish_config_state()

    try:
        while True:
            # readings
            t_raw = float(round(bme.get_temperature(), 2))
            h_raw = float(round(bme.get_humidity(), 2))
            p     = float(round(bme.get_pressure(), 2))
            lux   = float(round(ltr.get_lux(), 2))

            # CPU correction
            t_corr = t_raw
            if CPU_CORR_ENABLED:
                ct = cpu_temp_c()
                if ct is not None:
                    t_corr = t_raw - ((ct - t_raw) * CPU_CORR_ALPHA)

            # apply offsets
            t = round(t_corr + TEMP_OFFSET, 2)
            h = round(h_raw   + HUM_OFFSET, 2)

            g = gas.read_all()
            ox  = round(g.oxidising / 1000.0, 2)
            red = round(g.reducing  / 1000.0, 2)
            nh3 = round(g.nh3       / 1000.0, 2)

            # meta
            up_seconds = max(0, int(time.time() - psutil.boot_time()))
            cpu_t = cpu_temp_c()
            mem = psutil.virtual_memory().percent
            host = HOSTNAME
            ip   = get_ip()
            osrel = "unknown"
            try:
                with open("/etc/os-release") as f:
                    for ln in f:
                        if ln.startswith("PRETTY_NAME="):
                            osrel = ln.strip().split("=",1)[1].strip('"')
                            break
            except Exception:
                pass

            # publish
            pub = client.publish
            pub(f"{ROOT_TOPIC}/bme280/temperature", str(t), retain=True)
            pub(f"{ROOT_TOPIC}/bme280/humidity",    str(h), retain=True)
            pub(f"{ROOT_TOPIC}/bme280/pressure",    str(p), retain=True)
            pub(f"{ROOT_TOPIC}/ltr559/lux",         str(lux), retain=True)
            pub(f"{ROOT_TOPIC}/gas/oxidising",      str(ox), retain=True)
            pub(f"{ROOT_TOPIC}/gas/reducing",       str(red), retain=True)
            pub(f"{ROOT_TOPIC}/gas/nh3",            str(nh3), retain=True)

            pub(f"{ROOT_TOPIC}/meta/up_time",       str(up_seconds), retain=True)
            if cpu_t is not None:
                pub(f"{ROOT_TOPIC}/meta/processor_temp", f"{round(cpu_t,1)}", retain=True)
            pub(f"{ROOT_TOPIC}/meta/memory_usage",  f"{mem}", retain=True)
            pub(f"{ROOT_TOPIC}/meta/host_name",     host, retain=True)
            pub(f"{ROOT_TOPIC}/meta/network_address", ip, retain=True)
            pub(f"{ROOT_TOPIC}/meta/os_release",    osrel, retain=True)

            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        pass
    finally:
        client.publish(AVAIL_TOPIC, "offline", retain=True)
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()