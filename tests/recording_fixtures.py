"""Generated capture inputs used only by integration tests."""

from recorder.ffmpeg.command_builder import FFmpegCommandBuilder


class SyntheticCommandBuilder(FFmpegCommandBuilder):
    def __init__(self, recording_settings, duration_seconds=None):
        super().__init__(recording_settings)
        self.duration_seconds = duration_seconds

    def _build_capture_input_arguments(self):
        return [
            "-re", "-stream_loop", "-1", "-i", self.recording_settings.video_device_path,
            "-re", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        ]

    def build_recording_command(self, output_path):
        ffmpeg_command = super().build_recording_command(output_path)
        if self.duration_seconds is not None:
            ffmpeg_command = ffmpeg_command[:-3] + ["-t", str(self.duration_seconds)] + ffmpeg_command[-3:]
        return ffmpeg_command
