"""Assemble the recording service and its concrete dependencies."""

from recorder.config import Settings
from recorder.ffmpeg.command_builder import FFmpegCommandBuilder
from recorder.ffmpeg.ffmpeg_recorder import FFmpegRecorder
from recorder.services.recording_service import RecordingService
from recorder.storage.recording_files import RecordingFiles


def create_recording_service(settings: Settings) -> RecordingService:
    return RecordingService(
        recorder=FFmpegRecorder(
            command_builder=FFmpegCommandBuilder(settings),
            shutdown_timeout_seconds=settings.shutdown_timeout_seconds,
        ),
        files=RecordingFiles(settings.recordings_directory),
    )
