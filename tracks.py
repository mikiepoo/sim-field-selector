from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def load_tracks(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    rows = json.loads(source.read_text(encoding="utf-8"))
    return validate_tracks(rows)


def save_tracks(path: str | Path, rows: Any) -> list[dict[str, Any]]:
    tracks = validate_tracks(rows)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    temporary.write_text(json.dumps(tracks, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return tracks


def validate_tracks(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise TypeError("Tracks must be provided as an array")
    tracks: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise TypeError(f"Track row {index} must be an object")
        try:
            track_id = int(row.get("track_id"))
            pit_stalls = int(row.get("pit_stalls"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Track row {index} needs numeric Track ID and pit stalls") from exc
        if track_id <= 0:
            raise ValueError(f"Track row {index} Track ID must be positive")
        if not 1 <= pit_stalls <= 200:
            raise ValueError(f"Track row {index} pit stalls must be between 1 and 200")
        if track_id in seen_ids:
            raise ValueError(f"Duplicate Track ID: {track_id}")
        track_name = str(row.get("track_name") or "").strip()
        if not track_name:
            raise ValueError(f"Track row {index} needs a track name")
        seen_ids.add(track_id)
        tracks.append({
            "track_id": track_id,
            "track_name": track_name,
            "track_config": str(row.get("track_config") or "").strip(),
            "pit_stalls": pit_stalls,
        })
    return sorted(tracks, key=lambda row: (row["track_name"].lower(), row["track_config"].lower(), row["track_id"]))


def find_track(tracks: list[dict[str, Any]], track_id: Any) -> dict[str, Any] | None:
    try:
        target = int(track_id)
    except (TypeError, ValueError):
        return None
    return next((row for row in tracks if row["track_id"] == target), None)
