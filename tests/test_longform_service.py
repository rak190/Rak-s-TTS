"""
Unit tests for LongformService orchestration and checkpoint resume (Phase 4C).
"""
import sys
import threading
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
from app.engines.base import BaseTTSEngine

class MockTTSEngine(BaseTTSEngine):
    """Fast mock TTS engine generating 0.5s audio per chunk for testing."""
    def __init__(self):
        self.call_count = 0
        self.processed_texts = []

    def get_sample_rate(self) -> int:
        return NATIVE_SAMPLE_RATE

    def generate_tts(self, text, cfg_value=2.0, inference_timesteps=10):
        self.call_count += 1
        self.processed_texts.append(text)
        sr = NATIVE_SAMPLE_RATE
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        wav = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        return wav, sr, 0.05

    def generate_voice_cloning(self, text, reference_wav_path, cfg_value=2.0, inference_timesteps=10):
        return self.generate_tts(text)

    def generate_ultimate_cloning(self, text, prompt_wav_path, prompt_text, reference_wav_path=None, cfg_value=2.0, inference_timesteps=10):
        return self.generate_tts(text)

class TestLongformService(unittest.TestCase):

    def setUp(self):
        self.db = DatabaseManager.get_instance()
        self.mock_engine = MockTTSEngine()
        self.service = LongformService(db_manager=self.db, tts_engine=self.mock_engine)

    def test_01_prepare_job(self):
        """Verifies preparing a job segments text into multiple chunk records in SQLite."""
        text = (
            "Sentence one of the longform text. "
            "Sentence two follows immediately. "
            "Sentence three concludes the paragraph."
        )
        job, err = self.service.prepare_job(
            title="Unit Test Longform",
            text=text,
            target_chars=40,
            max_chars=60
        )
        self.assertIsNotNone(job)
        self.assertEqual(err, "")
        self.assertGreaterEqual(job.total_chunks, 2)
        self.assertEqual(job.completed_chunks, 0)
        self.assertEqual(job.status, "pending")

        # Verify DB records
        retrieved_job, chunks = self.service.get_job_details(job.id)
        self.assertIsNotNone(retrieved_job)
        self.assertEqual(len(chunks), job.total_chunks)
        for c in chunks:
            self.assertEqual(c.status, "pending")

        # Cleanup
        self.service.delete_job(job.id)

    def test_02_execute_and_checkpoint_resume(self):
        """Verifies multi-chunk execution, checkpoint persistence, and resume capability."""
        text = "First chunk. Second chunk. Third chunk."
        job, _ = self.service.prepare_job(
            title="Resume Test",
            text=text,
            target_chars=20,
            max_chars=35
        )
        self.assertIsNotNone(job)
        self.assertGreaterEqual(job.total_chunks, 2)

        # Simulate pausing after first chunk via cancel_event
        cancel_ev = threading.Event()
        progress_calls = []

        def on_prog(p):
            progress_calls.append(p)
            if p["completed_chunks"] == 1:
                cancel_ev.set()

        res1 = self.service.execute_job(
            job_id=job.id,
            cancel_event=cancel_ev,
            on_progress=on_prog
        )
        self.assertEqual(res1["status"], "paused")
        self.assertEqual(res1["completed_chunks"], 1)

        # Verify state in DB
        paused_job, chunks = self.service.get_job_details(job.id)
        self.assertEqual(paused_job.status, "paused")
        self.assertEqual(paused_job.completed_chunks, 1)
        self.assertEqual(chunks[0].status, "completed")
        self.assertEqual(chunks[1].status, "pending")

        # Now resume the job without cancel_event
        call_count_before = self.mock_engine.call_count
        res2 = self.service.resume_job(job_id=job.id)
        
        self.assertEqual(res2["status"], "completed")
        self.assertEqual(res2["completed_chunks"], job.total_chunks)
        self.assertTrue(Path(res2["output_wav_path"]).exists())
        self.assertTrue(Path(res2["output_mp3_path"]).exists())

        # Checkpoint check: Chunk 0 was NOT re-synthesized!
        additional_calls = self.mock_engine.call_count - call_count_before
        self.assertEqual(additional_calls, job.total_chunks - 1)

        # Verify full stitched audio properties
        info = sf.info(res2["output_wav_path"])
        self.assertEqual(info.samplerate, NATIVE_SAMPLE_RATE)
        self.assertGreater(info.duration, 1.0)

        # Cleanup
        self.service.delete_job(job.id)

if __name__ == "__main__":
    unittest.main()
