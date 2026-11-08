"""
Asynchronous single-worker FIFO generation queue with persistent SQLite state,
cooperative pause-after-chunk, crash/restart recovery, pre-flight safety checks,
and Windows sleep inhibition for overnight batch generation.
"""
import logging
import os
import queue
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.config import BASE_DIR, LONGFORM_DIR
from app.database.connection import DatabaseManager
from app.database.models import QueueJob
from app.utils.power_manager import WindowsPowerManager

logger = logging.getLogger(__name__)

def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class GenerationTask:
    job_id: str
    job_type: str = "tts"  # 'tts', 'cloning', 'ultimate_cloning', 'longform'
    target_text: str = ""
    title: str = "Untitled Job"
    voice_profile_id: Optional[str] = None
    voice_name: str = "Default Voice"
    language: str = "multilingual"
    mode: str = "tts"
    reference_wav_path: Optional[str] = None
    prompt_wav_path: Optional[str] = None
    prompt_text: Optional[str] = None
    cfg_value: float = 2.0
    inference_timesteps: int = 10
    total_chunks: int = 1
    completed_chunks: int = 0
    priority: int = 100
    on_complete: Optional[Callable[[Dict], None]] = None
    on_error: Optional[Callable[[str], None]] = None
    on_progress: Optional[Callable[[Dict], None]] = None
    executor: Optional[Callable[["GenerationTask"], Dict]] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    result: Optional[Dict] = None
    error: Optional[str] = None

class GenerationQueue:
    """
    Persistent single-inference FIFO batch queue.
    Guarantees concurrency = 1 to preserve CPU/RAM stability,
    checkpoints chunk progress, survives process crashes/restarts,
    and supports safe pause-after-chunk and Windows sleep prevention.
    """
    _instance: Optional["GenerationQueue"] = None
    _lock = threading.Lock()

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self._task_queue: queue.Queue[GenerationTask] = queue.Queue()
        self._jobs_registry: Dict[str, QueueJob] = {}
        self._current_task: Optional[GenerationTask] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._running = True
        self._pause_requested = threading.Event()
        self._post_completion_action = "none"
        self._power_mgr = WindowsPowerManager.get_instance()

        # Perform startup recovery and load any queued jobs from SQLite
        self.initialize_on_startup()
        self._start_worker()

    @classmethod
    def get_instance(cls) -> "GenerationQueue":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls):
        with cls._lock:
            if cls._instance is not None:
                try:
                    cls._instance.shutdown()
                except Exception:
                    pass
                cls._instance = None

    def _start_worker(self):
        """Starts background worker daemon."""
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="PersistentBatchQueueWorker"
        )
        self._worker_thread.start()

    def initialize_on_startup(self):
        """
        Detects unfinished/interrupted jobs from previous application runs,
        reconciles valid chunk checkpoints, and restores pending jobs.
        """
        try:
            # 1. Mark leftover 'processing' jobs as 'interrupted'
            interrupted_count = self.db.mark_interrupted_jobs_on_startup()
            if interrupted_count > 0:
                logger.warning(f"Startup recovery: Found and flagged {interrupted_count} interrupted jobs.")

            # 2. Reconcile chunks for interrupted longform jobs
            all_interrupted = self.db.list_batch_jobs(status_filter="interrupted")
            for job in all_interrupted:
                if job.job_type == "longform":
                    chunks = self.db.get_longform_chunks(job.id)
                    chunks_dir = LONGFORM_DIR / job.id / "chunks"
                    valid_chunks = 0
                    for c in chunks:
                        chk_file = chunks_dir / f"chunk_{c.chunk_index:03d}.wav"
                        if chk_file.exists() and chk_file.stat().st_size > 100:
                            valid_chunks += 1
                        else:
                            break
                    job.completed_chunks = valid_chunks
                    job.progress = round(valid_chunks / max(job.total_chunks, 1), 3)
                    job.status_message = f"Interrupted at chunk {valid_chunks}/{job.total_chunks} (ready to resume)"
                    self.db.update_job(job)

            # 3. Restore any jobs that were queued/pending when server stopped
            pending_jobs = self.db.list_pending_jobs()
            for p_job in pending_jobs:
                task = self._job_record_to_task(p_job)
                self._jobs_registry[task.job_id] = p_job
                self._task_queue.put(task)
            if pending_jobs:
                logger.info(f"Startup recovery: Reloaded {len(pending_jobs)} queued jobs into execution queue.")

        except Exception as e:
            logger.error(f"Error during startup queue recovery: {e}", exc_info=True)

    def _job_record_to_task(self, job: QueueJob) -> GenerationTask:
        """Converts a database QueueJob into a runnable GenerationTask."""
        ref_path = None
        prompt_path = None
        prompt_txt = None
        if job.voice_profile_id:
            prof = self.db.get_voice_profile(job.voice_profile_id)
            if prof:
                ref_path = prof.reference_segment_path
                prompt_path = prof.reference_segment_path
                prompt_txt = prof.transcript

        return GenerationTask(
            job_id=job.id,
            job_type=job.job_type,
            target_text=job.target_text,
            title=job.title,
            voice_profile_id=job.voice_profile_id,
            voice_name=job.voice_name,
            language=job.language,
            mode=job.mode,
            reference_wav_path=ref_path,
            prompt_wav_path=prompt_path,
            prompt_text=prompt_txt,
            cfg_value=job.cfg_value,
            inference_timesteps=job.inference_timesteps,
            total_chunks=job.total_chunks,
            completed_chunks=job.completed_chunks,
            priority=job.priority
        )

    def check_preflight_safety(self, task: GenerationTask) -> Tuple[bool, str]:
        """Validates disk space, reference audio files, and parameters before starting inference."""
        # 1. Disk space check (require >= 500 MB)
        try:
            total, used, free = shutil.disk_usage(str(BASE_DIR))
            free_mb = free / (1024 * 1024)
            if free_mb < 500:
                return False, f"Insufficient disk space: {int(free_mb)} MB remaining on drive (500 MB required)."
        except Exception as e:
            logger.debug(f"Disk check notice: {e}")

        # 2. Reference audio check for cloning
        if task.job_type in ("cloning", "ultimate_cloning") or task.mode in ("cloning", "ultimate_cloning"):
            if not task.reference_wav_path or not Path(task.reference_wav_path).exists():
                return False, f"Voice reference audio not found on disk: {task.reference_wav_path}"

        # 3. Transcript check for ultimate cloning
        if task.job_type == "ultimate_cloning" or task.mode == "ultimate_cloning":
            if not task.prompt_text or not task.prompt_text.strip():
                return False, "Ultimate cloning requires a reference transcript."

        return True, "Pre-flight checks passed."

    def submit_task(self, task: GenerationTask) -> QueueJob:
        """Submits a new generation task to the persistent FIFO queue."""
        job = QueueJob(
            id=task.job_id,
            job_type=task.job_type,
            status="queued",
            progress=0.0,
            status_message="Queued for processing",
            title=task.title or "Untitled Job",
            target_text=task.target_text,
            voice_profile_id=task.voice_profile_id,
            voice_name=task.voice_name,
            language=task.language,
            mode=task.mode or task.job_type,
            cfg_value=task.cfg_value,
            inference_timesteps=task.inference_timesteps,
            total_chunks=task.total_chunks,
            completed_chunks=task.completed_chunks,
            priority=task.priority,
            created_at=utc_iso_now(),
            updated_at=utc_iso_now()
        )
        self._jobs_registry[task.job_id] = job
        self.db.create_job(job)
        self._task_queue.put(task)
        logger.info(f"Task {task.job_id} ('{task.title}', {task.job_type}) enqueued. Queue depth: {self._task_queue.qsize()}")
        return job

    def pause_queue(self) -> bool:
        """
        Requests the queue to pause.
        The currently synthesizing chunk will complete cleanly and checkpoint to disk,
        and then the worker will halt without starting the next chunk.
        """
        with self._lock:
            self._pause_requested.set()
            if self._current_task:
                job = self.get_job_status(self._current_task.job_id)
                if job:
                    job.status_message = "Pausing after current chunk completes..."
                    self.db.update_job(job)
            logger.info("Pause requested: queue will pause at next chunk boundary.")
            return True

    def resume_queue(self) -> bool:
        """Clears pause flag and resumes processing queued and paused jobs."""
        with self._lock:
            was_paused = self._pause_requested.is_set()
            self._pause_requested.clear()

            # Find any actively paused jobs that are not in the memory queue
            active_ids = {self._current_task.job_id} if self._current_task else set()
            queued_ids = {t.job_id for t in list(self._task_queue.queue)}

            paused_jobs = self.db.list_batch_jobs(status_filter="paused")

            for p_job in paused_jobs:
                if p_job.id not in active_ids and p_job.id not in queued_ids:
                    p_job.status = "queued"
                    p_job.status_message = "Resumed — queued for processing"
                    p_job.updated_at = utc_iso_now()
                    self.db.update_job(p_job)
                    task = self._job_record_to_task(p_job)
                    self._jobs_registry[task.job_id] = p_job
                    self._task_queue.put(task)

            logger.info("Queue resumed.")
            return True

    def is_paused(self) -> bool:
        return self._pause_requested.is_set()

    def cancel_job(self, job_id: str) -> bool:
        """Requests cancellation of a pending or active job."""
        with self._lock:
            # Active job cancellation
            if self._current_task and self._current_task.job_id == job_id:
                self._current_task.cancel_event.set()
                job = self.get_job_status(job_id)
                if job:
                    job.status = "cancelled"
                    job.status_message = "Cancellation requested (stopping at chunk boundary)"
                    job.completed_at = utc_iso_now()
                    job.updated_at = utc_iso_now()
                    self.db.update_job(job)
                logger.info(f"Cancellation requested for active job {job_id}")
                return True

            # Pending job cancellation
            job = self.get_job_status(job_id)
            if job and job.status in ("queued", "pending", "paused", "interrupted"):
                for t in list(self._task_queue.queue):
                    if t.job_id == job_id:
                        t.cancel_event.set()
                        break
                job.status = "cancelled"
                job.status_message = "Cancelled before processing began"
                job.completed_at = utc_iso_now()
                job.updated_at = utc_iso_now()
                self.db.update_job(job)
                logger.info(f"Job {job_id} cancelled.")
                return True

        return False

    def retry_job(self, job_id: str) -> Tuple[bool, str]:
        """Retries a failed or cancelled job with retry loop limit."""
        with self._lock:
            job = self.db.get_job(job_id)
            if not job:
                return False, f"Job {job_id} not found."

            if job.retry_count >= 3:
                return False, f"Job {job_id} has reached maximum retry limit (3)."

            job.status = "queued"
            job.retry_count += 1
            job.error_message = ""
            job.status_message = f"Queued for retry #{job.retry_count}"
            job.completed_at = None
            job.updated_at = utc_iso_now()
            self.db.update_job(job)

            task = self._job_record_to_task(job)
            self._jobs_registry[task.job_id] = job
            self._task_queue.put(task)
            logger.info(f"Job {job_id} retried (attempt #{job.retry_count}).")
            return True, f"Job queued for retry #{job.retry_count}."

    def remove_job(self, job_id: str) -> bool:
        """Removes a finished job from the queue and database."""
        with self._lock:
            job = self.get_job_status(job_id)
            if not job:
                return False
            if job.status == "processing":
                return False  # Cannot remove active job without cancelling first
            self._jobs_registry.pop(job_id, None)
            return self.db.delete_job(job_id)

    def set_post_completion_action(self, action: str):
        self._post_completion_action = action

    def get_post_completion_action(self) -> str:
        return self._post_completion_action

    def get_job_position(self, job_id: str) -> Optional[Tuple[int, int]]:
        """Returns (1-based position, total_pending) if job is in pending queue, else None."""
        with self._lock:
            pending_ids = [t.job_id for t in list(self._task_queue.queue)]
            if job_id in pending_ids:
                return pending_ids.index(job_id) + 1, len(pending_ids)
        return None

    def get_job_status(self, job_id: str) -> Optional[QueueJob]:
        """Returns the current state of a registered job."""
        if job_id in self._jobs_registry:
            return self._jobs_registry[job_id]
        return self.db.get_job(job_id)

    def get_job_display_status(self, job_id: str) -> Dict[str, Any]:
        """Returns structured display status with formatted badge and elapsed time."""
        job = self.get_job_status(job_id)
        if not job:
            return {
                "status": "unknown",
                "badge": "⚪ Unknown",
                "message": "Job not found",
                "elapsed_sec": 0.0,
                "progress": 0.0,
                "result": None
            }

        elapsed_sec = 0.0
        if job.started_at:
            try:
                start_dt = datetime.fromisoformat(job.started_at)
                end_dt = datetime.fromisoformat(job.completed_at) if job.completed_at else datetime.now(timezone.utc)
                elapsed_sec = round((end_dt - start_dt).total_seconds(), 1)
            except Exception:
                pass

        pos = self.get_job_position(job_id)
        if job.status in ("queued", "pending"):
            pos_str = f" (Position {pos[0]} of {pos[1]})" if pos else ""
            badge = f"⏳ Queued{pos_str}"
        elif job.status == "processing":
            pct = int(job.progress * 100)
            badge = f"⚙️ Processing ({pct}% • {int(elapsed_sec)}s)"
        elif job.status == "paused":
            badge = f"⏸️ Paused (Chunk {job.completed_chunks}/{job.total_chunks})"
        elif job.status == "interrupted":
            badge = f"⚠️ Interrupted (Chunk {job.completed_chunks}/{job.total_chunks})"
        elif job.status == "completed":
            badge = f"✅ Completed ({elapsed_sec}s)"
        elif job.status == "failed":
            badge = "❌ Failed"
        elif job.status == "cancelled":
            badge = "🚫 Cancelled"
        else:
            badge = f"ℹ️ {job.status.capitalize()}"

        return {
            "status": job.status,
            "badge": badge,
            "message": job.status_message,
            "elapsed_sec": elapsed_sec,
            "progress": job.progress,
            "generation_id": job.generation_id,
            "error_message": job.error_message,
            "total_chunks": job.total_chunks,
            "completed_chunks": job.completed_chunks,
            "output_wav_path": job.output_wav_path,
            "output_mp3_path": job.output_mp3_path,
            "result": getattr(job, "_result", None)
        }

    def get_queue_stats(self) -> Dict[str, Any]:
        """Returns comprehensive live statistics of queue activity and power state."""
        curr_id = self._current_task.job_id if self._current_task else None
        curr_title = self._current_task.title if self._current_task else ""
        curr_chunks = (self._current_task.completed_chunks, self._current_task.total_chunks) if self._current_task else (0, 0)

        return {
            "queue_depth": self._task_queue.qsize(),
            "is_processing": self._current_task is not None,
            "is_paused": self._pause_requested.is_set(),
            "current_job_id": curr_id,
            "current_job_title": curr_title,
            "current_chunk": curr_chunks[0],
            "total_chunks": curr_chunks[1],
            "sleep_inhibited": self._power_mgr.is_sleep_inhibited,
            "post_completion_action": self._post_completion_action
        }

    def _worker_loop(self):
        """Worker executing batch tasks strictly one-by-one with CPU safety."""
        while self._running:
            # If pause is requested, sleep briefly and do not pull tasks
            if self._pause_requested.is_set():
                time.sleep(0.5)
                continue

            try:
                task = self._task_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            # If queue was paused while waiting on get(), put task back and wait
            if self._pause_requested.is_set():
                self._task_queue.put(task)
                self._task_queue.task_done()
                time.sleep(0.2)
                continue

            self._current_task = task
            job = self.get_job_status(task.job_id)
            if not job:
                job = QueueJob(id=task.job_id, job_type=task.job_type, title=task.title)
                self._jobs_registry[task.job_id] = job

            # Check if task was cancelled while sitting in queue
            if task.cancel_event.is_set() or job.status == "cancelled":
                job.status = "cancelled"
                job.status_message = "Cancelled before processing began"
                job.completed_at = utc_iso_now()
                job.updated_at = utc_iso_now()
                self.db.update_job(job)
                self._task_queue.task_done()
                self._current_task = None
                continue

            # Run Pre-Flight Safety Checks
            ok, preflight_msg = self.check_preflight_safety(task)
            if not ok:
                logger.error(f"Pre-flight safety check failed for {task.job_id}: {preflight_msg}")
                job.status = "failed"
                job.error_message = preflight_msg
                job.status_message = f"Pre-flight failure: {preflight_msg}"
                job.completed_at = utc_iso_now()
                job.updated_at = utc_iso_now()
                self.db.update_job(job)
                if task.on_error:
                    task.on_error(preflight_msg)
                self._task_queue.task_done()
                self._current_task = None
                continue

            # Inhibit Windows sleep during active computation
            self._power_mgr.inhibit_sleep(f"Batch job {task.job_id} ({task.title})")

            # Mark as processing
            job.status = "processing"
            job.status_message = "Synthesizing audio on CPU..."
            job.started_at = utc_iso_now()
            job.updated_at = utc_iso_now()
            self.db.update_job(job)

            try:
                if task.executor:
                    result = task.executor(task)
                elif task.job_type == "longform":
                    from app.services.longform_service import LongformService
                    lf_service = LongformService.get_instance()

                    def progress_cb(info):
                        task.completed_chunks = info.get("completed_chunks", 0)
                        job.completed_chunks = task.completed_chunks
                        job.progress = round(info.get("progress", 0.0), 3)
                        job.status_message = f"Synthesizing chunk {task.completed_chunks}/{task.total_chunks}..."
                        job.updated_at = utc_iso_now()
                        self.db.update_job(job)
                        if task.on_progress:
                            task.on_progress(info)

                    result = lf_service.execute_job(
                        job_id=task.job_id,
                        cancel_event=task.cancel_event,
                        pause_event=self._pause_requested,
                        on_progress=progress_cb,
                        cfg_value=task.cfg_value,
                        inference_timesteps=task.inference_timesteps
                    )
                else:
                    from app.services.generation_service import GenerationService
                    gen_service = GenerationService.get_instance()
                    result = gen_service.execute_generation_task(task)

                # Inspect execution outcome
                res_status = result.get("status") if isinstance(result, dict) else None

                if task.cancel_event.is_set() or job.status == "cancelled" or res_status == "cancelled":
                    job.status = "cancelled"
                    job.status_message = "Inference cancelled at chunk boundary"
                    job.completed_at = utc_iso_now()
                elif self._pause_requested.is_set() or res_status == "paused":
                    job.status = "paused"
                    job.status_message = f"Paused after chunk {job.completed_chunks} of {job.total_chunks}"
                else:
                    task.result = result
                    job._result = result
                    job.status = "completed"
                    job.progress = 1.0
                    job.completed_chunks = job.total_chunks
                    job.output_wav_path = result.get("output_wav_path") or result.get("output_path")
                    job.output_mp3_path = result.get("output_mp3_path")
                    job.generation_id = result.get("generation_id")
                    gen_time = result.get("generation_time_sec") or result.get("total_generation_time_sec", 0)
                    job.status_message = f"Completed in {gen_time}s"
                    job.completed_at = utc_iso_now()
                    if task.on_complete:
                        task.on_complete(result)

            except Exception as e:
                task.error = str(e)
                if task.cancel_event.is_set() or job.status == "cancelled":
                    job.status = "cancelled"
                    job.status_message = "Inference cancelled"
                else:
                    logger.exception(f"Job {task.job_id} failed: {e}")
                    job.status = "failed"
                    job.error_message = str(e)
                    job.status_message = f"Failed: {e}"
                    if task.on_error:
                        task.on_error(str(e))
                job.completed_at = utc_iso_now()

            finally:
                job.updated_at = utc_iso_now()
                self.db.update_job(job)
                self._task_queue.task_done()
                self._current_task = None

                # If queue is now idle (no pending items and no active task)
                if self._task_queue.empty() and self._current_task is None:
                    self._power_mgr.restore_sleep()
                    if self._post_completion_action and self._post_completion_action != "none":
                        logger.info(f"All batch jobs completed. Executing post-completion action: {self._post_completion_action}")
                        self._power_mgr.execute_post_completion_action(self._post_completion_action)

    def shutdown(self):
        """Stops the worker thread and restores Windows power state."""
        self._running = False
        self._power_mgr.restore_sleep()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)
