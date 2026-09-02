from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


APP_FOLDER = "SimFieldSelector"
RESOURCE_DIR = Path(__file__).resolve().parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def data_dir() -> Path:
    if not is_frozen():
        return RESOURCE_DIR
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    destination = root / APP_FOLDER
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def prepare_data_paths() -> dict[str, Path]:
    destination = data_dir()
    roster_path = destination / "roster.json"
    tracks_path = destination / "tracks.json"
    if is_frozen():
        _seed_file("roster.json", roster_path, "[]\n")
        _seed_file("tracks.json", tracks_path, "[]\n")
    return {
        "resource_dir": RESOURCE_DIR,
        "data_dir": destination,
        "roster": roster_path,
        "tracks": tracks_path,
        "snapshots": destination / "snapshots",
        "logs": destination / "logs",
    }


def _seed_file(resource_name: str, destination: Path, fallback: str) -> None:
    if destination.exists():
        return
    source = RESOURCE_DIR / resource_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.copy2(source, destination)
    else:
        destination.write_text(fallback, encoding="utf-8")
