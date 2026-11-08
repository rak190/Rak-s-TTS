"""
Long-Form Generation Orchestrator Service with Checkpoint & Resume.
Executes sentence-aware chunked speech synthesis, maintaining consistent speaker identity
across chunks, and stitching the final master audio in WAV and MP3.
"""
import gc
import json
import logging
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import soundfile as sf

from app.config import (
    LONGFORM_DIR,
    NATIVE_SAMPLE_RATE,
    DEFAULT_CFG_VALUE,
    DEFAULT_INFERENCE_TIMESTEPS
)
from app.database.connection import DatabaseManager
from app.database.models import (
    LongformJob,
    LongformChunkRecord,
    VoiceProfile
)
from app.engines.voxcpm_adapter import VoxCPM2Adapter
from app.utils.chunker import SentenceAwareChunker, TextChunk
from app.audio.stitcher import AudioStitcher

logger = logging.getLogger(__name__)

def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class LongformService:
    """
    Orchestrates long-form speech generation on mobile CPUs.
    Provides persistent chunk checkpoints, pause/resume capability,
    and consistent speaker timbre conditioning.
    """
    _instance: Optional["LongformService"] = None

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        tts_engine: Optional[VoxCPM2Adapter] = None
    ):
        self.db = db_manager or DatabaseManager.get_instance()
        self.engine = tts_engine or VoxCPM2Adapter()

    @classmethod
    def get_instance(cls) -> "LongformService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def prepare_job(
        self,
        title: str,
        text: str,
        voice_profile_id: Optional[str] = None,
        mode: str = "tts",
        language: str = "multilingual",
        target_chars: int = 110,
        max_chars: int = 150
    ) -> Tuple[Optional[LongformJob], str]:
        """
        Partitions long text into natural chunks and records initial job state
        and chunk records in SQLite before starting synthesis.
        """
        clean_title = title.strip() or f"Untitled Longform {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        text_clean = text.strip()
        if not text_clean:
            return None, "Input text cannot be empty."

        # Segment text using sentence-aware chunker
        chunks: List[TextChunk] = SentenceAwareChunker.chunk_text(
            text=text_clean,
            target_chars=target_chars,
            max_chars=max_chars
        )
        if not chunks:
            return None, "Failed to parse text into speech chunks."

        # Resolve voice profile metadata
        voice_name = "Default Voice"
        if voice_profile_id:
            prof = self.db.get_voice_profile(voice_profile_id)
            if prof:
                voice_name = prof.name
            else:
                return None, f"Voice profile '{voice_profile_id}' not found."

        job_id = f"lf_{uuid.uuid4().hex[:12]}"
        job_dir = LONGFORM_DIR / job_id
        (job_dir / "chunks").mkdir(parents=True, exist_ok=True)

        job = LongformJob(
            id=job_id,
            title=clean_title,
            voice_profile_id=voice_profile_id,
            voice_name=voice_name,
            mode=mode,
            language=language,
            total_chunks=len(chunks),
            completed_chunks=0,
            status="pending",
            created_at=utc_iso_now(),
            updated_at=utc_iso_now()
        )
        self.db.create_longform_job(job)

        chunk_records = []
        for c in chunks:
            chk_rec = LongformChunkRecord(
                id=f"chk_{job_id}_{c.index:03d}",
                job_id=job_id,
                chunk_index=c.index,
                text=c.text,
                char_count=c.char_count,
                pause_after_ms=c.pause_after_ms,
                status="pending",
                created_at=utc_iso_now()
            )
            chunk_records.append(chk_rec)

        self.db.create_longform_chunks(chunk_records)
        logger.info(f"Longform job {job_id} prepared with {len(chunk_records)} chunks.")
        return job, ""

    def execute_job(
        self,
        job_id: str,
        cancel_event = None,
        pause_event = None,
        on_progress: Optional[Callable[[Dict], None]] = None,
        cfg_value: float = DEFAULT_CFG_VALUE,
        inference_timesteps: int = DEFAULT_INFERENCE_TIMESTEPS
    ) -> Dict:
        """
        Executes synthesis for all pending chunks in the job.
        Skips already completed chunks (persistent checkpoint resumption).
        Cooperates with pause_event and cancel_event at chunk boundaries.
        """
        job = self.db.get_longform_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found.")

        job.status = "processing"
        job.updated_at = utc_iso_now()
        self.db.update_longform_job(job)

        job_dir = LONGFORM_DIR / job_id
        chunks_dir = job_dir / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)

        chunks = self.db.get_longform_chunks(job_id)

        # Resolve speaker reference paths for timbre consistency
        ref_wav_path: Optional[str] = None
        prompt_wav_path: Optional[str] = None
        prompt_text: Optional[str] = None

        if job.voice_profile_id:
            prof = self.db.get_voice_profile(job.voice_profile_id)
            if prof:
                ref_wav_path = prof.reference_segment_path
                prompt_wav_path = prof.reference_segment_path
                prompt_text = prof.transcript

        total_gen_time = 0.0

        for chk in chunks:
            # Check for cooperative cancellation
            if cancel_event and cancel_event.is_set():
                job.status = "cancelled"
                job.updated_at = utc_iso_now()
                self.db.update_longform_job(job)
                logger.info(f"Job {job_id} cancelled before chunk {chk.chunk_index}.")
                return {"status": "cancelled", "job_id": job_id, "completed_chunks": job.completed_chunks}

            # Check for cooperative pause
            if pause_event and pause_event.is_set():
                job.status = "paused"
                job.updated_at = utc_iso_now()
                self.db.update_longform_job(job)
                logger.info(f"Job {job_id} paused before chunk {chk.chunk_index}.")
                return {"status": "paused", "job_id": job_id, "completed_chunks": job.completed_chunks}

            chunk_out_wav = chunks_dir / f"chunk_{chk.chunk_index:03d}.wav"

            # Checkpoint check: if already completed and valid file exists on disk, reuse it!
            if chk.status == "completed" and chunk_out_wav.exists() and chunk_out_wav.stat().st_size > 100:
                logger.info(f"Chunk {chk.chunk_index} already completed ({chunk_out_wav.stat().st_size} bytes). Skipping (Checkpoint resumed).")
                continue

            # Mark chunk as processing
            chk.status = "processing"
            self.db.update_longform_chunk(chk)

            t0 = time.perf_counter()
            try:
                # Dispatch inference based on mode
                if job.mode == "cloning" and ref_wav_path:
                    wav_np, sr, elapsed = self.engine.generate_voice_cloning(
                        text=chk.text,
                        reference_wav_path=ref_wav_path,
                        cfg_value=cfg_value,
                        inference_timesteps=inference_timesteps
                    )
                elif job.mode == "ultimate_cloning" and prompt_wav_path and prompt_text:
                    wav_np, sr, elapsed = self.engine.generate_ultimate_cloning(
                        text=chk.text,
                        prompt_wav_path=prompt_wav_path,
                        prompt_text=prompt_text,
                        reference_wav_path=ref_wav_path,
                        cfg_value=cfg_value,
                        inference_timesteps=inference_timesteps
                    )
                else:
                    wav_np, sr, elapsed = self.engine.generate_tts(
                        text=chk.text,
                        cfg_value=cfg_value,
                        inference_timesteps=inference_timesteps
                    )

                # Save chunk WAV immediately
                sf.write(str(chunk_out_wav), wav_np, sr, subtype="PCM_16")
                chunk_duration = round(len(wav_np) / sr, 2)
                total_gen_time += elapsed

                # Update chunk record
                chk.status = "completed"
                chk.output_wav_path = str(chunk_out_wav)
                chk.duration_sec = chunk_duration
                chk.generation_time_sec = elapsed
                chk.completed_at = utc_iso_now()
                self.db.update_longform_chunk(chk)

                # Update job progress in database
                job.completed_chunks += 1
                job.total_generation_time_sec += elapsed
                job.updated_at = utc_iso_now()
                self.db.update_longform_job(job)

                # Memory hygiene
                del wav_np
                gc.collect()

                if on_progress:
                    on_progress({
                        "job_id": job_id,
                        "chunk_index": chk.chunk_index,
                        "completed_chunks": job.completed_chunks,
                        "total_chunks": job.total_chunks,
                        "progress": job.completed_chunks / job.total_chunks,
                        "chunk_duration": chunk_duration,
                        "chunk_elapsed": elapsed
                    })

                # Check if cancellation or pause was requested while synthesizing this chunk
                if cancel_event and cancel_event.is_set():
                    job.status = "cancelled"
                    job.updated_at = utc_iso_now()
                    self.db.update_longform_job(job)
                    logger.info(f"Job {job_id} cancelled after chunk {chk.chunk_index}.")
                    return {"status": "cancelled", "job_id": job_id, "completed_chunks": job.completed_chunks}

                if pause_event and pause_event.is_set():
                    job.status = "paused"
                    job.updated_at = utc_iso_now()
                    self.db.update_longform_job(job)
                    logger.info(f"Job {job_id} paused after chunk {chk.chunk_index}.")
                    return {"status": "paused", "job_id": job_id, "completed_chunks": job.completed_chunks}

            except Exception as e:
                logger.error(f"Error synthesizing chunk {chk.chunk_index}: {e}", exc_info=True)
                chk.status = "failed"
                chk.error_message = str(e)
                self.db.update_longform_chunk(chk)
                job.status = "failed"
                job.updated_at = utc_iso_now()
                self.db.update_longform_job(job)
                raise

        # -------------------------------------------------------------
        # All chunks completed: Stitch and Export
        # -------------------------------------------------------------
        updated_chunks = self.db.get_longform_chunks(job_id)
        valid_paths = [c.output_wav_path for c in updated_chunks if c.output_wav_path and Path(c.output_wav_path).exists()]
        pauses = [c.pause_after_ms for c in updated_chunks]

        if not valid_paths:
            job.status = "failed"
            self.db.update_longform_job(job)
            raise RuntimeError("No valid chunk audio files found for stitching.")

        stitched_audio, total_duration = AudioStitcher.stitch_chunks(
            chunk_paths=valid_paths,
            pauses_ms=pauses,
            target_sr=NATIVE_SAMPLE_RATE
        )

        full_wav_path = job_dir / "full_audio.wav"
        full_mp3_path = job_dir / "full_audio.mp3"

        AudioStitcher.export_wav(stitched_audio, full_wav_path)
        AudioStitcher.export_mp3(full_wav_path, full_mp3_path, bitrate="320k")

        job.status = "completed"
        job.output_wav_path = str(full_wav_path)
        job.output_mp3_path = str(full_mp3_path)
        job.total_duration_sec = total_duration
        job.updated_at = utc_iso_now()
        self.db.update_longform_job(job)

        del stitched_audio
        gc.collect()

        return {
            "job_id": job_id,
            "status": "completed",
            "total_chunks": job.total_chunks,
            "completed_chunks": job.completed_chunks,
            "output_wav_path": str(full_wav_path),
            "output_mp3_path": str(full_mp3_path),
            "total_duration_sec": total_duration,
            "total_generation_time_sec": round(job.total_generation_time_sec, 2),
            "rtf": round(job.total_generation_time_sec / total_duration, 2) if total_duration > 0 else 0.0
        }

    def resume_job(
        self,
        job_id: str,
        cancel_event = None,
        pause_event = None,
        on_progress: Optional[Callable[[Dict], None]] = None
    ) -> Dict:
        """Resumes execution of an unfinished or paused longform job from the next pending chunk."""
        return self.execute_job(
            job_id=job_id,
            cancel_event=cancel_event,
            pause_event=pause_event,
            on_progress=on_progress
        )

    def list_jobs(self, limit: int = 50, offset: int = 0) -> List[LongformJob]:
        return self.db.list_longform_jobs(limit=limit, offset=offset)

    def get_job_details(self, job_id: str) -> Tuple[Optional[LongformJob], List[LongformChunkRecord]]:
        job = self.db.get_longform_job(job_id)
        chunks = self.db.get_longform_chunks(job_id)
        return job, chunks

    def delete_job(self, job_id: str) -> bool:
        """Removes job files from disk and records from SQLite."""
        job_dir = LONGFORM_DIR / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return self.db.delete_longform_job(job_id)
