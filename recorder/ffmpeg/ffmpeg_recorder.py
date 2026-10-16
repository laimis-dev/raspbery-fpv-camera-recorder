"""Own the FFmpeg process and finalize capture safely on a stop request."""

from pathlib import Path
import signal
import subprocess
from threading import Event
import time

from recorder.errors.recording_error import RecordingError
from recorder.ffmpeg.command_builder import FFmpegCommandBuilder


class FFmpegRecorder:
    def __init__(self, command_builder: FFmpegCommandBuilder, shutdown_timeout_seconds: float) -> None:
        self.command_builder = command_builder
        self.shutdown_timeout_seconds = shutdown_timeout_seconds

    def record(self, output: Path, stop_requested: Event) -> None:
        try:
            # The CLI owns OS signals. FFmpeg receives only our forwarded stop.
            process = subprocess.Popen(self.command_builder.build(output), start_new_session=True)
        except FileNotFoundError as exc:
            raise RecordingError("FFmpeg is missing. Install it with: sudo apt install ffmpeg") from exc

        stop_time = None
        try:
            while True:
                if stop_requested.is_set() and stop_time is None:
                    stop_time = time.monotonic()
                    try:
                        process.send_signal(signal.SIGINT)
                    except ProcessLookupError:
                        pass
                try:
                    code = process.wait(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    if stop_time is not None and time.monotonic() - stop_time > self.shutdown_timeout_seconds:
                        raise RecordingError("Recorder did not stop; the file may be incomplete.")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

        if code != 0 and not (stop_time is not None and code == 255):
            raise RecordingError(
                f"Recording failed (FFmpeg exit {code}). See the error above. "
                "Close OBS if the camera is busy."
            )
