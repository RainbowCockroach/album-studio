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

# PyInstaller runs this as __main__, so it must not be src/main.py — see run.py.
ENTRY_POINT = 'run.py'

APP_NAME = 'AlbumStudio'
VOLUME_NAME = 'Album Studio'
APP_PATH = f'dist/{APP_NAME}.app'
DMG_PATH = f'dist/{APP_NAME}.dmg'


def require_icon(path):
    """Return the --icon flag for path, or exit if it is missing.

    Never skip the flag on a missing file: PyInstaller falls back to its own
    Python-logo icon and the build still reports success, so the wrong icon
    ships silently.
    """
    if not os.path.exists(path):
        print(f"\n[ERROR] Icon not found: {path}")
        print("Refusing to build — the app would ship with PyInstaller's default icon.")
        sys.exit(1)
    return f'--icon={path}'


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
        f'--name={APP_NAME}',
        '--windowed',  # No console window
        '--onedir',  # Create a bundle directory
        require_icon('assets/icon.icns'),
        '--add-data=config:config',  # Bundled defaults: settings + size groups
        '--add-data=assets:assets',  # DSEG7 date-stamp font + window icon
        '--noconfirm',
        ENTRY_POINT
    ]

    subprocess.run(cmd, check=True)
    print(f"\n[OK] macOS build complete! Check {APP_PATH}")
    print("Create the installer disk image with: python3 build.py dmg")


def build_windows():
    """Build Windows executable (.exe)."""
    print("\n=== Building for Windows ===\n")

    cmd = [
        'pyinstaller',
        f'--name={APP_NAME}',
        '--windowed',  # No console window
        '--onedir',  # Create a bundle directory
        require_icon('assets/icon.ico'),
        '--add-data=config;config',  # Windows uses a semicolon separator
        '--add-data=assets;assets',  # DSEG7 date-stamp font + window icon
        '--noconfirm',
        ENTRY_POINT
    ]

    subprocess.run(cmd, check=True)
    print(f"\n[OK] Windows build complete! Check dist/{APP_NAME}/")


def detach_stale_volume():
    """Unmount any volume left over from a previous DMG.

    Two volumes cannot share a name: macOS silently mounts the second as
    "<name> 1", and create-dmg's AppleScript then styles a window that is not
    there and exits 64, leaving a ~640MB rw.*.dmg behind. Mounting the DMG to
    test it and then rebuilding is the normal loop, so this must be handled.
    """
    volume = f'/Volumes/{VOLUME_NAME}'
    if os.path.ismount(volume):
        print(f"[note] unmounting stale {volume}")
        subprocess.run(['hdiutil', 'detach', volume, '-quiet'], check=False)


def clean_dmg_temp_files():
    """Remove rw.*.dmg scratch images abandoned by an interrupted create-dmg."""
    for leftover in Path('dist').glob('rw.*.dmg'):
        print(f"[note] removing leftover {leftover}")
        leftover.unlink()


def build_dmg():
    """Package dist/AlbumStudio.app into a drag-to-Applications disk image.

    The drag-and-drop window every Mac user expects is not something macOS
    provides: the image itself must contain an /Applications symlink next to the
    app. A bare `hdiutil create -srcfolder <app>` ships the app alone in an empty
    window, with nowhere to drag it to.
    """
    print("\n=== Building DMG ===\n")

    if not os.path.exists(APP_PATH):
        print(f"[ERROR] {APP_PATH} not found. Run: python3 build.py macos")
        sys.exit(1)

    detach_stale_volume()
    clean_dmg_temp_files()

    if os.path.exists(DMG_PATH):
        os.remove(DMG_PATH)

    if shutil.which('create-dmg'):
        # Positions the icons and hides the .app extension; purely cosmetic.
        subprocess.run([
            'create-dmg',
            '--volname', VOLUME_NAME,
            '--window-pos', '200', '120',
            '--window-size', '640', '400',
            '--icon-size', '128',
            '--icon', f'{APP_NAME}.app', '160', '185',
            '--hide-extension', f'{APP_NAME}.app',
            '--app-drop-link', '480', '185',
            DMG_PATH,
            APP_PATH,
        ], check=True)
    else:
        print("[note] create-dmg not installed (brew install create-dmg) —")
        print("       building a plain image: same drag-and-drop, default layout.\n")
        staging = 'dist/dmg-staging'
        if os.path.exists(staging):
            shutil.rmtree(staging)
        os.makedirs(staging)
        # symlinks=True: the .app is full of them, and copying their targets
        # instead would duplicate every framework and break code signing.
        shutil.copytree(APP_PATH, f'{staging}/{APP_NAME}.app', symlinks=True)
        os.symlink('/Applications', f'{staging}/Applications')
        subprocess.run([
            'hdiutil', 'create',
            '-volname', VOLUME_NAME,
            '-srcfolder', staging,
            '-ov', '-format', 'UDZO',
            DMG_PATH,
        ], check=True)
        shutil.rmtree(staging)

    print(f"\n[OK] DMG complete! {DMG_PATH}")
    print("Unsigned: first launch needs right-click > Open to pass Gatekeeper.")


def build_spec_file():
    """Generate PyInstaller spec file for advanced configuration."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('assets', 'assets'),
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

        elif command == 'dmg':
            # No clean: packages whatever dist/AlbumStudio.app is already there.
            build_dmg()
            return

        else:
            print(f"Unknown command: {command}")
            print("Usage: python build.py [clean|spec|macos|windows|dmg]")
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
