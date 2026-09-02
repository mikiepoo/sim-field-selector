from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from field_selector import SelectionError, load_roster, save_roster, select_field
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
    )
    if test_config:
        app.config.update(test_config)

    live_reader = app.config.get("LIVE_READER") or LiveIRacingReader()

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

    def calculate_demo_field(settings: dict) -> tuple[dict, int]:
        try:
            field_size, open_charter_spots, open_spots = field_settings(settings)
            configured_roster = roster()
            groups = {
                level: [driver for driver in configured_roster if driver.charter_level == level]
                for level in ("charter", "open-charter", "open")
            }
            selected = (
                groups["charter"][:22]
                + groups["open-charter"][:17]
                + groups["open"][:9]
            )
            selected_ids = {id(driver) for driver in selected}
            selected.extend(
                driver for driver in configured_roster
                if id(driver) not in selected_ids and len(selected) < 48
            )
            selected.sort(
                key=lambda driver: hashlib.sha256(
                    f"{driver.name}|{driver.car_number}".encode("utf-8")
                ).hexdigest()
            )
            candidates = [
                {
                    "name": driver.name,
                    "car_number": driver.car_number,
                    "cust_id": driver.cust_id,
                    "best_lap_time": round(23.348 + index * 0.011, 3),
                }
                for index, driver in enumerate(selected)
            ]
            result = select_field(
                candidates,
                configured_roster,
                open_charter_spots,
                open_spots,
                field_size,
            )
            captured_at = datetime.now(timezone.utc).isoformat()
            result["source"] = {"type": "dry-run", "captured_at": captured_at}
            result["live"] = {
                "connected": True,
                "sdk_available": True,
                "message": "Dry-run sample qualifying",
                "captured_at": captured_at,
                "subsession_id": "DEMO",
                "track_name": "Sim Field Selector Demo",
                "track_config": "Dry Run",
                "session_name": "QUALIFY",
                "session_state": "racing",
                "session_time_remaining": 600,
                "provisional": True,
                "driver_count": len(candidates),
                "pit_stalls": field_size,
                "dry_run": True,
            }
            return result, 200
        except (SelectionError, TypeError, ValueError) as exc:
            return {"error": str(exc)}, 400

    @app.get("/api/live/field")
    def live_field_api():
        result, status = calculate_live_field(request.args)
        return jsonify(result), status

    @app.get("/api/demo/field")
    def demo_field_api():
        result, status = calculate_demo_field(request.args)
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
