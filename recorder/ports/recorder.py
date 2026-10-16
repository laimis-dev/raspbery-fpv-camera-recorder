"""The capture capability required by the recording service."""

from pathlib import Path
from threading import Event
from typing import Protocol


class Recorder(Protocol):
    def record(self, output: Path, stop_requested: Event) -> None:
        """Capture video and audio; finalize the file before returning."""
        ...
