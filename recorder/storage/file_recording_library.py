"""Confine browsing to completed recordings in the configured directory."""

import hashlib
from pathlib import Path

from recorder.recording_state import RecordingState

RECORDING_FILE_SUFFIXES = (".mp4", ".mkv")


class FileRecordingLibrary:
    def __init__(self, recordings_directory_path: Path, recording_state: RecordingState) -> None:
        self.recordings_directory_path = recordings_directory_path.resolve()
        self.recording_state = recording_state

    def list_recordings(self) -> list[dict[str, str | int | float]]:
        recording_entries = []
        recording_paths = (recording_path for suffix in RECORDING_FILE_SUFFIXES
                           for recording_path in self.recordings_directory_path.glob(f"*{suffix}"))
        for recording_path in recording_paths:
            try:
                self.find_recording_path(recording_path.name)
                recording_stat = recording_path.stat()
                recording_entries.append({
                    "filename": recording_path.name, "size_bytes": recording_stat.st_size,
                    "modified_timestamp": recording_stat.st_mtime,
                })
            except (OSError, ValueError):
                continue
        return sorted(recording_entries, key=lambda entry: entry["modified_timestamp"], reverse=True)

    def find_recording_path(self, recording_filename: str) -> Path:
        if (not recording_filename or Path(recording_filename).name != recording_filename
                or not recording_filename.endswith(RECORDING_FILE_SUFFIXES) or "\\" in recording_filename):
            raise ValueError("Invalid recording filename.")
        recording_path = self.recordings_directory_path / recording_filename
        if (recording_path.is_symlink() or not recording_path.is_file()
                or self.recording_state.is_active_recording(recording_path)
                or recording_path.stat().st_size == 0):
            raise FileNotFoundError("Finished recording not found.")
        return recording_path

    def playback_cache_path(self, recording_path: Path) -> Path:
        recording_stat = recording_path.stat()
        cache_identity = f"webm-v1:{recording_path.name}:{recording_stat.st_size}:{recording_stat.st_mtime_ns}"
        cache_key = hashlib.sha256(cache_identity.encode()).hexdigest()
        return self.recordings_directory_path / ".playback-cache" / f"{cache_key}.webm"
