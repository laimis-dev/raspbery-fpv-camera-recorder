"""Application and FFmpeg integration checks without capture hardware."""

from dataclasses import replace
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from threading import Event
import time
import unittest
from unittest.mock import patch

PROJECT_ROOT_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT_PATH))

from recorder import cli
from recorder.config import Settings
from recorder.errors.recording_error import RecordingError
from recorder.ffmpeg.ffmpeg_recorder import FFmpegRecorder
from tests.recording_fixtures import SyntheticCommandBuilder


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and ffprobe are required")
class RecordingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_media_directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary_media_directory.cleanup)
        cls.video_fixture_path = Path(cls.temporary_media_directory.name) / "camera.avi"
        subprocess.run([
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x480:rate=25",
            "-t", "1", "-c:v", "mjpeg", "-threads", "1", str(cls.video_fixture_path),
        ], check=True, timeout=10)

    def assert_playable_recording(self, output_path):
        probe_result = subprocess.run([
            "ffprobe", "-v", "error", "-count_packets", "-show_streams", "-of", "json", str(output_path),
        ], capture_output=True, text=True, check=True, timeout=10)
        streams_by_type = {stream_metadata["codec_type"]: stream_metadata for stream_metadata in json.loads(probe_result.stdout)["streams"]}
        self.assertEqual(set(streams_by_type), {"video", "audio"})
        self.assertEqual(streams_by_type["video"]["codec_name"], "h264")
        self.assertEqual(streams_by_type["audio"]["codec_name"], "aac")
        for stream_metadata in streams_by_type.values():
            self.assertGreater(int(stream_metadata["nb_read_packets"]), 0)
        decode_result = subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(output_path), "-map", "0:v", "-map", "0:a", "-f", "null", "-",
        ], capture_output=True, text=True, timeout=10)
        self.assertEqual(decode_result.returncode, 0, decode_result.stderr)
        self.assertEqual(decode_result.stderr, "")
        return streams_by_type

    def test_main_starts_without_arguments_and_saves_both_streams(self):
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            recordings_directory_path = Path(temporary_directory_path) / "recordings"

            def create_synthetic_command_builder(recording_settings):
                return SyntheticCommandBuilder(
                    replace(recording_settings, video_device_path=str(self.video_fixture_path)),
                    duration_seconds=1,
                )

            service_environment = {
                "FPV_RECORDINGS_DIRECTORY_PATH": str(recordings_directory_path),
                "FPV_AUDIO_DEVICE_NAME": "plughw:CARD=LAV,DEV=0",
                "FPV_WEB_PORT": "0",
                "PATH": os.environ.get("PATH", os.defpath),
            }
            with patch.dict(os.environ, service_environment, clear=True), patch(
                "recorder.bootstrap.FFmpegCommandBuilder", side_effect=create_synthetic_command_builder
            ):
                self.assertEqual(cli.main(), 0)
            recording_paths = list(recordings_directory_path.glob("*.mkv"))
            self.assertEqual(len(recording_paths), 1)
            streams_by_type = self.assert_playable_recording(recording_paths[0])
            self.assertEqual(streams_by_type["video"]["width"], 640)
            self.assertEqual(streams_by_type["video"]["height"], 480)
            self.assertEqual(streams_by_type["video"]["r_frame_rate"], "25/1")
            self.assertEqual(int(streams_by_type["video"]["nb_read_packets"]), 25)

    def test_compression_preserves_detail_frames_and_audio_with_smaller_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            output_path = Path(temporary_directory_path) / "compressed.mkv"
            command_builder = SyntheticCommandBuilder(
                replace(Settings(), video_device_path=str(self.video_fixture_path)), duration_seconds=3,
            )
            ffmpeg_recorder = FFmpegRecorder(command_builder, 15)
            ffmpeg_recorder.record_to_file(output_path, Event())
            streams_by_type = self.assert_playable_recording(output_path)
            self.assertEqual(int(streams_by_type["video"]["nb_read_packets"]), 75)
            self.assertEqual(streams_by_type["video"]["width"], 640)
            self.assertEqual(streams_by_type["video"]["height"], 480)
            self.assertEqual(streams_by_type["video"]["r_frame_rate"], "25/1")
            # Compare against the same camera frames in the former MJPEG/AAC format.
            baseline_path = Path(temporary_directory_path) / "mjpeg-camera-copy.mkv"
            subprocess.run([
                "ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", str(self.video_fixture_path),
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "3",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", str(baseline_path),
            ], check=True, timeout=10)
            self.assertLess(output_path.stat().st_size, baseline_path.stat().st_size * 0.85)

            # Compare decoded detail with the previous, more aggressive defaults.
            aggressive_output_path = Path(temporary_directory_path) / "aggressive-compression.mkv"
            aggressive_command_builder = SyntheticCommandBuilder(
                replace(command_builder.recording_settings, recording_video_quality_crf=23,
                        recording_video_max_bitrate_bits_per_second=1_500_000,
                        recording_audio_bitrate_bits_per_second=96_000), duration_seconds=3,
            )
            aggressive_command = aggressive_command_builder.build_recording_command(aggressive_output_path)
            subprocess.run([argument for argument in aggressive_command if argument != "-re"],
                           check=True, timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

            def measure_video_similarity(recording_path):
                comparison_result = subprocess.run([
                    "ffmpeg", "-hide_banner", "-i", str(recording_path), "-i", str(self.video_fixture_path),
                    "-filter_complex", "[0:v]setpts=PTS-STARTPTS[encoded];"
                    "[1:v]setpts=PTS-STARTPTS[reference];[encoded][reference]ssim=shortest=1",
                    "-an", "-f", "null", "-",
                ], check=True, timeout=15, capture_output=True, text=True)
                return float(re.search(r"All:([0-9.]+)", comparison_result.stderr)[1])

            self.assertGreater(measure_video_similarity(output_path),
                               measure_video_similarity(aggressive_output_path))

    def test_ctrl_c_and_sigterm_finalize_recordings(self):
        for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=shutdown_signal), tempfile.TemporaryDirectory() as temporary_directory_path:
                recordings_directory_path = Path(temporary_directory_path) / "recordings"
                capture_log_path = Path(temporary_directory_path) / "capture.log"
                recorder_subprocess_script = f'''
import sys
from pathlib import Path
from unittest.mock import patch
from tests.recording_fixtures import SyntheticCommandBuilder
from recorder.config import Settings
from recorder import cli
recording_settings = Settings(video_device_path={str(self.video_fixture_path)!r}, recordings_directory_path=Path({str(recordings_directory_path)!r}), web_port=0)
with patch("recorder.cli.Settings.from_environment", return_value=recording_settings), patch("recorder.bootstrap.FFmpegCommandBuilder", SyntheticCommandBuilder):
    raise SystemExit(cli.main())
'''
                with capture_log_path.open("w") as log_file:
                    recorder_process = subprocess.Popen([sys.executable, "-c", recorder_subprocess_script], cwd=PROJECT_ROOT_PATH, stdout=log_file, stderr=log_file)
                    try:
                        startup_deadline_seconds = time.monotonic() + 10
                        while not re.search(r"frame=\s*[1-9]", capture_log_path.read_text()):
                            if recorder_process.poll() is not None or time.monotonic() > startup_deadline_seconds:
                                self.fail(capture_log_path.read_text())
                            time.sleep(0.05)
                        recorder_process.send_signal(shutdown_signal)
                        self.assertEqual(recorder_process.wait(timeout=20), 0, capture_log_path.read_text())
                    finally:
                        if recorder_process.poll() is None:
                            recorder_process.kill()
                            recorder_process.wait()
                recording_paths = list(recordings_directory_path.glob("*.mkv"))
                self.assertEqual(len(recording_paths), 1)
                self.assertIn("Saved:", capture_log_path.read_text())
                self.assert_playable_recording(recording_paths[0])

    def test_existing_recording_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            output_path = Path(temporary_directory_path) / "capture.mkv"
            output_path.write_bytes(b"existing recording")
            ffmpeg_recorder = FFmpegRecorder(SyntheticCommandBuilder(replace(Settings(), video_device_path=str(self.video_fixture_path))), 15)
            with self.assertRaises(RecordingError):
                ffmpeg_recorder.record_to_file(output_path, Event())
            self.assertEqual(output_path.read_bytes(), b"existing recording")

    def test_disk_write_failure_is_reported(self):
        class FullDiskCommandBuilder(SyntheticCommandBuilder):
            def build_recording_command(self, output_path):
                ffmpeg_command = super().build_recording_command(output_path)
                ffmpeg_command[ffmpeg_command.index("-n")] = "-y"
                ffmpeg_command[ffmpeg_command.index(str(output_path))] = "/dev/full"
                return ffmpeg_command
        command_builder = FullDiskCommandBuilder(replace(Settings(), video_device_path=str(self.video_fixture_path)), duration_seconds=0.1)
        ffmpeg_recorder = FFmpegRecorder(command_builder, 15)
        with tempfile.TemporaryDirectory() as temporary_directory_path:
            with self.assertRaises(RecordingError):
                ffmpeg_recorder.record_to_file(Path(temporary_directory_path) / "capture.mkv", Event())


if __name__ == "__main__":
    unittest.main()
