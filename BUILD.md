# Building Album Studio

This guide explains how to create distributable builds of Album Studio for macOS and Windows.

## Prerequisites

### Required for All Platforms

```bash
pip install pyinstaller
```

### macOS Specific (Optional)
- For DMG creation: Built-in `hdiutil` command
- For code signing: Apple Developer account and certificate

### Windows Specific (Optional)
- For installer creation: [Inno Setup](https://jrsoftware.org/isinfo.php) or [NSIS](https://nsis.sourceforge.io/)
- For code signing: Windows code signing certificate

## Quick Build

### Option 1: Using Build Script (Recommended)

```bash
# Build for current platform automatically
python3 build.py

# Build specifically for macOS
python3 build.py macos

# Build specifically for Windows
python3 build.py windows

# Clean build artifacts
python3 build.py clean

# Generate spec file for customization
python3 build.py spec
```

### Option 2: Using Platform Scripts

**macOS:**
```bash
./build-macos.sh
```

**Windows:**
```cmd
build-windows.bat
```

## Manual Build Process

### Building for macOS

1. **Install PyInstaller:**
```bash
pip install pyinstaller
```

2. **Build the application:**
```bash
pyinstaller \
    --name="AlbumStudio" \
    --windowed \
    --onedir \
    --add-data="config:config" \
    --noconfirm \
    src/main.py
```

3. **Output:**
   - Application bundle: `dist/AlbumStudio.app`
   - Supporting files: Included in the .app bundle

4. **Create DMG (Optional):**
```bash
# Simple DMG
hdiutil create -volname AlbumStudio -srcfolder dist/AlbumStudio.app -ov -format UDZO dist/AlbumStudio.dmg

# Or use create-dmg for prettier DMG with background
brew install create-dmg
create-dmg \
  --volname "Album Studio" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "AlbumStudio.app" 175 120 \
  --hide-extension "AlbumStudio.app" \
  --app-drop-link 425 120 \
  "dist/AlbumStudio.dmg" \
  "dist/AlbumStudio.app"
```

5. **Code Signing (Optional but recommended):**
```bash
# Sign the app
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/AlbumStudio.app

# Verify signature
codesign --verify --deep --strict --verbose=2 dist/AlbumStudio.app

# Notarize with Apple (required for Gatekeeper)
xcrun notarytool submit dist/AlbumStudio.dmg --apple-id your@email.com --password app-specific-password --team-id TEAMID
```

### Building for Windows

1. **Install PyInstaller:**
```cmd
pip install pyinstaller
```

2. **Build the application:**
```cmd
pyinstaller ^
    --name=AlbumStudio ^
    --windowed ^
    --onedir ^
    --add-data=config;config ^
    --noconfirm ^
    src\main.py
```

3. **Output:**
   - Executable: `dist\AlbumStudio\AlbumStudio.exe`
   - Supporting files: All files in `dist\AlbumStudio\` folder

4. **Create Installer with Inno Setup (Optional):**

Create `installer.iss`:
```iss
[Setup]
AppName=Album Studio
AppVersion=1.0
DefaultDirName={pf}\AlbumStudio
DefaultGroupName=Album Studio
OutputDir=dist
OutputBaseFilename=AlbumStudio-Setup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\AlbumStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Album Studio"; Filename: "{app}\AlbumStudio.exe"
Name: "{commondesktop}\Album Studio"; Filename: "{app}\AlbumStudio.exe"

[Run]
Filename: "{app}\AlbumStudio.exe"; Description: "Launch Album Studio"; Flags: nowait postinstall skipifsilent
```

Compile with:
```cmd
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

5. **Code Signing (Optional but recommended):**
```cmd
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com dist\AlbumStudio\AlbumStudio.exe
```

## Advanced: Using Spec File

For more control, generate and customize a spec file:

```bash
python3 build.py spec
```

This creates `AlbumStudio.spec`. Edit it to customize:
- Hidden imports
- Excluded modules
- Icon paths
- Bundle identifier (macOS)
- Resource files

Build with the spec file:
```bash
pyinstaller AlbumStudio.spec
```

## Build Configuration

### Adding an Application Icon

1. **Create icons:**
   - macOS: `assets/icon.icns` (512x512 PNG converted to ICNS)
   - Windows: `assets/icon.ico` (256x256 PNG converted to ICO)

2. **Convert icons:**

   **For macOS (.icns):**
   ```bash
   mkdir MyIcon.iconset
   # Create multiple sizes (16x16 to 512x512)
   sips -z 512 512 icon.png --out MyIcon.iconset/icon_512x512.png
   # ... more sizes ...
   iconutil -c icns MyIcon.iconset
   ```

   **For Windows (.ico):**
   Use online converter or ImageMagick:
   ```bash
   convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
   ```

3. **Update build command to include icon**

### Including Data Files

The config folder is automatically included. To add more:

```bash
# macOS
--add-data="source_path:destination_path"

# Windows
--add-data="source_path;destination_path"
```

### Reducing Build Size

1. **Use `--onefile` instead of `--onedir`** (slower startup, smaller size):
```bash
pyinstaller --onefile src/main.py
```

2. **Exclude unused modules:**
```bash
--exclude-module matplotlib --exclude-module PIL.tests
```

3. **Enable UPX compression:**
```bash
# Install UPX first
# macOS: brew install upx
# Windows: Download from upx.github.io

pyinstaller --upx-dir=/path/to/upx src/main.py
```

## Testing the Build

### macOS

1. **Test the .app locally:**
```bash
open dist/AlbumStudio.app
```

2. **Test on another Mac** (without Python installed)

3. **Check for missing dependencies:**
```bash
otool -L dist/AlbumStudio.app/Contents/MacOS/AlbumStudio
```

### Windows

1. **Test the .exe locally:**
```cmd
dist\AlbumStudio\AlbumStudio.exe
```

2. **Test on another Windows machine** (without Python installed)

3. **Check for missing DLLs:**
   - Use [Dependency Walker](https://www.dependencywalker.com/) or
   - [Dependencies](https://github.com/lucasg/Dependencies)

## Distribution

### macOS

**Option 1: DMG File**
- Create DMG as shown above
- Upload to website or GitHub releases

**Option 2: Mac App Store**
- Requires Apple Developer Program ($99/year)
- Additional requirements and review process

### Windows

**Option 1: Installer (Recommended)**
- Create installer with Inno Setup or NSIS
- Upload .exe installer to website or GitHub releases

**Option 2: Portable ZIP**
- Zip the entire `dist\AlbumStudio\` folder
- Users extract and run

**Option 3: Microsoft Store**
- Requires Windows Developer account ($19 one-time)
- Convert to MSIX format

## Troubleshooting

### "Module not found" errors
- Add missing modules to hiddenimports in spec file
- Example: `hiddenimports=['PIL._tkinter_finder']`

### Qt platform plugin errors
- Usually resolved by `--windowed` flag
- If not, manually include Qt plugins:
  ```bash
  --add-binary="/path/to/qt/plugins:qt_plugins"
  ```

### Large build size
- Use `--exclude-module` for unused packages
- Enable UPX compression
- Consider `--onefile` mode

### App won't open on other computers
- **macOS**: Sign and notarize the app
- **Windows**: Sign the executable with a code signing certificate
- Include all dependencies in the bundle

### Config files not found
- Ensure `--add-data` paths are correct
- Use relative paths in your code to access bundled data

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/build.yml`:

```yaml
name: Build

on:
  push:
    tags:
      - 'v*'

jobs:
  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install pyinstaller
      - run: python build.py macos
      - uses: actions/upload-artifact@v3
        with:
          name: AlbumStudio-macOS
          path: dist/AlbumStudio.app

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install pyinstaller
      - run: python build.py windows
      - uses: actions/upload-artifact@v3
        with:
          name: AlbumStudio-Windows
          path: dist/AlbumStudio/
```

## Version Management

Update version in multiple places:
1. `src/main.py` - Add `__version__ = "1.0.0"`
2. `AlbumStudio.spec` - Update version info
3. Installer scripts - Update version numbers

## Support

For build issues, check:
1. PyInstaller documentation: https://pyinstaller.org/
2. PyQt6 packaging guide: https://www.riverbankcomputing.com/
3. Project issues: GitHub issues page
