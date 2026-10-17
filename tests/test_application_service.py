from threading import Event
import unittest
from unittest.mock import Mock

from recorder.errors.recording_error import RecordingError
from recorder.recording_state import RecordingState
from recorder.services.application_service import ApplicationService


class ApplicationServiceTests(unittest.TestCase):
    def test_camera_retry_preserves_browser_and_stops_background_services(self):
        stop_requested_event = Event()
        recording_service = Mock()
        recording_service.record_until_stopped.side_effect = [RecordingError("camera unplugged"), None]
        browser_server, playback_service = Mock(), Mock()
        application_service = ApplicationService(recording_service, browser_server, playback_service,
                                                 RecordingState(), capture_retry_delay_seconds=0)
        with self.assertLogs("recorder.services.application_service", level="ERROR"):
            application_service.run_until_stopped(stop_requested_event)
        self.assertEqual(recording_service.record_until_stopped.call_count, 2)
        browser_server.start.assert_called_once()
        browser_server.stop.assert_called_once()
        playback_service.start.assert_called_once()
        playback_service.stop.assert_called_once()
