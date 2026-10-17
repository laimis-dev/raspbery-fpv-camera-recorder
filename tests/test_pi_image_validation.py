"""Generate filesystem fixtures to check image layout without physical drives."""

import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

from scripts.validate_pi_image import validate_pi_image

FILESYSTEM_TOOL_PATH = os.environ.get("PATH", os.defpath) + ":/usr/sbin:/sbin"
MKFS_FAT_PATH = shutil.which("mkfs.fat", path=FILESYSTEM_TOOL_PATH)
MKFS_EXT4_PATH = shutil.which("mkfs.ext4", path=FILESYSTEM_TOOL_PATH)


@unittest.skipUnless(MKFS_FAT_PATH and MKFS_EXT4_PATH, "dosfstools and e2fsprogs are required")
class PiImageValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixture_directory.cleanup)
        cls.fixture_directory_path = Path(cls.fixture_directory.name)
        for filesystem_name, size_mib, mkfs_arguments in (
            ("fat32", 512, [MKFS_FAT_PATH, "-F", "32"]),
            ("fat16", 30, [MKFS_FAT_PATH, "-F", "16"]),
            ("root", 32, [MKFS_EXT4_PATH, "-q", "-F"]),
        ):
            filesystem_path = cls.fixture_directory_path / f"{filesystem_name}.img"
            with filesystem_path.open("wb") as filesystem_file:
                filesystem_file.truncate(size_mib * 1048576)
            subprocess.run([*mkfs_arguments, str(filesystem_path)], check=True, capture_output=True, timeout=20)

    def create_disk_image(self, firmware_filesystem_name):
        firmware_path = self.fixture_directory_path / f"{firmware_filesystem_name}.img"
        root_path = self.fixture_directory_path / "root.img"
        firmware_first_sector = 2048
        firmware_sector_count = firmware_path.stat().st_size // 512
        root_first_sector = firmware_first_sector + firmware_sector_count
        root_sector_count = root_path.stat().st_size // 512
        master_boot_record = bytearray(512)
        for partition_index, partition_type, first_sector, sector_count in (
            (0, 0x0C if firmware_filesystem_name == "fat32" else 0x0B, firmware_first_sector, firmware_sector_count),
            (1, 0x83, root_first_sector, root_sector_count),
        ):
            struct.pack_into("<B3sB3sII", master_boot_record, 446 + partition_index * 16,
                             0, b"\0" * 3, partition_type, b"\0" * 3, first_sector, sector_count)
        master_boot_record[510:512] = b"\x55\xaa"
        disk_path = self.fixture_directory_path / f"disk-{self.id().split('.')[-1]}.img"
        with disk_path.open("wb") as disk_file:
            disk_file.truncate((root_first_sector + root_sector_count) * 512)
            disk_file.write(master_boot_record)
            for filesystem_path, first_sector in ((firmware_path, firmware_first_sector), (root_path, root_first_sector)):
                # Only the filesystem headers are needed by the structural check.
                # They come from real mkfs output, rather than handcrafted BPBs.
                with filesystem_path.open("rb") as filesystem_file:
                    disk_file.seek(first_sector * 512)
                    disk_file.write(filesystem_file.read(4096))
        self.addCleanup(disk_path.unlink)
        return disk_path

    def test_real_fat32_and_ext4_geometry_passes(self):
        image_layout = validate_pi_image(self.create_disk_image("fat32"))
        self.assertEqual(image_layout["firmware_filesystem"], "FAT32")
        self.assertEqual(image_layout["firmware_size_bytes"], 512 * 1048576)

    def test_fat16_filesystem_in_fat32_partition_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "marked FAT32 but contains FAT16"):
            validate_pi_image(self.create_disk_image("fat16"))

    def test_truncated_root_partition_is_rejected(self):
        disk_path = self.create_disk_image("fat32")
        with disk_path.open("r+b") as disk_file:
            disk_file.truncate(disk_path.stat().st_size - 512)
        with self.assertRaisesRegex(ValueError, "outside the image"):
            validate_pi_image(disk_path)
