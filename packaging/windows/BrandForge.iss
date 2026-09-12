; Compile on Windows with Inno Setup 6: ISCC /DSourceDir=... /DVersion=... BrandForge.iss
#ifndef SourceDir
  #error SourceDir must point to the verified native-candidate\BrandForge directory
#endif
#ifndef Version
  #error Version must match app/pyproject.toml
#endif
[Setup]
AppId={{2D653A09-3727-4795-B3A0-B3237A5A0C65}
AppName=BrandForge OS
AppVersion={#Version}
DefaultDirName={localappdata}\Programs\BrandForge OS
DefaultGroupName=BrandForge OS
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=BrandForge-{#Version}-windows-unsigned
OutputDir=installers
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\BrandForge.exe
CloseApplications=yes
RestartApplications=no
LicenseFile={#SourceDir}\THIRD-PARTY-NOTICES\END-CUSTOMER-LICENSE.md
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\THIRD-PARTY-NOTICES"
[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\BrandForge OS"; Filename: "{app}\BrandForge.exe"
Name: "{group}\Uninstall BrandForge OS"; Filename: "{uninstallexe}"
[Run]
Filename: "{app}\BrandForge.exe"; Description: "Open the local workspace"; Flags: nowait postinstall skipifsilent
; Never remove %LOCALAPPDATA%\BrandForgeOS on uninstall. It contains customer work.
