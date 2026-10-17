"""Durability operations used while the capture process writes a recording."""

from pathlib import Path
from typing import Protocol


class RecordingSyncer(Protocol):
    def start_syncing(self, output_path: Path) -> None:
        """Start periodic syncing without blocking capture on disk I/O."""
        ...

    def check_sync_failure(self) -> None:
        """Raise RecordingError if a background disk sync failed."""
        ...

    def stop_syncing(self) -> None:
        """Request a final sync and wait for it with a bounded deadline."""
        ...
