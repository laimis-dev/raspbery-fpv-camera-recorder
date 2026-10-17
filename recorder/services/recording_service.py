"""The record-until-stopped use case, independent of FFmpeg and CLI signals."""

import logging
from pathlib import Path
from threading import Event

from recorder.ports.recorder import Recorder
from recorder.ports.recording_store import RecordingStore
from recorder.recording_state import RecordingState

logger = logging.getLogger(__name__)


class RecordingService:
    def __init__(self, capture_recorder: Recorder, recording_store: RecordingStore,
                 recording_state: RecordingState | None = None) -> None:
        self.capture_recorder = capture_recorder
        self.recording_store = recording_store
        self.recording_state = recording_state if recording_state is not None else RecordingState()

    def record_until_stopped(self, stop_requested_event: Event) -> Path:
        output_path = self.recording_store.create_recording_path()
        self.recording_state.mark_started(output_path)
        logger.info("Starting recording: %s", output_path)
        try:
            self.capture_recorder.record_to_file(output_path, stop_requested_event)
            self.recording_store.validate_saved_recording(output_path)
        except Exception as error:
            self.recording_state.mark_finished(str(error))
            raise
        self.recording_state.mark_finished()
        logger.info("Saved: %s", output_path)
        return output_path
