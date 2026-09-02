import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import demo_replay


class FakeResponse:
    def __init__(self, payload: bytes, url: str):
        self.stream = io.BytesIO(payload)
        self.url = url
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int) -> bytes:
        return self.stream.read(size)

    def geturl(self) -> str:
        return self.url


class DemoReplayTests(unittest.TestCase):
    def test_download_verifies_and_atomically_installs_replay(self):
        payload = b"test replay payload"
        expected = hashlib.sha256(payload).hexdigest().upper()
        url = "https://estesl2l.com/private/testapiqslice.rpy"
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "iRacing" / "replay" / demo_replay.REPLAY_FILENAME
            with patch.object(demo_replay, "REPLAY_SHA256", expected), patch(
                "demo_replay.urllib.request.urlopen", return_value=FakeResponse(payload, url)
            ):
                result = demo_replay.download_replay(url, destination)
            self.assertTrue(result["downloaded"])
            self.assertEqual(destination.read_bytes(), payload)
            self.assertEqual(list(destination.parent.glob("*.part")), [])

    def test_checksum_failure_does_not_leave_replay_or_partial_file(self):
        payload = b"wrong replay payload"
        url = "https://estesl2l.com/private/testapiqslice.rpy"
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / demo_replay.REPLAY_FILENAME
            with patch.object(demo_replay, "REPLAY_SHA256", "0" * 64), patch(
                "demo_replay.urllib.request.urlopen", return_value=FakeResponse(payload, url)
            ):
                with self.assertRaisesRegex(demo_replay.ReplayDownloadError, "checksum"):
                    demo_replay.download_replay(url, destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(temp_dir).glob("*.part")), [])

    def test_non_estes_https_url_is_rejected_before_network_access(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "demo_replay.urllib.request.urlopen"
        ) as opener:
            with self.assertRaisesRegex(demo_replay.ReplayDownloadError, "estesl2l.com"):
                demo_replay.download_replay(
                    "https://example.com/testapiqslice.rpy",
                    Path(temp_dir) / demo_replay.REPLAY_FILENAME,
                )
            opener.assert_not_called()

    def test_open_iracing_uses_registered_windows_protocol(self):
        with patch.object(demo_replay.os, "name", "nt"), patch.object(
            demo_replay.os, "startfile", create=True
        ) as startfile:
            demo_replay.open_iracing()
        startfile.assert_called_once_with("iracing:")


if __name__ == "__main__":
    unittest.main()
