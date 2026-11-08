"""Asynchronous single-worker FIFO generation queue."""
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from app.database.connection import DatabaseManager
from app.database.models import QueueJob

logger = logging.getLogger(__name__)

def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class GenerationTask:
    job_id: str
    job_type: str
    target_text: str
    voice_profile_id: Optional[str] = None
    voice_name: str = "Default Voice"
    language: str = "multilingual"
    reference_wav_path: Optional[str] = None
    prompt_wav_path: Optional[str] = None
    prompt_text: Optional[str] = None
    cfg_value: float = 2.0
    inference_timesteps: int = 10
    on_complete: Optional[Callable[[Dict], None]] = None
    on_error: Optional[Callable[[str], None]] = None
    executor: Optional[Callable[["GenerationTask"], Dict]] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)

class GenerationQueue:
    """
    Asynchronous single-inference FIFO queue ensuring only one CPU-heavy
    synthesis job runs at any given time, preventing memory spikes and system lockup.
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
        self._start_worker()

    @classmethod
    def get_instance(cls) -> "GenerationQueue":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _start_worker(self):
        """Starts background worker daemon."""
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="GenerationQueueWorker"
        )
        self._worker_thread.start()

    def submit_task(self, task: GenerationTask) -> QueueJob:
        """Submits a new generation task to the FIFO queue."""
        job = QueueJob(
            id=task.job_id,
            job_type=task.job_type,
            status="pending",
            progress=0.0,
            status_message="Queued for processing",
            created_at=utc_iso_now()
        )
        self._jobs_registry[task.job_id] = job
        self.db.create_job(job)
        self._task_queue.put(task)
        logger.info(f"Task {task.job_id} ({task.job_type}) enqueued. Queue depth: {self._task_queue.qsize()}")
        return job

    def cancel_job(self, job_id: str) -> bool:
        """Requests cancellation of a pending or active job."""
        if self._current_task and self._current_task.job_id == job_id:
            self._current_task.cancel_event.set()
            job = self._jobs_registry.get(job_id)
            if job:
                job.status = "cancelled"
                job.status_message = "Generation cancelled by user"
                job.completed_at = utc_iso_now()
                self.db.update_job(job)
            return True

        job = self._jobs_registry.get(job_id)
        if job and job.status == "pending":
            job.status = "cancelled"
            job.status_message = "Cancelled while in queue"
            job.completed_at = utc_iso_now()
            self.db.update_job(job)
            return True
        return False

    def get_job_status(self, job_id: str) -> Optional[QueueJob]:
        """Returns the current state of a registered job."""
        if job_id in self._jobs_registry:
            return self._jobs_registry[job_id]
        return self.db.get_job(job_id)

    def get_queue_stats(self) -> Dict:
        """Returns live statistics of queue activity."""
        return {
            "queue_depth": self._task_queue.qsize(),
            "is_processing": self._current_task is not None,
            "current_job_id": self._current_task.job_id if self._current_task else None
        }

    def _worker_loop(self):
        """Worker executing tasks strictly one-by-one."""
        while self._running:
            try:
                task = self._task_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            self._current_task = task
            job = self._jobs_registry.get(task.job_id)
            if not job:
                job = QueueJob(id=task.job_id, job_type=task.job_type)
                self._jobs_registry[task.job_id] = job

            # Check if task was cancelled while sitting in queue
            if task.cancel_event.is_set() or job.status == "cancelled":
                job.status = "cancelled"
                job.status_message = "Cancelled before processing began"
                job.completed_at = utc_iso_now()
                self.db.update_job(job)
                self._task_queue.task_done()
                self._current_task = None
                continue

            # Mark as processing
            job.status = "processing"
            job.progress = 0.1
            job.status_message = "Synthesizing audio on CPU..."
            job.started_at = utc_iso_now()
            self.db.update_job(job)

            try:
                if task.executor:
                    result = task.executor(task)
                else:
                    from app.services.generation_service import GenerationService
                    gen_service = GenerationService.get_instance()
                    result = gen_service.execute_generation_task(task)

                if task.cancel_event.is_set() or job.status == "cancelled":
                    job.status = "cancelled"
                    job.status_message = "Inference cancelled"
                else:
                    job.status = "completed"
                    job.progress = 1.0
                    job.status_message = f"Completed in {result.get('generation_time_sec', 0)}s"
                    job.generation_id = result.get("generation_id")
                    if task.on_complete:
                        task.on_complete(result)

            except Exception as e:
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
            finally:
                if not job.completed_at:
                    job.completed_at = utc_iso_now()
                self.db.update_job(job)
                self._task_queue.task_done()
                self._current_task = None

    def shutdown(self):
        """Stops the worker thread cleanly."""
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)
