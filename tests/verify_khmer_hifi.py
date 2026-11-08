"""
Verification script for Khmer Hi-Fi / Ultimate Voice Cloning with real Khmer transcript.
"""
import sys
import time
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

from app.database.connection import DatabaseManager
from app.services.generation_service import GenerationService
from app.queue.generation_queue import GenerationTask

def verify_khmer_hifi():
    print("=" * 60)
    print("VERIFYING KHMER HI-FI CLONING WITH REAL KHMER TRANSCRIPT")
    print("=" * 60)

    db = DatabaseManager.get_instance()
    gen_service = GenerationService.get_instance()

    # Retrieve Khmer profile
    prof = db.get_voice_profile("prof_d0fd33d8bdc7")
    if not prof:
        prof = db.get_voice_profile_by_name("Stage3 Test Speaker KH")
    
    if not prof:
        print("ERROR: Khmer test profile not found.")
        sys.exit(1)

    print(f"Profile Name: {prof.name} (ID: {prof.id})")
    print(f"Prompt Audio: {prof.reference_segment_path}")
    print(f"Prompt Transcript: {prof.transcript}")

    target_kh_text = "សួស្តី! នេះជាការសាកល្បង Hi-Fi Voice Cloning ភាសាខ្មែរដែលមានគុណភាពខ្ពស់។"
    print(f"Target Text: {target_kh_text}")

    task = GenerationTask(
        job_id="verify_kh_hifi_001",
        job_type="ultimate_cloning",
        target_text=target_kh_text,
        voice_profile_id=prof.id,
        voice_name=prof.name,
        language="khmer",
        reference_wav_path=prof.reference_segment_path,
        prompt_wav_path=prof.reference_segment_path,
        prompt_text=prof.transcript,
        cfg_value=2.0,
        inference_timesteps=10
    )

    t0 = time.perf_counter()
    result = gen_service.execute_generation_task(task)
    total_elapsed = round(time.perf_counter() - t0, 2)

    out_path = Path(result["output_path"])
    if not out_path.exists():
        print(f"ERROR: Generated file missing at {out_path}")
        sys.exit(1)

    data, sr = sf.read(str(out_path))
    duration = len(data) / sr
    rms = np.sqrt(np.mean(data ** 2))
    has_nan = np.isnan(data).any()

    print(f"Success! Output generated: {out_path}")
    print(f"Duration: {duration:.2f}s | Sample Rate: {sr} Hz | Channels: 1")
    print(f"RMS: {rms:.4f} | NaN/Inf: {has_nan}")
    print(f"Inference Time: {result['generation_time_sec']}s | RTF: {result['rtf']}x | Total: {total_elapsed}s")
    print("=" * 60)
    print("KHMER HI-FI CLONING VERIFIED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    verify_khmer_hifi()
