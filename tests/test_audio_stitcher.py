"""
Unit tests for AudioStitcher and dual WAV/MP3 export (Phase 4D).
"""
import sys
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

from app.audio.stitcher import AudioStitcher
from app.config import TEMP_DIR, NATIVE_SAMPLE_RATE

class TestAudioStitcher(unittest.TestCase):

    def setUp(self):
        self.test_dir = TEMP_DIR / "stitcher_test"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # Generate two synthetic 1-second sine wave chunks
        sr = NATIVE_SAMPLE_RATE
        t = np.linspace(0, 1.0, sr, endpoint=False)
        self.chunk1_data = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
        self.chunk2_data = 0.5 * np.sin(2 * np.pi * 880 * t).astype(np.float32)

        self.c1_path = self.test_dir / "c1.wav"
        self.c2_path = self.test_dir / "c2.wav"
        sf.write(str(self.c1_path), self.chunk1_data, sr, subtype="PCM_16")
        sf.write(str(self.c2_path), self.chunk2_data, sr, subtype="PCM_16")

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_stitch_with_pause(self):
        """Verifies stitching chunks with pause between them."""
        # 1.0s + 0.3s pause + 1.0s = 2.3s total
        audio, dur = AudioStitcher.stitch_chunks(
            chunk_paths=[self.c1_path, self.c2_path],
            pauses_ms=[300],
            target_sr=NATIVE_SAMPLE_RATE
        )
        self.assertAlmostEqual(dur, 2.3, delta=0.05)
        # Peak normalization check (-1.0 dBFS = ~0.891)
        peak = np.max(np.abs(audio))
        self.assertAlmostEqual(peak, 0.891, delta=0.01)

    def test_02_export_wav(self):
        """Verifies export to uncompressed PCM_16 WAV."""
        audio, _ = AudioStitcher.stitch_chunks([self.c1_path, self.c2_path])
        out_wav = self.test_dir / "stitched.wav"
        res = AudioStitcher.export_wav(audio, out_wav)
        self.assertTrue(res.exists())
        info = sf.info(str(res))
        self.assertEqual(info.samplerate, NATIVE_SAMPLE_RATE)
        self.assertEqual(info.subtype, "PCM_16")

    def test_03_export_mp3_via_ffmpeg(self):
        """Verifies high-bitrate MP3 export."""
        audio, _ = AudioStitcher.stitch_chunks([self.c1_path, self.c2_path])
        out_wav = self.test_dir / "stitched.wav"
        AudioStitcher.export_wav(audio, out_wav)
        
        out_mp3 = self.test_dir / "stitched.mp3"
        res_mp3 = AudioStitcher.export_mp3(out_wav, out_mp3, bitrate="320k")
        self.assertTrue(res_mp3.exists())
        self.assertEqual(res_mp3.suffix.lower(), ".mp3")
        self.assertGreater(res_mp3.stat().st_size, 1000)

if __name__ == "__main__":
    unittest.main()
