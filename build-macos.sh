#!/bin/bash
# Build script for macOS

echo "Building Album Studio for macOS..."

# Install PyInstaller if not present
if ! command -v pyinstaller &> /dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Clean previous builds
rm -rf build dist

# Build the application.
# Entry point is run.py, not src/main.py — see run.py for why.
pyinstaller \
    --name="AlbumStudio" \
    --windowed \
    --onedir \
    --icon=assets/icon.icns \
    --add-data="config:config" \
    --add-data="assets:assets" \
    --noconfirm \
    run.py

echo ""
echo "✓ Build complete!"
echo "Application: dist/AlbumStudio.app"
echo ""
echo "To create a DMG installer:"
echo "  python3 build.py dmg"
