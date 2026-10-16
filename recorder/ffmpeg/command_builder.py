"""Build the single supported video and microphone recording command."""

from pathlib import Path

from recorder.config import Settings


class FFmpegCommandBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _input_arguments(self) -> list[str]:
        return [
            "-thread_queue_size", "32", "-f", "v4l2",
            "-input_format", "mjpeg", "-video_size", self.settings.video_size,
            "-framerate", str(self.settings.video_fps),
            "-i", self.settings.video_device,
            "-thread_queue_size", "256", "-f", "alsa",
            "-ac", "1", "-ar", "48000", "-i", self.settings.audio_device,
        ]

    def build(self, output: Path) -> list[str]:
        return [
            self.settings.ffmpeg_binary, "-hide_banner", "-nostdin", "-xerror", "-n",
            *self._input_arguments(),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-af", "aresample=async=1", "-f", "matroska", str(output),
        ]
