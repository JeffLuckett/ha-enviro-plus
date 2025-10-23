
#!/usr/bin/env python3
import os, json, time, socket, psutil, subprocess, logging, platform
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from bme280 import BME280
from ltr559 import LTR559
from enviroplus import gas

APP_NAME = "ha-enviro-plus"
VERSION  = "0.1.0"

# ---------- CONFIG via /etc/default/ha-enviro-plus ----------
MQTT_HOST             = os.getenv("MQTT_HOST", "homeassistant.local")
MQTT_PORT             = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER             = os.getenv("MQTT_USER", "")
MQTT_PASS             = os.getenv("MQTT_PASS", "")
MQTT_DISCOVERY_PREFIX = os.getenv("MQTT_DISCOVERY_PREFIX", "homeassistant")
POLL_SEC              = float(os.getenv("POLL_SEC", "2"))
TEMP_OFFSET           = float(os.getenv("TEMP_OFFSET", "0.0"))
HUM_OFFSET            = float(os.getenv("HUM_OFFSET", "0.0"))
LOG_TO_FILE           = int(os.getenv("LOG_TO_FILE", "0")) == 1
LOG_PATH              = f"/var/log/{APP_NAME}.log"
# ------------------------------------------------------------

hostname  = socket.gethostname()
device_id = f"enviro_{hostname.replace('-', '')}"
root      = device_id  # topic root for states & commands
avail_t   = f"{root}/status"
cmd_t     = f"{root}/cmd"              # expects: reboot|shutdown|restart
set_t     = f"{root}/set/+"            # retained settings, e.g. set/temp_offset

def get_ipv4_prefer_wlan0():
    try:
        addrs = psutil.net_if_addrs()
        # prefer wlan0, else first non-loopback IPv4
        if "wlan0" in addrs:
            for a in addrs["wlan0"]:
                if a.family.name == "AF_INET" and not a.address.startswith("127."):
                    return a.address
        for iface, lst in addrs.items():
            for a in lst:
                if a.family.name == "AF_INET" and not a.address.startswith("127."):
                    return a.address
    except Exception as e:
        logger.warning("Failed to get network address: %s", e)
    return "unknown"

def get_uptime_seconds():
    try:
        with open("/proc/uptime","r") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return 0

def get_model():
    try:
        with open("/proc/device-tree/model","rb") as f:
            return f.read().decode(errors="ignore").strip("\x00")
    except Exception:
        return "Raspberry Pi"

def get_serial():
    try:
        with open("/proc/cpuinfo","r") as f:
            for line in f:
                if line.startswith("Serial"):
                    return line.split(":")[1].strip()
    except Exception:
        pass
    return "unknown"

def get_os_release():
    """Get OS release information."""
    try:
        # Try to get more detailed OS info
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r") as f:
                lines = f.readlines()
            for line in lines:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
        # Fallback to platform info
        return platform.platform()
    except Exception as e:
        logger.warning("Failed to get OS release: %s", e)
        return "unknown"

# ---------- logging ----------
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
handlers = [logging.StreamHandler()]
if LOG_TO_FILE:
    try:
        fh = logging.FileHandler(LOG_PATH)
        fh.setFormatter(fmt)
        handlers.append(fh)
    except Exception:
        pass
for h in handlers:
    h.setFormatter(fmt)
    logger.handlers = []
    logger.addHandler(h)
# ----------------------------

DEVICE_INFO = {
    "identifiers": [device_id],
    "name": "Enviro+",
    "manufacturer": "Pimoroni",
    "model": "Enviro+ (no PMS5003)",
    "sw_version": f"{APP_NAME} {VERSION}",
    "configuration_url": "https://github.com/JeffLuckett/ha-enviro-plus",
}

SENSORS = {
    "bme280/temperature": ("Temperature", "°C",  "temperature"),
    "bme280/humidity":    ("Humidity",    "%",   "humidity"),
    "bme280/pressure":    ("Pressure",    "hPa", "atmospheric_pressure"),
    "ltr559/lux":         ("Illuminance", "lx",  "illuminance"),
    "gas/oxidising":      ("Gas Oxidising (kΩ)", "kΩ", None),
    "gas/reducing":       ("Gas Reducing (kΩ)",  "kΩ", None),
    "gas/nh3":            ("Gas NH3 (kΩ)",       "kΩ", None),
    "host/cpu_temp":      ("CPU Temp", "°C", "temperature"),
    "host/cpu_usage":     ("CPU Usage", "%", None),
    "host/mem_usage":     ("Mem Usage", "%", None),
    "host/mem_size":      ("Mem Size", "GB", None),
    "host/uptime":        ("Uptime", "s", "duration"),
    "host/hostname":      ("Host Name", None, None),
    "host/network":       ("Network Address", None, None),
    "host/os_release":    ("OS Release", None, None),
    "meta/last_update":   ("Last Update", None, None),
}

def disc_payload(topic_tail, name, unit, device_class=None, state_class="measurement", icon=None):
    cfg = {
        "name": name,
        "uniq_id": f"{device_id}_{topic_tail.replace('/', '_')}",
        "state_topic": f"{root}/{topic_tail}",
        "availability_topic": avail_t,
        "device": DEVICE_INFO,
    }
    if unit:        cfg["unit_of_measurement"] = unit
    if device_class:cfg["device_class"] = device_class
    if state_class: cfg["state_class"] = state_class
    if icon:        cfg["icon"] = icon
    return cfg

def publish_discovery(c):
    # sensors
    for tail, (name, unit, devcls) in SENSORS.items():
        obj = tail.replace("/", "_")
        topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{device_id}/{obj}/config"
        # For text sensors (no unit), don't set state_class
        state_class = None if unit is None else "measurement"
        c.publish(topic, json.dumps(disc_payload(tail, name, unit, devcls, state_class)), qos=1, retain=True)
    # controls: simple button commands
    def button(topic_key, name, icon):
        cfg = {
            "name": name,
            "uniq_id": f"{device_id}_btn_{topic_key}",
            "cmd_t": f"{root}/cmd",
            "pl_prs": topic_key,
            "availability_topic": avail_t,
            "device": DEVICE_INFO,
            "icon": icon
        }
        topic = f"{MQTT_DISCOVERY_PREFIX}/button/{device_id}/{topic_key}/config"
        c.publish(topic, json.dumps(cfg), qos=1, retain=True)
    button("reboot",          "Reboot Enviro Zero", "mdi:restart")
    button("shutdown",        "Shutdown Enviro Zero", "mdi:power")
    button("restart_service", "Restart Agent", "mdi:refresh")

    # number entities for offsets (so HA shows exact values)
    def number(name, key, unit, minv, maxv, step):
        cfg = {
            "name": name,
            "uniq_id": f"{device_id}_num_{key}",
            "cmd_t": f"{root}/set/{key}",
            "stat_t": f"{root}/set/{key}",
            "availability_topic": avail_t,
            "device": DEVICE_INFO,
            "unit_of_measurement": unit,
            "min": minv, "max": maxv, "step": step, "mode": "box"
        }
        topic = f"{MQTT_DISCOVERY_PREFIX}/number/{device_id}/{key}/config"
        c.publish(topic, json.dumps(cfg), qos=1, retain=True)
    number("Temp Offset", "temp_offset", "°C", -10, 10, 0.1)
    number("Humidity Offset", "hum_offset", "%", -20, 20, 0.5)

def read_cpu_temp():
    try:
        out = subprocess.check_output(["vcgencmd","measure_temp"], text=True).strip()
        # temp=42.0'C
        return float(out.split("=")[1].split("'")[0])
    except Exception:
        return 0.0

def read_all(bme, ltr):
    global TEMP_OFFSET, HUM_OFFSET
    t  = round(bme.get_temperature() + TEMP_OFFSET, 2)
    h  = round(max(0.0, min(100.0, bme.get_humidity() + HUM_OFFSET)), 2)
    p  = round(bme.get_pressure(), 2)
    lux = round(ltr.get_lux(), 2)
    g   = gas.read_all()
    ox  = round(g.oxidising/1000.0, 2)
    red = round(g.reducing/1000.0, 2)
    nh3 = round(g.nh3/1000.0, 2)

    mem = psutil.virtual_memory()
    vals = {
        "bme280/temperature": t,
        "bme280/humidity":    h,
        "bme280/pressure":    p,
        "ltr559/lux":         lux,
        "gas/oxidising":      ox,
        "gas/reducing":       red,
        "gas/nh3":            nh3,
        "host/cpu_temp":      round(read_cpu_temp(), 1),
        "host/cpu_usage":     round(psutil.cpu_percent(interval=None), 1),
        "host/mem_usage":     round(mem.percent, 1),
        "host/mem_size":      round(mem.total/1024/1024/1024, 3),
        "host/uptime":        get_uptime_seconds(),
        "host/hostname":      str(hostname),
        "host/network":       get_ipv4_prefer_wlan0(),
        "host/os_release":    get_os_release(),
        "meta/last_update":   datetime.now(timezone.utc).isoformat(),
    }
    return vals

def on_connect(client, userdata, flags, rc, properties=None):
    logger.info("Connected to MQTT (%s:%s) RC=%s", MQTT_HOST, MQTT_PORT, mqtt.connack_string(rc))
    client.publish(avail_t, "online", retain=True)
    # (Re)publish discovery on connect
    publish_discovery(client)
    # Publish retained offsets so HA shows the current values
    client.publish(f"{root}/set/temp_offset", str(TEMP_OFFSET), retain=True)
    client.publish(f"{root}/set/hum_offset",  str(HUM_OFFSET), retain=True)
    # Subscribe to commands and setters
    client.subscribe([(cmd_t, 1), (set_t, 1)])

def on_message(client, userdata, msg):
    global TEMP_OFFSET, HUM_OFFSET
    try:
        topic = msg.topic
        payload = msg.payload.decode().strip()
        if topic == cmd_t:
            if payload == "reboot":
                logger.info("Command: reboot")
                client.publish(avail_t, "offline", retain=True)
                subprocess.Popen(["sudo","reboot"])
            elif payload == "shutdown":
                logger.info("Command: shutdown")
                client.publish(avail_t, "offline", retain=True)
                subprocess.Popen(["sudo","shutdown","-h","now"])
            elif payload == "restart_service":
                logger.info("Command: restart service")
                subprocess.Popen(["sudo","systemctl","restart",f"{APP_NAME}.service"])
        elif topic.startswith(f"{root}/set/"):
            key = topic.split("/")[-1]
            if key == "temp_offset":
                TEMP_OFFSET = float(payload)
                logger.info("Set temp offset = %s", payload)
            elif key == "hum_offset":
                HUM_OFFSET = float(payload)
                logger.info("Set humidity offset = %s", payload)
    except Exception as e:
        logger.exception("on_message error: %s", e)

def main():
    logger.info("%s starting (v%s)", APP_NAME, VERSION)
    logger.info("Root topic: %s", root)
    logger.info("Discovery prefix: %s", MQTT_DISCOVERY_PREFIX)
    logger.info("Poll interval: %ss", POLL_SEC)
    logger.info("Initial offsets: TEMP=%s°C HUM=%s%%", TEMP_OFFSET, HUM_OFFSET)

    bme = BME280(i2c_addr=0x76)
    ltr = LTR559()

    client = mqtt.Client(client_id=root, protocol=mqtt.MQTTv5)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.will_set(avail_t, "offline", retain=True)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    # Publish static device attributes once
    static = {
        "model": get_model(),
        "serial": get_serial(),
    }
    client.publish(f"{root}/device/attributes", json.dumps(static), retain=True)

    try:
        while True:
            vals = read_all(bme, ltr)
            for tail, val in vals.items():
                client.publish(f"{root}/{tail}", str(val), retain=True)
            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        pass
    finally:
        client.publish(avail_t, "offline", retain=True)
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
