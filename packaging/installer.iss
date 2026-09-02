#define MyAppName "Sim Field Selector"
#define MyAppVersion "1.0.2"
#define MyAppPublisher "Sim Field Selector"
#define ProjectRoot AddBackslash(SourcePath) + ".."
#define AppSource ProjectRoot + "\dist\SimFieldSelector"
#include ProjectRoot + "\build\demo_config\installer_defines.iss"
#define DemoConfigSource ProjectRoot + "\build\demo_config\demo_replay_private.json"
#define BlankDemoConfigSource ProjectRoot + "\build\demo_config\demo_replay.json"

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
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce
#if DemoAvailable
Name: "demoreplay"; Description: "Enable the downloadable iRacing demo replay"; GroupDescription: "Optional demonstration:"; Flags: checkedonce
#endif

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ProjectRoot}\packaging\DEMO-README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BlankDemoConfigSource}"; DestDir: "{app}"; DestName: "demo_replay.json"; Flags: ignoreversion
#if DemoAvailable
Source: "{#DemoConfigSource}"; DestDir: "{app}"; DestName: "demo_replay.json"; Tasks: demoreplay; Flags: ignoreversion
#endif

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\SimFieldSelector.exe"
#if DemoAvailable
Name: "{group}\Demo Instructions"; Filename: "{app}\DEMO-README.txt"; Tasks: demoreplay
#endif
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\SimFieldSelector.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SimFieldSelector.exe"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
