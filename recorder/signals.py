"""Translate OS shutdown signals into an application stop request."""

from contextlib import contextmanager
import logging
import signal
from threading import Event
from types import FrameType
from typing import Iterator

logger = logging.getLogger(__name__)


@contextmanager
def handle_shutdown_signals(stop_requested_event: Event) -> Iterator[None]:
    def request_recording_stop(signal_number: int, signal_frame: FrameType | None) -> None:
        if not stop_requested_event.is_set():
            stop_requested_event.set()
            logger.info("Stopping recording...")

    previous_signal_handlers = {
        signal_number: signal.signal(signal_number, request_recording_stop)
        for signal_number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        yield
    finally:
        for signal_number, previous_handler in previous_signal_handlers.items():
            signal.signal(signal_number, previous_handler)
