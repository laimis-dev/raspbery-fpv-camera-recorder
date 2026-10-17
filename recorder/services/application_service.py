"""Keep browser access available while retrying unavailable capture devices."""

import logging
from threading import Event

from recorder.errors.recording_error import RecordingError
from recorder.ports.browser_server import BrowserServer
from recorder.recording_state import RecordingState
from recorder.services.playback_service import PlaybackService
from recorder.services.recording_service import RecordingService

logger = logging.getLogger(__name__)


class ApplicationService:
    def __init__(self, recording_service: RecordingService, browser_server: BrowserServer,
                 playback_service: PlaybackService, recording_state: RecordingState,
                 capture_retry_delay_seconds: float) -> None:
        self.recording_service = recording_service
        self.browser_server = browser_server
        self.playback_service = playback_service
        self.recording_state = recording_state
        self.capture_retry_delay_seconds = capture_retry_delay_seconds

    def run_until_stopped(self, stop_requested_event: Event) -> None:
        self.browser_server.start()
        try:
            self.playback_service.start()
            while not stop_requested_event.is_set():
                try:
                    self.recording_service.record_until_stopped(stop_requested_event)
                    return
                except (RecordingError, OSError) as error:
                    self.recording_state.mark_finished(str(error))
                    logger.error("Capture unavailable: %s Retrying shortly.", error)
                    stop_requested_event.wait(self.capture_retry_delay_seconds)
        finally:
            self.playback_service.stop()
            self.browser_server.stop()
