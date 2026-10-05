; Installer Windows LinkDeck (Inno Setup 6). Dipanggil oleh build/package.py:
;   ISCC /DAppVersion=1.0.0 build\windows\linkdeck.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8F1C2B7A-5D4E-4C1B-9A63-2F6E0D7C4B11}
AppName=LinkDeck
AppVersion={#AppVersion}
AppVerName=LinkDeck {#AppVersion}
AppPublisher=LinkDeck
DefaultDirName={autopf}\LinkDeck
DefaultGroupName=LinkDeck
DisableProgramGroupPage=yes
OutputDir=..\..\out
OutputBaseFilename=LinkDeck-{#AppVersion}-windows-setup
SetupIconFile=..\icons\linkdeck.ico
UninstallDisplayIcon={app}\LinkDeck.exe
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
en.DesktopIcon=Buat ikon di desktop
en.Shortcuts=Pintasan:
en.LaunchNow=Jalankan LinkDeck sekarang

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:Shortcuts}"

[Files]
Source: "..\..\dist\LinkDeck\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\LinkDeck"; Filename: "{app}\LinkDeck.exe"
Name: "{autodesktop}\LinkDeck"; Filename: "{app}\LinkDeck.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LinkDeck.exe"; Description: "{cm:LaunchNow}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\_internal\bin\adb.exe"; Parameters: "kill-server"; Flags: runhidden skipifdoesntexist; RunOnceId: "KillAdb"
