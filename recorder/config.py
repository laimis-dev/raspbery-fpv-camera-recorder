"""The single set of defaults used when the app starts."""

from dataclasses import dataclass, replace
import os
from pathlib import Path

from recorder.errors.recording_error import RecordingError


@dataclass(frozen=True)
class Settings:
    video_device_path: str = "/dev/video0"
    audio_device_name: str = "default"
    video_resolution: str = "640x480"
    video_frame_rate_fps: int = 25
    recordings_directory_path: Path = Path(__file__).resolve().parents[1] / "recordings"
    ffmpeg_executable: str = "ffmpeg"
    shutdown_timeout_seconds: float = 15.0

    @classmethod
    def from_environment(cls) -> "Settings":
        """Read deployment overrides while preserving local recording defaults."""
        default_settings = cls()
        try:
            video_frame_rate_fps = int(os.environ.get(
                "FPV_VIDEO_FRAME_RATE_FPS", str(default_settings.video_frame_rate_fps)
            ))
        except ValueError as error:
            raise RecordingError("FPV_VIDEO_FRAME_RATE_FPS must be a positive integer.") from error
        if video_frame_rate_fps <= 0:
            raise RecordingError("FPV_VIDEO_FRAME_RATE_FPS must be a positive integer.")
        return replace(
            default_settings,
            video_device_path=os.environ.get("FPV_VIDEO_DEVICE_PATH", default_settings.video_device_path),
            audio_device_name=os.environ.get("FPV_AUDIO_DEVICE_NAME", default_settings.audio_device_name),
            video_resolution=os.environ.get("FPV_VIDEO_RESOLUTION", default_settings.video_resolution),
            video_frame_rate_fps=video_frame_rate_fps,
            recordings_directory_path=Path(os.environ.get(
                "FPV_RECORDINGS_DIRECTORY_PATH", str(default_settings.recordings_directory_path)
            )).expanduser(),
        )
