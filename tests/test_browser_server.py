from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from recorder.live.frame_buffer import LiveFrameBuffer
from recorder.recording_state import RecordingState
from recorder.services.playback_service import PlaybackService
from recorder.storage.file_recording_library import FileRecordingLibrary
from recorder.web.server import RecorderWebServer


class BrowserServerTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.recordings_directory_path = Path(temporary_directory.name)
        self.recording_path = self.recordings_directory_path / "saved.mkv"
        self.recording_path.write_bytes(b"saved recording")
        self.recording_state = RecordingState()
        self.recording_library = FileRecordingLibrary(self.recordings_directory_path, self.recording_state)
        self.playback_service = PlaybackService(self.recording_library, Mock())
        self.frame_buffer = LiveFrameBuffer()
        self.browser_server = RecorderWebServer("127.0.0.1", 0, self.frame_buffer,
                                               self.recording_library, self.playback_service, self.recording_state)
        self.browser_server.start()
        self.addCleanup(self.browser_server.stop)
        self.browser_port = self.browser_server.server_address[1]

    def request(self, path, method="GET", headers=None):
        connection = HTTPConnection("127.0.0.1", self.browser_port, timeout=3)
        self.addCleanup(connection.close)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()

    def test_library_excludes_active_empty_and_symlink_files(self):
        active_path = self.recordings_directory_path / "active.mkv"
        active_path.write_bytes(b"in progress")
        self.recording_state.mark_started(active_path)
        (self.recordings_directory_path / "empty.mkv").touch()
        (self.recordings_directory_path / "linked.mkv").symlink_to(self.recording_path)
        status_code, _, response_body = self.request("/api/recordings")
        self.assertEqual(status_code, 200)
        self.assertEqual([entry["filename"] for entry in json.loads(response_body)], ["saved.mkv"])
        for filename in ("active.mkv", "empty.mkv", "linked.mkv", "..%2Fsaved.mkv", "%2Fetc%2Fpasswd"):
            with self.subTest(filename=filename):
                self.assertIn(self.request(f"/api/recordings/{filename}/download")[0], (400, 404))

    def test_browser_playback_supports_seeking_and_head(self):
        playback_path = self.recording_library.playback_cache_path(self.recording_path)
        playback_path.parent.mkdir()
        playback_path.write_bytes(b"0123456789")
        route_path = "/api/recordings/saved.mkv/play"
        status_code, response_headers, response_body = self.request(route_path, headers={"Range": "bytes=2-5"})
        self.assertEqual(status_code, 206)
        self.assertEqual(response_headers["Content-Range"], "bytes 2-5/10")
        self.assertEqual(response_body, b"2345")
        self.assertEqual(self.request(route_path, headers={"Range": "bytes=-3"})[2], b"789")
        self.assertEqual(self.request(route_path, headers={"Range": "bytes=7-"})[2], b"789")
        for byte_range in ("bytes=10-", "bytes=5-2", "bytes=-0", "bytes=0-1,4-5", "invalid"):
            with self.subTest(byte_range=byte_range):
                self.assertEqual(self.request(route_path, headers={"Range": byte_range})[0], 416)
        status_code, response_headers, response_body = self.request(route_path, method="HEAD")
        self.assertEqual((status_code, response_body), (200, b""))
        self.assertEqual(response_headers["Content-Length"], "10")

    def test_live_stream_sends_latest_frame_and_download_preserves_original(self):
        self.frame_buffer.publish_frame(b"jpeg payload")
        connection = HTTPConnection("127.0.0.1", self.browser_port, timeout=3)
        self.addCleanup(connection.close)
        connection.request("GET", "/live.mjpg")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.readline(), b"--frame\r\n")
        self.assertEqual(response.readline(), b"Content-Type: image/jpeg\r\n")
        self.assertEqual(response.readline(), b"Content-Length: 12\r\n")
        self.assertEqual(response.readline(), b"\r\n")
        self.assertEqual(response.read(12), b"jpeg payload")
        response.close()
        self.assertEqual(self.request("/api/recordings/saved.mkv/download")[2], b"saved recording")

    def test_offline_page_assets_and_cross_site_preparation_protection(self):
        for route_path in ("/", "/app.js", "/styles.css"):
            with self.subTest(route_path=route_path):
                self.assertEqual(self.request(route_path)[0], 200)
        self.assertEqual(self.request("/api/recordings/saved.mkv/prepare", "POST",
                                     {"Origin": "https://another-site.example"})[0], 403)
