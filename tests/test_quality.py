"""Unit tests for speech acoustic quality inspector."""
import unittest
from pathlib import Path

from app.audio.quality import QualityAnalyzer, AcousticQualityReport


class TestQualityAnalyzer(unittest.TestCase):
    """Verifies acoustic quality reporting, signal integrity, and grading."""

    @classmethod
    def setUpClass(cls):
        cls.test_audio = None
        for p in Path("storage/generated").glob("**/*.wav"):
            if p.stat().st_size > 10000:
                cls.test_audio = p
                break

    def test_01_analyze_real_audio(self):
        self.assertIsNotNone(self.test_audio)
        report = QualityAnalyzer.analyze_audio(self.test_audio)

        self.assertIsInstance(report, AcousticQualityReport)
        self.assertGreater(report.duration_sec, 0.0)
        self.assertEqual(report.sample_rate, 48000)
        self.assertEqual(report.channels, 1)

        # Loudness metrics
        self.assertLess(report.integrated_lufs, 0.0)
        self.assertLess(report.rms_dbfs, 0.0)
        self.assertLessEqual(report.true_peak_dbtp, 0.5)
        self.assertGreater(report.crest_factor_db, 0.0)

        # Silence & DC offset
        self.assertGreaterEqual(report.silence_percent, 0.0)
        self.assertLessEqual(report.silence_percent, 100.0)
        self.assertGreaterEqual(report.leading_silence_sec, 0.0)
        self.assertGreaterEqual(report.trailing_silence_sec, 0.0)
        self.assertFalse(report.is_clipped)

        # Quality grade
        self.assertIn(report.quality_grade, ["Excellent", "Good", "Needs Mastering", "Caution"])
        self.assertIsInstance(report.notes, list)
        self.assertGreater(len(report.notes), 0)

    def test_02_missing_file_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            QualityAnalyzer.analyze_audio("non_existent_quality_file.wav")


if __name__ == "__main__":
    unittest.main()
