"""Offline browser routes, bounded live streaming, and seekable media responses."""

from http.server import BaseHTTPRequestHandler
import json
import logging
import os
from pathlib import Path
import re
from typing import TYPE_CHECKING
from urllib.parse import quote, unquote, urlsplit

from recorder.errors.playback_error import PlaybackError

if TYPE_CHECKING:
    from recorder.web.server import RecorderWebServer

logger = logging.getLogger(__name__)
STATIC_DIRECTORY_PATH = Path(__file__).parent / "static"
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class RecorderRequestHandler(BaseHTTPRequestHandler):
    server: "RecorderWebServer"
    server_version = "FPVRecorder"

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(5)

    def do_GET(self) -> None:
        self._handle_request()

    def do_HEAD(self) -> None:
        self._handle_request()

    def do_POST(self) -> None:
        # Preparation consumes resources. Accept requests from this page only.
        request_origin = self.headers.get("Origin")
        if (self.headers.get("Sec-Fetch-Site") == "cross-site"
                or (request_origin and urlsplit(request_origin).netloc != self.headers.get("Host"))):
            self._send_json({"message": "Cross-site requests are not allowed."}, 403)
            return
        self._handle_request()

    def _handle_request(self) -> None:
        try:
            request_path = unquote(urlsplit(self.path).path)
            if self.command in ("GET", "HEAD"):
                if request_path in STATIC_ROUTES:
                    filename, content_type = STATIC_ROUTES[request_path]
                    self._send_file(STATIC_DIRECTORY_PATH / filename, content_type)
                    return
                if request_path == "/api/status":
                    self._send_json({**self.server.recording_state.snapshot(),
                                     "live_available": self.server.frame_buffer.has_recent_frame()})
                    return
                if request_path == "/api/recordings":
                    self._send_json(self.server.recording_library.list_recordings())
                    return
                if request_path == "/live.mjpg" and self.command == "GET":
                    self._stream_live_frames()
                    return
            route_parts = request_path.strip("/").split("/")
            if len(route_parts) == 4 and route_parts[:2] == ["api", "recordings"]:
                recording_filename, action_name = route_parts[2:]
                if self.command == "POST" and action_name == "prepare":
                    playback_status = self.server.playback_service.request_playback(
                        recording_filename, retry_failed=urlsplit(self.path).query == "retry=1")
                    self._send_json(playback_status)
                    return
                if self.command in ("GET", "HEAD") and action_name == "play":
                    self._send_file(self.server.playback_service.find_playback_path(recording_filename), "video/webm")
                    return
                if self.command in ("GET", "HEAD") and action_name == "download":
                    self._send_file(self.server.recording_library.find_recording_path(recording_filename),
                                    "application/octet-stream", recording_filename)
                    return
            self._send_json({"message": "Page not found."}, 404)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except FileNotFoundError as error:
            self._send_json({"message": str(error)}, 404)
        except ValueError as error:
            self._send_json({"message": str(error)}, 400)
        except PlaybackError as error:
            self._send_json({"message": str(error)}, 503)
        except OSError:
            logger.exception("Browser request failed")
            self._send_json({"message": "Storage is unavailable."}, 503)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        super().end_headers()

    def _send_json(self, response_data: object, status_code: int = 200) -> None:
        response_body = json.dumps(response_data).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response_body)

    def _send_file(self, file_path: Path, content_type: str, download_filename: str | None = None) -> None:
        with file_path.open("rb") as media_file:
            file_size_bytes = os.fstat(media_file.fileno()).st_size
            first_byte, last_byte = 0, file_size_bytes - 1
            range_header = self.headers.get("Range")
            if range_header is not None:
                range_match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
                if range_match and any(range_match.groups()):
                    range_start, range_end = range_match.groups()
                    if range_start:
                        first_byte = int(range_start)
                        last_byte = min(int(range_end), last_byte) if range_end else last_byte
                    else:
                        first_byte = max(0, file_size_bytes - int(range_end))
                else:
                    first_byte = file_size_bytes
                if not 0 <= first_byte <= last_byte < file_size_bytes:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size_bytes}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            self.send_response(206 if range_header is not None else 200)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            if download_filename:
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(download_filename)}")
            if range_header is not None:
                self.send_header("Content-Range", f"bytes {first_byte}-{last_byte}/{file_size_bytes}")
            remaining_bytes = max(0, last_byte - first_byte + 1)
            self.send_header("Content-Length", str(remaining_bytes))
            self.end_headers()
            if self.command == "HEAD":
                return
            media_file.seek(first_byte)
            while remaining_bytes > 0 and not self.server.stop_requested_event.is_set():
                media_chunk = media_file.read(min(65536, remaining_bytes))
                if not media_chunk:
                    break
                self.wfile.write(media_chunk)
                remaining_bytes -= len(media_chunk)

    def _stream_live_frames(self) -> None:
        if not self.server.live_viewer_slots.acquire(blocking=False):
            self._send_json({"message": "Live view is full. Close another viewer and try again."}, 503)
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            previous_sequence = -1
            while not self.server.stop_requested_event.is_set():
                frame_sequence, jpeg_frame = self.server.frame_buffer.wait_for_frame(previous_sequence)
                if jpeg_frame is None or frame_sequence == previous_sequence:
                    continue
                previous_sequence = frame_sequence
                self.wfile.write(f"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg_frame)}\r\n\r\n".encode())
                self.wfile.write(jpeg_frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        finally:
            self.server.live_viewer_slots.release()

    def log_message(self, format: str, *args: object) -> None:
        logger.debug("Browser: %s", format % args)
