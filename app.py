from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from field_selector import SelectionError, load_roster, save_roster, select_field
from demo_replay import (
    ReplayDownloadError,
    default_replay_destination,
    download_replay,
    load_download_url,
    open_iracing,
    replay_status,
)
from live_iracing import LiveIRacingReader
from runtime_paths import prepare_data_paths
from tracks import find_track, load_tracks, save_tracks


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PATHS = prepare_data_paths()


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(DEFAULT_PATHS["resource_dir"] / "templates"),
        static_folder=str(DEFAULT_PATHS["resource_dir"] / "static"),
    )
    app.config.from_mapping(
        ROSTER_PATH=str(DEFAULT_PATHS["roster"]),
        TRACKS_PATH=str(DEFAULT_PATHS["tracks"]),
        SNAPSHOT_PATH=str(DEFAULT_PATHS["snapshots"]),
        REPLAY_URL=load_download_url(DEFAULT_PATHS["resource_dir"]),
        REPLAY_DESTINATION=str(default_replay_destination()),
    )
    if test_config:
        app.config.update(test_config)

    live_reader = app.config.get("LIVE_READER") or LiveIRacingReader()
    replay_download_lock = threading.Lock()

    def roster():
        return load_roster(app.config["ROSTER_PATH"])

    def field_settings(values) -> tuple[int, int, int]:
        field_size = int(values.get("field_size", 40))
        if not 40 <= field_size <= 43:
            raise SelectionError("Total field size must be between 40 and 43")
        return field_size, field_size - 30, 5

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/overlay")
    def overlay():
        return render_template("overlay.html")

    @app.get("/overlay/details")
    def overlay_details():
        return render_template("overlay_details.html")

    @app.get("/api/roster")
    def get_roster():
        rows = [driver.as_dict() for driver in roster()]
        return jsonify({"drivers": rows, "count": len(rows)})

    @app.put("/api/roster")
    def update_roster():
        body = request.get_json(silent=True) or {}
        try:
            drivers = save_roster(app.config["ROSTER_PATH"], body.get("drivers"))
            return jsonify({
                "saved": True,
                "drivers": [driver.as_dict() for driver in drivers],
                "count": len(drivers),
            })
        except (SelectionError, TypeError, ValueError, OSError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/tracks")
    def get_tracks():
        rows = load_tracks(app.config["TRACKS_PATH"])
        return jsonify({"tracks": rows, "count": len(rows)})

    @app.put("/api/tracks")
    def update_tracks():
        body = request.get_json(silent=True) or {}
        try:
            tracks = save_tracks(app.config["TRACKS_PATH"], body.get("tracks"))
            return jsonify({"saved": True, "tracks": tracks, "count": len(tracks)})
        except (TypeError, ValueError, OSError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/demo-replay")
    def demo_replay_status_api():
        destination = Path(app.config["REPLAY_DESTINATION"])
        return jsonify(replay_status(destination, bool(app.config["REPLAY_URL"])))

    @app.post("/api/demo-replay/download")
    def demo_replay_download_api():
        url = str(app.config["REPLAY_URL"] or "").strip()
        if not url:
            return jsonify({"error": "This build does not have a demo replay download URL configured."}), 404
        if not replay_download_lock.acquire(blocking=False):
            return jsonify({"error": "The demo replay is already downloading."}), 409
        try:
            result = download_replay(url, Path(app.config["REPLAY_DESTINATION"]))
            return jsonify({"saved": True, **result})
        except ReplayDownloadError as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            replay_download_lock.release()

    @app.post("/api/demo-replay/open-iracing")
    def demo_replay_open_iracing_api():
        try:
            open_iracing()
            return jsonify({"opened": True})
        except ReplayDownloadError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/live/drivers")
    def live_drivers_api():
        live = live_reader.snapshot()
        return jsonify({
            "connected": bool(live.get("connected")),
            "message": live.get("message"),
            "subsession_id": live.get("subsession_id"),
            "track_id": live.get("track_id"),
            "track_name": live.get("track_name"),
            "track_config": live.get("track_config"),
            "drivers": live.get("drivers", []) if live.get("connected") else [],
        })

    def calculate_live_field(settings: dict) -> tuple[dict, int]:
        try:
            field_size, open_charter_spots, open_spots = field_settings(settings)
        except (SelectionError, TypeError, ValueError) as exc:
            return {"error": str(exc)}, 400
        live = live_reader.snapshot()
        if not live["connected"]:
            return {"live": live}, 200
        try:
            live["driver_count"] = len(live.get("drivers", []))
            track = find_track(load_tracks(app.config["TRACKS_PATH"]), live.get("track_id"))
            live["pit_stalls"] = track.get("pit_stalls") if track else None
            result = select_field(
                live["drivers"],
                roster(),
                open_charter_spots,
                open_spots,
                field_size,
            )
            result["source"] = {
                "type": "live",
                "subsession_id": live.get("subsession_id"),
                "captured_at": live["captured_at"],
            }
            result["live"] = {key: value for key, value in live.items() if key != "drivers"}
            return result, 200
        except (SelectionError, TypeError, ValueError) as exc:
            return {"error": str(exc), "live": live}, 400

    @app.get("/api/live/field")
    def live_field_api():
        result, status = calculate_live_field(request.args)
        return jsonify(result), status

    @app.post("/api/live/finalize")
    def finalize_live_api():
        body = request.get_json(silent=True) or {}
        result, status = calculate_live_field(body)
        if status != 200 or not result.get("live", {}).get("connected"):
            return jsonify(result), status
        snapshot_dir = Path(app.config["SNAPSHOT_PATH"])
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        subsession = result.get("source", {}).get("subsession_id") or "unknown"
        filename = f"field-{subsession}-{timestamp}.json"
        destination = snapshot_dir / filename
        destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return jsonify({"saved": True, "filename": filename, "result": result})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
