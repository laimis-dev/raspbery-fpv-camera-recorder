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
    web_bind_address: str = "127.0.0.1"
    web_port: int = 8080
    capture_retry_delay_seconds: float = 2.0

    @classmethod
    def from_environment(cls) -> "Settings":
        """Read deployment overrides; keep camera settings in the app."""
        default_settings = cls()
        try:
            web_port = int(os.environ.get("FPV_WEB_PORT", str(default_settings.web_port)))
        except ValueError as error:
            raise RecordingError("FPV_WEB_PORT must be an integer between 0 and 65535.") from error
        if not 0 <= web_port <= 65535:
            raise RecordingError("FPV_WEB_PORT must be an integer between 0 and 65535.")
        return replace(
            default_settings,
            audio_device_name=os.environ.get("FPV_AUDIO_DEVICE_NAME", default_settings.audio_device_name),
            recordings_directory_path=Path(os.environ.get(
                "FPV_RECORDINGS_DIRECTORY_PATH", str(default_settings.recordings_directory_path)
            )).expanduser(),
            web_bind_address=os.environ.get("FPV_WEB_BIND_ADDRESS", default_settings.web_bind_address),
            web_port=web_port,
        )
