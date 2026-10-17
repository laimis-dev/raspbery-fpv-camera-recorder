"""The single set of defaults used when the app starts."""

from dataclasses import dataclass, replace
import os
from pathlib import Path


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
        """Read deployment audio and storage overrides; keep capture defaults in the app."""
        default_settings = cls()
        return replace(
            default_settings,
            audio_device_name=os.environ.get("FPV_AUDIO_DEVICE_NAME", default_settings.audio_device_name),
            recordings_directory_path=Path(os.environ.get(
                "FPV_RECORDINGS_DIRECTORY_PATH", str(default_settings.recordings_directory_path)
            )).expanduser(),
        )
