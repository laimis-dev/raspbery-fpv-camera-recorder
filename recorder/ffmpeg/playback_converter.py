"""Make seekable VP8/Opus WebM copies at lower CPU priority than capture."""

import logging
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Event

from recorder.errors.playback_error import PlaybackError

logger = logging.getLogger(__name__)


class FFmpegPlaybackConverter:
    def __init__(self, ffmpeg_executable: str) -> None:
        self.ffmpeg_executable = ffmpeg_executable

    def convert_recording(self, recording_path: Path, playback_path: Path,
                          stop_requested_event: Event) -> None:
        playback_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=playback_path.parent, suffix=".part", delete=False) as temporary_file:
            temporary_playback_path = Path(temporary_file.name)
        ffmpeg_process = None
        try:
            ffmpeg_process = subprocess.Popen([
                self.ffmpeg_executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-xerror",
                "-i", str(recording_path), "-map", "0:v:0", "-map", "0:a:0?",
                "-c:v", "libvpx", "-threads", "1", "-deadline", "realtime", "-cpu-used", "6",
                "-crf", "10", "-b:v", "2M", "-pix_fmt", "yuv420p",
                "-c:a", "libopus", "-b:a", "96k", "-f", "webm", str(temporary_playback_path),
            ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
            if hasattr(os, "setpriority"):
                try:
                    os.setpriority(os.PRIO_PROCESS, ffmpeg_process.pid, 10)
                except (OSError, ProcessLookupError):
                    pass
            while True:
                if stop_requested_event.is_set():
                    raise PlaybackError("Playback preparation stopped.")
                try:
                    _, error_output = ffmpeg_process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if ffmpeg_process.returncode != 0 or temporary_playback_path.stat().st_size == 0:
                logger.error("Playback conversion failed: %s", error_output.decode(errors="replace")[-1500:])
                raise PlaybackError("Could not prepare this recording. The original can still be downloaded.")
            temporary_playback_path.replace(playback_path)
        except OSError as error:
            raise PlaybackError(f"Playback preparation failed: {error}") from error
        finally:
            if ffmpeg_process is not None:
                if ffmpeg_process.poll() is None:
                    ffmpeg_process.kill()
                ffmpeg_process.communicate()
            temporary_playback_path.unlink(missing_ok=True)
