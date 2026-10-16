from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock

from recorder.errors.recording_error import RecordingError
from recorder.services.recording_service import RecordingService
from recorder.storage.recording_files import RecordingFiles


class RecordingServiceTests(unittest.TestCase):
    def test_capture_without_saved_recording_is_reported_as_failure(self):
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            recording_service = RecordingService(Mock(), RecordingFiles(Path(temporary_directory_path)))
            with self.assertRaisesRegex(RecordingError, "No recording was saved"):
                recording_service.record_until_stopped(Event())
