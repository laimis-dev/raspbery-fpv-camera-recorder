import errno
import os
from pathlib import Path
import stat
import tempfile
from threading import Event
import time
import unittest
from unittest.mock import patch

from recorder.errors.recording_error import RecordingError
from recorder.storage.recording_file_syncer import RecordingFileSyncer


class RecordingFileSyncerTests(unittest.TestCase):
    def test_periodic_sync_includes_directory_entries_and_final_file_contents(self):
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            output_path = Path(temporary_directory_path) / "recordings" / "capture.mp4"
            output_path.parent.mkdir()
            output_path.write_bytes(b"first frames")
            recording_syncer = RecordingFileSyncer(0.01, 1)
            synced_sizes = []
            synced_directory_count = 0
            first_sync_completed = Event()
            real_fsync = os.fsync

            def observe_sync(file_descriptor):
                nonlocal synced_directory_count
                file_status = os.fstat(file_descriptor)
                real_fsync(file_descriptor)
                if stat.S_ISDIR(file_status.st_mode):
                    synced_directory_count += 1
                    first_sync_completed.set()
                else:
                    synced_sizes.append(file_status.st_size)

            with patch("recorder.storage.recording_file_syncer.os.fsync", side_effect=observe_sync):
                recording_syncer.start_syncing(output_path)
                try:
                    self.assertTrue(first_sync_completed.wait(2))
                    with output_path.open("ab") as recording_file:
                        recording_file.write(b" and final trailer")
                finally:
                    recording_syncer.stop_syncing()
            self.assertEqual(synced_sizes[0], len(b"first frames"))
            self.assertEqual(synced_sizes[-1], output_path.stat().st_size)
            self.assertGreaterEqual(synced_directory_count, 4)

    def test_sync_failure_is_reported_and_preserves_the_recording(self):
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            output_path = Path(temporary_directory_path) / "capture.mp4"
            output_path.write_bytes(b"partial recording")
            recording_syncer = RecordingFileSyncer(0.01, 1)
            with patch("recorder.storage.recording_file_syncer.os.fsync",
                       side_effect=OSError(errno.EIO, "storage write failed")):
                recording_syncer.start_syncing(output_path)
                self.assertTrue(recording_syncer.sync_failed_event.wait(2))
                with self.assertRaisesRegex(RecordingError, "storage write failed"):
                    recording_syncer.check_sync_failure()
                with self.assertRaises(RecordingError):
                    recording_syncer.stop_syncing()
            self.assertEqual(output_path.read_bytes(), b"partial recording")

    def test_blocked_sync_has_bounded_shutdown_and_cannot_spawn_more_workers(self):
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            output_path = Path(temporary_directory_path) / "capture.mp4"
            output_path.write_bytes(b"frames")
            recording_syncer = RecordingFileSyncer(0.01, 0.02)
            sync_started_event, release_sync_event = Event(), Event()

            def block_sync(file_descriptor):
                sync_started_event.set()
                release_sync_event.wait(5)

            with patch("recorder.storage.recording_file_syncer.os.fsync", side_effect=block_sync):
                recording_syncer.start_syncing(output_path)
                try:
                    self.assertTrue(sync_started_event.wait(2))
                    stop_started_seconds = time.monotonic()
                    with self.assertRaisesRegex(RecordingError, "did not finish"):
                        recording_syncer.stop_syncing()
                    self.assertLess(time.monotonic() - stop_started_seconds, 0.5)
                    with self.assertRaisesRegex(RecordingError, "still blocked"):
                        recording_syncer.start_syncing(output_path)
                finally:
                    release_sync_event.set()
                    recording_syncer.sync_thread.join(timeout=2)
            self.assertFalse(recording_syncer.sync_thread.is_alive())

    def test_missing_output_is_not_created_and_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            output_path = Path(temporary_directory_path) / "capture.mp4"
            recording_syncer = RecordingFileSyncer(0.01, 1)
            recording_syncer.start_syncing(output_path)
            recording_syncer.stop_syncing()
            self.assertFalse(output_path.exists())
            target_path = Path(temporary_directory_path) / "existing.mp4"
            target_path.write_bytes(b"original")
            output_path.symlink_to(target_path)
            recording_syncer.start_syncing(output_path)
            with self.assertRaises(RecordingError):
                recording_syncer.stop_syncing()
            self.assertEqual(target_path.read_bytes(), b"original")
