import os
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from recorder.config import Settings


class SettingsTests(unittest.TestCase):
    def test_no_environment_preserves_local_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Settings.from_environment(), Settings())

    def test_service_environment_selects_audio_and_storage_without_changing_video(self):
        service_environment = {
            "FPV_AUDIO_DEVICE_NAME": "plughw:CARD=CAMERA,DEV=0",
            "FPV_RECORDINGS_DIRECTORY_PATH": "/var/lib/fpv-recorder/recordings",
        }
        with patch.dict(os.environ, service_environment, clear=True):
            recording_settings = Settings.from_environment()
        self.assertEqual(recording_settings, replace(
            Settings(),
            audio_device_name="plughw:CARD=CAMERA,DEV=0",
            recordings_directory_path=Path("/var/lib/fpv-recorder/recordings"),
        ))
