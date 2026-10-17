"""Validate the exported Pi image layout without accessing a physical drive."""

import argparse
from pathlib import Path
import struct
from typing import BinaryIO

SECTOR_SIZE_BYTES = 512


def read_image_bytes(image_file: BinaryIO, offset_bytes: int, length_bytes: int) -> bytes:
    image_file.seek(offset_bytes)
    image_bytes = image_file.read(length_bytes)
    if len(image_bytes) != length_bytes:
        raise ValueError("The image is truncated.")
    return image_bytes


def validate_pi_image(image_path: Path) -> dict[str, str | int]:
    image_size_bytes = image_path.stat().st_size
    if image_size_bytes % SECTOR_SIZE_BYTES:
        raise ValueError("Image size is not aligned to 512-byte sectors.")
    with image_path.open("rb") as image_file:
        master_boot_record = read_image_bytes(image_file, 0, SECTOR_SIZE_BYTES)
        if master_boot_record[510:512] != b"\x55\xaa":
            raise ValueError("The image has no valid MBR signature.")
        partitions = []
        for partition_index in range(4):
            partition_entry_offset = 446 + partition_index * 16
            partition_type = master_boot_record[partition_entry_offset + 4]
            if partition_type == 0:
                continue
            first_sector, sector_count = struct.unpack_from("<II", master_boot_record, partition_entry_offset + 8)
            if first_sector == 0 or sector_count == 0 or (first_sector + sector_count) * SECTOR_SIZE_BYTES > image_size_bytes:
                raise ValueError("A partition lies outside the image or has an invalid size.")
            partitions.append((partition_type, first_sector, sector_count))
        if len(partitions) != 2 or partitions[0][0] not in (0x0B, 0x0C) or partitions[1][0] != 0x83:
            raise ValueError("Expected a FAT32 firmware partition followed by a Linux root partition.")
        _, firmware_first_sector, firmware_sector_count = partitions[0]
        _, root_first_sector, root_sector_count = partitions[1]
        if firmware_first_sector + firmware_sector_count > root_first_sector:
            raise ValueError("The firmware and root partitions overlap.")

        boot_sector = read_image_bytes(image_file, firmware_first_sector * SECTOR_SIZE_BYTES, SECTOR_SIZE_BYTES)
        if boot_sector[510:512] != b"\x55\xaa":
            raise ValueError("The firmware filesystem has no valid boot-sector signature.")
        bytes_per_sector = struct.unpack_from("<H", boot_sector, 11)[0]
        sectors_per_cluster = boot_sector[13]
        reserved_sector_count = struct.unpack_from("<H", boot_sector, 14)[0]
        fat_count = boot_sector[16]
        root_entry_count = struct.unpack_from("<H", boot_sector, 17)[0]
        filesystem_sector_count = struct.unpack_from("<H", boot_sector, 19)[0] or struct.unpack_from("<I", boot_sector, 32)[0]
        fat16_sector_count = struct.unpack_from("<H", boot_sector, 22)[0]
        fat_sector_count = fat16_sector_count or struct.unpack_from("<I", boot_sector, 36)[0]
        if (bytes_per_sector != SECTOR_SIZE_BYTES or sectors_per_cluster not in (1, 2, 4, 8, 16, 32, 64, 128)
                or not reserved_sector_count or fat_count not in (1, 2) or not fat_sector_count):
            raise ValueError("The firmware filesystem has invalid FAT geometry.")
        root_directory_sector_count = (root_entry_count * 32 + bytes_per_sector - 1) // bytes_per_sector
        data_sector_count = filesystem_sector_count - reserved_sector_count - fat_count * fat_sector_count - root_directory_sector_count
        cluster_count = data_sector_count // sectors_per_cluster
        filesystem_type = "FAT12" if cluster_count < 4085 else "FAT16" if cluster_count < 65525 else "FAT32"
        if filesystem_type != "FAT32":
            raise ValueError(f"Firmware partition is marked FAT32 but contains {filesystem_type}. Rebuild the image.")
        if (root_entry_count or fat16_sector_count or filesystem_sector_count > firmware_sector_count
                or fat_sector_count * bytes_per_sector // 4 < cluster_count + 2):
            raise ValueError("The FAT32 filesystem does not fit its declared geometry or partition.")

        superblock = read_image_bytes(image_file, root_first_sector * SECTOR_SIZE_BYTES + 1024, 1024)
        if struct.unpack_from("<H", superblock, 56)[0] != 0xEF53:
            raise ValueError("The Linux root partition has no valid ext filesystem signature.")
        block_size_exponent = struct.unpack_from("<I", superblock, 24)[0]
        if block_size_exponent > 6:
            raise ValueError("The root filesystem block size is invalid.")
        filesystem_block_count = struct.unpack_from("<I", superblock, 4)[0]
        incompatible_features = struct.unpack_from("<I", superblock, 96)[0]
        if incompatible_features & 0x80:
            filesystem_block_count |= struct.unpack_from("<I", superblock, 336)[0] << 32
        if not filesystem_block_count or filesystem_block_count * (1024 << block_size_exponent) > root_sector_count * SECTOR_SIZE_BYTES:
            raise ValueError("The root filesystem extends beyond its partition.")
    return {
        "image_size_bytes": image_size_bytes,
        "firmware_filesystem": filesystem_type,
        "firmware_size_bytes": firmware_sector_count * SECTOR_SIZE_BYTES,
        "root_filesystem": "ext",
        "root_size_bytes": root_sector_count * SECTOR_SIZE_BYTES,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_path", nargs="?", type=Path,
                        default=Path(__file__).resolve().parents[1] / "result-image/fpv-recorder-pi4.img")
    image_path = parser.parse_args().image_path
    try:
        image_layout = validate_pi_image(image_path)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Image validation failed: {error}\n")
    print(f"Image layout valid: FAT32 firmware ({image_layout['firmware_size_bytes'] // 1048576} MiB) "
          f"and Linux root; {image_layout['image_size_bytes']} bytes.")
    print("This checks image structure, not a completed card write or Pi boot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
