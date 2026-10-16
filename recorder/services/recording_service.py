"""The record-until-stopped use case, independent of FFmpeg and CLI signals."""

import logging
from pathlib import Path
from threading import Event

from recorder.ports.recorder import Recorder
from recorder.ports.recording_store import RecordingStore

logger = logging.getLogger(__name__)


class RecordingService:
    def __init__(self, capture_recorder: Recorder, recording_store: RecordingStore) -> None:
        self.capture_recorder = capture_recorder
        self.recording_store = recording_store

    def record_until_stopped(self, stop_requested_event: Event) -> Path:
        output_path = self.recording_store.create_recording_path()
        logger.info("Starting recording: %s", output_path)
        self.capture_recorder.record_to_file(output_path, stop_requested_event)
        self.recording_store.validate_saved_recording(output_path)
        logger.info("Saved: %s", output_path)
        return output_path
