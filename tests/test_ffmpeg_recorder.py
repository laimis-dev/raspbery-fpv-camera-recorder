from pathlib import Path
import signal
import subprocess
from threading import Event
import unittest
from unittest.mock import Mock, patch

from recorder.config import Settings
from recorder.errors.recording_error import RecordingError
from recorder.ffmpeg.command_builder import FFmpegCommandBuilder
from recorder.ffmpeg.ffmpeg_recorder import FFmpegRecorder


class FFmpegRecorderTests(unittest.TestCase):
    def test_ffmpeg_shutdown_timeout_kills_and_reaps_process(self):
        mock_ffmpeg_process = Mock()
        mock_ffmpeg_process.wait.side_effect = [subprocess.TimeoutExpired("ffmpeg", 0.25), -9]
        mock_ffmpeg_process.poll.return_value = None
        stop_requested_event = Event()
        stop_requested_event.set()
        ffmpeg_recorder = FFmpegRecorder(FFmpegCommandBuilder(Settings()), shutdown_timeout_seconds=0)
        with patch("recorder.ffmpeg.ffmpeg_recorder.subprocess.Popen", return_value=mock_ffmpeg_process):
            with self.assertRaisesRegex(RecordingError, "did not stop"):
                ffmpeg_recorder.record_to_file(Path("unused.mkv"), stop_requested_event)
        mock_ffmpeg_process.send_signal.assert_called_once_with(signal.SIGINT)
        mock_ffmpeg_process.kill.assert_called_once()
        self.assertEqual(mock_ffmpeg_process.wait.call_count, 2)

    def test_missing_ffmpeg_has_specific_error(self):
        ffmpeg_recorder = FFmpegRecorder(FFmpegCommandBuilder(Settings()), shutdown_timeout_seconds=15)
        with patch("recorder.ffmpeg.ffmpeg_recorder.subprocess.Popen", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(RecordingError, "FFmpeg is missing"):
                ffmpeg_recorder.record_to_file(Path("unused.mkv"), Event())
