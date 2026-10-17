from io import BytesIO
import unittest

from recorder.live.frame_buffer import LiveFrameBuffer
from recorder.live.mjpeg_reader import MJPEGReader


class LivePreviewTests(unittest.TestCase):
    def test_multipart_lengths_preserve_frames_and_skip_old_frames(self):
        frame_buffer = LiveFrameBuffer()
        # A JPEG may contain marker-like bytes; its declared length is authoritative.
        frame_payloads = [b"first\xff\xd9frame", b"newest frame"]
        multipart_stream = BytesIO(b"".join(
            b"--ffmpeg\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(frame_payload)).encode() + b"\r\n\r\n" + frame_payload + b"\r\n"
            for frame_payload in frame_payloads
        ) + b"--ffmpeg\r\n")
        MJPEGReader(frame_buffer).read_frames(multipart_stream)
        frame_sequence, jpeg_frame = frame_buffer.wait_for_frame(0, 0)
        self.assertEqual(frame_sequence, 2)
        self.assertEqual(jpeg_frame, frame_payloads[-1])
        self.assertTrue(frame_buffer.has_recent_frame())
        frame_buffer.clear_frame()
        self.assertFalse(frame_buffer.has_recent_frame())

    def test_malformed_preview_is_drained_without_blocking_recording(self):
        frame_stream = BytesIO(b"--ffmpeg\r\nContent-Length: -1\r\n\r\nremaining capture bytes")
        frame_buffer = LiveFrameBuffer()
        with self.assertLogs("recorder.live.mjpeg_reader", level="ERROR"):
            MJPEGReader(frame_buffer).read_frames(frame_stream)
        self.assertEqual(frame_stream.read(), b"")
        self.assertFalse(frame_buffer.has_recent_frame())
