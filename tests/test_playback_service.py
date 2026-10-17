from pathlib import Path
import subprocess
import tempfile
from threading import Event
import time
import unittest
from unittest.mock import Mock, patch

from recorder.errors.playback_error import PlaybackError
from recorder.ffmpeg.playback_converter import FFmpegPlaybackConverter
from recorder.recording_state import RecordingState
from recorder.services.playback_service import PlaybackService
from recorder.storage.file_recording_library import FileRecordingLibrary


class PlaybackServiceTests(unittest.TestCase):
    def test_preparation_failure_is_visible_and_original_remains_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            recording_path = Path(temporary_directory_path) / "saved.mkv"
            recording_path.write_bytes(b"original")
            recording_library = FileRecordingLibrary(Path(temporary_directory_path), RecordingState())
            playback_converter = Mock()
            playback_converter.convert_recording.side_effect = PlaybackError("Cannot decode recording")
            playback_service = PlaybackService(recording_library, playback_converter)
            playback_service.start()
            try:
                playback_service.request_playback("saved.mkv")
                deadline_seconds = time.monotonic() + 2
                while (job_status := playback_service.request_playback("saved.mkv"))["status"] != "error":
                    self.assertLess(time.monotonic(), deadline_seconds)
                    time.sleep(0.01)
                self.assertIn("Cannot decode", job_status["message"])
                playback_converter.convert_recording.assert_called_once()
                self.assertEqual(recording_path.read_bytes(), b"original")
            finally:
                playback_service.stop()

    def test_shutdown_kills_and_reaps_conversion_and_removes_only_partial_cache(self):
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            recording_path = Path(temporary_directory_path) / "saved.mkv"
            recording_path.write_bytes(b"original")
            playback_path = Path(temporary_directory_path) / "cache" / "saved.webm"
            stop_requested_event = Event()
            stop_requested_event.set()
            ffmpeg_process = Mock()
            ffmpeg_process.poll.return_value = None
            with patch("recorder.ffmpeg.playback_converter.subprocess.Popen", return_value=ffmpeg_process), patch(
                "recorder.ffmpeg.playback_converter.os.setpriority"
            ):
                with self.assertRaisesRegex(PlaybackError, "stopped"):
                    FFmpegPlaybackConverter("ffmpeg").convert_recording(recording_path, playback_path, stop_requested_event)
            ffmpeg_process.kill.assert_called_once()
            ffmpeg_process.communicate.assert_called_once()
            self.assertEqual(list(playback_path.parent.iterdir()), [])
            self.assertEqual(recording_path.read_bytes(), b"original")
