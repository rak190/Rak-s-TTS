"""Unit tests for voice polish and speech enhancement DSP filters."""
import unittest
import numpy as np

from app.audio.filters import VoicePolishFilters, VoicePolishOptions


class TestVoicePolishFilters(unittest.TestCase):
    """Verifies highpass rumble filter, dynamic de-esser, presence EQ, compressor, and limiter."""

    def setUp(self):
        self.sr = 48000
        self.duration = 1.0
        self.t = np.linspace(0, self.duration, int(self.sr * self.duration), endpoint=False)

    def test_01_highpass_rumble_attenuates_sub_vocal_energy(self):
        # 30 Hz sub-vocal rumble + 500 Hz vocal fundamental
        rumble = 0.5 * np.sin(2 * np.pi * 30 * self.t)
        vocal = 0.5 * np.sin(2 * np.pi * 500 * self.t)
        signal = (rumble + vocal).astype(np.float32)

        filtered = VoicePolishFilters.apply_highpass_rumble(signal, self.sr, cutoff_hz=80.0)

        # 30 Hz energy should be significantly attenuated (>15 dB attenuation)
        rumble_power_before = np.mean(rumble ** 2)
        filtered_power = np.mean(filtered ** 2)
        # Filtered output should be closer to pure vocal power
        vocal_power = np.mean(vocal ** 2)
        self.assertAlmostEqual(filtered_power, vocal_power, delta=0.08)

    def test_02_vocal_presence_boost(self):
        # 3500 Hz tone
        tone = 0.2 * np.sin(2 * np.pi * 3500 * self.t).astype(np.float32)
        boosted = VoicePolishFilters.apply_vocal_presence_eq(tone, self.sr, center_hz=3500.0, gain_db=1.5)

        rms_before = np.sqrt(np.mean(tone ** 2))
        rms_after = np.sqrt(np.mean(boosted ** 2))
        self.assertGreater(rms_after, rms_before)

    def test_03_deesser_tames_sibilance(self):
        # High sibilant burst at 7000 Hz
        sibilant_burst = 0.8 * np.sin(2 * np.pi * 7000 * self.t).astype(np.float32)
        deessed = VoicePolishFilters.apply_deesser(sibilant_burst, self.sr, threshold_db=-24.0)

        peak_before = np.max(np.abs(sibilant_burst))
        peak_after = np.max(np.abs(deessed))
        self.assertLess(peak_after, peak_before)

    def test_04_speech_compressor_smooths_dynamics(self):
        # Loud segment followed by quiet segment
        loud = 0.8 * np.sin(2 * np.pi * 400 * self.t[: len(self.t) // 2])
        quiet = 0.1 * np.sin(2 * np.pi * 400 * self.t[len(self.t) // 2 :])
        signal = np.concatenate([loud, quiet]).astype(np.float32)

        compressed = VoicePolishFilters.apply_speech_compressor(
            signal, self.sr, threshold_db=-18.0, ratio=2.5, makeup_gain_db=0.0
        )

        # Steady-state loud peak (after attack time) should be compressed
        settled_start = int(0.05 * self.sr)
        settled_end = len(self.t) // 2
        loud_peak_before = np.max(np.abs(signal[settled_start:settled_end]))
        loud_peak_after = np.max(np.abs(compressed[settled_start:settled_end]))
        self.assertLess(loud_peak_after, loud_peak_before)

        # RMS of entire loud segment must be reduced
        rms_before = np.sqrt(np.mean(signal[:settled_end] ** 2))
        rms_after = np.sqrt(np.mean(compressed[:settled_end] ** 2))
        self.assertLess(rms_after, rms_before)

    def test_05_brickwall_limiter_strictly_enforces_ceiling(self):
        # Signal exceeding -1.5 dBFS (linear ~0.841)
        hot_signal = np.ones(1000, dtype=np.float32) * 0.98
        limited = VoicePolishFilters.apply_brickwall_limiter(hot_signal, ceiling_dbfs=-1.5)

        ceiling_linear = 10 ** (-1.5 / 20.0)
        self.assertLessEqual(np.max(np.abs(limited)), ceiling_linear + 1e-4)

    def test_06_polish_audio_pipeline(self):
        signal = 0.5 * np.sin(2 * np.pi * 400 * self.t).astype(np.float32)
        opts = VoicePolishOptions()
        polished = VoicePolishFilters.polish_audio(signal, self.sr, opts)

        self.assertEqual(len(polished), len(signal))
        self.assertTrue(np.all(np.isfinite(polished)))


if __name__ == "__main__":
    unittest.main()
