#!/usr/bin/env python3
"""
Build script for Album Studio
Creates standalone executables for macOS and Windows
"""

import os
import re
import sys
import shutil
import subprocess
from pathlib import Path

# PyInstaller runs this as __main__, so it must not be src/main.py — see run.py.
ENTRY_POINT = 'run.py'

APP_NAME = 'AlbumStudio'
VOLUME_NAME = 'Album Studio'
# torchvision's compiled operators. PyInstaller's torchvision hook still asks
# for the pre-0.29 name `torchvision._C`, so `_C_stable` was silently left out
# and "Find similar" failed with "operator torchvision::nms does not exist".
TORCHVISION_EXTENSION = '--hidden-import=torchvision._C_stable'

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
    folders = ['build', 'dist', 'installer_output']
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
        TORCHVISION_EXTENSION,
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
        TORCHVISION_EXTENSION,
        '--noconfirm',
        ENTRY_POINT
    ]

    subprocess.run(cmd, check=True, env=system32_first_env())
    bundle = f'dist/{APP_NAME}/_internal'
    upgrade_bundled_msvc_runtime(
        bundle, os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32'))
    check_bundled_msvc_runtime(bundle)
    check_bundled_torchvision_ops(f'dist/{APP_NAME}/_internal/torchvision')
    print(f"\n[OK] Windows build complete! Check dist/{APP_NAME}/")


# torch's c10.dll fails to initialise (WinError 1114) on anything older.
MIN_MSVC_RUNTIME = (14, 40)


def system32_first_env():
    """os.environ with System32 moved to the front of PATH.

    PyInstaller bundles the first msvcp140.dll it finds on PATH. Any program
    that puts its own folder ahead of System32 decides the app's C++ runtime
    — a JDK 11 did exactly that and shipped a 2018 copy that broke torch.
    """
    # Read from os.environ, not the copy: on Windows only os.environ ignores
    # case, and the copy holds "SYSTEMROOT", so .get('SystemRoot') would miss.
    env = dict(os.environ)
    system32 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
    rest = [p for p in os.environ.get('PATH', '').split(os.pathsep)
            if p and os.path.normcase(p.rstrip('\\')) != os.path.normcase(system32)]
    env['PATH'] = os.pathsep.join([system32] + rest)
    return env


def check_bundled_torchvision_ops(torchvision_dir):
    """Abort if torchvision's compiled extension is missing from the bundle.

    The app still builds and launches without it; only "Find similar" fails.
    A future rename of the module would drop it again, so check the result.
    """
    found = list(Path(torchvision_dir).glob('_C*.pyd')) + \
        list(Path(torchvision_dir).glob('_C*.so'))
    if not found:
        print(f"\n[ERROR] No torchvision _C extension in {torchvision_dir}.")
        print("        Find its current name in site-packages/torchvision and "
              "update TORCHVISION_EXTENSION in build.py.")
        sys.exit(1)
    print(f"[OK] Bundled torchvision extension {found[0].name}")


def dll_file_version(path):
    """Return a Windows DLL's file version as a tuple, e.g. (14, 50, 35719, 0)."""
    import ctypes
    from ctypes import wintypes
    version = ctypes.WinDLL('version')  # type: ignore[attr-defined]
    size = version.GetFileVersionInfoSizeW(path, None)
    if not size:
        raise OSError(f"no version info in {path}")
    buf = ctypes.create_string_buffer(size)
    version.GetFileVersionInfoW(path, 0, size, buf)
    info = ctypes.c_void_p()
    length = wintypes.UINT()
    version.VerQueryValueW(buf, '\\', ctypes.byref(info), ctypes.byref(length))
    # VS_FIXEDFILEINFO: dwFileVersionMS / dwFileVersionLS are DWORDs 2 and 3.
    ms, ls = ctypes.cast(info, ctypes.POINTER(wintypes.DWORD))[2:4]
    return (ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF)


# The Microsoft C++ runtime files that packages bundle under their plain names.
# Hashed copies (numpy.libs/msvcp140-<hash>.dll) are private and left alone.
MSVC_RUNTIME_DLLS = {
    'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'msvcp140_atomic_wait.dll',
    'vcruntime140.dll', 'vcruntime140_1.dll', 'vcruntime140_threads.dll',
    'concrt140.dll',
}

# Shipped beside the app whatever PyInstaller collected: none of these are part
# of Windows itself, only of the VC++ Redistributable. torch_cpu.dll imports
# vcruntime140_threads.dll, which PyInstaller never bundled — the build PC had
# it from some other program, and a clean PC would not.
APP_LOCAL_MSVC_RUNTIME = sorted(MSVC_RUNTIME_DLLS)


def _bundled_runtime_dlls(bundle_dir):
    return [p for p in Path(bundle_dir).rglob('*.dll')
            if p.name.lower() in MSVC_RUNTIME_DLLS]


def upgrade_bundled_msvc_runtime(bundle_dir, system32, read_version=dll_file_version):
    """Replace every bundled C++ runtime DLL older than System32's copy.

    PyQt6 ships its own 2020 runtime (14.26) in Qt6/bin, and Windows loads it
    for Qt from there; torch's c10.dll then gets that old copy and fails with
    WinError 1114. Preloading a newer copy at startup does not stop it — Qt
    still loads its own beside it. So no old copy may be left in the bundle.
    Microsoft keeps every v14 runtime backward compatible, so Qt runs fine on
    the newer one.
    """
    for dll in _bundled_runtime_dlls(bundle_dir):
        source = Path(system32) / dll.name
        if source.exists() and read_version(str(source)) > read_version(str(dll)):
            shutil.copy2(source, dll)
            print(f"[note] upgraded {dll.relative_to(bundle_dir)}")

    # Then make sure the whole runtime sits at the bundle root, so the app
    # never depends on what the user's PC happens to have installed.
    present = {p.name.lower() for p in Path(bundle_dir).iterdir()}
    for name in APP_LOCAL_MSVC_RUNTIME:
        source = Path(system32) / name
        if name not in present:
            if not source.exists():
                print(f"\n[ERROR] {name} is not in {system32}; install the latest "
                      "VC++ Redistributable on the build machine.")
                sys.exit(1)
            shutil.copy2(source, Path(bundle_dir) / name)
            print(f"[note] added {name}")


def check_bundled_msvc_runtime(bundle_dir, read_version=dll_file_version):
    """Abort if any bundled msvcp140.dll is too old for torch, or none exists.

    An old copy builds and launches fine; only "Find similar" breaks, and only
    on Windows — so the build has to be the one to notice.
    """
    copies = [p for p in _bundled_runtime_dlls(bundle_dir)
              if p.name.lower() == 'msvcp140.dll']
    if not copies:
        print(f"\n[ERROR] No msvcp140.dll in {bundle_dir}.")
        sys.exit(1)
    need = '.'.join(map(str, MIN_MSVC_RUNTIME))
    for dll in copies:
        found = read_version(str(dll))
        if found[:2] < MIN_MSVC_RUNTIME:
            print(f"\n[ERROR] {dll} is {'.'.join(map(str, found))}; torch needs {need}+.")
            print("        Update the Visual C++ Redistributable on this machine.")
            sys.exit(1)
    print(f"[OK] All {len(copies)} bundled msvcp140.dll copies are {need}+")


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


INSTALLER_PATH = 'installer_output/AlbumStudio-Windows-Setup.exe'


def read_app_version():
    """Return __version__ from src/version.py without importing the app.

    CI rewrites that line with the build number before building, so this is the
    version the installer must register — or every install shows up in
    Settings > Apps as installer.iss's placeholder 1.0.0.
    """
    text = Path('src/version.py').read_text()
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        print("[ERROR] Could not find __version__ in src/version.py")
        sys.exit(1)
    return match.group(1)


def find_iscc():
    """Locate Inno Setup's compiler, or None.

    A per-user install (`winget install --scope user`) lands under
    %LOCALAPPDATA%\\Programs and is not put on PATH, so it is checked by hand.
    """
    for path in [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        os.path.join(os.environ.get('LOCALAPPDATA', ''),
                     'Programs', 'Inno Setup 6', 'ISCC.exe'),
    ]:
        if os.path.exists(path):
            return path
    return shutil.which("ISCC")


def build_installer():
    """Build Windows installer using Inno Setup after PyInstaller.

    A missing Inno Setup aborts rather than skipping: a skip exits 0, so CI
    would publish a release with no installer and nobody would notice.
    """
    print("\n=== Building Windows Installer ===\n")

    iscc = find_iscc()
    if iscc is None:
        print("[ERROR] Inno Setup not found — cannot build the installer.")
        print("        Download from: https://jrsoftware.org/isinfo.php")
        print("        (or: choco install innosetup)")
        sys.exit(1)

    if not os.path.exists(f'dist/{APP_NAME}/{APP_NAME}.exe'):
        print(f"[ERROR] dist/{APP_NAME}/ not found. Run: python build.py windows")
        sys.exit(1)

    version = read_app_version()
    subprocess.run([iscc, f'/DMyAppVersion={version}', 'installer.iss'], check=True)
    print(f"\n[OK] Installer created: {INSTALLER_PATH} (version {version})")


def build_spec_file():
    """Generate PyInstaller spec file for advanced configuration."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=['.'],
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
            build_installer()
            return

        elif command == 'installer':
            build_installer()
            return

        elif command == 'dmg':
            # No clean: packages whatever dist/AlbumStudio.app is already there.
            build_dmg()
            return

        else:
            print(f"Unknown command: {command}")
            print("Usage: python build.py [clean|spec|macos|windows|dmg|installer]")
            sys.exit(1)

    # Auto-detect platform and build
    clean_build_folders()

    if platform == 'darwin':
        build_macos()
    elif platform == 'win32':
        build_windows()
        build_installer()
    else:
        print(f"Unsupported platform: {platform}")
        print("Use: python build.py [macos|windows]")
        sys.exit(1)


if __name__ == '__main__':
    main()
