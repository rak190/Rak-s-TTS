"""
Batch Speech Generation Orchestration Service.
Coordinates multi-script submissions, single-shot vs longform dispatch,
queue lifecycle controls, and status summaries for the UI.
"""
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.database.connection import DatabaseManager
from app.database.models import QueueJob
from app.queue.generation_queue import GenerationQueue, GenerationTask
from app.services.longform_service import LongformService
from app.services.voice_service import VoiceProfileService
from app.utils.text_processor import TextProcessor

logger = logging.getLogger(__name__)

class BatchService:
    """
    High-level orchestrator for batch speech synthesis jobs.
    Allows non-blocking queueing of multi-script jobs (Khmer, English, Mixed, Long-form).
    """
    _instance: Optional["BatchService"] = None

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self.queue = GenerationQueue.get_instance()
        self.voice_service = VoiceProfileService.get_instance()
        self.longform_service = LongformService.get_instance()

    @classmethod
    def get_instance(cls) -> "BatchService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    def submit_batch_item(
        self,
        title: str,
        text: str,
        voice_profile_id: Optional[str] = None,
        mode: str = "tts",
        cfg_value: float = 2.0,
        inference_timesteps: int = 10,
        priority: int = 100,
        force_longform: bool = False
    ) -> Tuple[Optional[str], str]:
        """
        Submits an individual speech script into the persistent batch queue.
        Automatically routes long texts (> 200 chars or force_longform) to chunked longform pipeline.
        """
        clean_text = (text or "").strip()
        if not clean_text:
            return None, "Target script cannot be empty."

        clean_title = (title or "").strip() or f"Batch Item {uuid.uuid4().hex[:6]}"
        detected_lang = TextProcessor.detect_language(clean_text)

        # Resolve voice profile
        voice_name = "Default Voice"
        ref_path = None
        prompt_path = None
        prompt_text = None

        if voice_profile_id and voice_profile_id != "Default Voice (No Profile)":
            # Extract profile ID if formatted as "Name (id)"
            if "(" in voice_profile_id and voice_profile_id.endswith(")"):
                prof_id = voice_profile_id.split("(")[-1].rstrip(")").strip()
            else:
                prof_id = voice_profile_id

            prof = self.voice_service.get_profile(prof_id)
            if prof:
                voice_profile_id = prof.id
                voice_name = prof.name
                ref_path = prof.reference_segment_path
                prompt_path = prof.reference_segment_path
                prompt_text = prof.transcript
            else:
                return None, f"Voice profile '{voice_profile_id}' not found."

        # Map UI mode to internal mode
        internal_mode = "tts"
        if mode in ("Voice Cloning", "cloning"):
            if not ref_path:
                return None, "Voice Cloning requires a voice profile with valid reference audio."
            internal_mode = "cloning"
        elif mode in ("Ultimate Cloning", "ultimate_cloning"):
            if not ref_path:
                return None, "Ultimate Cloning requires a voice profile with reference audio."
            if not prompt_text or not prompt_text.strip():
                return None, "Ultimate Cloning requires an exact transcript for the reference segment."
            internal_mode = "ultimate_cloning"

        # Determine whether to use longform chunked pipeline
        is_longform = force_longform or len(clean_text) > 200

        if is_longform:
            lf_job, err = self.longform_service.prepare_job(
                title=clean_title,
                text=clean_text,
                voice_profile_id=voice_profile_id,
                mode=internal_mode,
                language=detected_lang
            )
            if err or not lf_job:
                return None, f"Failed to prepare chunked narration: {err}"

            task = GenerationTask(
                job_id=lf_job.id,
                job_type="longform",
                target_text=clean_text,
                title=clean_title,
                voice_profile_id=voice_profile_id,
                voice_name=voice_name,
                language=detected_lang,
                mode=internal_mode,
                reference_wav_path=ref_path,
                prompt_wav_path=prompt_path,
                prompt_text=prompt_text,
                cfg_value=float(cfg_value),
                inference_timesteps=int(inference_timesteps),
                total_chunks=lf_job.total_chunks,
                completed_chunks=0,
                priority=int(priority)
            )
            self.queue.submit_task(task)
            return lf_job.id, f"Queued as Long-form ({lf_job.total_chunks} chunks)"

        else:
            job_id = f"job_{uuid.uuid4().hex[:10]}"
            task = GenerationTask(
                job_id=job_id,
                job_type=internal_mode,
                target_text=clean_text,
                title=clean_title,
                voice_profile_id=voice_profile_id,
                voice_name=voice_name,
                language=detected_lang,
                mode=internal_mode,
                reference_wav_path=ref_path,
                prompt_wav_path=prompt_path,
                prompt_text=prompt_text,
                cfg_value=float(cfg_value),
                inference_timesteps=int(inference_timesteps),
                total_chunks=1,
                completed_chunks=0,
                priority=int(priority)
            )
            self.queue.submit_task(task)
            return job_id, "Queued as standard speech generation"

    def submit_multi_script_batch(self, scripts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Submits a collection of scripts at once, returning their job IDs."""
        results = []
        for idx, item in enumerate(scripts):
            job_id, msg = self.submit_batch_item(
                title=item.get("title", f"Batch Script #{idx + 1}"),
                text=item.get("text", ""),
                voice_profile_id=item.get("voice_profile_id"),
                mode=item.get("mode", "tts"),
                cfg_value=float(item.get("cfg_value", 2.0)),
                inference_timesteps=int(item.get("inference_timesteps", 10)),
                priority=int(item.get("priority", 100)),
                force_longform=bool(item.get("force_longform", False))
            )
            results.append({
                "index": idx,
                "title": item.get("title"),
                "job_id": job_id,
                "success": job_id is not None,
                "message": msg
            })
        return results

    def start_or_resume_queue(self) -> bool:
        return self.queue.resume_queue()

    def pause_queue(self) -> bool:
        return self.queue.pause_queue()

    def cancel_job(self, job_id: str) -> bool:
        return self.queue.cancel_job(job_id)

    def retry_job(self, job_id: str) -> Tuple[bool, str]:
        return self.queue.retry_job(job_id)

    def remove_job(self, job_id: str) -> bool:
        return self.queue.remove_job(job_id)

    def clear_completed_jobs(self) -> int:
        return self.db.delete_completed_jobs()

    def get_queue_summary(self) -> Dict[str, Any]:
        """Provides full queue metrics and active job details for UI display."""
        stats = self.queue.get_queue_stats()
        active_job = None
        if stats.get("current_job_id"):
            active_job = self.queue.get_job_display_status(stats["current_job_id"])

        pending_jobs = self.db.list_pending_jobs()
        all_jobs = self.db.list_batch_jobs(limit=50)

        completed_count = sum(1 for j in all_jobs if j.status == "completed")
        failed_count = sum(1 for j in all_jobs if j.status == "failed")
        interrupted_count = sum(1 for j in all_jobs if j.status in ("interrupted", "paused"))

        return {
            "is_processing": stats["is_processing"],
            "is_paused": stats["is_paused"],
            "queue_depth": stats["queue_depth"],
            "sleep_inhibited": stats["sleep_inhibited"],
            "post_completion_action": stats["post_completion_action"],
            "active_job": active_job,
            "pending_count": len(pending_jobs),
            "completed_count": completed_count,
            "failed_count": failed_count,
            "interrupted_count": interrupted_count,
            "total_jobs": len(all_jobs)
        }
