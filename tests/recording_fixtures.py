"""Generated capture inputs used only by integration tests."""

from recorder.ffmpeg.command_builder import FFmpegCommandBuilder


class SyntheticCommandBuilder(FFmpegCommandBuilder):
    def __init__(self, recording_settings, duration_seconds=None):
        super().__init__(recording_settings)
        self.duration_seconds = duration_seconds

    def _build_capture_input_arguments(self):
        duration_arguments = ["-t", str(self.duration_seconds)] if self.duration_seconds is not None else []
        return [
            "-re", "-stream_loop", "-1", *duration_arguments, "-i", self.recording_settings.video_device_path,
            "-re", "-f", "lavfi", *duration_arguments, "-i", "sine=frequency=440:sample_rate=48000",
        ]
