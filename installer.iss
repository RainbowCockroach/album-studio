; AlbumStudio Inno Setup Script
; Builds a Windows installer from PyInstaller --onedir output
;
; Usage: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; Requires: PyInstaller build completed first (dist\AlbumStudio\ must exist)

#define MyAppName "AlbumStudio"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "RainbowCockroach"
#define MyAppURL "https://github.com/RainbowCockroach/album-studio"
#define MyAppExeName "AlbumStudio.exe"

[Setup]
AppId={{8F3B2A1E-5C4D-4E6F-9A8B-7C2D1E0F3A5B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=installer_output
OutputBaseFilename=AlbumStudio_Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\AlbumStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
