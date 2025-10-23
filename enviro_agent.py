#!/usr/bin/env python3
import os, json, time, socket, psutil, subprocess, logging, platform
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from bme280 import BME280
from ltr559 import LTR559
from enviroplus import gas

APP_VER = "v0.1.0"

# ---------- CONFIG from /etc/default/ha-enviro-plus ----------
MQTT_HOST = os.getenv("MQTT_HOST", "homeassistant.local")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_DISCOVERY_PREFIX = os.getenv("MQTT_DISCOVERY_PREFIX", "homeassistant")

POLL_SEC = float(os.getenv("POLL_SEC", "2"))
TEMP_OFFSET = float(os.getenv("TEMP_OFFSET", "0"))
HUM_OFFSET = float(os.getenv("HUM_OFFSET", "0"))

CPU_ALPHA = float(os.getenv("CPU_ALPHA", "0.8"))
CPU_CORRECTION = float(os.getenv("CPU_CORRECTION", "1.5"))
# -------------------------------------------------------------

# ---- Logging to journal (systemd captures stdout/stderr) ----
logger = logging.getLogger("ha-enviro-plus")
logger.setLevel(logging.INFO)
fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
sh = logging.StreamHandler()
sh.setFormatter(fmt)
logger.handlers.clear()
logger.addHandler(sh)
# -------------------------------------------------------------

hostname = socket.gethostname()
ROOT_TOPIC = f"enviro_{hostname.replace('-', '')}"
AVAIL_TOPIC = f"{ROOT_TOPIC}/status"

def _ipv4_prefer_wlan0():
    """Return best IPv4 address (prefer wlan0, else first non-loopback)."""
    try:
        addrs = psutil.net_if_addrs()
        for key in ("wlan0", "wlan1", "eth0", "en0"):
            if key in addrs:
                for a in addrs[key]:
                    if a.family.name == "AF_INET" and a.address != "127.0.0.1":
                        return a.address
        # fallback: first non-loopback anywhere
        for ifname, lst in addrs.items():
            for a in lst:
                if a.family.name == "AF_INET" and a.address != "127.0.0.1":
                    return a.address
    except Exception:
        pass
    return "Unknown"

def discovery_sensor(topic_tail, name, unit, device_class=None, state_class="measurement", icon=None, extra=None):
    cfg = {
        "name": name,
        "uniq_id": f"{ROOT_TOPIC}_{topic_tail.replace('/', '_')}",
        "state_topic": f"{ROOT_TOPIC}/{topic_tail}",
        "availability_topic": AVAIL_TOPIC,
        "device": {
            "identifiers": [ROOT_TOPIC],
            "name": f"Enviro+ ({hostname})",
            "manufacturer": "Pimoroni",
            "model": "Enviro+ (no PMS5003)",
            "sw_version": APP_VER,
            "configuration_url": "https://github.com/JeffLuckett/ha-enviro-plus"
        },
        "unit_of_measurement": unit,
        "state_class": state_class
    }
    if device_class:
        cfg["device_class"] = device_class
    if icon:
        cfg["icon"] = icon
    if extra:
        cfg.update(extra)
    return cfg

SENSORS = {
    "bme280/temperature": ("Temperature", "°C", "temperature"),
    "bme280/humidity":    ("Humidity",    "%",  "humidity"),
    "bme280/pressure":    ("Pressure",    "hPa","atmospheric_pressure"),
    "ltr559/lux":         ("Illuminance", "lx", "illuminance"),
    "gas/oxidising":      ("Gas Oxidising (kΩ)", "kΩ", None),
    "gas/reducing":       ("Gas Reducing (kΩ)",  "kΩ", None),
    "gas/nh3":            ("Gas NH3 (kΩ)",       "kΩ", None),
    # Optional: a human uptime sensor (string)
    "agent/uptime_human": ("Uptime (human)", "",  None),
}

def publish_discovery(client):
    for tail, (name, unit, devclass) in SENSORS.items():
        disc = f"{MQTT_DISCOVERY_PREFIX}/sensor/{ROOT_TOPIC}/{tail.replace('/', '_')}/config"
        payload = discovery_sensor(tail, f"{hostname} {name}", unit, device_class=devclass)
        client.publish(disc, json.dumps(payload), qos=1, retain=True)

def cpu_temperature_c():
    try:
        out = subprocess.check_output(["vcgencmd", "measure_temp"], text=True).strip()
        # e.g. temp=44.5'C
        if "=" in out:
            return float(out.split("=")[1].split("'")[0])
    except Exception:
        pass
    return None

def compensated_temp(raw_c, last_cpu=None):
    """Optional CPU heat compensation (simple exponential smoothing)."""
    cpu_c = cpu_temperature_c()
    if cpu_c is None:
        return raw_c, last_cpu
    if last_cpu is None:
        last_cpu = cpu_c
    cpu_smoothed = (cpu_c * CPU_ALPHA) + (last_cpu * (1.0 - CPU_ALPHA))
    comp = raw_c - ((cpu_smoothed - raw_c) / CPU_CORRECTION)
    return comp, cpu_smoothed

def to_human_duration(seconds):
    seconds = int(max(0, seconds))
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s  = divmod(rem, 60)
    if d:
        return f"{d}d {h:02d}:{m:02d}:{s:02d}"
    return f"{h:02d}:{m:02d}:{s:02d}"

def main():
    logger.info("ha-enviro-plus starting (%s)", APP_VER)
    logger.info("Root topic: %s", ROOT_TOPIC)
    logger.info("Discovery prefix: %s", MQTT_DISCOVERY_PREFIX)
    logger.info("Poll interval: %ss", POLL_SEC)
    logger.info("Initial offsets: TEMP=%s°C HUM=%s%%", TEMP_OFFSET, HUM_OFFSET)

    bme = BME280(i2c_addr=0x76)
    ltr = LTR559()

    client = mqtt.Client(client_id=ROOT_TOPIC, protocol=mqtt.MQTTv5)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.will_set(AVAIL_TOPIC, "offline", retain=True)

    def _on_connect(cl, ud, flags, rc, props=None):
        logger.info("Connected to MQTT (%s:%s) RC=%s", MQTT_HOST, MQTT_PORT, mqtt.connack_string(rc))
        cl.publish(AVAIL_TOPIC, "online", retain=True)
        # subscribe to control topics (reboot, restart, offsets)
        cl.subscribe(f"{ROOT_TOPIC}/control/#", qos=1)

    client.on_connect = _on_connect

    def _on_message(cl, ud, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8", "ignore").strip()
        if topic.endswith("/control/reboot") and payload.lower() == "now":
            logger.warning("Reboot requested via MQTT")
            subprocess.Popen(["sudo", "reboot"])
        elif topic.endswith("/control/restart_service") and payload.lower() == "now":
            logger.warning("Service restart requested via MQTT")
            subprocess.Popen(["sudo", "systemctl", "restart", "ha-enviro-plus.service"])
        elif topic.endswith("/control/temp_offset"):
            try:
                val = float(payload)
                os.environ["TEMP_OFFSET"] = str(val)
                globals()["TEMP_OFFSET"] = val
                cl.publish(f"{ROOT_TOPIC}/agent/controls/temp_offset", str(val), retain=True)
                logger.info("Set temp offset = %s", val)
            except Exception:
                logger.exception("Bad temp_offset: %r", payload)
        elif topic.endswith("/control/hum_offset"):
            try:
                val = float(payload)
                os.environ["HUM_OFFSET"] = str(val)
                globals()["HUM_OFFSET"] = val
                cl.publish(f"{ROOT_TOPIC}/agent/controls/hum_offset", str(val), retain=True)
                logger.info("Set humidity offset = %s", val)
            except Exception:
                logger.exception("Bad hum_offset: %r", payload)

    client.on_message = _on_message

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    publish_discovery(client)

    boot_ts = time.time()
    last_cpu = None

    try:
        while True:
            raw_t = bme.get_temperature()
            t_comp, last_cpu = compensated_temp(raw_t, last_cpu)

            t = round(t_comp + TEMP_OFFSET, 2)
            h = round(bme.get_humidity() + HUM_OFFSET, 2)
            p = round(bme.get_pressure(), 2)
            lux = round(ltr.get_lux(), 2)

            g = gas.read_all()
            ox = round(g.oxidising / 1000.0, 2)
            rd = round(g.reducing  / 1000.0, 2)
            nh = round(g.nh3       / 1000.0, 2)

            # Publish readings
            client.publish(f"{ROOT_TOPIC}/bme280/temperature", str(t), retain=True)
            client.publish(f"{ROOT_TOPIC}/bme280/humidity",    str(h), retain=True)
            client.publish(f"{ROOT_TOPIC}/bme280/pressure",    str(p), retain=True)
            client.publish(f"{ROOT_TOPIC}/ltr559/lux",         str(lux), retain=True)
            client.publish(f"{ROOT_TOPIC}/gas/oxidising",      str(ox), retain=True)
            client.publish(f"{ROOT_TOPIC}/gas/reducing",       str(rd), retain=True)
            client.publish(f"{ROOT_TOPIC}/gas/nh3",            str(nh), retain=True)

            # Meta / attributes
            up_s = int(time.time() - boot_ts)
            client.publish(f"{ROOT_TOPIC}/agent/uptime", str(up_s), retain=True)
            client.publish(f"{ROOT_TOPIC}/agent/uptime_human", to_human_duration(up_s), retain=True)

            client.publish(f"{ROOT_TOPIC}/agent/host_name", hostname, retain=True)
            client.publish(f"{ROOT_TOPIC}/agent/network_address", _ipv4_prefer_wlan0(), retain=True)
            client.publish(f"{ROOT_TOPIC}/agent/os_release", platform.platform(), retain=True)

            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        pass
    finally:
        client.publish(AVAIL_TOPIC, "offline", retain=True)
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()