"""Run the recording workflow and present results in the terminal."""

import logging
from threading import Event

from recorder.bootstrap import create_recording_service
from recorder.config import Settings
from recorder.errors.recording_error import RecordingError
from recorder.signals import handle_shutdown_signals

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    recording_settings = Settings()
    recording_service = create_recording_service(recording_settings)
    stop_requested_event = Event()
    try:
        with handle_shutdown_signals(stop_requested_event):
            logger.info("Press Ctrl+C to stop.")
            recording_service.record_until_stopped(stop_requested_event)
        return 0
    except (OSError, RecordingError) as error:
        logger.error("Error: %s", error)
        return 1
