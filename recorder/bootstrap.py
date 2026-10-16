"""Assemble the recording service and its concrete dependencies."""

from recorder.config import Settings
from recorder.ffmpeg.command_builder import FFmpegCommandBuilder
from recorder.ffmpeg.ffmpeg_recorder import FFmpegRecorder
from recorder.services.recording_service import RecordingService
from recorder.storage.recording_files import RecordingFiles


def create_recording_service(recording_settings: Settings) -> RecordingService:
    return RecordingService(
        capture_recorder=FFmpegRecorder(
            command_builder=FFmpegCommandBuilder(recording_settings),
            shutdown_timeout_seconds=recording_settings.shutdown_timeout_seconds,
        ),
        recording_store=RecordingFiles(recording_settings.recordings_directory_path),
    )
