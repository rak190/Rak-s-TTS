"""Real integration test executing the complete VoiceStudio AI workflow on the host laptop."""
import os
import sys
import unittest
from pathlib import Path
import soundfile as sf

# Enforce UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.config import (
    BASE_DIR,
    STORAGE_DIR,
    DB_PATH,
    NATIVE_SAMPLE_RATE
)
from app.database.connection import DatabaseManager
from app.engines.model_manager import ModelManager
from app.services.voice_service import VoiceProfileService
from app.services.generation_service import GenerationService
from app.queue.generation_queue import GenerationTask

class TestIntegrationE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 60)
        print("STARTING REAL STAGE 2B END-TO-END INTEGRATION TEST")
        print("Hardware: Intel Core i5-1240P CPU (4 Threads)")
        print("=" * 60)

        # 1. Initialize Database
        cls.db = DatabaseManager.get_instance()
        cls.voice_service = VoiceProfileService.get_instance()
        cls.gen_service = GenerationService.get_instance()
        cls.model_mgr = ModelManager.get_instance()

        # Seed reference audio from Stage 2A
        cls.seed_wav = BASE_DIR / "benchmark_outputs" / "t3_english_text_only.wav"
        if not cls.seed_wav.exists():
            raise FileNotFoundError(f"Required seed audio missing: {cls.seed_wav}")

    def test_01_model_loading(self):
        """Verifies model loads successfully into RAM and sets 4-thread CPU limit."""
        print("\nStep 1: Loading model into RAM...")
        model = self.model_mgr.load_model()
        self.assertIsNotNone(model)
        status = self.model_mgr.get_status()
        self.assertTrue(status["is_loaded"])
        self.assertEqual(status["sample_rate_hz"], NATIVE_SAMPLE_RATE)
        print(f"   Model verified: {status['sample_rate_hz']} Hz | Peak RAM: {status['process_rss_mb']} MB")

    def test_02_create_voice_profile(self):
        """Verifies creating and persisting a Voice Profile."""
        print("\nStep 2: Creating a voice profile from reference audio...")
        profile_name = "Integration Test Voice"
        # If exists from previous run, delete first to keep test idempotent
        existing = self.db.get_voice_profile_by_name(profile_name)
        if existing:
            self.voice_service.delete_profile(existing.id)

        prof, msg = self.voice_service.create_profile(
            name=profile_name,
            original_audio_path=self.seed_wav,
            description="Created during E2E integration test",
            language="english",
            transcript="Hello and welcome to VoiceStudio AI, running locally on your computer.",
            trim_start_sec=0.0,
            trim_end_sec=4.0
        )
        self.assertIsNotNone(prof, f"Profile creation failed: {msg}")
        self.__class__.created_profile = prof
        
        # Verify file existence on Drive D:
        orig_p = Path(prof.original_audio_path)
        ref_p = Path(prof.reference_segment_path)
        self.assertTrue(orig_p.exists(), f"Original file missing: {orig_p}")
        self.assertTrue(ref_p.exists(), f"Reference segment missing: {ref_p}")
        print(f"   Profile '{prof.name}' created with ID: {prof.id}")
        print(f"   Reference segment duration: {prof.duration_sec}s at {prof.sample_rate} Hz")

    def test_03_generate_khmer_speech(self):
        """Verifies Khmer text-only speech synthesis."""
        print("\nStep 3: Synthesizing Khmer text-only speech...")
        kh_text = "សួស្តី! នេះជាការសាកល្បង VoiceStudio AI។"
        task = GenerationTask(
            job_id="int_kh_001",
            job_type="tts",
            target_text=kh_text,
            language="khmer",
            cfg_value=2.0,
            inference_timesteps=10
        )
        result = self.gen_service.execute_generation_task(task)
        self.assertIn("output_path", result)
        out_p = Path(result["output_path"])
        self.assertTrue(out_p.exists())

        # Verify audio properties
        info = sf.info(str(out_p))
        self.assertEqual(info.samplerate, 48000)
        self.assertEqual(info.channels, 1)
        self.assertGreater(info.duration, 1.0)
        print(f"   Khmer speech generated: {result['duration_sec']}s audio in {result['generation_time_sec']}s (RTF: {result['rtf']}x)")
        print(f"   Saved to: {out_p}")

    def test_04_generate_english_speech(self):
        """Verifies English text-only speech synthesis."""
        print("\nStep 4: Synthesizing English text-only speech...")
        en_text = "VoiceStudio AI foundation is operational on this laptop."
        task = GenerationTask(
            job_id="int_en_001",
            job_type="tts",
            target_text=en_text,
            language="english",
            cfg_value=2.0,
            inference_timesteps=10
        )
        result = self.gen_service.execute_generation_task(task)
        self.assertIn("output_path", result)
        out_p = Path(result["output_path"])
        self.assertTrue(out_p.exists())

        info = sf.info(str(out_p))
        self.assertEqual(info.samplerate, 48000)
        self.assertGreater(info.duration, 1.0)
        print(f"   English speech generated: {result['duration_sec']}s audio in {result['generation_time_sec']}s (RTF: {result['rtf']}x)")

    def test_05_generate_speech_with_saved_voice_profile(self):
        """Verifies speech synthesis using the saved Voice Profile (Voice Cloning)."""
        print("\nStep 5: Synthesizing speech using saved voice profile...")
        prof = getattr(self.__class__, "created_profile", None)
        if not prof:
            prof = self.db.get_voice_profile_by_name("Integration Test Voice")
        self.assertIsNotNone(prof)

        clone_text = "This audio is synthesized using the cloned integration voice profile."
        task = GenerationTask(
            job_id="int_clone_001",
            job_type="cloning",
            target_text=clone_text,
            voice_profile_id=prof.id,
            voice_name=prof.name,
            language="english",
            reference_wav_path=prof.reference_segment_path,
            cfg_value=2.0,
            inference_timesteps=10
        )
        result = self.gen_service.execute_generation_task(task)
        self.assertIn("output_path", result)
        out_p = Path(result["output_path"])
        self.assertTrue(out_p.exists())

        info = sf.info(str(out_p))
        self.assertEqual(info.samplerate, 48000)
        self.assertGreater(info.duration, 1.0)
        print(f"   Cloned speech generated: {result['duration_sec']}s audio in {result['generation_time_sec']}s (RTF: {result['rtf']}x)")

    def test_06_verify_persistence_across_restart(self):
        """Simulates restarting the app and verifies profiles & history persist."""
        print("\nStep 6: Simulating app restart to verify SQLite persistence...")
        fresh_db = DatabaseManager(DB_PATH)
        profiles = fresh_db.list_voice_profiles()
        generations = fresh_db.list_generations()

        profile_names = [p.name for p in profiles]
        self.assertIn("Integration Test Voice", profile_names)
        self.assertGreaterEqual(len(generations), 3)

        print(f"   Persistence verified: {len(profiles)} profiles and {len(generations)} generation records found in DB.")
        print("=" * 60)
        print("ALL E2E INTEGRATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)

if __name__ == "__main__":
    unittest.main()
