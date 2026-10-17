"""Read FFmpeg's multipart JPEG output using explicit payload lengths."""

import logging
from typing import BinaryIO

from recorder.live.frame_buffer import LiveFrameBuffer

logger = logging.getLogger(__name__)


class MJPEGReader:
    def __init__(self, frame_buffer: LiveFrameBuffer) -> None:
        self.frame_buffer = frame_buffer

    def read_frames(self, frame_stream: BinaryIO) -> None:
        try:
            while boundary_line := frame_stream.readline(4096):
                if not boundary_line.startswith(b"--"):
                    continue
                content_length = 0
                while header_line := frame_stream.readline(4096):
                    if header_line in (b"\r\n", b"\n"):
                        break
                    if header_line.lower().startswith(b"content-length:"):
                        content_length = int(header_line.split(b":", 1)[1])
                if not header_line:
                    return  # FFmpeg leaves a trailing boundary at normal EOF.
                if not 0 < content_length <= 16 * 1024 * 1024:
                    raise ValueError("Invalid live-frame length")
                frame_chunks = bytearray()
                while len(frame_chunks) < content_length:
                    frame_chunk = frame_stream.read(content_length - len(frame_chunks))
                    if not frame_chunk:
                        return
                    frame_chunks.extend(frame_chunk)
                self.frame_buffer.publish_frame(bytes(frame_chunks))
        except (ValueError, OSError):
            logger.exception("Live preview unavailable; continuing to drain the camera stream.")
            # Never let a preview parser failure fill the pipe and block capture.
            try:
                while frame_stream.read(65536):
                    pass
            except OSError:
                pass
