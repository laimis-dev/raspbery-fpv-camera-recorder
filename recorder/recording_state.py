"""Thread-safe recording status shared with the browser."""

from pathlib import Path
from threading import RLock


class RecordingState:
    def __init__(self) -> None:
        self.lock = RLock()
        self.active_recording_path: Path | None = None
        self.recording_error: str | None = None

    def mark_started(self, output_path: Path) -> None:
        with self.lock:
            self.active_recording_path = output_path.resolve()
            self.recording_error = None

    def mark_finished(self, error_message: str | None = None) -> None:
        with self.lock:
            self.active_recording_path = None
            self.recording_error = error_message

    def is_active_recording(self, recording_path: Path) -> bool:
        with self.lock:
            return self.active_recording_path == recording_path

    def snapshot(self) -> dict[str, str | None]:
        with self.lock:
            return {
                "recording_filename": self.active_recording_path.name if self.active_recording_path else None,
                "recording_error": self.recording_error,
            }
