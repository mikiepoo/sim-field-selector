SIM FIELD SELECTOR - DEMO
=========================

The application can download testapiqslice.rpy to:

  Documents\iRacing\replay\testapiqslice.rpy

To run the demonstration:

1. Launch Sim Field Selector from the desktop or Start menu.
2. Select Download Demo Replay and wait for the download to finish.
3. When prompted, allow the application to open the iRacing UI and sign in normally.
4. In iRacing, choose Replays, load testapiqslice.rpy, and press Play.
5. The browser opens to http://127.0.0.1:5000 and connects to the replay through
   the local iRacing SDK.
6. Open the Live Breakdown or Broadcast Overlay from the main screen.

The download is verified against its expected SHA-256 checksum before it is
installed. No iRacing web credentials are used. Replay SDK data can be more limited than
a live qualifying session, so this demo proves local SDK connectivity and the
saved qualifying data contained in the replay.

Editable application data and logs are stored in:

  %LOCALAPPDATA%\SimFieldSelector
