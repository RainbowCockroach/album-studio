; AlbumStudio Inno Setup Script
; Builds a Windows installer from PyInstaller --onedir output
;
; Usage: python build.py windows   (or: python build.py installer)
; build.py passes the real version as /DMyAppVersion=<x.y.z> from src/version.py.
; Requires: PyInstaller build completed first (dist\AlbumStudio\ must exist)

#define MyAppName "Album Studio"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "RainbowCockroach"
#define MyAppURL "https://github.com/RainbowCockroach/album-studio"
#define MyAppExeName "AlbumStudio.exe"

[Setup]
; AppId is how Setup recognises an existing install to upgrade. Never change it.
AppId={{8F3B2A1E-5C4D-4E6F-9A8B-7C2D1E0F3A5B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\AlbumStudio
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\icon.ico
; The release workflow uploads this exact name, and UpdateService picks the
; installer out of a release by its "setup.exe" suffix.
OutputDir=installer_output
OutputBaseFilename=AlbumStudio-Windows-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Per-user install into %LOCALAPPDATA%\Programs: no admin prompt, and the
; in-app updater can re-run Setup silently. Deliberately no "install for all
; users" option: a silent update always installs per-user, so an all-users
; copy would be left behind next to a fresh second one.
PrivilegesRequired=lowest
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; PyInstaller's library folder is replaced wholesale on upgrade. Copying a new
; version over the old one would leave stale DLLs from dropped dependencies.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\AlbumStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
