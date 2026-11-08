"""End-to-end integration tests for VoiceStudio AI Loudness Mastering Engine."""
import os
import unittest
from pathlib import Path

import soundfile as sf

from app.audio.filters import VoicePolishOptions
from app.audio.mastering import AudioMasterer, MASTERING_PRESETS
from app.services.mastering_service import MasteringService
from app.database.connection import DatabaseManager


class TestMasteringE2E(unittest.TestCase):
    """Verifies end-to-end mastering pipeline on real generated speech audio."""

    @classmethod
    def setUpClass(cls):
        # Locate real generated audio file
        cls.test_input = None
        for p in Path("storage/generated").glob("**/*.wav"):
            if p.stat().st_size > 10000:
                cls.test_input = p
                break
        if cls.test_input is None:
            for p in Path("storage/references").glob("**/*.wav"):
                cls.test_input = p
                break

        cls.service = MasteringService()

    def test_01_preset_podcast_mastering(self):
        self.assertIsNotNone(self.test_input)
        input_mtime_before = self.test_input.stat().st_mtime

        res = self.service.master_file(
            self.test_input,
            preset_key="podcast",
            enable_silence_trim=True,
            voice_polish_options=VoicePolishOptions()
        )

        self.assertTrue(res.success)
        self.assertEqual(res.preset_name, "Podcast / Streaming")
        self.assertEqual(res.target_lufs, -16.0)
        self.assertEqual(res.target_tp, -1.5)

        # Non-destructive: original input file must be completely untouched
        self.assertEqual(self.test_input.stat().st_mtime, input_mtime_before)

        # Output WAV verification
        out_wav = Path(res.output_wav_path)
        self.assertTrue(out_wav.exists())
        info_wav = sf.info(str(out_wav))
        self.assertEqual(info_wav.samplerate, 48000)
        self.assertEqual(info_wav.subtype, "PCM_24")

        # Output MP3 verification
        out_mp3 = Path(res.output_mp3_path)
        self.assertTrue(out_mp3.exists())
        self.assertGreater(out_mp3.stat().st_size, 1000)

        # Loudness convergence within +/- 1.0 LUFS of target (-16.0 LUFS) per EBU R128 short-form tolerance
        self.assertAlmostEqual(res.final_metrics.integrated_lufs, -16.0, delta=1.0)
        # True-Peak ceiling compliance
        self.assertLessEqual(res.final_metrics.true_peak_dbtp, -1.4)

    def test_02_preset_audiobook_mastering(self):
        self.assertIsNotNone(self.test_input)
        res = self.service.master_file(
            self.test_input,
            preset_key="audiobook",
            enable_silence_trim=False,
            voice_polish_options=VoicePolishOptions(enable_compressor=False)
        )

        self.assertTrue(res.success)
        self.assertEqual(res.preset_name, "Audiobook / ACX")
        self.assertEqual(res.target_lufs, -18.0)
        self.assertAlmostEqual(res.final_metrics.integrated_lufs, -18.0, delta=1.0)
        self.assertLessEqual(res.final_metrics.true_peak_dbtp, -1.4)

    def test_03_preset_soft_mastering(self):
        self.assertIsNotNone(self.test_input)
        res = self.service.master_file(
            self.test_input,
            preset_key="soft"
        )

        self.assertTrue(res.success)
        self.assertEqual(res.preset_name, "Soft / Natural")
        self.assertEqual(res.target_lufs, -20.0)
        self.assertAlmostEqual(res.final_metrics.integrated_lufs, -20.0, delta=1.0)
        self.assertLessEqual(res.final_metrics.true_peak_dbtp, -1.9)

    def test_04_custom_mastering_targets(self):
        self.assertIsNotNone(self.test_input)
        custom_target_i = -17.5
        custom_target_tp = -2.0

        res = self.service.master_file(
            self.test_input,
            preset_key="custom",
            custom_target_lufs=custom_target_i,
            custom_true_peak=custom_target_tp
        )

        self.assertTrue(res.success)
        self.assertEqual(res.target_lufs, custom_target_i)
        self.assertEqual(res.target_tp, custom_target_tp)
        self.assertAlmostEqual(res.final_metrics.integrated_lufs, custom_target_i, delta=1.0)
        self.assertLessEqual(res.final_metrics.true_peak_dbtp, custom_target_tp + 0.1)

    def test_05_sqlite_audit_logging(self):
        # Verify that mastering history is queryable and records accurately
        jobs = self.service.list_mastering_history(limit=10)
        self.assertGreater(len(jobs), 0)

        latest_job = jobs[0]
        self.assertTrue(latest_job.id.startswith("mst_"))
        self.assertIn(latest_job.status, ["completed", "failed"])
        self.assertIsNotNone(latest_job.measured_output_lufs)
        self.assertIsNotNone(latest_job.measured_output_tp)
        self.assertGreater(latest_job.duration_sec, 0.0)
        self.assertGreater(latest_job.processing_time_sec, 0.0)


if __name__ == "__main__":
    unittest.main()
