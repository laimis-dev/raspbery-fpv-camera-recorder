"""Assemble the recording service and its concrete dependencies."""

from recorder.config import Settings
from recorder.ffmpeg.command_builder import FFmpegCommandBuilder
from recorder.ffmpeg.ffmpeg_recorder import FFmpegRecorder
from recorder.ffmpeg.playback_converter import FFmpegPlaybackConverter
from recorder.live.frame_buffer import LiveFrameBuffer
from recorder.recording_state import RecordingState
from recorder.services.application_service import ApplicationService
from recorder.services.playback_service import PlaybackService
from recorder.services.recording_service import RecordingService
from recorder.storage.file_recording_library import FileRecordingLibrary
from recorder.storage.recording_files import RecordingFiles
from recorder.web.server import RecorderWebServer


def create_application_service(recording_settings: Settings) -> ApplicationService:
    frame_buffer = LiveFrameBuffer()
    recording_state = RecordingState()
    recording_library = FileRecordingLibrary(recording_settings.recordings_directory_path, recording_state)
    playback_service = PlaybackService(recording_library, FFmpegPlaybackConverter(recording_settings.ffmpeg_executable))
    recording_service = RecordingService(
        capture_recorder=FFmpegRecorder(
            command_builder=FFmpegCommandBuilder(recording_settings),
            shutdown_timeout_seconds=recording_settings.shutdown_timeout_seconds,
            frame_buffer=frame_buffer,
        ),
        recording_store=RecordingFiles(recording_settings.recordings_directory_path),
        recording_state=recording_state,
    )
    return ApplicationService(
        recording_service=recording_service,
        browser_server=RecorderWebServer(recording_settings.web_bind_address, recording_settings.web_port,
                                        frame_buffer, recording_library, playback_service, recording_state),
        playback_service=playback_service,
        recording_state=recording_state,
        capture_retry_delay_seconds=recording_settings.capture_retry_delay_seconds,
    )
