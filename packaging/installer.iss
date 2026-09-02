#define MyAppName "Sim Field Selector"
#define MyAppVersion "1.3.1"
#define MyAppPublisher "Sim Field Selector"
#define ProjectRoot AddBackslash(SourcePath) + ".."
#define AppSource ProjectRoot + "\dist\SimFieldSelector"
#define AIRosterSource ProjectRoot + "\packaging\ai-demo-roster\roster.json"

[Setup]
AppId={{76DFEE6F-9583-4D02-912E-D29025323CBD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SimFieldSelector
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#ProjectRoot}\release
OutputBaseFilename=SimFieldSelectorSetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\SimFieldSelector.exe
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "aidemo"; Description: "Install the AI qualifying demo roster"; GroupDescription: "Optional demonstration:"

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ProjectRoot}\static\AI-DEMO-GUIDE.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#AIRosterSource}"; DestDir: "{userdocs}\iRacing\airosters\Sim Field Selector Demo"; DestName: "roster.json"; Tasks: aidemo; Flags: onlyifdoesntexist uninsneveruninstall

[InstallDelete]
Type: files; Name: "{app}\demo_replay.json"
Type: files; Name: "{app}\_internal\demo_replay.json"
Type: files; Name: "{app}\DEMO-README.txt"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\SimFieldSelector.exe"
Name: "{group}\AI Demo Guide"; Filename: "{app}\AI-DEMO-GUIDE.html"; Tasks: aidemo
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\SimFieldSelector.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SimFieldSelector.exe"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
