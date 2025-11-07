#!/usr/bin/env python3
"""
Diagnostic script for noise sensor detection.

Run this on the Raspberry Pi to diagnose noise sensor issues:
    python3 scripts/diagnose_noise_sensor.py
"""

import sys
import traceback

print("=" * 60)
print("Noise Sensor Diagnostic Tool")
print("=" * 60)
print()

# Test 1: Check if sounddevice is installed
print("1. Checking if sounddevice is installed...")
try:
    import sounddevice as sd

    print("   ✓ sounddevice is installed")
    print(f"   Version: {sd.__version__ if hasattr(sd, '__version__') else 'unknown'}")
except ImportError as e:
    print(f"   ✗ sounddevice is NOT installed: {e}")
    print("   Install with: pip install sounddevice")
    sys.exit(1)
except OSError as e:
    print(f"   ✗ PortAudio library not found: {e}")
    print("   Install with: sudo apt-get install portaudio19-dev libportaudio2 libportaudiocpp0")
    sys.exit(1)
print()

# Test 2: Check if scipy is installed
print("2. Checking if scipy is installed...")
try:
    from scipy.signal import lfilter, butter

    print("   ✓ scipy is installed")
except ImportError as e:
    print(f"   ✗ scipy is NOT installed: {e}")
    print("   Install with: pip install scipy")
    sys.exit(1)
print()

# Test 3: Query all input devices
print("3. Querying all input devices...")
try:
    devices = sd.query_devices(kind="input")
    if devices and len(devices) > 0:
        print(f"   ✓ Found {len(devices)} input device(s):")
        for i, device in enumerate(devices):
            print(f"      [{i}] {device.get('name', 'unknown')}")
            print(f"          Channels: {device.get('max_input_channels', 0)}")
            print(f"          Sample rate: {device.get('default_samplerate', 'unknown')} Hz")
    else:
        print("   ✗ No input devices found via query_devices()")
except Exception as e:
    print(f"   ✗ Error querying devices: {e}")
    traceback.print_exc()
print()

# Test 4: Check default input device
print("4. Checking default input device...")
try:
    default_input = sd.default.device[0]  # Input device index
    if default_input is not None and default_input >= 0:
        print(f"   ✓ Default input device index: {default_input}")
        try:
            default_device_info = sd.query_devices(default_input)
            print(f"   ✓ Default device: {default_device_info.get('name', 'unknown')}")
            print(f"      Channels: {default_device_info.get('max_input_channels', 0)}")
            print(
                f"      Sample rate: {default_device_info.get('default_samplerate', 'unknown')} Hz"
            )
        except Exception as e:
            print(f"   ✗ Error querying default device: {e}")
    else:
        print(f"   ✗ No default input device (index: {default_input})")
except Exception as e:
    print(f"   ✗ Error checking default device: {e}")
    traceback.print_exc()
print()

# Test 5: Try to record a test chunk
print("5. Testing microphone recording...")
try:
    print("   Attempting to record 100 frames at 44100 Hz...")
    test_data = sd.rec(
        frames=100,
        samplerate=44100,
        channels=1,
        dtype="float32",
    )
    sd.wait()  # Wait for recording to complete

    if test_data is not None and len(test_data) > 0:
        print(f"   ✓ Recording successful!")
        print(f"      Data shape: {test_data.shape}")
        print(f"      Data type: {test_data.dtype}")
        print(f"      Min value: {test_data.min():.6f}")
        print(f"      Max value: {test_data.max():.6f}")
        print(f"      Mean value: {test_data.mean():.6f}")
        print(f"      RMS: {(test_data**2).mean()**0.5:.6f}")

        # Check if data is all zeros (microphone might not be working)
        if (test_data == 0).all():
            print("   ⚠ WARNING: All samples are zero - microphone may not be working!")
        elif test_data.max() < 0.0001:
            print("   ⚠ WARNING: Signal level is very low - microphone may not be working!")
        else:
            print("   ✓ Microphone appears to be working (non-zero signal detected)")
    else:
        print("   ✗ Recording returned no data")
except Exception as e:
    print(f"   ✗ Recording failed: {e}")
    traceback.print_exc()
print()

# Test 6: Check ALSA configuration (for I2S microphones)
print("6. Checking ALSA configuration...")
import os

asoundrc_path = os.path.expanduser("~/.asoundrc")
if os.path.exists(asoundrc_path):
    print(f"   ✓ Found ~/.asoundrc")
    try:
        with open(asoundrc_path, "r") as f:
            content = f.read()
            if "adau7002" in content or "dmic" in content.lower():
                print("   ✓ Contains I2S microphone configuration (adau7002/dmic)")
            else:
                print("   ⚠ Does not appear to contain I2S microphone configuration")
    except Exception as e:
        print(f"   ✗ Error reading ~/.asoundrc: {e}")
else:
    print("   ⚠ ~/.asoundrc not found")
    print("   For I2S microphones (Enviro+), you may need to configure ALSA")
    print(
        "   See: https://learn.adafruit.com/adafruit-i2s-mems-microphone-breakout/raspberry-pi-wiring-test"
    )
print()

# Test 7: Check system audio devices
print("7. Checking system audio devices...")
try:
    import subprocess

    result = subprocess.run(
        ["arecord", "-l"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode == 0:
        print("   System audio devices (arecord -l):")
        for line in result.stdout.split("\n"):
            if line.strip():
                print(f"      {line}")
    else:
        print("   ⚠ 'arecord' command not available or failed")
except FileNotFoundError:
    print("   ⚠ 'arecord' command not found (install alsa-utils)")
except Exception as e:
    print(f"   ⚠ Error checking system audio: {e}")
print()

print("=" * 60)
print("Diagnostic complete!")
print("=" * 60)
print()
print("If the microphone is not detected:")
print("  1. For I2S microphones (Enviro+), ensure ALSA is configured")
print("  2. Check microphone volume: alsamixer (press F6, select I2S mic, F4)")
print("  3. Test with: arecord -D dmic_sv -c2 -r 48000 -f S32_LE -t wav -V mono test.wav")
print("  4. Check PortAudio: python3 -c 'import sounddevice; print(sounddevice.query_devices())'")
