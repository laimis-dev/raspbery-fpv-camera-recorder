"""Recording destination creation and completed-file checks."""

from datetime import datetime
from pathlib import Path

from recorder.errors.recording_error import RecordingError


class RecordingFiles:
    def __init__(self, recordings_directory_path: Path) -> None:
        self.recordings_directory_path = recordings_directory_path

    def create_recording_path(self) -> Path:
        self.recordings_directory_path.mkdir(parents=True, exist_ok=True)
        return self.recordings_directory_path / f"capture-{datetime.now():%Y%m%d-%H%M%S-%f}.mkv"

    def validate_saved_recording(self, output_path: Path) -> None:
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RecordingError("No recording was saved.")
