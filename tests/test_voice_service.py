"""Automated unit tests for VoiceProfileService and Stage 3 profile management."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf

from app.config import NATIVE_SAMPLE_RATE, TEMP_DIR, VOICES_DIR
from app.database.connection import DatabaseManager
from app.services.voice_service import VoiceProfileService

class TestVoiceProfileService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_voice.db"
        self.db = DatabaseManager.get_instance(self.db_path)
        self.service = VoiceProfileService(db_manager=self.db)

        # Create dummy source WAV
        self.test_audio_path = Path(self.temp_dir.name) / "sample_recording.wav"
        audio = (0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 3.0, 3 * NATIVE_SAMPLE_RATE))).astype(np.float32)
        sf.write(str(self.test_audio_path), audio, NATIVE_SAMPLE_RATE, subtype="PCM_16")

        self.created_profile_id = None

    def tearDown(self):
        if self.created_profile_id:
            self.service.delete_profile(self.created_profile_id)
        self.temp_dir.cleanup()

    def test_create_and_manage_profile_lifecycle(self):
        # 1. Create Profile
        prof, msg = self.service.create_profile(
            name="Stage 3 Test Voice",
            original_audio_path=self.test_audio_path,
            description="Testing Stage 3 profile lifecycle",
            language="khmer",
            transcript="សួស្តី នេះជាសំឡេងសាកល្បង",
            trim_start_sec=0.5,
            trim_end_sec=2.5
        )
        self.assertIsNotNone(prof)
        self.created_profile_id = prof.id

        # 2. Check Directory Artifacts (Section 11 requirement)
        prof_dir = VOICES_DIR / prof.id
        self.assertTrue(prof_dir.exists())
        self.assertTrue((prof_dir / "reference.wav").exists())
        self.assertTrue((prof_dir / "transcript.txt").exists())
        self.assertTrue((prof_dir / "metadata.json").exists())

        # Verify metadata.json content
        meta = json.loads((prof_dir / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["name"], "Stage 3 Test Voice")
        self.assertEqual(meta["transcript"], "សួស្តី នេះជាសំឡេងសាកល្បង")

        # 3. Update Profile
        ok, msg = self.service.update_profile(
            profile_id=prof.id,
            name="Stage 3 Renamed Voice",
            description="Updated description",
            transcript="អត្ថបទដែលបានកែសម្រួល"
        )
        self.assertTrue(ok)
        updated = self.service.get_profile(prof.id)
        self.assertEqual(updated.name, "Stage 3 Renamed Voice")
        self.assertEqual(updated.transcript, "អត្ថបទដែលបានកែសម្រួល")

        # 4. Replace Reference Audio
        new_audio_path = Path(self.temp_dir.name) / "new_recording.wav"
        new_audio = (0.5 * np.sin(2 * np.pi * 880 * np.linspace(0, 4.0, 4 * NATIVE_SAMPLE_RATE))).astype(np.float32)
        sf.write(str(new_audio_path), new_audio, NATIVE_SAMPLE_RATE, subtype="PCM_16")

        ok, msg = self.service.replace_reference_audio(
            profile_id=prof.id,
            new_audio_path=new_audio_path,
            trim_start_sec=1.0,
            trim_end_sec=3.0,
            new_transcript="សំឡេងថ្មីដែលបានជំនួស"
        )
        self.assertTrue(ok)
        replaced = self.service.get_profile(prof.id)
        self.assertEqual(replaced.transcript, "សំឡេងថ្មីដែលបានជំនួស")
        self.assertAlmostEqual(replaced.duration_sec, 2.0, delta=0.1)

        # 5. Delete Profile
        del_id = prof.id
        ok, msg = self.service.delete_profile(del_id)
        self.assertTrue(ok)
        self.assertIsNone(self.service.get_profile(del_id))
        self.assertFalse(prof_dir.exists())
        self.created_profile_id = None

if __name__ == "__main__":
    unittest.main()
