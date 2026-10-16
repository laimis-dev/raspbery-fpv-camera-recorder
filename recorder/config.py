"""The single set of defaults used when the app starts."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    video_device_path: str = "/dev/video0"
    audio_device_name: str = "default"
    video_resolution: str = "640x480"
    video_frame_rate_fps: int = 60
    recordings_directory_path: Path = Path(__file__).resolve().parents[1] / "recordings"
    ffmpeg_executable: str = "ffmpeg"
    shutdown_timeout_seconds: float = 15.0
