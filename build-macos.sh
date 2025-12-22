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

# Build the application
pyinstaller \
    --name="AlbumStudio" \
    --windowed \
    --onedir \
    --add-data="config:config" \
    --noconfirm \
    src/main.py

echo ""
echo "✓ Build complete!"
echo "Application: dist/AlbumStudio.app"
echo ""
echo "To create a DMG installer:"
echo "  hdiutil create -volname AlbumStudio -srcfolder dist/AlbumStudio.app -ov -format UDZO dist/AlbumStudio.dmg"
