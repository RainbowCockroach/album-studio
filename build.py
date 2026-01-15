#!/usr/bin/env python3
"""
Build script for Album Studio
Creates standalone executables for macOS and Windows
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean_build_folders():
    """Remove old build artifacts."""
    folders = ['build', 'dist']
    for folder in folders:
        if os.path.exists(folder):
            print(f"Cleaning {folder}/...")
            shutil.rmtree(folder)


def build_macos():
    """Build macOS application bundle (.app)."""
    print("\n=== Building for macOS ===\n")

    cmd = [
        'pyinstaller',
        '--name=AlbumStudio',
        '--windowed',  # No console window
        '--onedir',  # Create a bundle directory
        '--icon=assets/icon.icns' if os.path.exists('assets/icon.icns') else '',
        '--add-data=config:config',  # Include config folder
        '--noconfirm',
        'src/main.py'
    ]

    # Remove empty icon argument if no icon exists
    cmd = [arg for arg in cmd if arg]

    subprocess.run(cmd, check=True)
    print("\n[OK] macOS build complete! Check dist/AlbumStudio.app")


def build_windows():
    """Build Windows executable (.exe)."""
    print("\n=== Building for Windows ===\n")

    cmd = [
        'pyinstaller',
        '--name=AlbumStudio',
        '--windowed',  # No console window
        '--onedir',  # Create a bundle directory
        '--icon=assets/icon.ico' if os.path.exists('assets/icon.ico') else '',
        '--add-data=config;config',  # Include config folder (Windows uses semicolon)
        '--noconfirm',
        'src/main.py'
    ]

    # Remove empty icon argument if no icon exists
    cmd = [arg for arg in cmd if arg]

    subprocess.run(cmd, check=True)
    print("\n[OK] Windows build complete! Check dist/AlbumStudio/")


def build_spec_file():
    """Generate PyInstaller spec file for advanced configuration."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AlbumStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AlbumStudio',
)

# macOS specific
app = BUNDLE(
    coll,
    name='AlbumStudio.app',
    icon='assets/icon.icns',
    bundle_identifier='com.albumstudio.app',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
    },
)
'''

    with open('AlbumStudio.spec', 'w') as f:
        f.write(spec_content)

    print("[OK] Generated AlbumStudio.spec file")


def main():
    """Main build function."""
    print("Album Studio Build Script")
    print("=" * 50)

    # Check if PyInstaller is installed
    try:
        subprocess.run(['pyinstaller', '--version'],
                      capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\n[ERROR] PyInstaller not found!")
        print("Install it with: pip install pyinstaller")
        sys.exit(1)

    # Determine platform
    platform = sys.platform

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == 'clean':
            clean_build_folders()
            print("[OK] Cleaned build folders")
            return

        elif command == 'spec':
            build_spec_file()
            return

        elif command == 'macos':
            clean_build_folders()
            build_macos()
            return

        elif command == 'windows':
            clean_build_folders()
            build_windows()
            return

        else:
            print(f"Unknown command: {command}")
            print("Usage: python build.py [clean|spec|macos|windows]")
            sys.exit(1)

    # Auto-detect platform and build
    clean_build_folders()

    if platform == 'darwin':
        build_macos()
    elif platform == 'win32':
        build_windows()
    else:
        print(f"Unsupported platform: {platform}")
        print("Use: python build.py [macos|windows]")
        sys.exit(1)


if __name__ == '__main__':
    main()
