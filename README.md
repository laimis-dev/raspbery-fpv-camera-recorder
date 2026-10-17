# Camera recorder

Run the app to start recording video and microphone audio immediately:

```sh
make run
```

Open **http://127.0.0.1:8080** for the live view, saved recordings, replay, and
original-file downloads. Press **Ctrl+C** to stop and finalize the recording.
Each session saves a new `.mkv` file in `recordings/` next to `main.py`.
Bare `make` and `python3 main.py` start the same app.

## Raspberry Pi hotspot

The [NixOS Pi 4 image](nixos/README.md) starts recording and opens a Wi-Fi
hotspot automatically at boot:

| Setting | Value |
| --- | --- |
| Wi-Fi name | `FPV-Recorder` |
| Wi-Fi password | `12345678` |
| Browser address | **http://192.168.4.1** |

Connect your phone or computer to that Wi-Fi, stay connected if it reports
**no internet**, and enter the browser address. No SSH, login, external router,
or internet connection is needed. The hotspot does not share internet access.
Its configuration is in `nixos/hosts/pi4/hotspot.nix`; the country is set to
Lithuania (`LT`). Set the country to where you operate the Pi.

The app keeps recording without a browser connected. If the camera or
microphone is unavailable, it retries every two seconds while keeping the page
and existing recordings available. Recordings on the Pi are stored in
`/var/lib/fpv-recorder/recordings`.

The image configuration has been evaluated; an SD image build, physical Pi boot,
Wi-Fi connection, and Pi performance still need validation on the target hardware.

## Live view and replay

- **Live view** shows video from the same camera capture process used for
  recording. It has no live audio. Saved recordings include microphone audio.
- **Replay** prepares a browser-compatible WebM copy of a selected finished
  recording, then opens it with playback, sound, and seeking controls. Long
  recordings take longer to prepare. Further replays reuse the cached copy.
- **Download original** saves the original `.mkv`, preserving the captured
  video quality. Replay copies use VP8 video and Opus audio; originals retain
  MJPEG video and AAC audio.
- The current recording appears in the library after its session finishes.
  There is no remote stop button; recording continues while you browse.
- Preparation runs one file at a time with one video encoder thread and lower
  CPU priority. Slow viewers skip old live frames rather than blocking capture.
  Up to four live viewers can connect at once.

Playback copies use additional storage in `recordings/.playback-cache/`. They
are not deleted automatically. With the app stopped, you can remove that cache
directory to reclaim space; original recordings are outside it. Originals are
never rotated or deleted automatically. Partial recordings after a failure are
preserved and listed if nonempty, but may not be playable.

## Capture settings

The defaults in `recorder/config.py` request `/dev/video0`, MJPEG video at
**640x480 and PAL's 25 fps**, and the system's default microphone. Video is
saved without re-encoding; audio is saved as AAC. Close OBS or deactivate its
camera source before starting the recorder.

640x480 is the highest resolution advertised by the connected ARKMICRO USB DVR.
Measured input frames arrived about 40 ms apart (approximately 25 fps). The
adapter may negotiate a different rate in its metadata. Requested settings do
not guarantee the negotiated mode or actual frame timing. Higher resolutions
require a capture device that supports them.

On Raspberry Pi OS, install the dependencies first:

```sh
sudo apt install python3 ffmpeg make
```

Use an FFmpeg build with MJPEG/AAC support for recording and `libvpx`/`libopus`
encoders for replay; the Nix package supplies these. Set `audio_device_name` to
the microphone's ALSA identifier if it is not the default. The Nix service uses
`plughw:CARD=CAMERA,DEV=0` directly without a desktop audio server.

`Settings.from_environment()` supports deployment overrides for
`FPV_AUDIO_DEVICE_NAME`, `FPV_RECORDINGS_DIRECTORY_PATH`, `FPV_WEB_BIND_ADDRESS`,
and `FPV_WEB_PORT`. Local HTTP defaults to loopback port 8080; the Nix service
binds port 80 on all interfaces, with a firewall opening on `wlan0`. Camera
settings remain defined in the app only. Port 0 selects an ephemeral port for
automated tests. The page is intended for the private hotspot; anyone connected
to that network can view and download recordings.

## Development commands

| Command | Action |
| --- | --- |
| `make run` | Start recording and the browser page. |
| `make test` | Run component and generated-media integration tests. |
| `make check` | Check Python syntax. |
| `make nixos-check` | Evaluate the NixOS configuration. |
| `make nixos-image` | Build the Pi 4 SD image using an AArch64 builder. |
| `make clean` | Remove Python caches; preserve recordings and playback copies. |
| `make help` | Show commands. |

Use another interpreter with `make test PYTHON=.venv/bin/python`. Do not use
bare `make` for build verification: it starts capture. `make -n run` prints the
launch command without accessing devices. Package version metadata comes from
`pyproject.toml`.

## Architecture

```mermaid
flowchart TD
    Main[main.py / CLI] --> App[ApplicationService]
    App --> Recording[RecordingService]
    App --> Web[RecorderWebServer]
    App --> Playback[PlaybackService: one conversion worker]
    Recording --> RecorderPort[Recorder interface]
    Recording --> StoragePort[RecordingStore interface]
    RecorderPort --> Capture[FFmpegRecorder: one camera and microphone capture]
    StoragePort --> Files[RecordingFiles: new MKV session]
    Capture --> Frames[LiveFrameBuffer: latest JPEG only]
    Frames --> Web
    Web --> Library[RecordingLibrary interface]
    Playback --> Library
    Playback --> ConverterPort[PlaybackConverter interface]
    ConverterPort --> Converter[FFmpegPlaybackConverter: saved file only]
    Converter --> Cache[Seekable WebM cache]
    Cache --> Web
```

- `main.py` launches the CLI; `recorder/cli.py` presents status and exit codes.
- `recorder/bootstrap.py` connects dependencies; `config.py` owns app defaults.
- `recorder/services/` coordinates recording, retry lifecycle, and replay jobs.
- `recorder/ports/` defines capture, storage, library, converter, and browser
  lifecycle contracts.
- `recorder/ffmpeg/` builds capture arguments, owns the capture child, and
  prepares saved-file playback copies in a separate adapter.
- `recorder/live/` parses captured multipart JPEG frames and keeps the newest.
- `recorder/storage/` creates recording paths, checks saves, and confines
  library access to finished regular files.
- `recorder/web/` serves HTTP routes and bundled HTML/CSS/JavaScript offline.
- `recorder/recording_state.py` shares recording status safely across threads.
- `recorder/signals.py` turns Ctrl+C/SIGTERM into a shared stop event;
  `recorder/errors/` contains application error types.

Only the capture process accesses devices; replay conversion reads saved media.
The live reader always drains FFmpeg output, independently of browser clients.
On shutdown, capture gets up to 15 seconds to finalize before it is killed and
reaped; conversion is cancelled and its partial cache file removed. Originals
and partial recordings are preserved. Existing recordings cannot be overwritten.
A successful save requires a successful capture result and a nonempty file;
this does not establish hardware signal quality or A/V synchronization.

Tests use generated media and mocks, never physical capture devices. They cover
capture and replay decoding, shared live frames, seeking, file access, retries,
conversion failures, shutdown, original-file protection, and disk write failures.
See [AGENTS.md](AGENTS.md) for implementation guidelines and
[the deployment guide](nixos/README.md) for installation.
