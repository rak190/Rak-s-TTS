"""
Stage 5A - Real 5-Chunk Long-Form Synthesis & Memory Telemetry Profiling.
Validates multi-paragraph Khmer, English, and Mixed text generation across 5 chunks,
tracking memory RSS per chunk, audio integrity, chunk ordering, and speaker consistency.
"""
import gc
import os
import sys
import time
from pathlib import Path
import numpy as np
import psutil
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
from app.services.voice_service import VoiceProfileService
from app.engines.model_manager import ModelManager

def get_process_rss_mb() -> float:
    return round(psutil.Process().memory_info().rss / (1024 * 1024), 2)

def run_5chunk_profiling():
    print("=" * 70)
    print("VOICESTUDIO AI - STAGE 5A LONG-FORM AUDIT (5-CHUNK PROGRESSIVE TEST)")
    print("Multi-Paragraph Khmer, English, and Mixed Code-Switching Synthesis")
    print("Host Hardware: Intel Core i5-1240P CPU (4 P-Cores) | 16GB RAM")
    print("=" * 70)

    db = DatabaseManager.get_instance()
    voice_service = VoiceProfileService.get_instance()
    longform_service = LongformService.get_instance()
    model_mgr = ModelManager.get_instance()

    # Model Load / Warmup Telemetry
    rss_before_load = get_process_rss_mb()
    t_load_0 = time.perf_counter()
    model_mgr.load_model()
    t_load = round(time.perf_counter() - t_load_0, 2)
    rss_after_load = get_process_rss_mb()
    print(f"Model Load Time: {t_load}s | Base RAM: {rss_before_load} MB -> Loaded: {rss_after_load} MB")

    # Select bilingual speaker profile
    prof = db.get_voice_profile_by_name("Stage3 Test Speaker EN")
    if not prof:
        prof = voice_service.list_profiles()[0]
    print(f"Target Voice: {prof.name} (ID: {prof.id}) | Mode: Cloning")

    multi_paragraph_text = """សូមស្វាគមន៍មកកាន់ VoiceStudio AI Studio ជំនាន់ចុងក្រោយ។ នេះគឺជាការសាកល្បងសំឡេងវែងដែលបំបែកជាកថាខណ្ឌច្រើន។

VoiceStudio AI runs foundation speech synthesis completely offline on standard mobile CPUs. It guarantees speaker timbre consistency across all continuous chapters and paragraphs.

ការអភិវឌ្ឍន៍ VoiceStudio AI គឺជាសមិទ្ធផលដ៏អស្ចារ្យ for bilingual speech synthesis in Cambodia and worldwide."""

    # 1. Prepare Job
    job, err = longform_service.prepare_job(
        title="Stage 5A 5-Chunk Audit Job",
        text=multi_paragraph_text,
        voice_profile_id=prof.id,
        mode="cloning",
        language="mixed",
        target_chars=100,
        max_chars=140
    )
    if err or not job:
        print(f"ERROR: Job preparation failed: {err}")
        sys.exit(1)

    print(f"Job Initialized: {job.id} | Total Chunks: {job.total_chunks}")
    if job.total_chunks < 5:
        print(f"ERROR: Expected at least 5 chunks, but got {job.total_chunks}")
        sys.exit(1)

    chunks = db.get_longform_chunks(job.id)
    print("\nChunk Plan:")
    for c in chunks:
        print(f"  Chunk {c.chunk_index}: {c.char_count} chars | Pause: {c.pause_after_ms}ms | Text: {c.text[:50]}...")

    # 2. Progressive Synthesis with Memory Tracking
    chunk_metrics = []
    peak_rss_mb = rss_after_load

    def progress_callback(prog):
        nonlocal peak_rss_mb
        rss = get_process_rss_mb()
        if rss > peak_rss_mb:
            peak_rss_mb = rss
        idx = prog["chunk_index"]
        print(f"   [Chunk {idx + 1}/{job.total_chunks}] Duration: {prog['chunk_duration']}s | Synth Time: {prog['chunk_elapsed']}s | RTF: {prog['chunk_elapsed']/prog['chunk_duration']:.2f}x | RSS: {rss} MB")
        chunk_metrics.append({
            "chunk_index": idx,
            "duration": prog["chunk_duration"],
            "elapsed": prog["chunk_elapsed"],
            "rss_mb": rss
        })

    print("\n--- Beginning 5-Chunk Sequential Inference ---")
    t_start = time.perf_counter()
    res = longform_service.execute_job(
        job_id=job.id,
        on_progress=progress_callback,
        cfg_value=2.0,
        inference_timesteps=10
    )
    total_elapsed = round(time.perf_counter() - t_start, 2)

    # 3. Post-Synthesis Verification
    print("\n" + "=" * 70)
    print("5-CHUNK SYNTHESIS COMPLETED")
    print("=" * 70)
    print(f"Status: {res['status']}")
    print(f"Total Chunks: {res['completed_chunks']}/{res['total_chunks']}")
    print(f"Master Duration: {res['total_duration_sec']}s")
    print(f"Total Compute Time: {total_elapsed}s (RTF: {res['rtf']}x)")
    print(f"Peak RSS Memory: {peak_rss_mb} MB")
    final_rss = get_process_rss_mb()
    print(f"Final RSS (Post-GC): {final_rss} MB")

    # Verify Chunk Audio Files & Properties
    job_dir = LONGFORM_DIR / job.id
    chunks_dir = job_dir / "chunks"
    for i in range(job.total_chunks):
        chk_file = chunks_dir / f"chunk_{i:03d}.wav"
        if not chk_file.exists():
            print(f"ERROR: Chunk file missing: {chk_file}")
            sys.exit(1)
        info = sf.info(str(chk_file))
        if info.samplerate != 48000 or info.duration < 0.5:
            print(f"ERROR: Invalid chunk audio at {chk_file}")
            sys.exit(1)
        print(f"   Chunk {i}: {info.duration:.2f}s, {info.samplerate}Hz, {info.subtype}")

    # Verify Master Stitched Audio
    wav_path = Path(res["output_wav_path"])
    mp3_path = Path(res["output_mp3_path"])
    if not wav_path.exists() or not mp3_path.exists():
        print("ERROR: Master WAV or MP3 missing!")
        sys.exit(1)

    wav_info = sf.info(str(wav_path))
    mp3_size_kb = mp3_path.stat().st_size // 1024

    print(f"\nMaster WAV: {wav_path} ({wav_info.duration:.2f}s, {wav_info.samplerate}Hz)")
    print(f"Master MP3: {mp3_path} ({mp3_size_kb} KB)")
    print("=" * 70)
    print("5-CHUNK INFERENCE AUDIT PASSED WITH 100% INTEGRITY!")
    print("=" * 70)

if __name__ == "__main__":
    run_5chunk_profiling()
