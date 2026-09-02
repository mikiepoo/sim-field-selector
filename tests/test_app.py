import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app


class ConnectedReader:
    def snapshot(self):
        return {
            "connected": True,
            "sdk_available": True,
            "message": "connected",
            "captured_at": "2026-08-26T00:00:00+00:00",
            "subsession_id": 88235141,
            "track_id": 123,
            "track_name": "Charlotte Motor Speedway",
            "track_config": "Oval",
            "session_num": -2,
            "session_name": "QUALIFY",
            "session_state": "racing",
            "provisional": True,
            "drivers": [
                {"name": "Terrence Murphy", "car_number": "5", "cust_id": 1109711, "best_lap_time": 29.8},
                {"name": "James Coffman", "car_number": "01", "cust_id": 574792, "best_lap_time": 30.0},
            ],
        }


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app({"TESTING": True, "SECRET_KEY": "test"}).test_client()

    def test_main_page_is_live_only_and_has_editors(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Waiting for the iRacing simulator", response.data)
        self.assertIn(b"Edit Driver Lists", response.data)
        self.assertIn(b"Edit Track List", response.data)
        self.assertIn(b"Download Demo Replay", response.data)
        self.assertNotIn(b"Paste qualifying order", response.data)
        self.assertNotIn(b"Upload result file", response.data)
        self.assertNotIn(b"Connect iRacing", response.data)

    def test_removed_online_and_manual_routes_are_unavailable(self):
        self.assertEqual(self.client.get("/auth/login").status_code, 404)
        self.assertEqual(self.client.post("/api/field/select", json={}).status_code, 404)
        self.assertEqual(self.client.post("/api/field/from-file").status_code, 404)
        self.assertEqual(self.client.post("/api/field/from-iracing", json={}).status_code, 404)

    def test_roster_is_loaded(self):
        response = self.client.get("/api/roster")
        self.assertEqual(response.status_code, 200)
        expected = len(json.loads(Path("roster.json").read_text(encoding="utf-8")))
        self.assertEqual(response.get_json()["count"], expected)

    def test_roster_can_be_reassigned_and_new_driver_added(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            roster_path = Path(temp_dir) / "roster.json"
            roster_path.write_text(json.dumps([
                {"car_number": "1", "name": "Existing Driver", "charter_level": "open", "cust_id": None},
            ]), encoding="utf-8")
            client = create_app({"TESTING": True, "ROSTER_PATH": str(roster_path)}).test_client()
            response = client.put("/api/roster", json={"drivers": [
                {"car_number": "1", "name": "Existing Driver", "charter_level": "charter", "cust_id": None},
                {"car_number": "02", "name": "New Driver", "charter_level": "open-charter", "cust_id": 12345},
            ]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["count"], 2)
            saved = json.loads(roster_path.read_text(encoding="utf-8"))
            self.assertEqual(saved[0]["charter_level"], "charter")
            self.assertEqual(saved[1]["name"], "New Driver")

    def test_roster_update_rejects_duplicate_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            roster_path = Path(temp_dir) / "roster.json"
            roster_path.write_text("[]", encoding="utf-8")
            client = create_app({"TESTING": True, "ROSTER_PATH": str(roster_path)}).test_client()
            response = client.put("/api/roster", json={"drivers": [
                {"car_number": "1", "name": "Same Driver", "charter_level": "open"},
                {"car_number": "2", "name": "same  driver", "charter_level": "charter"},
            ]})
            self.assertEqual(response.status_code, 400)
            self.assertIn("Duplicate driver name", response.get_json()["error"])
            self.assertEqual(json.loads(roster_path.read_text(encoding="utf-8")), [])

    def test_track_list_can_be_saved_and_loaded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tracks_path = Path(temp_dir) / "tracks.json"
            client = create_app({"TESTING": True, "TRACKS_PATH": str(tracks_path)}).test_client()
            response = client.put("/api/tracks", json={"tracks": [{
                "track_id": 123,
                "track_name": "Charlotte Motor Speedway",
                "track_config": "Oval",
                "pit_stalls": 43,
            }]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["count"], 1)
            loaded = client.get("/api/tracks").get_json()["tracks"]
            self.assertEqual(loaded[0]["pit_stalls"], 43)

    def test_track_list_rejects_duplicate_track_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            client = create_app({"TESTING": True, "TRACKS_PATH": str(Path(temp_dir) / "tracks.json")}).test_client()
            response = client.put("/api/tracks", json={"tracks": [
                {"track_id": 123, "track_name": "Track", "track_config": "A", "pit_stalls": 40},
                {"track_id": 123, "track_name": "Track", "track_config": "B", "pit_stalls": 41},
            ]})
            self.assertEqual(response.status_code, 400)
            self.assertIn("Duplicate Track ID", response.get_json()["error"])

    def test_demo_replay_status_and_download(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "testapiqslice.rpy"
            client = create_app({
                "TESTING": True,
                "REPLAY_URL": "https://estesl2l.com/private/testapiqslice.rpy",
                "REPLAY_DESTINATION": str(destination),
            }).test_client()
            status = client.get("/api/demo-replay").get_json()
            self.assertTrue(status["configured"])
            self.assertFalse(status["installed"])
            with patch("app.download_replay", return_value={
                "downloaded": True,
                "already_installed": False,
                "destination": str(destination),
                "bytes": 298453960,
            }) as downloader:
                response = client.post("/api/demo-replay/download")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json()["saved"])
            downloader.assert_called_once()

    def test_demo_replay_download_requires_build_url(self):
        client = create_app({"TESTING": True, "REPLAY_URL": ""}).test_client()
        response = client.post("/api/demo-replay/download")
        self.assertEqual(response.status_code, 404)
        self.assertIn("does not have", response.get_json()["error"])

    def test_demo_replay_can_request_iracing_ui_open(self):
        with patch("app.open_iracing") as opener:
            response = self.client.post("/api/demo-replay/open-iracing")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["opened"])
        opener.assert_called_once_with()

    def test_overlay_pages_are_available(self):
        overlay = self.client.get("/overlay")
        self.assertEqual(overlay.status_code, 200)
        self.assertIn(b"Live Qualifying", overlay.data)
        details = self.client.get("/overlay/details")
        self.assertEqual(details.status_code, 200)
        self.assertIn(b"Field Breakdown", details.data)
        self.assertIn(b"Total drivers", details.data)
        self.assertNotIn(b"Edit Driver Lists", details.data)

    def test_live_field_includes_driver_count_and_stored_pit_stalls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tracks_path = Path(temp_dir) / "tracks.json"
            tracks_path.write_text(json.dumps([{
                "track_id": 123,
                "track_name": "Charlotte Motor Speedway",
                "track_config": "Oval",
                "pit_stalls": 43,
            }]), encoding="utf-8")
            client = create_app({"TESTING": True, "LIVE_READER": ConnectedReader(), "TRACKS_PATH": str(tracks_path)}).test_client()
            response = client.get("/api/live/field?field_size=40")
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            self.assertEqual(result["source"]["type"], "live")
            self.assertEqual(result["summary"]["in_field"], 2)
            self.assertEqual(result["live"]["driver_count"], 2)
            self.assertEqual(result["live"]["pit_stalls"], 43)

            session = client.get("/api/live/drivers").get_json()
            self.assertTrue(session["connected"])
            self.assertEqual(session["track_id"], 123)
            self.assertEqual(len(session["drivers"]), 2)

    def test_field_size_derives_open_charter_count(self):
        client = create_app({"TESTING": True, "LIVE_READER": ConnectedReader()}).test_client()
        result = client.get("/api/live/field?field_size=43").get_json()
        self.assertEqual(result["rules"]["field_size"], 43)
        self.assertEqual(result["rules"]["open_charter_spots"], 13)
        self.assertEqual(result["rules"]["base_open_spots"], 5)

    def test_field_size_must_be_between_40_and_43(self):
        client = create_app({"TESTING": True, "LIVE_READER": ConnectedReader()}).test_client()
        for field_size in (39, 44):
            response = client.get(f"/api/live/field?field_size={field_size}")
            self.assertEqual(response.status_code, 400)
            self.assertIn("between 40 and 43", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
