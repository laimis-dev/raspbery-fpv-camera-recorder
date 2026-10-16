"""Own the FFmpeg process and finalize capture safely on a stop request."""

from pathlib import Path
import signal
import subprocess
from threading import Event
import time

from recorder.errors.recording_error import RecordingError
from recorder.ffmpeg.command_builder import FFmpegCommandBuilder


class FFmpegRecorder:
    def __init__(
        self, command_builder: FFmpegCommandBuilder, shutdown_timeout_seconds: float
    ) -> None:
        self.command_builder = command_builder
        self.shutdown_timeout_seconds = shutdown_timeout_seconds

    def record_to_file(self, output_path: Path, stop_requested_event: Event) -> None:
        try:
            # The CLI owns OS signals. FFmpeg receives only our forwarded stop.
            ffmpeg_process = subprocess.Popen(
                self.command_builder.build_recording_command(output_path),
                start_new_session=True,
            )
        except FileNotFoundError as error:
            raise RecordingError("FFmpeg is missing. Install it with: sudo apt install ffmpeg") from error

        shutdown_started_at = None
        try:
            while True:
                if stop_requested_event.is_set() and shutdown_started_at is None:
                    shutdown_started_at = time.monotonic()
                    try:
                        ffmpeg_process.send_signal(signal.SIGINT)
                    except ProcessLookupError:
                        pass
                try:
                    exit_code = ffmpeg_process.wait(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    if (
                        shutdown_started_at is not None
                        and time.monotonic() - shutdown_started_at > self.shutdown_timeout_seconds
                    ):
                        raise RecordingError("Recorder did not stop; the file may be incomplete.")
        finally:
            if ffmpeg_process.poll() is None:
                ffmpeg_process.kill()
                ffmpeg_process.wait()

        if exit_code != 0 and not (shutdown_started_at is not None and exit_code == 255):
            raise RecordingError(
                f"Recording failed (FFmpeg exit {exit_code}). See the error above. "
                "Close OBS if the camera is busy."
            )
