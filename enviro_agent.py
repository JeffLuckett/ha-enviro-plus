#!/usr/bin/env python3
"""
Enviro+ → Home Assistant MQTT Agent
Publishes Enviro+ and Pi system metrics via MQTT with Home Assistant discovery.
"""

import os, json, time, socket, psutil, subprocess, logging, platform
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from bme280 import BME280
from ltr559 import LTR559
from enviroplus import gas

AGENT_VERSION = "0.1.0"

# ------------------------------------------------------------------
# Configuration from /etc/default/ha-enviro-plus
# ------------------------------------------------------------------
MQTT_HOST  = os.getenv("MQTT_HOST",  "homeassistant.local")
MQTT_PORT  = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER  = os.getenv("MQTT_USER",  "")
MQTT_PASS  = os.getenv("MQTT_PASS",  "")
DEVICE_NAME = os.getenv("DEVICE_NAME", "Enviro+")
POLL_SEC    = float(os.getenv("POLL_SEC", "2"))
TEMP_OFFSET = float(os.getenv("TEMP_OFFSET", "0"))
HUM_OFFSET  = float(os.getenv("HUM_OFFSET", "0"))
CPU_CORRECT = os.getenv("CPU_CORRECT", "true").lower() == "true"
CPU_ALPHA   = float(os.getenv("CPU_ALPHA", "0.6"))
DISCOVERY_PREFIX = os.getenv("MQTT_DISCOVERY_PREFIX", "homeassistant")

# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------
LOG_PATH = "/var/log/ha-enviro-plus.log"
logger = logging.getLogger("ha-enviro-plus")
logger.setLevel(logging.INFO)
fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
fh = logging.FileHandler(LOG_PATH)
fh.setFormatter(fmt)
sh = logging.StreamHandler()
sh.setFormatter(fmt)
logger.addHandler(fh)
logger.addHandler(sh)

logger.info(f"ha-enviro-plus starting (v{AGENT_VERSION})")

# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------
def get_system_info():
    """Return hostname, IP, OS name."""
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "Unknown"

    try:
        ip = socket.gethostbyname(hostname)
    except Exception:
        ip = "Unknown"

    try:
        with open("/etc/os-release") as f:
            os_name = next(
                (line.split("=")[1].strip().strip('"') for line in f if line.startswith("PRETTY_NAME")),
                "Unknown",
            )
    except Exception:
        os_name = "Unknown"

    return hostname, ip, os_name


def get_uptime_human():
    sec = time.time() - psutil.boot_time()
    minutes = int(sec // 60)
    return f"{minutes} min" if minutes < 60 else f"{minutes//60} hr"


def corrected_temp(bme_temp):
    """Optionally correct Enviro+ temp based on CPU heat."""
    if not CPU_CORRECT:
        return bme_temp + TEMP_OFFSET
    try:
        cpu_temp = psutil.sensors_temperatures()["cpu_thermal"][0].current
    except Exception:
        cpu_temp = bme_temp
    smoothed = (CPU_ALPHA * cpu_temp) + ((1 - CPU_ALPHA) * bme_temp)
    return bme_temp - (smoothed - bme_temp) + TEMP_OFFSET


# ------------------------------------------------------------------
# MQTT setup
# ------------------------------------------------------------------
hostname, ip, os_name = get_system_info()
root_topic = f"enviro_{hostname.replace('-', '')}"
availability_topic = f"{root_topic}/status"

SENSORS = {
    "bme280/temperature": ("Temperature", "°C", "temperature"),
    "bme280/humidity": ("Humidity", "%", "humidity"),
    "bme280/pressure": ("Pressure", "hPa", "atmospheric_pressure"),
    "ltr559/lux": ("Illuminance", "lx", "illuminance"),
    "gas/oxidising": ("Gas Oxidising (kΩ)", "kΩ", None),
    "gas/reducing": ("Gas Reducing (kΩ)", "kΩ", None),
    "gas/nh3": ("Gas NH3 (kΩ)", "kΩ", None),
    "sys/uptime": ("Node Uptime", "", None),
    "sys/mem_used": ("Node Memory Used", "%", None),
    "sys/disk_used": ("Node Disk Used", "%", None),
    "sys/cpu_temp": ("Node CPU Temp", "°C", "temperature"),
    "sys/load": ("Node Load Avg (1m)", "", None),
    "sys/ip": ("Network Address", "", None),
    "sys/hostname": ("Host Name", "", None),
    "sys/os": ("OS Release", "", None),
}

def discovery_payload(topic_tail, name, unit, device_class=None):
    return {
        "name": f"{DEVICE_NAME} {name}",
        "uniq_id": f"{root_topic}_{topic_tail.replace('/', '_')}",
        "state_topic": f"{root_topic}/{topic_tail}",
        "availability_topic": availability_topic,
        "device": {
            "identifiers": [root_topic],
            "name": DEVICE_NAME,
            "manufacturer": "Pimoroni",
            "model": "Enviro+ for Raspberry Pi Zero 2W",
            "sw_version": f"ha-enviro-plus v{AGENT_VERSION}",
            "configuration_url": "https://github.com/JeffLuckett/ha-enviro-plus"
        },
        "unit_of_measurement": unit,
        "state_class": "measurement",
        **({"device_class": device_class} if device_class else {})
    }

def publish_discovery(client):
    for topic_tail, (name, unit, dev_class) in SENSORS.items():
        disc_topic = f"{DISCOVERY_PREFIX}/sensor/{root_topic}/{topic_tail.replace('/', '_')}/config"
        client.publish(disc_topic, json.dumps(discovery_payload(topic_tail, name, unit, dev_class)), qos=1, retain=True)
    logger.info("Published discovery payloads")

def read_sensors(bme, ltr):
    t_raw = bme.get_temperature()
    t = round(corrected_temp(t_raw), 2)
    h = round(bme.get_humidity() + HUM_OFFSET, 2)
    p = round(bme.get_pressure(), 2)
    lux = round(ltr.get_lux(), 2)
    g = gas.read_all()
    ox = round(g.oxidising / 1000.0, 2)
    red = round(g.reducing / 1000.0, 2)
    nh3 = round(g.nh3 / 1000.0, 2)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_temp = psutil.sensors_temperatures().get("cpu_thermal", [psutil._common.shwtemp(label="", current=t, high=None, critical=None)])[0].current
    load1 = psutil.getloadavg()[0]
    return {
        "bme280/temperature": t,
        "bme280/humidity": h,
        "bme280/pressure": p,
        "ltr559/lux": lux,
        "gas/oxidising": ox,
        "gas/reducing": red,
        "gas/nh3": nh3,
        "sys/uptime": get_uptime_human(),
        "sys/mem_used": mem.percent,
        "sys/disk_used": disk.percent,
        "sys/cpu_temp": round(cpu_temp, 1),
        "sys/load": round(load1, 2),
        "sys/ip": ip,
        "sys/hostname": hostname,
        "sys/os": os_name,
    }

def on_connect(client, userdata, flags, rc, properties=None):
    client.publish(availability_topic, "online", retain=True)

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    bme = BME280(i2c_addr=0x76)
    ltr = LTR559()

    client = mqtt.Client(client_id=root_topic, protocol=mqtt.MQTTv5)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.will_set(availability_topic, "offline", retain=True)
    client.on_connect = on_connect

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    publish_discovery(client)
    client.publish(availability_topic, "online", retain=True)
    logger.info(f"Root topic: {root_topic}")
    logger.info(f"Discovery prefix: {DISCOVERY_PREFIX}")
    logger.info(f"Poll interval: {POLL_SEC}s")
    logger.info(f"Initial offsets: TEMP={TEMP_OFFSET}°C HUM={HUM_OFFSET}%")

    try:
        while True:
            vals = read_sensors(bme, ltr)
            for topic_tail, val in vals.items():
                client.publish(f"{root_topic}/{topic_tail}", str(val), retain=True)
            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        logger.info("Stopping service (Ctrl+C)")
    finally:
        client.publish(availability_topic, "offline", retain=True)
        client.loop_stop()
        client.disconnect()
        logger.info("Service stopped")

if __name__ == "__main__":
    main()