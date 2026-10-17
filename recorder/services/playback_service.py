"""Serialize on-demand playback preparation to protect capture resources."""

from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread

from recorder.errors.playback_error import PlaybackError
from recorder.ports.playback_converter import PlaybackConverter
from recorder.ports.recording_library import RecordingLibrary


class PlaybackService:
    def __init__(self, recording_library: RecordingLibrary, playback_converter: PlaybackConverter) -> None:
        self.recording_library = recording_library
        self.playback_converter = playback_converter
        self.stop_requested_event = Event()
        self.job_queue: Queue[tuple[Path, Path]] = Queue(maxsize=8)
        self.job_states: dict[Path, dict[str, str]] = {}
        self.job_lock = Lock()
        self.worker_thread: Thread | None = None

    def start(self) -> None:
        self.worker_thread = Thread(target=self._prepare_queued_recordings, name="playback-converter", daemon=True)
        self.worker_thread.start()

    def stop(self) -> None:
        self.stop_requested_event.set()
        if self.worker_thread is not None:
            self.worker_thread.join(timeout=3)

    def request_playback(self, recording_filename: str, retry_failed: bool = False) -> dict[str, str]:
        recording_path = self.recording_library.find_recording_path(recording_filename)
        playback_path = self.recording_library.playback_cache_path(recording_path)
        with self.job_lock:
            if playback_path.is_file() and playback_path.stat().st_size > 0:
                return {"status": "ready"}
            job_state = self.job_states.get(playback_path)
            if job_state is None or (retry_failed and job_state["status"] == "error"):
                try:
                    self.job_queue.put_nowait((recording_path, playback_path))
                except Full:
                    raise PlaybackError("Playback queue is full. Try again shortly.") from None
                job_state = {"status": "queued"}
                self.job_states[playback_path] = job_state
            return dict(job_state)

    def find_playback_path(self, recording_filename: str) -> Path:
        recording_path = self.recording_library.find_recording_path(recording_filename)
        playback_path = self.recording_library.playback_cache_path(recording_path)
        if not playback_path.is_file() or playback_path.stat().st_size == 0:
            raise FileNotFoundError("Playback is still being prepared.")
        return playback_path

    def _prepare_queued_recordings(self) -> None:
        while not self.stop_requested_event.is_set():
            try:
                recording_path, playback_path = self.job_queue.get(timeout=0.25)
            except Empty:
                continue
            with self.job_lock:
                self.job_states[playback_path] = {"status": "preparing"}
            try:
                self.playback_converter.convert_recording(recording_path, playback_path, self.stop_requested_event)
                job_state = {"status": "ready"}
            except (PlaybackError, OSError) as error:
                job_state = {"status": "error", "message": str(error)}
            with self.job_lock:
                self.job_states[playback_path] = job_state
            self.job_queue.task_done()
