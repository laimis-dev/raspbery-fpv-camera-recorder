"""Run the recording workflow and present results in the terminal."""

import logging
from threading import Event

from recorder.bootstrap import create_recording_service
from recorder.config import Settings
from recorder.errors.recording_error import RecordingError
from recorder.signals import stop_on_signals

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings()
    service = create_recording_service(settings)
    stop_requested = Event()
    try:
        with stop_on_signals(stop_requested):
            logger.info("Press Ctrl+C to stop.")
            service.record(stop_requested)
        return 0
    except (OSError, RecordingError) as exc:
        logger.error("Error: %s", exc)
        return 1
