"""Read-only access to finished recordings and their playback cache."""

from pathlib import Path
from typing import Protocol


class RecordingLibrary(Protocol):
    def list_recordings(self) -> list[dict[str, str | int | float]]: ...

    def find_recording_path(self, recording_filename: str) -> Path: ...

    def playback_cache_path(self, recording_path: Path) -> Path: ...
