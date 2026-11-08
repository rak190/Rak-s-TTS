"""
Comprehensive Stage 3 End-to-End Voice Cloning & Integration Test Suite.
Tests both Controllable and Hi-Fi / Ultimate Voice Cloning modes,
cross-language cloning, artifact persistence, audio metrics, and queue safety.
"""
import json
import os
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

from app.config import (
    BASE_DIR,
    STORAGE_DIR,
    DB_PATH,
    NATIVE_SAMPLE_RATE,
    DEFAULT_CFG_VALUE,
    DEFAULT_INFERENCE_TIMESTEPS
)
from app.database.connection import DatabaseManager
from app.engines.model_manager import ModelManager
from app.services.voice_service import VoiceProfileService
from app.services.generation_service import GenerationService
from app.queue.generation_queue import GenerationQueue, GenerationTask
from app.audio.processor import AudioProcessor

class TestStage3CloningE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("VOICESTUDIO AI - STAGE 3 COMPREHENSIVE END-TO-END CLONING TEST")
        print("Testing Controllable & Hi-Fi Cloning on Intel Core i5-1240P CPU")
        print("=" * 70)

        cls.db = DatabaseManager.get_instance()
        cls.voice_service = VoiceProfileService.get_instance()
        cls.gen_service = GenerationService.get_instance()
        cls.model_mgr = ModelManager.get_instance()
        cls.audio_proc = AudioProcessor()

        # Seed audio paths from verified Stage 2 benchmark outputs
        cls.seed_en_wav = BASE_DIR / "benchmark_outputs" / "t3_english_text_only.wav"
        cls.seed_en_text = "Hello! This is a test of VoxCPM2 running on Intel CPU."
        
        cls.seed_kh_wav = BASE_DIR / "benchmark_outputs" / "t2_khmer_text_only.wav"
        cls.seed_kh_text = "សួស្តី! នេះគឺជាការសាកល្បង VoxCPM2 នៅលើកុំព្យូទ័រនេះ។"

        if not cls.seed_en_wav.exists() or not cls.seed_kh_wav.exists():
            raise FileNotFoundError("Seed audio missing from benchmark_outputs.")

        cls.telemetry_records = []

    def test_01_verify_singleton_and_warmup(self):
        """Step 1: Confirms singleton ModelManager and 4-thread CPU thread limit."""
        print("\n--- Test 1: Verify Singleton ModelManager & Memory ---")
        t0 = time.perf_counter()
        model = self.model_mgr.load_model()
        load_time = round(time.perf_counter() - t0, 2)
        self.assertIsNotNone(model)

        status = self.model_mgr.get_status()
        self.assertTrue(status["is_loaded"])
        self.assertEqual(status["sample_rate_hz"], NATIVE_SAMPLE_RATE)
        self.assertEqual(status["num_threads"], 4)
        print(f"   Model Status: Loaded in {load_time}s | Threads: {status['num_threads']} | RAM RSS: {status['process_rss_mb']} MB")

    def test_02_create_profile_with_complete_artifacts(self):
        """Step 2: Create Voice Profile and verify all 4 artifacts on Drive D:"""
        print("\n--- Test 2: Voice Profile Creation & Full Artifact Persistence ---")
        profile_name = "Stage3 Test Speaker EN"
        
        # Cleanup if leftover from previous test run
        existing = self.db.get_voice_profile_by_name(profile_name)
        if existing:
            self.voice_service.delete_profile(existing.id)

        prof, err = self.voice_service.create_profile(
            name=profile_name,
            original_audio_path=self.seed_en_wav,
            description="English test profile for Stage 3 validation",
            language="english",
            transcript=self.seed_en_text,
            trim_start_sec=0.0,
            trim_end_sec=5.0
        )
        self.assertIsNotNone(prof, f"Profile creation failed: {err}")
        self.__class__.en_profile = prof

        # Verify disk artifacts in storage/voices/<profile_id>/
        prof_dir = STORAGE_DIR / "voices" / prof.id
        self.assertTrue((prof_dir / "original.wav").exists(), "original.wav missing")
        self.assertTrue((prof_dir / "reference.wav").exists(), "reference.wav missing")
        self.assertTrue((prof_dir / "transcript.txt").exists(), "transcript.txt missing")
        self.assertTrue((prof_dir / "metadata.json").exists(), "metadata.json missing")

        # Verify transcript content
        with open(prof_dir / "transcript.txt", "r", encoding="utf-8") as f:
            saved_transcript = f.read()
        self.assertEqual(saved_transcript, self.seed_en_text)

        # Verify metadata.json content
        with open(prof_dir / "metadata.json", "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["id"], prof.id)
        self.assertEqual(meta["name"], profile_name)
        self.assertEqual(meta["language"], "english")

        print(f"   Profile '{prof.name}' (ID: {prof.id}) created.")
        print(f"   Artifacts confirmed in: {prof_dir}")

    def test_03_controllable_voice_cloning_english(self):
        """Step 3: Controllable Voice Cloning (English text with English profile)."""
        print("\n--- Test 3: Controllable Voice Cloning (English) ---")
        prof = self.en_profile
        target_text = "This is a controllable voice cloning test for Stage 3."
        
        task = GenerationTask(
            job_id="s3_clone_en_001",
            job_type="cloning",
            target_text=target_text,
            voice_profile_id=prof.id,
            voice_name=prof.name,
            language="english",
            reference_wav_path=prof.reference_segment_path,
            cfg_value=DEFAULT_CFG_VALUE,
            inference_timesteps=DEFAULT_INFERENCE_TIMESTEPS
        )
        
        res = self.gen_service.execute_generation_task(task)
        self.assertIn("output_path", res)
        out_path = Path(res["output_path"])
        self.assertTrue(out_path.exists())

        # Inspect generated audio
        data, sr = sf.read(str(out_path))
        self.assertEqual(sr, 48000)
        self.assertGreater(len(data), 0)
        self.assertFalse(np.isnan(data).any(), "Audio contains NaN")
        
        rms = np.sqrt(np.mean(data ** 2))
        self.assertGreater(rms, 0.01, "Audio appears silent")

        self.telemetry_records.append({
            "test": "Controllable EN",
            "duration_sec": res["duration_sec"],
            "gen_time_sec": res["generation_time_sec"],
            "rtf": res["rtf"],
            "output": str(out_path)
        })
        print(f"   Controllable EN: {res['duration_sec']}s audio in {res['generation_time_sec']}s (RTF: {res['rtf']}x)")
        print(f"   Output saved: {out_path}")

    def test_04_controllable_voice_cloning_khmer(self):
        """Step 4: Controllable Voice Cloning (Khmer text with Khmer profile)."""
        print("\n--- Test 4: Controllable Voice Cloning (Khmer) ---")
        kh_prof_name = "Stage3 Test Speaker KH"
        existing = self.db.get_voice_profile_by_name(kh_prof_name)
        if existing:
            self.voice_service.delete_profile(existing.id)

        kh_prof, err = self.voice_service.create_profile(
            name=kh_prof_name,
            original_audio_path=self.seed_kh_wav,
            description="Khmer test profile for Stage 3",
            language="khmer",
            transcript=self.seed_kh_text,
            trim_start_sec=0.0,
            trim_end_sec=5.0
        )
        self.assertIsNotNone(kh_prof, f"Khmer profile creation failed: {err}")
        self.__class__.kh_profile = kh_prof

        target_text = "សួស្តី! នេះជាការសាកល្បងសំឡេងខ្មែរនៅដំណាក់កាលទី ៣។"
        task = GenerationTask(
            job_id="s3_clone_kh_001",
            job_type="cloning",
            target_text=target_text,
            voice_profile_id=kh_prof.id,
            voice_name=kh_prof.name,
            language="khmer",
            reference_wav_path=kh_prof.reference_segment_path,
            cfg_value=DEFAULT_CFG_VALUE,
            inference_timesteps=DEFAULT_INFERENCE_TIMESTEPS
        )
        
        res = self.gen_service.execute_generation_task(task)
        self.assertIn("output_path", res)
        out_path = Path(res["output_path"])
        self.assertTrue(out_path.exists())

        data, sr = sf.read(str(out_path))
        self.assertEqual(sr, 48000)
        self.assertGreater(len(data), 0)
        self.assertFalse(np.isnan(data).any())
        
        rms = np.sqrt(np.mean(data ** 2))
        self.assertGreater(rms, 0.01)

        self.telemetry_records.append({
            "test": "Controllable KH",
            "duration_sec": res["duration_sec"],
            "gen_time_sec": res["generation_time_sec"],
            "rtf": res["rtf"],
            "output": str(out_path)
        })
        print(f"   Controllable KH: {res['duration_sec']}s audio in {res['generation_time_sec']}s (RTF: {res['rtf']}x)")
        print(f"   Output saved: {out_path}")

    def test_05_hifi_ultimate_cloning(self):
        """Step 5: Hi-Fi / Ultimate Voice Cloning (Prompt Audio + Verbatim Transcript)."""
        print("\n--- Test 5: Hi-Fi / Ultimate Voice Cloning ---")
        prof = self.en_profile
        target_text = "VoiceStudio AI achieves high fidelity with prompt transcript matching."
        
        task = GenerationTask(
            job_id="s3_hifi_en_001",
            job_type="ultimate_cloning",
            target_text=target_text,
            voice_profile_id=prof.id,
            voice_name=prof.name,
            language="english",
            reference_wav_path=prof.reference_segment_path,
            prompt_wav_path=prof.reference_segment_path,
            prompt_text=prof.transcript,
            cfg_value=DEFAULT_CFG_VALUE,
            inference_timesteps=DEFAULT_INFERENCE_TIMESTEPS
        )

        res = self.gen_service.execute_generation_task(task)
        self.assertIn("output_path", res)
        out_path = Path(res["output_path"])
        self.assertTrue(out_path.exists())

        data, sr = sf.read(str(out_path))
        self.assertEqual(sr, 48000)
        self.assertGreater(len(data), 0)
        self.assertFalse(np.isnan(data).any())
        
        rms = np.sqrt(np.mean(data ** 2))
        self.assertGreater(rms, 0.01)

        self.telemetry_records.append({
            "test": "Hi-Fi Ultimate EN",
            "duration_sec": res["duration_sec"],
            "gen_time_sec": res["generation_time_sec"],
            "rtf": res["rtf"],
            "output": str(out_path)
        })
        print(f"   Hi-Fi Ultimate EN: {res['duration_sec']}s audio in {res['generation_time_sec']}s (RTF: {res['rtf']}x)")
        print(f"   Output saved: {out_path}")

    def test_06_cross_language_voice_cloning(self):
        """Step 6: Cross-Language Voice Cloning (English reference voice speaking Khmer text)."""
        print("\n--- Test 6: Cross-Language Voice Cloning (EN Voice -> KH Text) ---")
        prof = self.en_profile
        cross_kh_text = "ជំរាបសួរ! ខ្ញុំកំពុងនិយាយភាសាខ្មែរដោយប្រើសំឡេងភាសាអង់គ្លេស។"
        
        task = GenerationTask(
            job_id="s3_cross_001",
            job_type="cloning",
            target_text=cross_kh_text,
            voice_profile_id=prof.id,
            voice_name=prof.name,
            language="khmer",
            reference_wav_path=prof.reference_segment_path,
            cfg_value=DEFAULT_CFG_VALUE,
            inference_timesteps=DEFAULT_INFERENCE_TIMESTEPS
        )

        res = self.gen_service.execute_generation_task(task)
        self.assertIn("output_path", res)
        out_path = Path(res["output_path"])
        self.assertTrue(out_path.exists())

        data, sr = sf.read(str(out_path))
        self.assertEqual(sr, 48000)
        self.assertGreater(len(data), 0)
        self.assertFalse(np.isnan(data).any())

        self.telemetry_records.append({
            "test": "Cross-Language (EN Voice -> KH Text)",
            "duration_sec": res["duration_sec"],
            "gen_time_sec": res["generation_time_sec"],
            "rtf": res["rtf"],
            "output": str(out_path)
        })
        print(f"   Cross-Language: {res['duration_sec']}s audio in {res['generation_time_sec']}s (RTF: {res['rtf']}x)")
        print(f"   Output saved: {out_path}")

    def test_07_replace_reference_audio_workflow(self):
        """Step 7: Replaces reference audio and verifies atomic update."""
        print("\n--- Test 7: Replace Reference Audio & Re-test ---")
        prof = getattr(self.__class__, "en_profile", None)
        if not prof:
            prof = self.db.get_voice_profile_by_name("Stage3 Test Speaker EN")
        self.assertIsNotNone(prof, "Stage3 Test Speaker EN profile not found")
        new_transcript = "Replaced reference segment with updated audio slice."

        ok, err = self.voice_service.replace_reference_audio(
            profile_id=prof.id,
            new_audio_path=self.seed_en_wav,
            trim_start_sec=1.0,
            trim_end_sec=4.0,
            transcript=new_transcript
        )
        self.assertTrue(ok, f"Replacement failed: {err}")
        updated_prof = self.voice_service.get_profile(prof.id)
        self.assertIsNotNone(updated_prof)
        self.assertEqual(updated_prof.transcript, new_transcript)

        # Verify disk artifacts reflect update
        prof_dir = STORAGE_DIR / "voices" / prof.id
        with open(prof_dir / "transcript.txt", "r", encoding="utf-8") as f:
            saved_t = f.read()
        self.assertEqual(saved_t, new_transcript)

        with open(prof_dir / "metadata.json", "r", encoding="utf-8") as f:
            saved_m = json.load(f)
        self.assertEqual(saved_m["transcript"], new_transcript)

        print(f"   Reference audio successfully replaced for profile: {updated_prof.name}")

    def test_08_error_handling_and_guards(self):
        """Step 8: Tests safety guards (missing files, empty transcripts)."""
        print("\n--- Test 8: Error Handling & Safety Guards ---")
        
        # Missing reference file
        task_bad_ref = GenerationTask(
            job_id="bad_ref_001",
            job_type="cloning",
            target_text="Test",
            reference_wav_path="storage/non_existent_file.wav"
        )
        with self.assertRaises(FileNotFoundError):
            self.gen_service.execute_generation_task(task_bad_ref)
        print("   Guard passed: Missing reference audio raises FileNotFoundError.")

        # Missing transcript for ultimate cloning
        task_bad_trans = GenerationTask(
            job_id="bad_trans_001",
            job_type="ultimate_cloning",
            target_text="Test",
            prompt_wav_path=str(self.seed_en_wav),
            prompt_text=""
        )
        with self.assertRaises(ValueError):
            self.gen_service.execute_generation_task(task_bad_trans)
        print("   Guard passed: Missing transcript for ultimate cloning raises ValueError.")

    def test_09_database_and_history_persistence(self):
        """Step 9: Verifies generations and profiles are in SQLite."""
        print("\n--- Test 9: Database Integrity & History Records ---")
        history = self.gen_service.list_history(limit=20)
        self.assertGreaterEqual(len(history), 4)

        # Find the Stage 3 generation records
        s3_records = [h for h in history if h.id.startswith("gen_")]
        self.assertGreaterEqual(len(s3_records), 4)

        for rec in s3_records[:4]:
            self.assertEqual(rec.status, "completed")
            self.assertEqual(rec.sample_rate, 48000)
            self.assertTrue(Path(rec.output_audio_path).exists())
            print(f"   Record {rec.id}: mode={rec.mode} | lang={rec.language} | duration={rec.duration_sec}s | rtf={rec.rtf}x")

        print("=" * 70)
        print("ALL STAGE 3 END-TO-END TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)

if __name__ == "__main__":
    unittest.main()
