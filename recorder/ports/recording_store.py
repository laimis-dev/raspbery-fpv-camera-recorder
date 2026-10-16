"""The file storage capability required by the recording service."""

from pathlib import Path
from typing import Protocol


class RecordingStore(Protocol):
    def create_recording_path(self) -> Path:
        """Prepare storage and return a destination for a new recording."""
        ...

    def validate_saved_recording(self, output_path: Path) -> None:
        """Raise a recording error if the output is missing or empty."""
        ...
