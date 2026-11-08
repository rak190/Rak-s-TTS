"""Unit tests for ITU-R BS.1770-4 loudness measurement engine."""
import unittest
from pathlib import Path

from app.audio.loudness import LoudnessAnalyzer, LoudnessMetrics


class TestLoudnessAnalyzer(unittest.TestCase):
    """Verifies FFmpeg loudnorm and ebur128 measurement accuracy."""

    @classmethod
    def setUpClass(cls):
        # Locate an existing real audio file from generated speech
        cls.test_audio = None
        for p in Path("storage/generated").glob("**/*.wav"):
            if p.stat().st_size > 10000:
                cls.test_audio = p
                break
        if cls.test_audio is None:
            # Fallback to reference slice
            for p in Path("storage/references").glob("**/*.wav"):
                cls.test_audio = p
                break

    def test_01_measure_existing_file(self):
        self.assertIsNotNone(self.test_audio, "A real WAV file must be present in storage")
        metrics = LoudnessAnalyzer.measure_loudness(self.test_audio)
        self.assertIsInstance(metrics, LoudnessMetrics)
        self.assertIsInstance(metrics.integrated_lufs, float)
        self.assertIsInstance(metrics.true_peak_dbtp, float)
        self.assertIsInstance(metrics.loudness_range_lra, float)
        self.assertIsInstance(metrics.threshold_lufs, float)

        # Sanity ranges for typical speech
        self.assertLess(metrics.integrated_lufs, 0.0)
        self.assertGreater(metrics.integrated_lufs, -60.0)
        self.assertLessEqual(metrics.true_peak_dbtp, 0.5)
        self.assertGreaterEqual(metrics.loudness_range_lra, 0.0)

    def test_02_missing_file_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            LoudnessAnalyzer.measure_loudness("non_existent_audio_file_123.wav")

    def test_03_target_presets_tuning(self):
        self.assertIsNotNone(self.test_audio)
        metrics_podcast = LoudnessAnalyzer.measure_loudness(self.test_audio, target_i=-16.0, target_tp=-1.5)
        metrics_audiobook = LoudnessAnalyzer.measure_loudness(self.test_audio, target_i=-18.0, target_tp=-1.5)

        self.assertAlmostEqual(metrics_podcast.integrated_lufs, metrics_audiobook.integrated_lufs, delta=0.5)
        self.assertAlmostEqual(metrics_podcast.true_peak_dbtp, metrics_audiobook.true_peak_dbtp, delta=0.5)


if __name__ == "__main__":
    unittest.main()
