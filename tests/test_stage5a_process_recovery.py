"""
Stage 5A - Controlled OS Process-Restart Recovery and Checkpoint Resume Test.
Simulates a hard process stop after Chunk 0, restarts in an independent OS process,
recovers the job, verifies Chunk 0 is not regenerated, and completes the master audio.
"""
import json
import subprocess
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

SUBPROCESS_CODE = """
import sys
from pathlib import Path
import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(r"{project_root}")
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import DatabaseManager
from app.services.longform_service import LongformService
from app.engines.base import BaseTTSEngine
from app.config import NATIVE_SAMPLE_RATE

class FastMockEngine(BaseTTSEngine):
    def __init__(self):
        self.calls = 0
    def get_sample_rate(self):
        return NATIVE_SAMPLE_RATE
    def generate_tts(self, text, cfg_value=2.0, inference_timesteps=10):
        self.calls += 1
        t = np.linspace(0, 0.4, int(NATIVE_SAMPLE_RATE * 0.4), endpoint=False)
        wav = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        return wav, NATIVE_SAMPLE_RATE, 0.02
    def generate_voice_cloning(self, text, reference_wav_path, cfg_value=2.0, inference_timesteps=10):
        return self.generate_tts(text)
    def generate_ultimate_cloning(self, text, prompt_wav_path, prompt_text, reference_wav_path=None, cfg_value=2.0, inference_timesteps=10):
        return self.generate_tts(text)

mode = sys.argv[1]
job_id = sys.argv[2] if len(sys.argv) > 2 else ""

db = DatabaseManager.get_instance()
engine = FastMockEngine()
service = LongformService(db_manager=db, tts_engine=engine)

if mode == "step1_start_and_pause":
    text = "First test sentence. Second test sentence. Third test sentence."
    job, err = service.prepare_job(title="Process Recovery Audit Job", text=text, target_chars=22, max_chars=35)
    assert job is not None, err
    
    # Synthesize only Chunk 0 manually to simulate crash/pause
    chunks = db.get_longform_chunks(job.id)
    c0 = chunks[0]
    wav_np, sr, el = engine.generate_tts(c0.text)
    chk_path = PROJECT_ROOT / "storage" / "longform" / job.id / "chunks" / "chunk_000.wav"
    sf.write(str(chk_path), wav_np, sr, subtype="PCM_16")
    
    c0.status = "completed"
    c0.output_wav_path = str(chk_path)
    c0.duration_sec = 0.4
    c0.generation_time_sec = el
    db.update_longform_chunk(c0)
    
    job.completed_chunks = 1
    job.status = "paused"
    db.update_longform_job(job)
    
    print("JOB_CREATED:" + job.id)
    sys.exit(0)

elif mode == "step2_recover_and_finish":
    job = db.get_longform_job(job_id)
    assert job is not None, "Job not found: " + job_id
    assert job.status == "paused", f"Expected paused, got {{job.status}}"
    assert job.completed_chunks == 1
    
    chunks_before = db.get_longform_chunks(job_id)
    assert chunks_before[0].status == "completed"
    assert chunks_before[1].status == "pending"
    
    # Resume job
    res = service.resume_job(job_id)
    assert res["status"] == "completed"
    assert res["completed_chunks"] == 3
    # Engine should only have been called for Chunk 1 and Chunk 2 (2 calls, NOT 3)
    assert engine.calls == 2, f"Expected 2 calls, got {{engine.calls}}"
    
    # Verify master WAV & MP3
    wav_p = Path(res["output_wav_path"])
    mp3_p = Path(res["output_mp3_path"])
    assert wav_p.exists(), "Master WAV missing"
    assert mp3_p.exists(), "Master MP3 missing"
    
    info = sf.info(str(wav_p))
    assert info.samplerate == NATIVE_SAMPLE_RATE
    assert info.duration > 1.0
    
    print("RECOVERY_SUCCESS")
    # Clean up test job
    service.delete_job(job_id)
    sys.exit(0)
"""

class TestProcessRecovery(unittest.TestCase):
    def test_os_process_restart_recovery(self):
        """Executes a real two-process crash and resume recovery test."""
        python_bin = sys.executable
        formatted_code = SUBPROCESS_CODE.replace("{project_root}", str(PROJECT_ROOT).replace("\\", "\\\\"))

        # Step 1: Process A starts job, finishes 1 chunk, and terminates
        p1 = subprocess.run(
            [python_bin, "-c", formatted_code, "step1_start_and_pause"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        self.assertEqual(p1.returncode, 0, f"Process A failed: {p1.stderr}")
        
        job_id = ""
        for line in p1.stdout.splitlines():
            if line.startswith("JOB_CREATED:"):
                job_id = line.split(":", 1)[1].strip()
        self.assertTrue(len(job_id) > 0, "Failed to retrieve job_id from Process A")
        print(f"\n[Process A Exit] Created job {job_id} with 1 chunk completed. Process terminated.")

        # Step 2: Process B (completely new OS interpreter) recovers and finishes
        p2 = subprocess.run(
            [python_bin, "-c", formatted_code, "step2_recover_and_finish", job_id],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        self.assertEqual(p2.returncode, 0, f"Process B failed: {p2.stderr}")
        self.assertIn("RECOVERY_SUCCESS", p2.stdout)
        print(f"[Process B Exit] Job {job_id} recovered, Chunk 0 was skipped, remaining chunks synthesized, and master WAV/MP3 generated successfully.")

if __name__ == "__main__":
    unittest.main()
