# Quick Font Diagnostics for Pi Zero

Copy and paste these commands directly on your Pi Zero:

## Quick Check (One Command)

```bash
echo "=== Font Check ===" && \
echo "Fontconfig: $(which fc-list >/dev/null 2>&1 && echo 'INSTALLED' || echo 'NOT INSTALLED')" && \
echo "DejaVu packages: $(dpkg -l | grep -i dejavu | wc -l)" && \
echo "Font files found: $(find /usr/share/fonts -name '*DejaVu*.ttf' 2>/dev/null | wc -l)" && \
echo "Fonts in cache: $(fc-list 2>/dev/null | grep -i dejavu | wc -l)" && \
echo "" && \
echo "Font paths:" && \
find /usr/share/fonts -name "*DejaVu*.ttf" -type f 2>/dev/null | head -5
```

## Test Python Font Loading

```bash
python3 << 'EOF'
from PIL import ImageFont
import os

print("Testing font paths...")
paths = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]

for path in paths:
    if os.path.exists(path):
        try:
            font = ImageFont.truetype(path, 12)
            print(f"✓ {path} - WORKS")
        except Exception as e:
            print(f"✗ {path} - FAILED: {e}")
    else:
        print(f"✗ {path} - NOT FOUND")

print("\nSearching for any working TTF fonts...")
found = False
for root, dirs, files in os.walk("/usr/share/fonts"):
    for file in files:
        if file.endswith(".ttf") and "DejaVu" in file:
            path = os.path.join(root, file)
            try:
                font = ImageFont.truetype(path, 12)
                print(f"✓ Found working: {path}")
                found = True
                break
            except:
                pass
    if found:
        break
if not found:
    print("✗ No working DejaVu fonts found")
EOF
```

## Check Application Logs

```bash
sudo journalctl -u ha-enviro-plus -n 100 | grep -i "font\|truetype\|bitmap"
```

## Install Fonts (if needed)

```bash
sudo apt-get update && \
sudo apt-get install -y fonts-dejavu-core fonts-dejavu-extra fontconfig && \
sudo fc-cache -fv && \
echo "Fonts installed! Restart service: sudo systemctl restart ha-enviro-plus"
```

