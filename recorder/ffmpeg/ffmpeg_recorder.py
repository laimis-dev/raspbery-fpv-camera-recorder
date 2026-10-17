"""Own the FFmpeg process and finalize capture safely on a stop request."""

from pathlib import Path
import signal
import subprocess
from threading import Event, Thread
import time

from recorder.errors.recording_error import RecordingError
from recorder.ffmpeg.command_builder import FFmpegCommandBuilder
from recorder.live.frame_buffer import LiveFrameBuffer
from recorder.live.mjpeg_reader import MJPEGReader


class FFmpegRecorder:
    def __init__(
        self, command_builder: FFmpegCommandBuilder, shutdown_timeout_seconds: float,
        frame_buffer: LiveFrameBuffer | None = None,
    ) -> None:
        self.command_builder = command_builder
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self.frame_buffer = frame_buffer

    def record_to_file(self, output_path: Path, stop_requested_event: Event) -> None:
        # Some FFmpeg versions exit successfully when -n refuses an existing file.
        # Treat that condition as a failure instead of reporting the old file saved.
        if output_path.exists() or output_path.is_symlink():
            raise RecordingError(f"Recording already exists: {output_path}")
        try:
            # The CLI owns OS signals. FFmpeg receives only our forwarded stop.
            ffmpeg_process = subprocess.Popen(
                self.command_builder.build_recording_command(output_path),
                start_new_session=True,
                stdout=subprocess.PIPE if self.frame_buffer is not None else subprocess.DEVNULL,
            )
        except FileNotFoundError as error:
            raise RecordingError("FFmpeg is missing. Install it with: sudo apt install ffmpeg") from error

        preview_reader_thread = None
        if self.frame_buffer is not None and ffmpeg_process.stdout is not None:
            preview_reader_thread = Thread(
                target=MJPEGReader(self.frame_buffer).read_frames,
                args=(ffmpeg_process.stdout,), name="live-frame-reader", daemon=True,
            )
            preview_reader_thread.start()
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
            if preview_reader_thread is not None:
                preview_reader_thread.join(timeout=2)
                ffmpeg_process.stdout.close()
            if self.frame_buffer is not None:
                self.frame_buffer.clear_frame()

        if exit_code != 0 and not (shutdown_started_at is not None and exit_code == 255):
            raise RecordingError(
                f"Recording failed (FFmpeg exit {exit_code}). See the error above. "
                "Close OBS if the camera is busy."
            )
