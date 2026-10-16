"""The capture capability required by the recording service."""

from pathlib import Path
from threading import Event
from typing import Protocol


class Recorder(Protocol):
    def record_to_file(self, output_path: Path, stop_requested_event: Event) -> None:
        """Capture video and audio; finalize the file before returning."""
        ...
