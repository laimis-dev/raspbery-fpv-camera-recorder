# Raspberry Pi 4: record automatically at boot

The NixOS service runs the same app as `make run`, using Python and FFmpeg from
the Nix store. It starts when the system reaches `multi-user.target`, without a
login, desktop, or network dependency. Recording begins as soon as the USB video
and audio inputs are usable. Failed capture is retried every two seconds,
including when devices are connected after boot or reconnect after a failure.

Recordings are owned by the `fpv-recorder` system user and stored persistently in
`/var/lib/fpv-recorder/recordings`. Each restart creates a new file. A normal
shutdown sends SIGTERM to Python, which asks FFmpeg to finalize the recording.
systemd allows 20 seconds for shutdown; the app's own deadline is 15 seconds.
Power removal cannot perform graceful finalization.

## Existing NixOS installation

Run these commands from a checkout of this project **on the Pi**:

```sh
sudo mkdir -p /etc/nixos/fpv-recorder
sudo cp -r main.py pyproject.toml recorder nixos /etc/nixos/fpv-recorder/
```

Add the module to the existing `imports` in `/etc/nixos/configuration.nix`, keeping
the other imports and machine configuration:

```nix
{
  imports = [
    ./hardware-configuration.nix
    ./fpv-recorder/nixos/module.nix
  ];

  services.fpv-recorder.enable = true;
}
```

Apply the configuration:

```sh
sudo nixos-rebuild switch
```

The service starts immediately and on subsequent boots. Existing flake-based
systems can import `nixosModules.default` from this project's flake instead; use
their normal rebuild command and retain their machine configuration.

The module exposes only service enablement and the package to run. The app's
`recorder/config.py` supplies the video device, resolution, and frame rate:
`/dev/video0`, 640x480, and a requested 25 fps. Change those defaults in the app
and rebuild to use a different capture mode; there is no second set in NixOS.

Two service environment values account for the deployment: the writable
recordings directory and `FPV_AUDIO_DEVICE_NAME=plughw:CARD=CAMERA,DEV=0`.
The microphone override opens the USB input directly without a desktop's audio
server. If your microphone is a separate USB device, change that value in
`nixos/module.nix` to its ALSA name. Check names with `arecord -l` (provided by
`alsa-utils`). Close other apps that hold the camera or ALSA input open.

If the video device number changes, set `video_device_path` in the app to the
appropriate stable `/dev/v4l/by-id/` path.

See the [project README](../README.md) for measured capture-device limits.

## New SD card

`flake.nix` also defines `nixosConfigurations.fpv-recorder`, a Pi 4 image based on
NixOS 26.05's official generic AArch64 SD-image module. It includes the recorder,
boot service, USB camera/audio drivers, and Ethernet DHCP. SSH is disabled. No
SSH key, local settings file, or administrator account setup is required to
build the image or start recording.

On an AArch64 Linux builder with Nix and flakes enabled:

```sh
make nixos-check
make nixos-image
```

An x86 Linux machine needs an AArch64 remote builder or configured AArch64
emulation to build the image. Selecting an architecture alone does not provide
that builder. Nix pins dependencies in `flake.lock`.

The image is under `result/sd-image/` as an `.img.zst` file. Decompress it with
`zstd -d`, then use Raspberry Pi Imager's **Use custom** option to write the `.img`
to the intended SD card. Writing an image erases that card. This repository has
no automatic flashing target.

Insert the card into the Pi 4, connect the capture adapter and microphone, and
power it on. The first boot expands the root partition to fill the card. The
recorder starts automatically. You do not need to connect to the Pi or log in.

The configuration prepares the image; it does not update the Pi's EEPROM.
Use a Pi 4 that can already boot from microSD. Physical Pi boot and USB capture
still need validation on the target hardware.

## Retrieve recordings without SSH

After shutting down the Pi, put its SD card in a Linux computer and mount the
ext4 root partition. Recordings are under `var/lib/fpv-recorder/recordings` on
that partition. Copy them using administrator permissions if necessary. The
small FAT boot partition does not contain the recordings.

## Manage the service from a local console

These commands apply when a local administrator login is available, such as on
an existing NixOS installation. The standalone image does not provision an
administrator account.

```sh
sudo systemctl status fpv-recorder
sudo journalctl -u fpv-recorder -f
sudo ls -lh /var/lib/fpv-recorder/recordings
```

Stop recording and finalize the current file:

```sh
sudo systemctl stop fpv-recorder
```

Start again, or power down the Pi cleanly:

```sh
sudo systemctl start fpv-recorder
sudo systemctl poweroff
```

`systemctl stop` keeps it stopped until started again or rebooted. To disable
future boot recording, set `services.fpv-recorder.enable = false` and rebuild.

Storage uses the SD card by default. For external storage, mount it at
`/var/lib/fpv-recorder` with a normal NixOS `fileSystems` entry; the service waits
for the configured mount. Recordings are not rotated or deleted automatically.
When storage fills, capture fails and the service retries; free space before
expecting it to resume. Failed recordings remain available for recovery.

## Files and validation

- `package.nix`: read version metadata from `pyproject.toml`, package the app,
  and wrap it with Python/FFmpeg.
- `module.nix`: boot service, headless audio selection, permissions, and state storage.
- `hosts/pi4/default.nix`: standalone Pi 4 SD-image configuration with SSH disabled.
- `../flake.nix`: pinned package/module/image entry points.

Run `make test` and `make check` for the app, and `make nixos-check` to evaluate
the NixOS configuration. Evaluation does not build an image or prove it boots.

Reference: [official Pi 4 installation documentation](https://wiki.nixos.org/wiki/NixOS_on_ARM/Raspberry_Pi_4)
and [NixOS service configuration](https://nixos.org/manual/nixos/stable/#sec-systemd-state).
