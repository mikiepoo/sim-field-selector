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

The main screen waits for an active simulator session and then refreshes the live qualifying calculation once per second.

## Build the Windows installer

The main installer can include an optional **Enable the downloadable iRacing demo replay** setup component. The installer does not contain the 298 MB replay. When that component is selected, the waiting screen can download `testapiqslice.rpy` over HTTPS from `estesl2l.com`, verify its fixed SHA-256 checksum, and save it to `Documents\iRacing\replay`. It will not overwrite a different existing file. If the component is not selected, the normal live SDK application is installed without the private replay URL.

Keep the private download URL out of Git by placing it on one line in `.demo-replay-url`, or pass it only when building:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_demo.ps1 -ReplayUrl "https://estesl2l.com/your-private-folder/testapiqslice.rpy"
```

The `.demo-replay-url` file is ignored by Git. The URL is hidden from the browser interface, but anyone with access to the compiled application or network traffic can still recover it; an unguessable URL is suitable for casual sharing, not strong access control.

After a verified download, the application asks whether to open iRacing using the registered `iracing:` Windows protocol. iRacing does not register `.rpy` files for direct opening, so the user must still choose **Replays** and launch `testapiqslice.rpy` in the iRacing UI.

Install the pinned build tools, then build:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt -r .\build-requirements.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_demo.ps1
```

The signed-or-unsigned installer is written to `release\SimFieldSelectorSetup.exe`. The build uses PyInstaller one-directory mode with UPX disabled. Installed rosters, tracks, snapshots, and logs are stored under `%LOCALAPPDATA%\SimFieldSelector`, so application upgrades do not overwrite user data.

The generated installer is not automatically code-signed. Sign both the packaged executable and final installer with an Authenticode certificate before public distribution.

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

For OBS, add the desired URL as a Browser Source at 1920x1080. Start the collector before qualifying; a race-only replay cannot reconstruct qualifying laps that were never saved.

The **Finalize Field** button writes an auditable JSON snapshot under `snapshots/`.

## Local endpoints

- `GET /api/live/field` returns the current live field calculation.
- `POST /api/live/finalize` saves the current live field snapshot.
- `GET /api/live/drivers` returns the active simulator roster for the driver editor.
- `GET` and `PUT /api/roster` load and save the configured driver list.
- `GET` and `PUT /api/tracks` load and save local track pit-stall data.
- `GET /api/demo-replay` reports whether the configured demo replay is installed.
- `POST /api/demo-replay/download` downloads and checksum-verifies the configured demo replay.
- `POST /api/demo-replay/open-iracing` opens the installed iRacing UI through its Windows protocol.

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m unittest discover -s tests -v
node --check .\static\app.js
node --check .\static\overlay.js
node --check .\static\details.js
```
