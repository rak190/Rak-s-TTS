"""Test SQLite database persistence across simulated application restart and process termination."""
import os
import unittest
import numpy as np
import soundfile as sf
from pathlib import Path
from datetime import datetime, timezone

from app.config import STORAGE_DIR, TEMP_DIR, NATIVE_SAMPLE_RATE
from app.database.connection import DatabaseManager
from app.database.models import VoiceProfile, GenerationRecord

class TestRestartPersistence(unittest.TestCase):
    """Verifies that voice profiles and generation records survive full restarts."""

    def setUp(self):
        self.test_dir = TEMP_DIR / "test_restart"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create dummy WAV files at 48kHz PCM_16
        self.orig_wav = self.test_dir / "orig_ref.wav"
        self.slice_wav = self.test_dir / "slice_ref.wav"
        self.gen_wav = self.test_dir / "gen_output.wav"
        
        sample_audio = (np.sin(2 * np.pi * 440 * np.linspace(0, 2.0, 2 * NATIVE_SAMPLE_RATE))).astype(np.float32)
        sf.write(str(self.orig_wav), sample_audio, NATIVE_SAMPLE_RATE, subtype="PCM_16")
        sf.write(str(self.slice_wav), sample_audio[:NATIVE_SAMPLE_RATE], NATIVE_SAMPLE_RATE, subtype="PCM_16")
        sf.write(str(self.gen_wav), sample_audio, NATIVE_SAMPLE_RATE, subtype="PCM_16")
        
        self.db = DatabaseManager.get_instance()
        self.profile_id = f"test_prof_persist_{int(datetime.now().timestamp())}"
        self.gen_id = f"test_gen_persist_{int(datetime.now().timestamp())}"

    def tearDown(self):
        # Clean up database test entries
        try:
            self.db.delete_voice_profile(self.profile_id)
            self.db.delete_generation(self.gen_id)
        except Exception:
            pass
        # Clean up temporary test files
        for f in [self.orig_wav, self.slice_wav, self.gen_wav]:
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass
        if self.test_dir.exists():
            try:
                self.test_dir.rmdir()
            except Exception:
                pass

    def test_database_and_file_persistence_across_restart(self):
        # Step 1: Create profile
        prof = VoiceProfile(
            id=self.profile_id,
            name=f"Persistence Voice {self.profile_id}",
            description="Testing restart persistence",
            language="khmer",
            original_audio_path=str(self.orig_wav),
            reference_segment_path=str(self.slice_wav),
            transcript="សួស្តី ខ្ញុំជាសម្លេងសាកល្បង",
            duration_sec=1.0,
            sample_rate=NATIVE_SAMPLE_RATE
        )
        self.db.create_voice_profile(prof)

        # Step 2: Create generation record
        gen = GenerationRecord(
            id=self.gen_id,
            voice_profile_id=self.profile_id,
            voice_name=prof.name,
            target_text="អត្ថបទសាកល្បងសម្រាប់ការចាប់ផ្តើមឡើងវិញ",
            mode="cloning",
            language="khmer",
            output_audio_path=str(self.gen_wav),
            duration_sec=2.0,
            generation_time_sec=15.2,
            rtf=7.6,
            sample_rate=NATIVE_SAMPLE_RATE,
            status="completed"
        )
        self.db.create_generation(gen)

        # Step 3: Simulate full process termination and restart
        # Wipe singleton instance and simulate fresh process lifecycle
        DatabaseManager._instance = None
        new_db = DatabaseManager.get_instance()
        self.assertIsNot(self.db, new_db or None) # New instance check

        # Step 4: Verify retrieved records
        retrieved_prof = new_db.get_voice_profile(self.profile_id)
        self.assertIsNotNone(retrieved_prof, "Voice profile failed to persist across restart")
        self.assertEqual(retrieved_prof.name, prof.name)
        self.assertEqual(retrieved_prof.transcript, prof.transcript)
        self.assertEqual(retrieved_prof.sample_rate, NATIVE_SAMPLE_RATE)

        # Step 5: Verify files on disk still exist and are valid WAV
        self.assertTrue(Path(retrieved_prof.reference_segment_path).exists())
        info_slice = sf.info(retrieved_prof.reference_segment_path)
        self.assertEqual(info_slice.samplerate, NATIVE_SAMPLE_RATE)
        self.assertEqual(info_slice.channels, 1)

        # Step 6: Verify generation record persistence
        history = new_db.list_generations(limit=100)
        matching = [g for g in history if g.id == self.gen_id]
        self.assertEqual(len(matching), 1, "Generation record failed to persist across restart")
        self.assertEqual(matching[0].target_text, gen.target_text)
        self.assertTrue(Path(matching[0].output_audio_path).exists())
        
        info_gen = sf.info(matching[0].output_audio_path)
        self.assertEqual(info_gen.samplerate, NATIVE_SAMPLE_RATE)
        self.assertEqual(info_gen.channels, 1)

if __name__ == "__main__":
    unittest.main()
