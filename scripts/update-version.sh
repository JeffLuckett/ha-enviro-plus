#!/usr/bin/env bash
#
# Version Management Script for ha-enviro-plus
#
# This script updates the version across all files and prepares for GitHub release.
# Usage: ./scripts/update-version.sh 0.2.0 [--release]
#
# Options:
#   --release    Also create a git tag and push (triggers GitHub release)
#

set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    echo "Usage: $0 <version> [--release]"
    echo "Example: $0 0.2.0"
    echo "Example: $0 0.2.0 --release"
    echo ""
    echo "Options:"
    echo "  --release    Create git tag and push (triggers GitHub release)"
    exit 1
fi

# Check for help flags
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0 <version> [--release]"
    echo "Example: $0 0.2.0"
    echo "Example: $0 0.2.0 --release"
    echo ""
    echo "Options:"
    echo "  --release    Create git tag and push (triggers GitHub release)"
    echo ""
    echo "This script updates the version across all files and optionally creates a GitHub release."
    exit 0
fi

NEW_VERSION="$1"
CREATE_RELEASE=false

if [ $# -eq 2 ] && [ "$2" = "--release" ]; then
    CREATE_RELEASE=true
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Detect OS type for sed compatibility
if [[ "$OSTYPE" == "darwin"* ]]; then
    SED_INPLACE="sed -i.bak"
else
    SED_INPLACE="sed -i"
fi

echo "Updating version to ${NEW_VERSION}..."

# Check for uncommitted changes BEFORE making any changes
if [ "$CREATE_RELEASE" = true ]; then
    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo "❌ Error: Not in a git repository"
        exit 1
    fi

    # Check if there are uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        echo "❌ Error: You have uncommitted changes. Please commit or stash them first."
        echo "Run: git status"
        exit 1
    fi
fi

# Update __init__.py
INIT_FILE="${PROJECT_ROOT}/ha_enviro_plus/__init__.py"
if [ -f "$INIT_FILE" ]; then
    $SED_INPLACE "s/__version__ = \".*\"/__version__ = \"${NEW_VERSION}\"/" "$INIT_FILE"
    rm -f "${INIT_FILE}.bak"
    echo "✅ Updated ${INIT_FILE}"
fi

# Update README.md version section
README_FILE="${PROJECT_ROOT}/README.md"
if [ -f "$README_FILE" ]; then
    $SED_INPLACE "s/\*\*v[0-9.]* —/\*\*v${NEW_VERSION} —/" "$README_FILE"
    rm -f "${README_FILE}.bak"
    echo "✅ Updated ${README_FILE}"
fi

# Update install script fallback version
INSTALL_SCRIPT="${PROJECT_ROOT}/scripts/install.sh"
if [ -f "$INSTALL_SCRIPT" ]; then
    $SED_INPLACE "s/SCRIPT_VERSION=\"v[0-9.]*\"/SCRIPT_VERSION=\"v${NEW_VERSION}\"/" "$INSTALL_SCRIPT"
    rm -f "${INSTALL_SCRIPT}.bak"
    echo "✅ Updated ${INSTALL_SCRIPT}"
fi

# Update uninstall script version
UNINSTALL_SCRIPT="${PROJECT_ROOT}/scripts/uninstall.sh"
if [ -f "$UNINSTALL_SCRIPT" ]; then
    $SED_INPLACE "s/SCRIPT_VERSION=\"v[0-9.]*\"/SCRIPT_VERSION=\"v${NEW_VERSION}\"/" "$UNINSTALL_SCRIPT"
    rm -f "${UNINSTALL_SCRIPT}.bak"
    echo "✅ Updated ${UNINSTALL_SCRIPT}"
fi

echo ""
echo "🎉 Version updated to ${NEW_VERSION}!"

if [ "$CREATE_RELEASE" = true ]; then
    echo ""
    echo "🚀 Creating GitHub release..."

    # Commit the version changes (only if there are changes)
    git add ha_enviro_plus/__init__.py README.md scripts/install.sh scripts/uninstall.sh
    if ! git diff --cached --quiet; then
        git commit -m "Bump version to ${NEW_VERSION}"
    else
        echo "ℹ️  No changes to commit (version already set to ${NEW_VERSION})"
    fi

    # Create and push tag
    git tag "v${NEW_VERSION}"
    git push origin main
    git push origin "v${NEW_VERSION}"

    echo ""
    echo "🎉 GitHub release created!"
    echo "📋 Release URL: https://github.com/JeffLuckett/ha-enviro-plus/releases/tag/v${NEW_VERSION}"
    echo ""
    echo "The GitHub Actions workflow will automatically:"
    echo "  • Run all tests"
    echo "  • Build the package"
    echo "  • Generate changelog"
    echo "  • Create release with assets"
else
    echo ""
    echo "Next steps:"
    echo "1. Review the changes: git diff"
    echo "2. Commit the changes: git commit -m \"Bump version to ${NEW_VERSION}\""
    echo "3. Create a tag: git tag v${NEW_VERSION}"
    echo "4. Push changes: git push && git push --tags"
    echo ""
    echo "Or use --release flag to do all of the above automatically:"
    echo "  $0 ${NEW_VERSION} --release"
fi
