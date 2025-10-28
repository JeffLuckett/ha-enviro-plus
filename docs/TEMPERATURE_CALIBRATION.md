# Temperature Sensor Calibration Guide

## Important: Sensor Sensitivity to Air Movement

⚠️ **The Enviro+ temperature sensor is EXTREMELY sensitive to air currents and local thermal effects.**

For general room or environmental monitoring, the sensor MUST be placed in still air (inside a vented housing) to prevent readings from being heavily influenced by:
- Local air currents (drafts, fans, HVAC)
- Direct sunlight
- Radiant heat sources (heaters, electronics)
- Human movement near the sensor
- Door openings and wind

Without protection from air movement, temperature readings will fluctuate dramatically and may not represent the actual room temperature.

### Recommended Enclosures

For accurate environmental monitoring:
- Place the Enviro+ inside a ventilated enclosure (plastic box with small holes)
- Keep away from direct airflow
- Mount on a wall or surface that doesn't conduct heat
- Allow for air exchange to prevent temperature buildup

---

## Calibration Overview

The system uses three parameters to accurately measure temperature:

1. **`cpu_temp_factor`** - Controls CPU heat compensation (primary calibration)
2. **`temp_offset`** - Fine-tuning offset in °C (secondary calibration)
3. **`cpu_temp_smoothing`** - Response time to CPU temperature changes (optional - reduces jitter from transient loads, etc...)

### Temperature Calculation Formula

```
compensated_temp = raw_temp - ((cpu_temp - raw_temp) / cpu_temp_factor)
final_temp = compensated_temp + temp_offset
```

---

## Step-by-Step Calibration Process

### Prerequisites

1. **Install and start** the ha-enviro-plus service
2. **Set up reference conditions** - Place a known-accurate thermometer next to the sensor
3. **Wait for stabilization** - Allow 15-30 minutes for the system to stabilize

### Step 1: Adjust CPU Temperature Factor (Primary)

The `cpu_temp_factor` controls how much the CPU heating affects the sensor. This is the most important calibration parameter.

**Default value:** `1.8`
**Recommended range:** `1.2` to `2.5`

#### Adjustment Logic:

- **Sensor reads too HIGH** → **Decrease** the factor (more compensation)
  - Try values: 1.6, 1.4, 1.2 depending on how high the reading is
- **Sensor reads too LOW** → **Increase** the factor (less compensation)
  - Try values: 2.0, 2.2, 2.5 depending on how low the reading is

#### Process:

1. Observe the current sensor reading vs. reference thermometer
2. Note the difference:
   - "Reading is 3°C too high" → decrease factor to 1.4
   - "Reading is 1°C too low" → increase factor to 2.0
3. Make small adjustments (0.2 increments)
4. Wait 5-10 minutes for readings to stabilize
5. Test across different CPU loads:
   - Under light load (Idle)
   - Under heavy load (Run a CPU-intensive task)

#### Example Scenario:

**Initial conditions:**
- Reference thermometer: 21.5°C
- Sensor reading: 24.2°C (too high by 2.7°C)
- Current: `cpu_temp_factor = 1.8`

**Step 1:** Decrease factor to compensate more
- Try `cpu_temp_factor = 1.5` → reading drops to ~22.1°C

**Step 2:** Further adjustment
- Try `cpu_temp_factor = 1.3` → reading drops to ~21.8°C
- Close enough! Continue to Step 2.

### Step 2: Fine-tune with Temperature Offset

Once you've got the compensation right, use `temp_offset` for final fine-tuning.

**Default value:** `0.0`
**Recommended range:** `-3.0` to `+3.0` °C

#### Process:

1. Calculate the remaining difference
2. Apply that difference as the offset

#### Example (continuing from above):

- Reference: 21.5°C
- Sensor reads: 21.8°C (after cpu_temp_factor adjustment)
- Difference: -0.3°C
- **Set `temp_offset = -0.3`** → final reading: 21.5°C ✅

### Step 3: Configure CPU Temperature Smoothing (Optional)

This controls how quickly the system responds to CPU temperature changes. The default is usually fine.

**Default value:** `0.1`
**Recommended range:** `0.05` to `0.2`

- **Lower value** (0.05-0.08) = More smoothing, slower response, more stable readings
- **Higher value** (0.15-0.2) = Less smoothing, faster response, more responsive readings

Only adjust if you notice:
- Erratic temperature fluctuations → reduce smoothing
- Slow response to temperature changes → increase smoothing

---

## Calibration Parameters Summary

| Parameter | Default | Purpose | Typical Range |
|-----------|---------|---------|---------------|
| `cpu_temp_factor` | 1.8 | Primary compensation for CPU heating | 1.2 - 2.5 |
| `temp_offset` | 0.0 | Fine-tuning offset | -3.0 to +3.0 °C |
| `cpu_temp_smoothing` | 0.1 | Response time to CPU changes | 0.05 - 0.2 |

---

## Quick Reference Guide

### If Sensor Reads Too High
1. **Decrease** `cpu_temp_factor` by 0.2-0.4
2. Then adjust `temp_offset` for final tuning

### If Sensor Reads Too Low
1. **Increase** `cpu_temp_factor` by 0.2-0.4
2. Then adjust `temp_offset` for final tuning

### Typical Calibration Workflow
```
1. Start with defaults
2. Adjust cpu_temp_factor → target within ±1°C
3. Fine-tune with temp_offset → target within ±0.2°C
4. Test across different conditions
5. Document your final values
```

---

## Adjusting Calibration Values

### Via Home Assistant

The installation creates Home Assistant number entities for each parameter:

- **Temp Offset** - Adjust `temp_offset` in °C
- **Humidity Offset** - Adjust `hum_offset` in %
- **CPU Temp Factor** - Adjust `cpu_temp_factor`
- **CPU Temp Smoothing** - Adjust `cpu_temp_smoothing`

### Via Configuration File

Edit `/etc/default/ha-enviro-plus`:

```bash
TEMP_OFFSET=-0.5
CPU_TEMP_FACTOR=1.6
CPU_TEMP_SMOOTHING=0.1
```

Then restart the service:
```bash
sudo systemctl restart ha-enviro-plus
```

### Via MQTT

Publish to MQTT topics (values are persistent):

```bash
mosquitto_pub -h homeassistant.local \
  -t "enviro_raspberrypi/set/temp_offset" \
  -m "-0.5"

mosquitto_pub -h homeassistant.local \
  -t "enviro_raspberrypi/set/cpu_temp_factor" \
  -m "1.6"
```

---

## Tips for Best Results

1. **Calibrate in stable conditions** - Room temperature (20-25°C), stable environment
2. **Test across loads** - Verify readings remain accurate when CPU load changes
3. **Allow settling time** - Wait 5-10 minutes after each adjustment
4. **Check consistency** - Verify readings over several hours
5. **Document your values** - Save your calibrated values for future reference or restoration

---

## Humidity Calibration

Humidity readings are affected by CPU heating in two ways:
1. The humidity sensor is physically heated by the CPU (similar to temperature)
2. The BME280 uses its internal temperature reading to convert absolute humidity to relative humidity, so temperature inaccuracies affect humidity calculations

Currently, humidity calibration uses a simple offset parameter:

- **`hum_offset`** - Additive offset in percentage points (%)

**Default value:** `0.0`
**Recommended range:** `-10` to `+10` %

### Calibration Process

**Important**: Calibrate temperature FIRST, then calibrate humidity.

1. Complete temperature calibration (Steps 1-3 above)
2. Allow the system to stabilize (5-10 minutes)
3. Compare humidity readings with a known-accurate hygrometer
4. Apply the difference as `hum_offset`

### Example

- After temperature calibration, sensor reads: 48% RH
- Reference hygrometer reads: 45% RH
- Difference: +3%
- **Set `hum_offset = -3`** → final reading: 45% RH ✅

### Large Humidity Errors (10+ percentage points)

If you're seeing humidity errors greater than 10 percentage points after temperature calibration (e.g., 20% error), this indicates the BME280's internal temperature compensation is being affected by CPU heating. The BME280 uses its internal temperature sensor to convert absolute humidity to relative humidity, so errors in temperature reading cascade to large humidity errors.

**Example observation:**
- Reference hygrometer: 43.7% RH
- Enviro+ reading: 22.3% RH
- Error: -21.4 percentage points

This magnitude of error suggests the humidity sensor compensation needs to account for the CPU temperature effect more directly than a simple offset can provide.

**Workaround (for now):** Use a large offset (e.g., `hum_offset = +21`), but be aware this may not be stable across different CPU loads or environmental conditions.

**Future enhancement:** Implementing CPU temperature compensation for humidity would improve accuracy for users experiencing large errors.

---

## Troubleshooting

### Temperature Still Wrong After Calibration

1. Verify reference thermometer is accurate
2. Ensure still air conditions (no drafts or air currents)
3. Check that sensor is not in direct sunlight or near heat sources
4. Re-check CPU temperature compensation range

### Temperature Fluctuates Wildly

1. Reduce `cpu_temp_smoothing` (try 0.05-0.08)
2. Check for air currents affecting the sensor
3. Ensure sensor is in still air or proper housing

### Readings Don't Match Between Load Levels

1. Adjust `cpu_temp_factor` to balance compensation
2. You may need different offsets for high vs. low CPU load
3. Consider using a better enclosure to isolate from CPU heat

---

## Example Calibrated Values

Here are some example calibrated values from various installations:

| Environment | cpu_temp_factor | temp_offset | Notes |
|-------------|----------------|-------------|-------|
| Room temp, enclosed | 1.8 | -0.3 | Default factor, small offset |
| High CPU load | 1.5 | -1.2 | More compensation needed |
| Low CPU load | 2.0 | +0.5 | Less compensation needed |
| Well-isolated | 1.8 | 0.0 | Good thermal isolation |

Your optimal values will depend on your specific hardware, environment, and usage patterns.

