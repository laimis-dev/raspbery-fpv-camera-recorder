"""Own the local HTTP listener and its background serving thread."""

from http.server import ThreadingHTTPServer
import logging
from threading import BoundedSemaphore, Event, Thread

from recorder.live.frame_buffer import LiveFrameBuffer
from recorder.ports.recording_library import RecordingLibrary
from recorder.recording_state import RecordingState
from recorder.services.playback_service import PlaybackService
from recorder.web.request_handler import RecorderRequestHandler

logger = logging.getLogger(__name__)


class RecorderWebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, bind_address: str, port: int, frame_buffer: LiveFrameBuffer,
                 recording_library: RecordingLibrary, playback_service: PlaybackService,
                 recording_state: RecordingState) -> None:
        super().__init__((bind_address, port), RecorderRequestHandler, bind_and_activate=False)
        self.frame_buffer = frame_buffer
        self.recording_library = recording_library
        self.playback_service = playback_service
        self.recording_state = recording_state
        self.stop_requested_event = Event()
        self.live_viewer_slots = BoundedSemaphore(4)
        self.server_thread: Thread | None = None

    def start(self) -> None:
        try:
            self.server_bind()
            self.server_activate()
        except OSError:
            self.server_close()
            raise
        self.server_thread = Thread(target=self.serve_forever, kwargs={"poll_interval": 0.1},
                                    name="browser-server", daemon=True)
        self.server_thread.start()
        logger.info("Browser page: http://%s:%s", *self.server_address)

    def stop(self) -> None:
        self.stop_requested_event.set()
        if self.server_thread is not None:
            self.shutdown()
            self.server_thread.join(timeout=2)
        self.server_close()
