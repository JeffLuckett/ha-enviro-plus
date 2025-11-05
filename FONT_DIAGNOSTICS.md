# Font Loading Diagnostics

If fonts are not loading on the display, run these diagnostic commands on your Pi Zero to help identify the issue.

## Basic Font Checks

```bash
# Check if fontconfig is installed
which fc-list
dpkg -l | grep fontconfig

# Check if DejaVu fonts are installed
dpkg -l | grep -i dejavu
dpkg -l | grep fonts-dejavu

# List all DejaVu fonts found by fontconfig
fc-list | grep -i dejavu

# List all fonts with file paths
fc-list : file

# Find DejaVu fonts using find command
find /usr/share/fonts -name "*DejaVu*" -type f

# Check specific font paths
ls -la /usr/share/fonts/truetype/dejavu/
ls -la /usr/share/fonts/TTF/DejaVu* 2>/dev/null
```

## Test Font Loading with Python

```bash
# Test if PIL can load fonts
python3 << 'EOF'
from PIL import ImageFont
import os

# Test font paths
font_paths = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]

print("Testing font paths:")
for path in font_paths:
    exists = os.path.exists(path)
    print(f"  {path}: {'EXISTS' if exists else 'NOT FOUND'}")
    if exists:
        try:
            font = ImageFont.truetype(path, 12)
            print(f"    ✓ Successfully loaded")
        except Exception as e:
            print(f"    ✗ Failed to load: {e}")

# Test fc-list
print("\nTesting fc-list:")
import subprocess
try:
    result = subprocess.run(
        ["fc-list", ":family=DejaVu"],
        capture_output=True,
        text=True,
        timeout=2
    )
    if result.returncode == 0:
        print("  fc-list output:")
        for line in result.stdout.strip().split("\n")[:5]:
            print(f"    {line}")
    else:
        print(f"  fc-list failed: {result.stderr}")
except Exception as e:
    print(f"  fc-list error: {e}")

# Test find command
print("\nTesting find command:")
try:
    result = subprocess.run(
        ["find", "/usr/share/fonts", "-name", "*DejaVu*.ttf", "-type", "f"],
        capture_output=True,
        text=True,
        timeout=3
    )
    if result.returncode == 0:
        print("  Found fonts:")
        for line in result.stdout.strip().split("\n"):
            if line:
                print(f"    {line}")
    else:
        print(f"  find failed: {result.stderr}")
except Exception as e:
    print(f"  find error: {e}")
EOF
```

## Check Application Logs

```bash
# Check if fonts are being found in application logs
sudo journalctl -u ha-enviro-plus -n 100 | grep -i font

# Check for font-related warnings
sudo journalctl -u ha-enviro-plus -n 100 | grep -i "truetype\|bitmap\|font"
```

## Install Fonts Manually (if needed)

```bash
# Update package list
sudo apt-get update

# Install DejaVu fonts and fontconfig
sudo apt-get install -y fonts-dejavu-core fonts-dejavu-extra fontconfig

# Update font cache
sudo fc-cache -fv

# Verify installation
fc-list | grep -i dejavu | head -5
```

## Check Font File Permissions

```bash
# Check if font files are readable
find /usr/share/fonts -name "*DejaVu*.ttf" -type f -exec ls -la {} \;

# Check if application can read fonts
sudo -u root ls -la /usr/share/fonts/truetype/dejavu/ 2>/dev/null
```

## Manual Font Path Test

```bash
# Test if a specific font file can be loaded
python3 << 'EOF'
from PIL import ImageFont
import os

# Try to find any TTF font
font_path = None
for root, dirs, files in os.walk("/usr/share/fonts"):
    for file in files:
        if file.endswith(".ttf") and "DejaVu" in file:
            path = os.path.join(root, file)
            if os.path.exists(path):
                try:
                    test_font = ImageFont.truetype(path, 12)
                    print(f"✓ Found working font: {path}")
                    font_path = path
                    break
                except:
                    pass
    if font_path:
        break

if not font_path:
    print("✗ No working DejaVu fonts found")
    print("\nSearching for any TTF fonts...")
    for root, dirs, files in os.walk("/usr/share/fonts"):
        for file in files:
            if file.endswith(".ttf"):
                path = os.path.join(root, file)
                try:
                    test_font = ImageFont.truetype(path, 12)
                    print(f"  Found working font: {path}")
                    break
                except:
                    pass
EOF
```

## Common Issues and Solutions

1. **Fonts not installed**: Run `sudo apt-get install fonts-dejavu-core fontconfig`
2. **Font cache not updated**: Run `sudo fc-cache -fv`
3. **Wrong font path**: Check actual paths with `find /usr/share/fonts -name "*DejaVu*.ttf"`
4. **Permission issues**: Ensure fonts are readable by all users
5. **Fontconfig not installed**: Install with `sudo apt-get install fontconfig`

## Report Diagnostics

After running the diagnostics above, provide the output of:

```bash
# Summary command
echo "=== Font Diagnostic Summary ==="
echo "Fontconfig installed: $(which fc-list >/dev/null 2>&1 && echo 'YES' || echo 'NO')"
echo "DejaVu packages: $(dpkg -l | grep -i dejavu | wc -l)"
echo "Font files found: $(find /usr/share/fonts -name '*DejaVu*.ttf' 2>/dev/null | wc -l)"
echo "Fonts in cache: $(fc-list | grep -i dejavu | wc -l)"
echo ""
echo "Font paths:"
find /usr/share/fonts -name "*DejaVu*.ttf" -type f 2>/dev/null | head -10
```

