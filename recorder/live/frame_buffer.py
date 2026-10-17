"""Keep only the newest frame so slow viewers cannot block recording."""

from threading import Condition
import time


class LiveFrameBuffer:
    def __init__(self) -> None:
        self.condition = Condition()
        self.frame_sequence = 0
        self.jpeg_frame: bytes | None = None
        self.frame_received_at = 0.0

    def publish_frame(self, jpeg_frame: bytes) -> None:
        with self.condition:
            self.jpeg_frame = jpeg_frame
            self.frame_sequence += 1
            self.frame_received_at = time.monotonic()
            self.condition.notify_all()

    def wait_for_frame(self, previous_sequence: int, timeout_seconds: float = 1.0) -> tuple[int, bytes | None]:
        with self.condition:
            self.condition.wait_for(lambda: self.frame_sequence != previous_sequence, timeout_seconds)
            return self.frame_sequence, self.jpeg_frame

    def has_recent_frame(self) -> bool:
        with self.condition:
            return self.jpeg_frame is not None and time.monotonic() - self.frame_received_at < 3

    def clear_frame(self) -> None:
        with self.condition:
            self.jpeg_frame = None
            self.condition.notify_all()
