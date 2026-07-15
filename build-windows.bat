@echo off
REM Build script for Windows

echo Building Album Studio for Windows...

REM Install PyInstaller if not present
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build the application
REM Entry point is run.py, not src\main.py -- see run.py for why.
pyinstaller ^
    --name=AlbumStudio ^
    --windowed ^
    --onedir ^
    --icon=assets/icon.ico ^
    --add-data=config;config ^
    --add-data=assets;assets ^
    --noconfirm ^
    run.py

echo.
echo Build complete!
echo Application: dist\AlbumStudio\AlbumStudio.exe
echo.
echo To create an installer, use Inno Setup or NSIS with the files in dist\AlbumStudio\
pause
