from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlparse


REPLAY_FILENAME = "testapiqslice.rpy"
REPLAY_SHA256 = "74DE11BD4D6672C31821B026348906332029BAE8DFC16B8390234BBFF225E724"
MAX_REPLAY_BYTES = 400 * 1024 * 1024
ALLOWED_HOSTS = {"estesl2l.com", "www.estesl2l.com"}


class ReplayDownloadError(RuntimeError):
    pass


def load_download_url(resource_dir: Path) -> str:
    configured = os.environ.get("SIM_FIELD_SELECTOR_REPLAY_URL", "").strip()
    if configured:
        return configured
    executable_dir = Path(sys.executable).resolve().parent
    candidates = [
        executable_dir / "demo_replay.json",
        Path(resource_dir) / "demo_replay.json",
        executable_dir / "_internal" / "demo_replay.json",
    ]
    for config_path in dict.fromkeys(candidates):
        if not config_path.exists():
            continue
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        configured = str(payload.get("url") or "").strip()
        if configured:
            return configured
    return ""


def default_replay_destination() -> Path:
    documents = _windows_documents_folder() if os.name == "nt" else None
    return (documents or Path.home() / "Documents") / "iRacing" / "replay" / REPLAY_FILENAME


def replay_status(destination: Path, configured: bool) -> dict:
    return {
        "configured": configured,
        "installed": destination.is_file(),
        "filename": REPLAY_FILENAME,
        "destination": str(destination),
    }


def open_iracing() -> None:
    if os.name != "nt" or not hasattr(os, "startfile"):
        raise ReplayDownloadError("Opening iRacing automatically is only supported on Windows.")
    try:
        os.startfile("iracing:")
    except OSError as exc:
        raise ReplayDownloadError(
            "Windows could not open iRacing. Start the iRacing UI normally, then choose Replays."
        ) from exc


def download_replay(url: str, destination: Path) -> dict:
    _validate_url(url)
    destination = Path(destination)
    if destination.exists():
        if _sha256(destination) == REPLAY_SHA256:
            return {"downloaded": False, "already_installed": True, "destination": str(destination)}
        raise ReplayDownloadError(
            f"A different file already exists at {destination}. Move or rename it before downloading the demo."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "SimFieldSelector/1.0"})
        with urllib.request.urlopen(request, timeout=45) as response:
            _validate_url(response.geturl())
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_REPLAY_BYTES:
                raise ReplayDownloadError("The server reported a replay larger than the allowed 400 MB.")

            digest = hashlib.sha256()
            total = 0
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=f"{REPLAY_FILENAME}.", suffix=".part", dir=destination.parent, delete=False
            ) as temp_file:
                temp_path = Path(temp_file.name)
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_REPLAY_BYTES:
                        raise ReplayDownloadError("The downloaded replay exceeded the allowed 400 MB.")
                    digest.update(chunk)
                    temp_file.write(chunk)

        if digest.hexdigest().upper() != REPLAY_SHA256:
            raise ReplayDownloadError("The replay download did not match the expected SHA-256 checksum.")
        os.replace(temp_path, destination)
        temp_path = None
        return {"downloaded": True, "already_installed": False, "destination": str(destination), "bytes": total}
    except ReplayDownloadError:
        raise
    except Exception as exc:
        raise ReplayDownloadError(f"Replay download failed: {exc}") from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise ReplayDownloadError("The demo replay URL must use HTTPS on estesl2l.com.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _windows_documents_folder() -> Path | None:
    try:
        guid = ctypes.create_string_buffer(uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7").bytes_le)
        folder_path = ctypes.c_wchar_p()
        # FDD39AD0-238F-46AF-ADB4-6C85480369C7 (FOLDERID_Documents)
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(folder_path)
        )
        if result == 0 and folder_path.value:
            value = folder_path.value
            ctypes.windll.ole32.CoTaskMemFree(folder_path)
            return Path(value)
    except Exception:
        return None
    return None
