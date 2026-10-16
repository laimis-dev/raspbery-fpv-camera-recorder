"""Build the single supported video and microphone recording command."""

from pathlib import Path

from recorder.config import Settings


class FFmpegCommandBuilder:
    def __init__(self, recording_settings: Settings) -> None:
        self.recording_settings = recording_settings

    def _build_capture_input_arguments(self) -> list[str]:
        return [
            "-thread_queue_size", "32", "-f", "v4l2",
            "-input_format", "mjpeg", "-video_size", self.recording_settings.video_resolution,
            "-framerate", str(self.recording_settings.video_frame_rate_fps),
            "-i", self.recording_settings.video_device_path,
            "-thread_queue_size", "256", "-f", "alsa",
            "-ac", "1", "-ar", "48000", "-i", self.recording_settings.audio_device_name,
        ]

    def build_recording_command(self, output_path: Path) -> list[str]:
        return [
            self.recording_settings.ffmpeg_executable, "-hide_banner", "-nostdin", "-xerror", "-n",
            *self._build_capture_input_arguments(),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-af", "aresample=async=1", "-f", "matroska", str(output_path),
        ]
