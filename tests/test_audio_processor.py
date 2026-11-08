"""Automated unit tests for AudioProcessor layer."""
import os
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf

from app.audio.processor import AudioProcessor

class TestAudioProcessor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Create a valid synthetic stereo 44.1kHz WAV
        self.sr = 44100
        self.dur = 5.0
        t = np.linspace(0, self.dur, int(self.sr * self.dur), endpoint=False)
        left = 0.5 * np.sin(2 * np.pi * 440 * t)
        right = 0.5 * np.sin(2 * np.pi * 880 * t)
        stereo_wav = np.column_stack([left, right]).astype(np.float32)

        self.valid_wav = self.dir_path / "valid_stereo.wav"
        sf.write(str(self.valid_wav), stereo_wav, self.sr)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_inspect_valid_audio(self):
        meta = AudioProcessor.inspect_audio(self.valid_wav)
        self.assertTrue(meta.is_valid)
        self.assertEqual(meta.channels, 2)
        self.assertEqual(meta.sample_rate, 44100)
        self.assertAlmostEqual(meta.duration_sec, 5.0, delta=0.1)

    def test_validate_audio_bounds(self):
        # Valid bounds
        ok, msg = AudioProcessor.validate_audio(self.valid_wav, min_duration=1.0, max_duration=10.0)
        self.assertTrue(ok)

        # Exceeds max duration
        ok, msg = AudioProcessor.validate_audio(self.valid_wav, min_duration=1.0, max_duration=3.0)
        self.assertFalse(ok)
        self.assertIn("exceeds limit", msg)

        # Fails min duration
        ok, msg = AudioProcessor.validate_audio(self.valid_wav, min_duration=10.0, max_duration=20.0)
        self.assertFalse(ok)
        self.assertIn("too short", msg)

    def test_convert_to_pcm16_mono(self):
        dest_wav = self.dir_path / "converted_mono_48k.wav"
        meta = AudioProcessor.convert_to_pcm16_mono(
            input_path=self.valid_wav,
            output_path=dest_wav,
            target_sr=48000
        )
        self.assertTrue(meta.is_valid)
        self.assertEqual(meta.channels, 1)
        self.assertEqual(meta.sample_rate, 48000)
        self.assertEqual(meta.subtype, "PCM_16")

        # Verify original was NOT modified
        orig_meta = AudioProcessor.inspect_audio(self.valid_wav)
        self.assertEqual(orig_meta.channels, 2)
        self.assertEqual(orig_meta.sample_rate, 44100)

    def test_trim_audio_segment(self):
        trimmed_wav = self.dir_path / "trimmed_2s.wav"
        meta = AudioProcessor.trim_audio_segment(
            input_path=self.valid_wav,
            output_path=trimmed_wav,
            start_sec=1.0,
            end_sec=3.0,
            target_sr=48000
        )
        self.assertTrue(meta.is_valid)
        self.assertEqual(meta.channels, 1)
        self.assertEqual(meta.sample_rate, 48000)
        self.assertAlmostEqual(meta.duration_sec, 2.0, delta=0.05)

    def test_invalid_file_handling(self):
        non_existent = self.dir_path / "does_not_exist.wav"
        meta = AudioProcessor.inspect_audio(non_existent)
        self.assertFalse(meta.is_valid)

        empty_file = self.dir_path / "empty.wav"
        empty_file.touch()
        meta_empty = AudioProcessor.inspect_audio(empty_file)
        self.assertFalse(meta_empty.is_valid)

if __name__ == "__main__":
    unittest.main()
