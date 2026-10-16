# Project guidelines

These guidelines apply to the entire repository.

## Product behavior

- Keep one simple recording workflow: `make run` or `python3 main.py` starts
  recording immediately with defaults. Bare `make` also starts recording.
- Keep settings in `recorder/config.py`. Do not introduce command-line modes,
  menus, or alternate capture paths unless the requested feature needs them.
- Capture camera video and microphone audio together in one FFmpeg process.
- Save each session to a new `.mkv` file under the configured recordings directory.

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

## Implementation conventions

- Prefer standard-library solutions and explicit constructor dependencies.
  Introduce dependencies and abstractions when a concrete requirement needs them.
- Add type annotations to production function signatures. Keep functions focused
  and document behavior or constraints that are not clear from their names.
- Use module loggers for application messages. Leave FFmpeg diagnostics visible.
- Pass subprocess arguments as a list; do not use `shell=True`.
- Importing a module must not start capture, spawn processes, or create files.

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
