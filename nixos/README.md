# Raspberry Pi 4: boot recording and offline Wi-Fi

The NixOS image starts the recorder, browser page, and a WPA2 Wi-Fi hotspot at
boot, without a desktop, SSH keys, login, router, or internet connection.

1. Power the Pi with its USB capture adapter and microphone connected.
2. Connect to Wi-Fi **`FPV-Recorder`**, password **`12345678`**.
3. Stay connected if your device reports **no internet**.
4. Open **http://192.168.4.1** to watch live video, replay finished sessions,
   or download original recordings.

The optional local DNS name is `http://recorder.lan`; the IP address also works
when your browser uses its own DNS service. This is an offline access point,
with no internet forwarding or automatic captive-portal page.

## Existing NixOS installation

From a checkout **on the Pi**, copy the app and deployment files:

```sh
sudo mkdir -p /etc/nixos/fpv-recorder
sudo cp -r main.py pyproject.toml recorder nixos /etc/nixos/fpv-recorder/
```

Add these imports to `/etc/nixos/configuration.nix`, preserving its other
imports and machine-specific settings:

```nix
{
  imports = [
    ./hardware-configuration.nix
    ./fpv-recorder/nixos/module.nix
    ./fpv-recorder/nixos/hosts/pi4/hotspot.nix
  ];

  services.fpv-recorder.enable = true;
}
```

The hotspot dedicates `wlan0` to access-point mode, disables Wi-Fi client
management and NetworkManager, and uses static address `192.168.4.1/24`. Resolve
any existing Wi-Fi-manager or addressing configuration for that interface before
merging this into an already customized installation. Ethernet can still use
DHCP. The standalone image already includes these settings.

Edit `hosts/pi4/hotspot.nix` for the SSID, password, and Wi-Fi
country code (`LT`, Lithuania). Credentials are included in the built image's
Nix store. There is no separate local settings file. For different Pi locations,
use the country code for where the radio operates.

Apply your configuration:

```sh
sudo nixos-rebuild switch
```

The service starts immediately and on subsequent boots. A flake-based existing
system can import this project's `nixosModules.default` and the hotspot file
instead, using its normal rebuild command and retaining its machine configuration.
The recorder module alone starts recording and HTTP but does not change Wi-Fi
management; the hotspot module supplies the wireless network.

## New SD card

`flake.nix` defines `nixosConfigurations.fpv-recorder` using NixOS 26.05's
official generic AArch64 SD-image module. It includes Pi 4 boot firmware, USB
camera/audio support, the recorder, HTTP service, hotspot, and Ethernet DHCP.
SSH is disabled; no administrator account setup is required to start recording.

On an x86_64 or ARM64 **Linux PC**, install Docker, Python 3, and `zstd`, make sure the
Docker daemon is running and accessible to your user, then run:

```sh
make image
```

No host Nix installation is needed. On x86_64, the target first uses a privileged
`tonistiigi/binfmt` container to register ARM64 emulation on the host. It then
builds using `nixos/nix`, exports the compressed image, and decompresses it to:

```text
result-image/fpv-recorder-pi4.img
```

The first build downloads dependencies and can take a while under emulation.
The Docker volume `fpv-recorder-nix` caches Nix dependencies for later builds.
Only source inputs are copied into the build; recordings and previous images
are excluded. Completed images are replaced on a successful rebuild. Extraction
uses a temporary file so a failed extraction preserves the previous `.img`.
Both `.img` and `.img.zst` are retained in the ignored `result-image/` directory.
This target does not flash an SD card.

The Pi configuration uses a **512 MiB FAT32 LBA firmware partition**, followed by
the ext4 root partition. The generic image module's 30 MiB default selected
FAT16 while its partition table declared FAT32. The larger firmware partition
makes those formats consistent; the LBA partition type matches Raspberry Pi OS.
This corrects a layout inconsistency; it has
not been established as the cause of the earlier write errors.

The build validates partition boundaries, FAT32 geometry, and the root
filesystem bounds before publishing the decompressed image. Repeat this check
on an existing export with:

```sh
make image-check
```

Alternatively, on an AArch64 Linux builder with Nix and flakes enabled:

```sh
make nixos-check
make nixos-image
```

An x86 Linux builder needs an AArch64 remote builder or configured AArch64
emulation. Selecting an architecture does not provide a builder. Dependencies
are pinned in `flake.lock`.

With `make nixos-image`, the image is under `result/sd-image/` as an `.img.zst`;
decompress it with `zstd -d`. With `make image`, it is already decompressed.
Use Raspberry Pi Imager's **Use custom** option to write the `.img`
to the intended SD card. Writing the image erases that card. There is no automatic
flashing target.

If Raspberry Pi Imager closes near the start of writing without an error, try
the current official [Imager release](https://github.com/raspberrypi/rpi-imager/releases).
On this development PC, Imager 2.0.6 crashed in its write-progress watchdog;
the generated image's FAT and ext4 filesystems both passed read-only checks,
and its bytes matched the decompressed archive. This identifies where Imager
crashed, but does not establish that a newer version will finish the card write.
The official Linux AppImage can be run with `--appimage-extract-and-run` if FUSE
is unavailable. Select the `.img` under **Use custom** and skip OS customisation:
the recorder, hotspot, and settings are already configured in NixOS.

To check an archive and compare its decompressed content with the exported image:

```sh
zstd -t result-image/fpv-recorder-pi4.img.zst
sha256sum result-image/fpv-recorder-pi4.img
zstd -dc result-image/fpv-recorder-pi4.img.zst | sha256sum
```

The two SHA256 values should match. These checks do not write to the SD card
and do not establish Pi boot or successful flashing.

If writing fails with **Input/output error**, inspect the kernel log with
`sudo journalctl -k -n 100`. USB resets, “device offline or changed”, or “medium
may have changed” messages identify an I/O failure, but alone do not establish
whether the card, reader, USB connection, host software, or write method caused
it. These errors also preceded the Imager 2.0.6 crash observed here. Compare
images using the same card, reader, port, and writer settings before assigning
a cause. A successful write using another card is useful evidence, but does not
isolate those variables. A failed write leaves an incomplete image; repeat the
full write and verification before attempting to boot from it.

The rebuilt FAT32 LBA image was successfully written to a 31.95 GB microSD card
and all 5,263,962,112 written bytes matched the source image's SHA256 during a
direct read-back. That card differed from the 31.29 GB card in the failed
attempts, so this result does not isolate the cause of those failures. Pi boot,
hotspot availability, and capture on the target hardware remain unverified.

Insert the card and power on. The first boot expands the root partition to fill
the card. The Pi must already support booting from microSD; this configuration
does not update its EEPROM. Recording does not wait for Wi-Fi to be ready.
The web listener can start before `wlan0` receives its address.

## Service and capture configuration

The module exposes service enablement and package selection. Capture defaults
come from `recorder/config.py`: `/dev/video0`, MJPEG 640x480, requested PAL 25 fps.
Saved video is compressed to H.264, with AAC microphone audio in MKV. The app's
compression defaults control recording size; see the project README for tuning
and storage estimates. Live preview continues using the original MJPEG frames.
Change the app and rebuild for another capture mode. See the
[project README](../README.md) for measured hardware limits.

The service overrides only deployment details:

| Environment variable | Deployment value |
| --- | --- |
| `FPV_AUDIO_DEVICE_NAME` | `plughw:CARD=CAMERA,DEV=0` |
| `FPV_RECORDINGS_DIRECTORY_PATH` | `/var/lib/fpv-recorder/recordings` |
| `FPV_WEB_BIND_ADDRESS` | `0.0.0.0` |
| `FPV_WEB_PORT` | `80` |

If the microphone is a separate USB device, change the ALSA name in `module.nix`.
`arecord -l` from `alsa-utils` lists audio devices. If video numbering changes,
set the app's `video_device_path` to a stable `/dev/v4l/by-id/` path. Close other
apps that hold the camera or ALSA input open.

The service runs as `fpv-recorder`, with video/audio group access and only the
capability required to bind HTTP port 80. Its writable state is outside the Nix
store. The firewall opens HTTP on `wlan0`; the hotspot opens DHCP and local DNS
on that interface. There is no browser login: connected hotspot clients can
view and download recordings. Assets and playback work without external sites.

Capture retries every two seconds while browser access remains available.
systemd restarts unexpected app exits. Files persist between restarts, with a
new `.mkv` for every capture session. Normal shutdown sends SIGTERM to Python,
which asks FFmpeg to finalize. systemd allows 25 seconds for capture and the
background services to stop; capture's deadline is 15 seconds. Power removal
cannot finalize recordings gracefully.

## Storage and local management

Recordings and `.playback-cache/` are under `/var/lib/fpv-recorder/recordings`.
Replay creates a VP8/Opus WebM copy without changing the original. A single,
lower-priority conversion runs at a time; first playback of long sessions may
take time. Playback copies consume extra disk space. No recordings or completed
playback copies are automatically deleted. When storage fills, recording fails
and retries until space is available. Failed nonempty recordings remain visible
for download but might not play.

For external storage, mount it at `/var/lib/fpv-recorder` with a normal NixOS
`fileSystems` entry. The service waits for that mount. To retrieve originals
without the hotspot, shut down the Pi and mount its SD card's ext4 root partition
on Linux; files are under `var/lib/fpv-recorder/recordings`. They are not on the
small FAT boot partition.

The service creates folders readable and traversable by other users (0755),
and recordings readable by other users (0644), so a Linux desktop can retrieve
them directly from the card. Only the recorder's user can write them. Images
built before this permission change used restricted access. For those cards,
after mounting the root partition, replace the mount path below as needed:

```sh
sudo chmod o+rx /run/media/$USER/NIXOS_SD/var/lib/fpv-recorder
sudo chmod o+rx /run/media/$USER/NIXOS_SD/var/lib/fpv-recorder/recordings
sudo find /run/media/$USER/NIXOS_SD/var/lib/fpv-recorder/recordings \
  -maxdepth 1 -type f -name '*.mkv' -exec chmod o+r {} +
```

Rebuild and install the updated image for future recordings to use the new
permissions automatically; changing existing files alone does not update the
installed service.

When a local administrator login is available, use:

```sh
sudo systemctl status fpv-recorder
sudo journalctl -u fpv-recorder -f
sudo systemctl stop fpv-recorder
sudo systemctl start fpv-recorder
sudo systemctl poweroff
```

`stop` finalizes recording and stops the page until the service starts again.
The standalone image does not provision an administrator account. Disabling
`services.fpv-recorder.enable` stops future boot recording; remove the hotspot
import separately if you also want to disable its Wi-Fi network.

## Files and validation

- `package.nix`: package Python code and offline web assets, wrapping Python/FFmpeg.
- `module.nix`: boot service, headless audio, HTTP, permissions, and storage.
- `hosts/pi4/default.nix`: standalone Pi image with SSH disabled.
- `hosts/pi4/hotspot.nix`: Wi-Fi radio, credentials, DHCP, DNS, and hotspot firewall.
- `../flake.nix`: pinned package, module, and image entry points.

Run `make test`, `make check`, and `make nixos-check`. Generated-media tests
exercise shared live capture, recorded audio/video, and replay without hardware.
Nix evaluation validates module options and derivations; it does not build an SD
image or prove Pi boot, hotspot connectivity, or Pi capture/conversion performance.
Those require target-hardware validation. `make image-check` checks the exported
image's structure; it does not check every filesystem block or access the card.

References: [official Pi 4 installation documentation](https://wiki.nixos.org/wiki/NixOS_on_ARM/Raspberry_Pi_4),
[NixOS hostapd module](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/services/networking/hostapd.nix),
[NixOS dnsmasq module](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/services/networking/dnsmasq.nix),
and [FFmpeg's libvpx encoder](https://ffmpeg.org/ffmpeg-codecs.html#libvpx).
