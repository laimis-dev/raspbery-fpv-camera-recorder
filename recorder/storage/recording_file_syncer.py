"""Periodically sync recording data and directory entries to the storage device."""

import os
from pathlib import Path
import stat
from threading import Event, Thread

from recorder.errors.recording_error import RecordingError


class RecordingFileSyncer:
    def __init__(self, sync_interval_seconds: float, shutdown_timeout_seconds: float) -> None:
        if sync_interval_seconds <= 0 or shutdown_timeout_seconds <= 0:
            raise ValueError("Recording sync intervals and timeouts must be positive.")
        self.sync_interval_seconds = sync_interval_seconds
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self.sync_thread: Thread | None = None
        self.stop_sync_event = Event()
        self.sync_failed_event = Event()
        self.sync_error_message: str | None = None

    def start_syncing(self, output_path: Path) -> None:
        if self.sync_thread is not None and self.sync_thread.is_alive():
            raise RecordingError("The previous recording's disk sync is still blocked.")
        self.stop_sync_event = Event()
        self.sync_failed_event.clear()
        self.sync_error_message = None
        # A stuck device must not prevent the app from honoring its stop deadline.
        self.sync_thread = Thread(target=self._sync_until_stopped,
                                  args=(output_path, self.stop_sync_event),
                                  name="recording-disk-sync", daemon=True)
        self.sync_thread.start()

    def check_sync_failure(self) -> None:
        if self.sync_failed_event.is_set():
            raise RecordingError(self.sync_error_message)

    def stop_syncing(self) -> None:
        self.stop_sync_event.set()
        if self.sync_thread is not None:
            self.sync_thread.join(timeout=self.shutdown_timeout_seconds)
            if self.sync_thread.is_alive():
                raise RecordingError("Recording disk sync did not finish; recent footage may not be saved.")
        self.check_sync_failure()

    def _sync_until_stopped(self, output_path: Path, stop_sync_event: Event) -> None:
        try:
            while not stop_sync_event.wait(self.sync_interval_seconds):
                self._sync_recording_file(output_path)
            # Capture has exited before stop_syncing is called; include its trailer.
            self._sync_recording_file(output_path)
        except OSError as error:
            self.sync_error_message = f"Could not sync recording to disk: {error}"
            self.sync_failed_event.set()

    def _sync_recording_file(self, output_path: Path) -> None:
        try:
            recording_descriptor = os.open(output_path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            # FFmpeg can still be opening devices; never create its output ourselves.
            return
        try:
            if not stat.S_ISREG(os.fstat(recording_descriptor).st_mode):
                raise OSError("The recording destination is not a regular file.")
            os.fsync(recording_descriptor)
        finally:
            os.close(recording_descriptor)
        # File fsync alone does not persist its name or a newly created recordings
        # directory. The service's state directory already exists before capture.
        for directory_path in (output_path.parent, output_path.parent.parent):
            directory_descriptor = os.open(directory_path, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
