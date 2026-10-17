"""Exercise simultaneous capture, live HTTP preview, and seekable A/V replay."""

from http.client import HTTPConnection
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch

from recorder.bootstrap import create_application_service
from recorder.config import Settings
from tests.recording_fixtures import SyntheticCommandBuilder


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and ffprobe are required")
class BrowserIntegrationTests(unittest.TestCase):
    def test_shared_capture_live_view_and_cached_replay_include_audio(self):
        for saved_recording_suffix in (".mp4", ".mkv"):
            with self.subTest(saved_recording_suffix=saved_recording_suffix):
                self.assert_shared_capture_and_replay(saved_recording_suffix)

    def assert_shared_capture_and_replay(self, saved_recording_suffix):
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            media_directory_path = Path(temporary_directory_path)
            video_fixture_path = media_directory_path / "camera.avi"
            subprocess.run([
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25",
                "-t", "1", "-c:v", "mjpeg", "-threads", "1", str(video_fixture_path),
            ], check=True, timeout=10)
            recordings_directory_path = media_directory_path / "recordings"
            recordings_directory_path.mkdir()
            saved_recording_path = recordings_directory_path / f"previous-session{saved_recording_suffix}"
            recording_route = f"/api/recordings/{saved_recording_path.name}"
            subprocess.run([
                "ffmpeg", "-v", "error", "-i", str(video_fixture_path),
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                "-t", "1", "-c:v", "libx264", "-preset", "veryfast", "-threads:v", "2",
                "-pix_fmt", "yuv420p", "-c:a", "aac", str(saved_recording_path),
            ], check=True, timeout=10)
            original_recording_bytes = saved_recording_path.read_bytes()
            recording_settings = Settings(video_device_path=str(video_fixture_path),
                                          recordings_directory_path=recordings_directory_path, web_port=0)
            with patch("recorder.bootstrap.FFmpegCommandBuilder", SyntheticCommandBuilder):
                application_service = create_application_service(recording_settings)
            stop_requested_event = Event()
            application_errors = []

            def run_application():
                try:
                    application_service.run_until_stopped(stop_requested_event)
                except Exception as error:
                    application_errors.append(error)

            application_thread = Thread(target=run_application)
            application_thread.start()
            connection = None
            live_connection = None
            try:
                startup_deadline_seconds = time.monotonic() + 10
                while not application_service.browser_server.frame_buffer.has_recent_frame():
                    self.assertLess(time.monotonic(), startup_deadline_seconds, application_errors)
                    time.sleep(0.02)
                browser_port = application_service.browser_server.server_address[1]
                connection = HTTPConnection("127.0.0.1", browser_port, timeout=10)
                live_connection = HTTPConnection("127.0.0.1", browser_port, timeout=5)
                live_connection.request("GET", "/live.mjpg")
                live_response = live_connection.getresponse()
                self.assertEqual(live_response.status, 200)
                self.assertEqual(live_response.readline(), b"--frame\r\n")
                self.assertEqual(live_response.readline(), b"Content-Type: image/jpeg\r\n")
                frame_length_bytes = int(live_response.readline().split(b":")[1])
                self.assertEqual(live_response.readline(), b"\r\n")
                jpeg_frame = live_response.read(frame_length_bytes)
                self.assertTrue(jpeg_frame.startswith(b"\xff\xd8"))
                self.assertTrue(jpeg_frame.endswith(b"\xff\xd9"))
                # Leave this viewer idle while the recorder and replay converter continue.
                connection.request("GET", "/api/recordings")
                recordings = json.loads(connection.getresponse().read())
                self.assertEqual([entry["filename"] for entry in recordings], [saved_recording_path.name])
                prepare_deadline_seconds = time.monotonic() + 15
                while True:
                    connection.request("POST", f"{recording_route}/prepare")
                    job_status = json.loads(connection.getresponse().read())
                    self.assertNotEqual(job_status["status"], "error", job_status)
                    if job_status["status"] == "ready":
                        break
                    self.assertLess(time.monotonic(), prepare_deadline_seconds, job_status)
                    time.sleep(0.05)
                playback_path = application_service.playback_service.find_playback_path(saved_recording_path.name)
                connection.request("GET", f"{recording_route}/play", headers={"Range": "bytes=0-255"})
                range_response = connection.getresponse()
                self.assertEqual(range_response.status, 206)
                self.assertEqual(range_response.read(), playback_path.read_bytes()[:256])
                probe_result = subprocess.run([
                    "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(playback_path),
                ], capture_output=True, check=True, timeout=10)
                streams_by_type = {stream["codec_type"]: stream["codec_name"]
                                   for stream in json.loads(probe_result.stdout)["streams"]}
                self.assertEqual(streams_by_type, {"video": "vp8", "audio": "opus"})
                subprocess.run(["ffmpeg", "-v", "error", "-i", str(playback_path), "-f", "null", "-"],
                               check=True, timeout=10, capture_output=True)
                self.assertEqual(saved_recording_path.read_bytes(), original_recording_bytes)
            finally:
                if connection is not None:
                    connection.close()
                if live_connection is not None:
                    live_connection.close()
                stop_requested_event.set()
                application_thread.join(timeout=20)
            self.assertFalse(application_thread.is_alive())
            self.assertEqual(application_errors, [])
            new_recording_paths = [path for path in recordings_directory_path.glob("*.mp4") if path != saved_recording_path]
            self.assertEqual(len(new_recording_paths), 1)
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(new_recording_paths[0]), "-f", "null", "-"],
                           check=True, timeout=10, capture_output=True)
