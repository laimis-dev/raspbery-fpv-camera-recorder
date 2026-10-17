"""Prepare a browser-compatible copy without modifying the original."""

from pathlib import Path
from threading import Event
from typing import Protocol


class PlaybackConverter(Protocol):
    def convert_recording(self, recording_path: Path, playback_path: Path,
                          stop_requested_event: Event) -> None: ...
