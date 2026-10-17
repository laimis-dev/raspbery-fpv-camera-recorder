#!/bin/sh
# Build on Linux without installing Nix on the host. Never flash a device.
set -eu

project_directory_path=$(cd -- "$(dirname -- "$0")/.." && pwd)
output_directory_path="$project_directory_path/result-image"
image_output_path="$output_directory_path/fpv-recorder-pi4.img"
docker_executable=${DOCKER:-docker}
zstd_executable=${ZSTD:-zstd}
python_executable=${PYTHON:-python3}

for required_executable in "$docker_executable" "$zstd_executable" "$python_executable"; do
    if ! command -v "$required_executable" >/dev/null 2>&1; then
        printf 'Required command is missing: %s\n' "$required_executable" >&2
        exit 1
    fi
done

if [ "$(uname -s)" != Linux ]; then
    printf '%s\n' 'This image builder requires a Linux host with Docker.' >&2
    exit 1
fi
case $(uname -m) in
    x86_64|aarch64|arm64) ;;
    *) printf '%s\n' 'Supported build hosts: x86_64 and ARM64 Linux.' >&2; exit 1 ;;
esac

"$docker_executable" info >/dev/null
case $(uname -m) in
    x86_64)
        printf '%s\n' 'Setting up ARM64 emulation (privileged Docker container)…'
        "$docker_executable" run --privileged --rm tonistiigi/binfmt:latest --install arm64
        ;;
esac

mkdir -p "$output_directory_path"
printf '%s\n' 'Building the Raspberry Pi 4 SD image…'
"$docker_executable" run --rm --init \
    --volume "$project_directory_path:/project:ro" \
    --volume "$output_directory_path:/output" \
    --volume fpv-recorder-nix:/nix \
    --env "IMAGE_OWNER_UID=$(id -u)" \
    --env "IMAGE_OWNER_GID=$(id -g)" \
    --workdir /project \
    nixos/nix:latest sh -eu -c '
        # Snapshot only build inputs, excluding recordings and previous images.
        mkdir -p /tmp/recorder-source
        cp main.py pyproject.toml flake.nix flake.lock /tmp/recorder-source/
        cp -R recorder nixos /tmp/recorder-source/
        nix --extra-experimental-features "nix-command flakes" \
            --option sandbox false \
            --option extra-platforms aarch64-linux \
            build path:/tmp/recorder-source#sd-image \
            --out-link /tmp/recorder-image

        set -- /tmp/recorder-image/sd-image/*.img.zst
        if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
            printf "%s\n" "Expected exactly one compressed SD image." >&2
            exit 1
        fi
        compressed_image_temporary_path=$(mktemp /output/.pi4-image.XXXXXX)
        trap '\''rm -f "$compressed_image_temporary_path"'\'' EXIT
        cp "$1" "$compressed_image_temporary_path"
        chown "$IMAGE_OWNER_UID:$IMAGE_OWNER_GID" "$compressed_image_temporary_path"
        chmod 644 "$compressed_image_temporary_path"
        mv -f "$compressed_image_temporary_path" /output/fpv-recorder-pi4.img.zst
    '

# Publish the decompressed image only after successful extraction. Preserve any
# previous completed image if decompression fails or the build is interrupted.
image_temporary_path=$(mktemp "$output_directory_path/.pi4-image.XXXXXX")
trap 'rm -f "$image_temporary_path"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf '%s\n' 'Decompressing the SD image…'
"$zstd_executable" -dc "$image_output_path.zst" > "$image_temporary_path"
"$python_executable" "$project_directory_path/scripts/validate_pi_image.py" "$image_temporary_path"
chmod 644 "$image_temporary_path"
mv -f "$image_temporary_path" "$image_output_path"
printf 'Ready for Raspberry Pi Imager: %s\n' "$image_output_path"
