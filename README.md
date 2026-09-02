# Sim Field Selector

A local Windows tool that reads live qualifying data from the iRacing simulator and applies the series Charter, Open-Charter, and Open selection rules.

No iRacing web credentials or online data service is used. The tool must run on the same Windows computer and at the same privilege level as the simulator.

## Start the tool

For the quickest local start, double-click `start_iracing_field_tool.bat`. It creates the Python environment when needed, starts the local server, and opens `http://127.0.0.1:5000`.

To start it manually:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

The main screen waits for an active simulator session and then refreshes the live qualifying calculation once per second. Use **Testing Instructions** on the main screen for the AI-roster walkthrough.

Use **Close App** in the upper-right corner to stop the background server. The browser confirms the action and then shows when it is safe to close the tab.

## Build the Windows installer

The main installer offers an optional **Install the AI qualifying demo roster** component. It is selected by default. When selected, it installs the 58-driver roster at `Documents\iRacing\airosters\Sim Field Selector Demo\roster.json` and adds an **AI Demo Guide** Start-menu shortcut. The roster is left in place when the application is uninstalled and an existing roster with the same name is never overwritten. The guide does not open automatically after setup.

The AI demonstration uses a real local qualifying session, so results appear and improve as AI drivers complete laps. No replay file or external demo download is used.

Install the pinned build tools, then build:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt -r .\build-requirements.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_installer.ps1
```

The signed-or-unsigned installer is written to `release\SimFieldSelectorSetup.exe`. The build uses PyInstaller one-directory mode with UPX disabled. Installed rosters, tracks, snapshots, and logs are stored under `%LOCALAPPDATA%\SimFieldSelector`, so application upgrades do not overwrite user data.

The generated installer is not automatically code-signed. Sign both the packaged executable and final installer with an Authenticode certificate before public distribution.

## AI qualifying demo

After installing the optional AI demo component, restart the iRacing UI and create an **AI Single Player** race using the **Sim Field Selector Demo** opponent roster. Choose a compatible NASCAR Xfinity car, an AI-enabled track, and a qualifying session. Start Sim Field Selector before qualifying begins. The installed guide contains the complete walkthrough and remains available from the Start menu.

## Selection logic

1. Every configured `charter` driver in qualifying is locked into the field.
2. The fastest configured 10-13 `open-charter` drivers receive guaranteed positions, based on the selected field size of 40-43.
3. Remaining `open-charter` and `open` drivers compete together by qualifying speed for the five-position final shared pool.
4. Each missing Charter position expands the final shared pool without changing the Open-Charter guarantee.

Driver matching uses customer ID when populated, then exact normalized name, then exact car number. It intentionally does not use fuzzy matching.

## Driver and track lists

Use **Edit Driver Lists** on the main screen to reassign existing drivers or add unconfigured drivers from the active simulator session.

Use **Edit Track List** to store the pit-stall count for a track configuration. The active track can be added directly. Track configurations are matched using the SDK `TrackID`, and the data is saved in `tracks.json`.

## Broadcast views

- `http://127.0.0.1:5000/overlay` provides the compact broadcast overlay.
- `http://127.0.0.1:5000/overlay/details` provides the live qualifying breakdown, including the total number of drivers in the session.

For OBS, add the desired URL as a Browser Source at 1920x1080. Start the collector before qualifying begins.

The **Finalize Field** button writes an auditable JSON snapshot under `snapshots/`.

## Local endpoints

- `GET /api/live/field` returns the current live field calculation.
- `POST /api/live/finalize` saves the current live field snapshot.
- `GET /api/live/drivers` returns the active simulator roster for the driver editor.
- `GET` and `PUT /api/roster` load and save the configured driver list.
- `GET` and `PUT /api/tracks` load and save local track pit-stall data.

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m unittest discover -s tests -v
node --check .\static\app.js
node --check .\static\overlay.js
node --check .\static\details.js
```
