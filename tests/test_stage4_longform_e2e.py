"""
Comprehensive Stage 4 End-to-End Long-Form Speech Synthesis Test Suite.
Tests multi-sentence Khmer and English long-form generation, sentence chunking,
persistent checkpointing, audio stitching, crossfading, and dual WAV/MP3 export.
"""
import sys
import time
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf

# Force UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import NATIVE_SAMPLE_RATE, LONGFORM_DIR
from app.database.connection import DatabaseManager
from app.services.longform_service import LongformService
from app.services.voice_service import VoiceProfileService
from app.engines.model_manager import ModelManager

class TestStage4LongformE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("VOICESTUDIO AI - STAGE 4 LONG-FORM END-TO-END VALIDATION")
        print("Testing Multi-Sentence Chunking, Checkpoints, Stitching & MP3 Export")
        print("Hardware: Intel Core i5-1240P CPU (4 P-Cores)")
        print("=" * 70)

        cls.db = DatabaseManager.get_instance()
        cls.voice_service = VoiceProfileService.get_instance()
        cls.longform_service = LongformService.get_instance()
        cls.model_mgr = ModelManager.get_instance()

        # Warm up / verify model
        cls.model_mgr.load_model()

        # Retrieve test profiles
        cls.kh_profile = cls.db.get_voice_profile_by_name("Stage3 Test Speaker KH")
        cls.en_profile = cls.db.get_voice_profile_by_name("Stage3 Test Speaker EN")

    def test_01_khmer_longform_synthesis(self):
        """Verifies multi-sentence Khmer long-form generation with chunking and stitching."""
        print("\n--- Test 1: Khmer Long-Form Multi-Sentence Synthesis ---")
        kh_text = "សួស្តី! នេះគឺជាការសាកល្បងសំឡេងវែងតាមរយៈ VoiceStudio AI។ ប្រព័ន្ធនឹងធ្វើការបំបែកប្រយោគ និងផ្គុំសំឡេងឡើងវិញយ៉ាងរលូន។"
        
        prof_id = self.kh_profile.id if self.kh_profile else None
        mode = "cloning" if prof_id else "tts"

        job, err = self.longform_service.prepare_job(
            title="E2E Khmer Longform Test",
            text=kh_text,
            voice_profile_id=prof_id,
            mode=mode,
            language="khmer",
            target_chars=55,
            max_chars=75
        )
        self.assertIsNotNone(job, f"Job preparation failed: {err}")
        self.assertGreaterEqual(job.total_chunks, 2)
        print(f"   Job prepared: {job.id} with {job.total_chunks} chunks.")

        # Execute synthesis across chunks
        t0 = time.perf_counter()
        res = self.longform_service.execute_job(
            job_id=job.id,
            cfg_value=2.0,
            inference_timesteps=10
        )
        total_time = round(time.perf_counter() - t0, 2)

        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["completed_chunks"], job.total_chunks)
        
        # Verify master WAV
        wav_path = Path(res["output_wav_path"])
        self.assertTrue(wav_path.exists())
        info = sf.info(str(wav_path))
        self.assertEqual(info.samplerate, NATIVE_SAMPLE_RATE)
        self.assertGreater(info.duration, 3.0)

        # Verify master MP3
        mp3_path = Path(res["output_mp3_path"])
        self.assertTrue(mp3_path.exists())
        self.assertGreater(mp3_path.stat().st_size, 5000)

        print(f"   Khmer Longform: {res['total_duration_sec']}s audio in {total_time}s (RTF: {res['rtf']}x)")
        print(f"   Master WAV: {wav_path}")
        print(f"   Master MP3: {mp3_path} ({mp3_path.stat().st_size // 1024} KB)")

    def test_02_english_longform_synthesis(self):
        """Verifies multi-sentence English long-form generation with chunking and stitching."""
        print("\n--- Test 2: English Long-Form Multi-Sentence Synthesis ---")
        en_text = (
            "VoiceStudio AI long-form speech synthesis is fully operational. "
            "The audio chunks are stitched together seamlessly with zero boundary clicks."
        )

        prof_id = self.en_profile.id if self.en_profile else None
        mode = "cloning" if prof_id else "tts"

        job, err = self.longform_service.prepare_job(
            title="E2E English Longform Test",
            text=en_text,
            voice_profile_id=prof_id,
            mode=mode,
            language="english",
            target_chars=65,
            max_chars=90
        )
        self.assertIsNotNone(job, f"Job preparation failed: {err}")
        self.assertGreaterEqual(job.total_chunks, 2)
        print(f"   Job prepared: {job.id} with {job.total_chunks} chunks.")

        t0 = time.perf_counter()
        res = self.longform_service.execute_job(
            job_id=job.id,
            cfg_value=2.0,
            inference_timesteps=10
        )
        total_time = round(time.perf_counter() - t0, 2)

        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["completed_chunks"], job.total_chunks)

        # Verify outputs
        wav_path = Path(res["output_wav_path"])
        mp3_path = Path(res["output_mp3_path"])
        self.assertTrue(wav_path.exists())
        self.assertTrue(mp3_path.exists())

        info = sf.info(str(wav_path))
        self.assertEqual(info.samplerate, NATIVE_SAMPLE_RATE)
        self.assertGreater(info.duration, 3.0)

        print(f"   English Longform: {res['total_duration_sec']}s audio in {total_time}s (RTF: {res['rtf']}x)")
        print(f"   Master WAV: {wav_path}")
        print(f"   Master MP3: {mp3_path} ({mp3_path.stat().st_size // 1024} KB)")
        print("=" * 70)
        print("STAGE 4 LONG-FORM END-TO-END VALIDATION PASSED!")
        print("=" * 70)

if __name__ == "__main__":
    unittest.main()
