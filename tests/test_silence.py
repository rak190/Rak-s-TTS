"""Unit tests for non-destructive silence processor."""
import unittest
import numpy as np

from app.audio.silence import SilenceProcessor


class TestSilenceProcessor(unittest.TestCase):
    """Verifies edge silence trimming, natural margin retention, and safety preservation."""

    def test_01_trim_synthetic_audio_with_silence_padding(self):
        sr = 48000
        # 1.0s silence + 1.0s speech tone + 1.0s silence
        lead_silence = np.zeros(sr, dtype=np.float32)
        t = np.linspace(0, 1.0, sr, endpoint=False)
        speech_tone = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
        trail_silence = np.zeros(sr, dtype=np.float32)

        full_audio = np.concatenate([lead_silence, speech_tone, trail_silence])
        total_dur = len(full_audio) / sr  # 3.0s

        trimmed, lead_sec, trail_sec = SilenceProcessor.trim_silence_edges(
            full_audio, sr,
            threshold_db=-45.0,
            leading_margin_sec=0.10,
            trailing_margin_sec=0.20
        )

        # Leading trimmed should be roughly 1.0s - 0.10s = 0.90s
        self.assertAlmostEqual(lead_sec, 0.90, delta=0.05)
        # Trailing trimmed should be roughly 1.0s - 0.20s = 0.80s
        self.assertAlmostEqual(trail_sec, 0.80, delta=0.05)

        new_dur = len(trimmed) / sr
        # Expected new duration: 3.0s - (0.90s + 0.80s) = 1.30s
        self.assertAlmostEqual(new_dur, 1.30, delta=0.06)

    def test_02_preserves_audio_already_tight(self):
        sr = 48000
        # 50ms silence + speech
        lead_silence = np.zeros(int(0.05 * sr), dtype=np.float32)
        t = np.linspace(0, 1.0, sr, endpoint=False)
        speech = 0.4 * np.sin(2 * np.pi * 300 * t).astype(np.float32)
        audio = np.concatenate([lead_silence, speech])

        trimmed, lead_sec, trail_sec = SilenceProcessor.trim_silence_edges(
            audio, sr,
            leading_margin_sec=0.10,
            trailing_margin_sec=0.20
        )
        # Should not trim if already within margin
        self.assertEqual(lead_sec, 0.0)
        self.assertEqual(trail_sec, 0.0)
        self.assertEqual(len(trimmed), len(audio))

    def test_03_preserves_pure_silence_without_crash(self):
        sr = 48000
        pure_silence = np.zeros(sr * 2, dtype=np.float32)
        trimmed, lead_sec, trail_sec = SilenceProcessor.trim_silence_edges(pure_silence, sr)

        self.assertEqual(lead_sec, 0.0)
        self.assertEqual(trail_sec, 0.0)
        self.assertEqual(len(trimmed), len(pure_silence))


if __name__ == "__main__":
    unittest.main()
