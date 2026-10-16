"""The single set of defaults used when the app starts."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    video_device: str = "/dev/video0"
    audio_device: str = "default"
    video_size: str = "640x480"
    video_fps: int = 60
    recordings_directory: Path = Path(__file__).resolve().parents[1] / "recordings"
    ffmpeg_binary: str = "ffmpeg"
    shutdown_timeout_seconds: float = 15.0
