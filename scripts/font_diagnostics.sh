#!/usr/bin/env bash
#
# Font Loading Diagnostics Script
#
# Run this script on your Pi Zero to diagnose font loading issues.
# Usage: bash font_diagnostics.sh

echo "=========================================="
echo "Font Loading Diagnostics"
echo "=========================================="
echo ""

# Check fontconfig
echo "1. Checking fontconfig installation..."
if command -v fc-list >/dev/null 2>&1; then
    echo "   ✓ fontconfig is installed"
    FC_LIST_VERSION=$(fc-list --version 2>/dev/null || echo "unknown")
    echo "   Version: $FC_LIST_VERSION"
else
    echo "   ✗ fontconfig is NOT installed"
    echo "   Install with: sudo apt-get install fontconfig"
fi
echo ""

# Check DejaVu font packages
echo "2. Checking DejaVu font packages..."
DEJAVU_PACKAGES=$(dpkg -l | grep -i dejavu | grep -v "^rc" || echo "")
if [ -n "$DEJAVU_PACKAGES" ]; then
    echo "   ✓ DejaVu packages found:"
    echo "$DEJAVU_PACKAGES" | while read -r line; do
        echo "     $line"
    done
else
    echo "   ✗ No DejaVu packages installed"
    echo "   Install with: sudo apt-get install fonts-dejavu-core fonts-dejavu-extra"
fi
echo ""

# Check font files on disk
echo "3. Checking for DejaVu font files on disk..."
FONT_FILES=$(find /usr/share/fonts -name "*DejaVu*.ttf" -type f 2>/dev/null)
FONT_COUNT=$(echo "$FONT_FILES" | grep -c . || echo "0")
if [ "$FONT_COUNT" -gt 0 ]; then
    echo "   ✓ Found $FONT_COUNT DejaVu font file(s):"
    echo "$FONT_FILES" | head -5 | while read -r file; do
        if [ -n "$file" ]; then
            echo "     $file"
        fi
    done
    if [ "$FONT_COUNT" -gt 5 ]; then
        echo "     ... and $((FONT_COUNT - 5)) more"
    fi
else
    echo "   ✗ No DejaVu font files found in /usr/share/fonts"
fi
echo ""

# Check fontconfig cache
echo "4. Checking fontconfig cache..."
if command -v fc-list >/dev/null 2>&1; then
    FC_DEJAVU_COUNT=$(fc-list | grep -i dejavu | wc -l)
    if [ "$FC_DEJAVU_COUNT" -gt 0 ]; then
        echo "   ✓ Found $FC_DEJAVU_COUNT DejaVu font(s) in fontconfig cache:"
        fc-list | grep -i dejavu | head -3 | while read -r line; do
            echo "     $line"
        done
    else
        echo "   ✗ No DejaVu fonts in fontconfig cache"
        echo "   Try: sudo fc-cache -fv"
    fi
else
    echo "   ⚠ fontconfig not installed, cannot check cache"
fi
echo ""

# Test specific font paths
echo "5. Testing specific font paths..."
TEST_PATHS=(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
    "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans-Bold.ttf"
)

for path in "${TEST_PATHS[@]}"; do
    if [ -f "$path" ]; then
        echo "   ✓ $path (exists)"
    else
        echo "   ✗ $path (not found)"
    fi
done
echo ""

# Test Python PIL font loading
echo "6. Testing Python PIL font loading..."
python3 << 'PYEOF'
from PIL import ImageFont
import os
import subprocess

print("   Testing font loading with PIL...")
font_paths = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]

found_working = False
for path in font_paths:
    if os.path.exists(path):
        try:
            font = ImageFont.truetype(path, 12)
            print(f"   ✓ {path} - Successfully loaded")
            found_working = True
        except Exception as e:
            print(f"   ✗ {path} - Failed to load: {e}")

if not found_working:
    print("   ✗ No working fonts found in test paths")
    print("   Searching for any working TTF fonts...")
    for root, dirs, files in os.walk("/usr/share/fonts"):
        for file in files:
            if file.endswith(".ttf"):
                path = os.path.join(root, file)
                try:
                    font = ImageFont.truetype(path, 12)
                    print(f"   ✓ Found working font: {path}")
                    found_working = True
                    break
                except:
                    pass
        if found_working:
            break

print("")
print("   Testing fc-list command...")
try:
    result = subprocess.run(
        ["fc-list", ":family=DejaVu"],
        capture_output=True,
        text=True,
        timeout=2
    )
    if result.returncode == 0 and result.stdout:
        lines = result.stdout.strip().split("\n")
        print(f"   ✓ fc-list found {len(lines)} DejaVu font(s)")
        for line in lines[:3]:
            print(f"     {line}")
    else:
        print(f"   ✗ fc-list failed or returned no results")
        if result.stderr:
            print(f"     Error: {result.stderr}")
except Exception as e:
    print(f"   ✗ fc-list error: {e}")

print("")
print("   Testing find command...")
try:
    result = subprocess.run(
        ["find", "/usr/share/fonts", "-name", "*DejaVu*.ttf", "-type", "f"],
        capture_output=True,
        text=True,
        timeout=3
    )
    if result.returncode == 0 and result.stdout:
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        print(f"   ✓ find found {len(lines)} DejaVu font file(s)")
        for line in lines[:3]:
            print(f"     {line}")
    else:
        print(f"   ✗ find found no DejaVu fonts")
except Exception as e:
    print(f"   ✗ find error: {e}")
PYEOF

echo ""
echo "7. Checking application logs..."
if systemctl is-active --quiet ha-enviro-plus.service 2>/dev/null; then
    echo "   Application service is running"
    echo "   Recent font-related log entries:"
    sudo journalctl -u ha-enviro-plus -n 50 --no-pager | grep -i font | head -10 || echo "   (no font-related log entries found)"
else
    echo "   ⚠ Application service is not running"
fi
echo ""

echo "=========================================="
echo "Diagnostics Complete"
echo "=========================================="
echo ""
echo "If fonts are not found, try:"
echo "  1. sudo apt-get update"
echo "  2. sudo apt-get install fonts-dejavu-core fonts-dejavu-extra fontconfig"
echo "  3. sudo fc-cache -fv"
echo "  4. sudo systemctl restart ha-enviro-plus"
echo ""

