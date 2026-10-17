# Project guidelines

These guidelines apply to the entire repository.

## Product behavior

- Keep one simple recording workflow: `make run` or `python3 main.py` starts
  recording immediately with defaults. Bare `make` also starts recording.
- Keep settings in `recorder/config.py`. Do not introduce command-line modes,
  menus, or alternate capture paths unless the requested feature needs them.
- Keep deployment overrides in `Settings.from_environment()`; local runs retain
  their defaults. Configure the boot service through `nixos/module.nix`.
- Keep capture defaults in the app only. Do not duplicate video device,
  resolution, or frame-rate defaults as NixOS options. Limit service overrides
  to deployment needs such as writable storage and headless audio selection.
- Capture camera video and microphone audio together in one FFmpeg process.
- Save each session to a new `.mkv` file under the configured recordings directory.
- Keep the standalone Pi image usable without SSH keys or account setup.
  SSH is disabled by default; recording starts without a login or network.
- Start the browser interface with the recorder. Keep it available during capture
  retries so finished recordings remain accessible when a device is unplugged.
- Configure the Pi's offline Wi-Fi hotspot in `nixos/hosts/pi4/hotspot.nix`.
  Keep radio, DHCP, and firewall configuration outside the Python app.

## Architecture and file organization

- Give each service, interface, concrete adapter, and error type its own file.
  Use descriptive snake_case filenames and PascalCase class names.
- Keep `main.py` limited to launching the application and returning its exit code.
- Keep terminal presentation and exit status handling in `recorder/cli.py`.
- Assemble concrete dependencies in `recorder/bootstrap.py`.
- Put recording workflows in `recorder/services/`. Services depend on interfaces
  in `recorder/ports/`, not concrete FFmpeg or file storage implementations.
- Put capture and storage contracts in `recorder/ports/`. Keep these interfaces
  small and focused on what the service actually needs.
- Keep FFmpeg argument construction in `recorder/ffmpeg/command_builder.py` and
  process ownership in `recorder/ffmpeg/ffmpeg_recorder.py`.
- Put directory creation, recording filenames, and saved-file checks in
  `recorder/storage/`.
- Put application error types in `recorder/errors/`. Use `RecordingError` for
  capture failures that the CLI should explain without a traceback.
- Keep OS signal handling in `recorder/signals.py`. Pass a shared stop event to
  the recording backend instead of installing signal handlers inside services.
- Keep package `__init__.py` files free of startup work and device access.
- Keep HTTP routes and offline assets in `recorder/web/`, latest-frame buffering
  and parsing in `recorder/live/`, and playback preparation in its own service
  and FFmpeg adapter. Connect shared recording status in `bootstrap.py`.

## Implementation conventions

- Prefer standard-library solutions and explicit constructor dependencies.
  Introduce dependencies and abstractions when a concrete requirement needs them.
- Keep runtime settings and package metadata in one authoritative place.
  Derive shared paths and package versions instead of repeating their values.
- Add type annotations to production function signatures. Keep functions focused
  and document behavior or constraints that are not clear from their names.
- Use module loggers for application messages. Leave FFmpeg diagnostics visible.
- Pass subprocess arguments as a list; do not use `shell=True`.
- Importing a module must not start capture, spawn processes, or create files.

## Naming conventions

- Use names that describe a value's purpose and distinguish it from related
  values. Prefer `output_path`, `recording_store`, `ffmpeg_process`, and
  `exit_code` over `output`, `files`, `process`, and `code`.
- Distinguish paths, device names, and executables: use `video_device_path`,
  `audio_device_name`, and `ffmpeg_executable`. Name collections for their
  contents, such as `recording_paths` and `streams_by_type`.
- Include units where they clarify numeric settings or durations, such as
  `video_frame_rate_fps`, `shutdown_timeout_seconds`, and `duration_seconds`.
- Give events and callbacks names that explain their role, such as
  `stop_requested_event` and `request_recording_stop`.
- Name functions and methods with specific action verbs and their subject, such
  as `create_recording_path`, `validate_saved_recording`,
  `build_recording_command`, and `record_until_stopped`.
- Apply these conventions consistently to interfaces, implementations, keyword
  arguments, test fixtures, and documentation. Keep conventional entry points
  and framework hooks such as `main` and `setUpClass`.

## Recording lifecycle and files

- Never overwrite an existing recording. Preserve FFmpeg's `-n` protection.
- Preserve `-xerror` so FFmpeg write failures produce a failed recording result.
- Handle Ctrl+C and SIGTERM through a graceful stop request. Let FFmpeg finalize
  the file before reporting success.
- Keep shutdown bounded by the configured timeout. Kill and reap a child process
  that does not stop, and restore previous OS signal handlers on exit.
- Report success only after capture returns successfully and storage confirms a
  nonempty output file. This check does not establish signal quality or A/V sync.
- Preserve partial recordings after failures. Cache cleanup must not delete media.
- Derive live frames from the existing capture process. Never open the camera
  again for a browser viewer. Drain preview output even without viewers; keep
  only the latest frame so a slow client cannot stall recording.
- Exclude the active recording from replay and downloads. Confine browser file
  access to regular completed recording files; reject traversal and symlinks.
- Prepare browser replay copies on demand with one low-priority conversion at a
  time. Publish cache files only after successful conversion; preserve originals
  and kill/reap conversion children during shutdown. Support HTTP byte ranges
  for seeking. Keep all browser assets local for offline use.

## Validation and documentation

- Run `make test` and `make check` after code changes. Documentation-only changes
  do not require rerunning recording tests.
- Keep tests split by component. Use mocks for workflow and failure handling;
  use generated media for actual FFmpeg integration checks.
- Keep automated tests independent of physical capture devices. Test fixtures
  belong in `tests/`, not in production capture paths.
- Cover changes to shutdown, file protection, or failure reporting with meaningful
  regression checks. Avoid tests that only repeat command-builder implementation.
- Do not use bare `make` as a build check: it starts recording. Use `make -n run`
  to inspect the launch command without accessing devices.
- Distinguish generated-media validation from hardware validation when reporting
  results. Account for other apps holding the camera open during hardware checks.
- Update `README.md` when commands, settings, module locations, or behavior change.
  Keep Makefile help consistent with its targets.
- Keep recordings, generated media, and Python caches out of version control.
- For NixOS changes, evaluate the flake with `make nixos-check`.
  Keep dependencies pinned in `flake.lock`.
- Boot recording must use persistent writable storage outside the Nix store and
  named hardware inputs that work without a desktop login. Preserve systemd's
  `KillMode=mixed` and a stop timeout longer than the app's shutdown deadline.
- Do not claim a configuration boots on the Pi based only on Nix evaluation or
  generated-media tests. Report image-build and target-hardware validation
  separately.
- Cover shared live capture, replay audio/video, byte ranges, file access, and
  conversion failure/shutdown with device-independent tests. Validate browser
  behavior separately from physical Wi-Fi and target-device performance.
