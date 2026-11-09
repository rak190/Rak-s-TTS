"""SQLite connection manager and repository queries."""
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from app.config import DB_PATH
from app.database.schema import initialize_database
from app.database.models import (
    VoiceProfile,
    GenerationRecord,
    QueueJob,
    LongformJob,
    LongformChunkRecord,
    MasteringJobRecord,
    ScriptProjectRecord
)

def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class DatabaseManager:
    """Thread-safe SQLite connection and repository manager."""
    
    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        # Initialize schema once
        with self.get_connection() as conn:
            initialize_database(conn)
            
    @classmethod
    def get_instance(cls, db_path: Path = DB_PATH) -> "DatabaseManager":
        with cls._lock:
            if cls._instance is None or cls._instance.db_path != db_path:
                cls._instance = cls(db_path=db_path)
            return cls._instance

    @classmethod
    def reset_instance(cls):
        with cls._lock:
            cls._instance = None

    @contextmanager
    def get_connection(self):
        """Yields an SQLite connection configured with foreign keys and WAL mode."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # -------------------------------------------------------------
    # Voice Profiles Repository
    # -------------------------------------------------------------
    def create_voice_profile(self, profile: VoiceProfile) -> VoiceProfile:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO voice_profiles (
                    id, name, description, language, original_audio_path,
                    reference_segment_path, transcript, duration_sec, sample_rate,
                    created_at, updated_at, display_name, khmer_display_name,
                    category, gender, speaking_style, origin, source_license,
                    preview_audio_path, preview_type, is_favorite, is_default,
                    last_used_at, validation_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.id, profile.name, profile.description, profile.language,
                    profile.original_audio_path, profile.reference_segment_path,
                    profile.transcript, profile.duration_sec, profile.sample_rate,
                    profile.created_at, profile.updated_at, profile.display_name,
                    profile.khmer_display_name, profile.category, profile.gender,
                    profile.speaking_style, profile.origin, profile.source_license,
                    profile.preview_audio_path, profile.preview_type,
                    profile.is_favorite, profile.is_default, profile.last_used_at,
                    profile.validation_status
                )
            )
            return profile

    def get_voice_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM voice_profiles WHERE id = ?", (profile_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return VoiceProfile(**dict(row))

    def get_voice_profile_by_name(self, name: str) -> Optional[VoiceProfile]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM voice_profiles WHERE name = ?", (name,))
            row = cursor.fetchone()
            if not row:
                return None
            return VoiceProfile(**dict(row))

    def list_voice_profiles(self) -> List[VoiceProfile]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM voice_profiles ORDER BY is_default DESC, is_favorite DESC, created_at DESC")
            return [VoiceProfile(**dict(row)) for row in cursor.fetchall()]

    def update_voice_profile(self, profile: VoiceProfile) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE voice_profiles SET
                    name = ?, description = ?, language = ?,
                    original_audio_path = ?, reference_segment_path = ?,
                    transcript = ?, duration_sec = ?, sample_rate = ?,
                    updated_at = ?, display_name = ?, khmer_display_name = ?,
                    category = ?, gender = ?, speaking_style = ?, origin = ?,
                    source_license = ?, preview_audio_path = ?, preview_type = ?,
                    is_favorite = ?, is_default = ?, last_used_at = ?,
                    validation_status = ?
                WHERE id = ?
                """,
                (
                    profile.name, profile.description, profile.language,
                    profile.original_audio_path, profile.reference_segment_path,
                    profile.transcript, profile.duration_sec, profile.sample_rate,
                    profile.updated_at, profile.display_name, profile.khmer_display_name,
                    profile.category, profile.gender, profile.speaking_style, profile.origin,
                    profile.source_license, profile.preview_audio_path, profile.preview_type,
                    profile.is_favorite, profile.is_default, profile.last_used_at,
                    profile.validation_status, profile.id
                )
            )
            return cursor.rowcount > 0

    def set_voice_favorite(self, profile_id: str, is_favorite: bool) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE voice_profiles SET is_favorite = ?, updated_at = ? WHERE id = ?",
                (1 if is_favorite else 0, utc_iso_now(), profile_id)
            )
            return cursor.rowcount > 0

    def set_voice_default(self, profile_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE voice_profiles SET is_default = 0")
            cursor.execute(
                "UPDATE voice_profiles SET is_default = 1, updated_at = ? WHERE id = ?",
                (utc_iso_now(), profile_id)
            )
            cursor.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES ('active_voice_id', ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (profile_id, utc_iso_now())
            )
            return cursor.rowcount > 0

    def get_default_voice_profile(self) -> Optional[VoiceProfile]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Try setting first
            cursor.execute("SELECT value FROM settings WHERE key = 'active_voice_id'")
            row = cursor.fetchone()
            if row and row[0]:
                cursor.execute("SELECT * FROM voice_profiles WHERE id = ?", (row[0],))
                prof_row = cursor.fetchone()
                if prof_row:
                    return VoiceProfile(**dict(prof_row))

            cursor.execute("SELECT * FROM voice_profiles WHERE is_default = 1 LIMIT 1")
            row = cursor.fetchone()
            if row:
                return VoiceProfile(**dict(row))

            cursor.execute("SELECT * FROM voice_profiles ORDER BY is_favorite DESC, created_at ASC LIMIT 1")
            row = cursor.fetchone()
            return VoiceProfile(**dict(row)) if row else None

    def record_voice_used(self, profile_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE voice_profiles SET last_used_at = ? WHERE id = ?",
                (utc_iso_now(), profile_id)
            )
            return cursor.rowcount > 0

    def search_voice_catalog(
        self,
        search_term: str = "",
        category: Optional[str] = None,
        gender: Optional[str] = None,
        origin: Optional[str] = None,
        favorites_only: bool = False,
        validation_status: Optional[str] = None
    ) -> List[VoiceProfile]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM voice_profiles WHERE 1=1"
            params: List[Any] = []

            if search_term:
                term = f"%{search_term.strip()}%"
                query += " AND (name LIKE ? OR display_name LIKE ? OR khmer_display_name LIKE ? OR description LIKE ? OR speaking_style LIKE ?)"
                params.extend([term, term, term, term, term])

            if category and category.lower() != "all":
                query += " AND LOWER(category) = LOWER(?)"
                params.append(category)

            if gender and gender.lower() != "all":
                query += " AND LOWER(gender) = LOWER(?)"
                params.append(gender)

            if origin and origin.lower() != "all":
                query += " AND LOWER(origin) = LOWER(?)"
                params.append(origin)

            if favorites_only:
                query += " AND is_favorite = 1"

            if validation_status and validation_status.lower() != "all":
                query += " AND LOWER(validation_status) = LOWER(?)"
                params.append(validation_status)

            query += " ORDER BY is_default DESC, is_favorite DESC, created_at DESC"
            cursor.execute(query, tuple(params))
            return [VoiceProfile(**dict(row)) for row in cursor.fetchall()]

    def delete_voice_profile(self, profile_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM voice_profiles WHERE id = ?", (profile_id,))
            return cursor.rowcount > 0

    # -------------------------------------------------------------
    # Generations Repository
    # -------------------------------------------------------------
    def create_generation(self, record: GenerationRecord) -> GenerationRecord:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO generations (
                    id, voice_profile_id, voice_name, target_text, mode,
                    language, output_audio_path, duration_sec, generation_time_sec,
                    rtf, sample_rate, status, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id, record.voice_profile_id, record.voice_name, record.target_text,
                    record.mode, record.language, record.output_audio_path, record.duration_sec,
                    record.generation_time_sec, record.rtf, record.sample_rate, record.status,
                    record.error_message, record.created_at
                )
            )
            return record

    def list_generations(self, limit: int = 50, offset: int = 0) -> List[GenerationRecord]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM generations ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return [GenerationRecord(**dict(row)) for row in cursor.fetchall()]

    def delete_generation(self, generation_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM generations WHERE id = ?", (generation_id,))
            return cursor.rowcount > 0

    # -------------------------------------------------------------
    # Jobs Repository (Extended for Schema v4 Batch Queue)
    # -------------------------------------------------------------
    @staticmethod
    def _row_to_queue_job(row: sqlite3.Row) -> QueueJob:
        d = dict(row)
        return QueueJob(
            id=d["id"],
            job_type=d.get("job_type", "tts"),
            status=d.get("status", "queued"),
            progress=float(d.get("progress") or 0.0),
            status_message=d.get("status_message") or "",
            error_message=d.get("error_message") or "",
            generation_id=d.get("generation_id"),
            title=d.get("title") or "Untitled Job",
            target_text=d.get("target_text") or "",
            voice_profile_id=d.get("voice_profile_id"),
            voice_name=d.get("voice_name") or "Default Voice",
            language=d.get("language") or "multilingual",
            mode=d.get("mode") or "tts",
            cfg_value=float(d.get("cfg_value") or 2.0),
            inference_timesteps=int(d.get("inference_timesteps") or 10),
            total_chunks=int(d.get("total_chunks") or 1),
            completed_chunks=int(d.get("completed_chunks") or 0),
            output_wav_path=d.get("output_wav_path"),
            output_mp3_path=d.get("output_mp3_path"),
            retry_count=int(d.get("retry_count") or 0),
            priority=int(d.get("priority") or 100),
            created_at=d.get("created_at") or utc_iso_now(),
            started_at=d.get("started_at"),
            completed_at=d.get("completed_at"),
            updated_at=d.get("updated_at") or d.get("created_at") or utc_iso_now()
        )

    def create_job(self, job: QueueJob) -> QueueJob:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO jobs (
                    id, job_type, status, progress, status_message,
                    error_message, generation_id, title, target_text,
                    voice_profile_id, voice_name, language, mode,
                    cfg_value, inference_timesteps, total_chunks, completed_chunks,
                    output_wav_path, output_mp3_path, retry_count, priority,
                    created_at, started_at, completed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id, job.job_type, job.status, job.progress, job.status_message,
                    job.error_message, job.generation_id, job.title, job.target_text,
                    job.voice_profile_id, job.voice_name, job.language, job.mode,
                    job.cfg_value, job.inference_timesteps, job.total_chunks, job.completed_chunks,
                    job.output_wav_path, job.output_mp3_path, job.retry_count, job.priority,
                    job.created_at, job.started_at, job.completed_at, job.updated_at
                )
            )
            return job

    def update_job(self, job: QueueJob) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE jobs SET
                    status = ?, progress = ?, status_message = ?,
                    error_message = ?, generation_id = ?, title = ?,
                    target_text = ?, voice_profile_id = ?, voice_name = ?,
                    language = ?, mode = ?, cfg_value = ?, inference_timesteps = ?,
                    total_chunks = ?, completed_chunks = ?, output_wav_path = ?,
                    output_mp3_path = ?, retry_count = ?, priority = ?,
                    started_at = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    job.status, job.progress, job.status_message,
                    job.error_message, job.generation_id, job.title,
                    job.target_text, job.voice_profile_id, job.voice_name,
                    job.language, job.mode, job.cfg_value, job.inference_timesteps,
                    job.total_chunks, job.completed_chunks, job.output_wav_path,
                    job.output_mp3_path, job.retry_count, job.priority,
                    job.started_at, job.completed_at, job.updated_at or utc_iso_now(),
                    job.id
                )
            )
            return cursor.rowcount > 0

    def get_job(self, job_id: str) -> Optional[QueueJob]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_queue_job(row)

    def list_jobs(self, limit: int = 30) -> List[QueueJob]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            return [self._row_to_queue_job(row) for row in cursor.fetchall()]

    def list_batch_jobs(self, status_filter: Optional[str] = None, limit: int = 50) -> List[QueueJob]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status_filter:
                cursor.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY priority DESC, created_at ASC LIMIT ?",
                    (status_filter, limit)
                )
            else:
                cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            return [self._row_to_queue_job(row) for row in cursor.fetchall()]

    def list_pending_jobs(self) -> List[QueueJob]:
        """Returns all queued/pending jobs ordered strictly by priority and submission timestamp."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM jobs WHERE status IN ('queued', 'pending') ORDER BY priority DESC, created_at ASC"
            )
            return [self._row_to_queue_job(row) for row in cursor.fetchall()]

    def mark_interrupted_jobs_on_startup(self) -> int:
        """Finds any jobs left in 'processing' on application startup and marks them 'interrupted'."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE jobs SET
                    status = 'interrupted',
                    status_message = 'Interrupted by application restart (ready to resume)',
                    updated_at = ?
                WHERE status = 'processing'
                """,
                (utc_iso_now(),)
            )
            return cursor.rowcount

    def delete_completed_jobs(self) -> int:
        """Cleans finished jobs (completed, cancelled) from queue registry."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE status IN ('completed', 'cancelled')")
            return cursor.rowcount

    def delete_job(self, job_id: str) -> bool:
        """Deletes a job by id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            return cursor.rowcount > 0

    # -------------------------------------------------------------
    # Long-Form Jobs & Chunks Repository (Stage 4)
    # -------------------------------------------------------------
    def create_longform_job(self, job: LongformJob) -> LongformJob:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO longform_jobs (
                    id, title, voice_profile_id, voice_name, mode, language,
                    total_chunks, completed_chunks, status, output_wav_path,
                    output_mp3_path, total_duration_sec, total_generation_time_sec,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id, job.title, job.voice_profile_id, job.voice_name, job.mode,
                    job.language, job.total_chunks, job.completed_chunks, job.status,
                    job.output_wav_path, job.output_mp3_path, job.total_duration_sec,
                    job.total_generation_time_sec, job.created_at, job.updated_at
                )
            )
            return job

    def get_longform_job(self, job_id: str) -> Optional[LongformJob]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM longform_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return LongformJob(**dict(row))

    def list_longform_jobs(self, limit: int = 50, offset: int = 0) -> List[LongformJob]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM longform_jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return [LongformJob(**dict(row)) for row in cursor.fetchall()]

    def update_longform_job(self, job: LongformJob) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE longform_jobs SET
                    title = ?, voice_profile_id = ?, voice_name = ?, mode = ?,
                    language = ?, total_chunks = ?, completed_chunks = ?,
                    status = ?, output_wav_path = ?, output_mp3_path = ?,
                    total_duration_sec = ?, total_generation_time_sec = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    job.title, job.voice_profile_id, job.voice_name, job.mode,
                    job.language, job.total_chunks, job.completed_chunks,
                    job.status, job.output_wav_path, job.output_mp3_path,
                    job.total_duration_sec, job.total_generation_time_sec,
                    job.updated_at, job.id
                )
            )
            return cursor.rowcount > 0

    def delete_longform_job(self, job_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM longform_jobs WHERE id = ?", (job_id,))
            return cursor.rowcount > 0

    def create_longform_chunks(self, chunks: List[LongformChunkRecord]) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO longform_chunks (
                    id, job_id, chunk_index, text, char_count, pause_after_ms,
                    status, output_wav_path, duration_sec, generation_time_sec,
                    error_message, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        c.id, c.job_id, c.chunk_index, c.text, c.char_count,
                        c.pause_after_ms, c.status, c.output_wav_path,
                        c.duration_sec, c.generation_time_sec, c.error_message,
                        c.created_at, c.completed_at
                    )
                    for c in chunks
                ]
            )
            return True

    def get_longform_chunks(self, job_id: str) -> List[LongformChunkRecord]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM longform_chunks WHERE job_id = ? ORDER BY chunk_index ASC",
                (job_id,)
            )
            return [LongformChunkRecord(**dict(row)) for row in cursor.fetchall()]

    def update_longform_chunk(self, chunk: LongformChunkRecord) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE longform_chunks SET
                    status = ?, output_wav_path = ?, duration_sec = ?,
                    generation_time_sec = ?, error_message = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    chunk.status, chunk.output_wav_path, chunk.duration_sec,
                    chunk.generation_time_sec, chunk.error_message,
                    chunk.completed_at, chunk.id
                )
            )
            return cursor.rowcount > 0

    # -------------------------------------------------------------
    # Mastering Jobs Repository
    # -------------------------------------------------------------
    def create_mastering_job(self, record: MasteringJobRecord) -> MasteringJobRecord:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO mastering_jobs (
                    id, source_type, source_id, input_audio_path, output_wav_path,
                    output_mp3_path, preset, target_lufs, target_tp, measured_input_lufs,
                    measured_output_lufs, measured_input_tp, measured_output_tp,
                    filters_applied, duration_sec, processing_time_sec, status,
                    error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id, record.source_type, record.source_id, record.input_audio_path,
                    record.output_wav_path, record.output_mp3_path, record.preset,
                    record.target_lufs, record.target_tp, record.measured_input_lufs,
                    record.measured_output_lufs, record.measured_input_tp, record.measured_output_tp,
                    record.filters_applied, record.duration_sec, record.processing_time_sec,
                    record.status, record.error_message, record.created_at
                )
            )
            return record

    def get_mastering_job(self, job_id: str) -> Optional[MasteringJobRecord]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mastering_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return MasteringJobRecord(**dict(row))

    def list_mastering_jobs(self, limit: int = 50, offset: int = 0) -> List[MasteringJobRecord]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM mastering_jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return [MasteringJobRecord(**dict(row)) for row in cursor.fetchall()]

    def get_mastering_job_by_source(self, source_type: str, source_id: str) -> Optional[MasteringJobRecord]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM mastering_jobs WHERE source_type = ? AND source_id = ? ORDER BY created_at DESC LIMIT 1",
                (source_type, source_id)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return MasteringJobRecord(**dict(row))

    # -------------------------------------------------------------
    # Settings Repository
    # -------------------------------------------------------------
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if not row or row["value"] is None:
                return default
            return str(row["value"])

    def set_setting(self, key: str, value: str) -> bool:
        from app.database.models import utc_iso_now
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, str(value), utc_iso_now())
            )
            return cursor.rowcount > 0

    def get_all_settings(self) -> Dict[str, str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    # -------------------------------------------------------------
    # Script Projects Repository (Smart Script Studio)
    # -------------------------------------------------------------
    def create_script_project(self, project: ScriptProjectRecord) -> ScriptProjectRecord:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO script_projects (
                    id, title, topic, source_filename, source_copy_path,
                    project_json_path, scene_count, completed_scenes,
                    planned_duration_sec, actual_duration_sec, status,
                    combined_wav_path, combined_mp3_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.id, project.title, project.topic, project.source_filename,
                    project.source_copy_path, project.project_json_path, project.scene_count,
                    project.completed_scenes, project.planned_duration_sec, project.actual_duration_sec,
                    project.status, project.combined_wav_path, project.combined_mp3_path,
                    project.created_at, project.updated_at
                )
            )
            return project

    def get_script_project(self, project_id: str) -> Optional[ScriptProjectRecord]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM script_projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return ScriptProjectRecord(**dict(row))

    def update_script_project(self, project: ScriptProjectRecord) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE script_projects SET
                    title = ?, topic = ?, source_filename = ?, source_copy_path = ?,
                    project_json_path = ?, scene_count = ?, completed_scenes = ?,
                    planned_duration_sec = ?, actual_duration_sec = ?, status = ?,
                    combined_wav_path = ?, combined_mp3_path = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    project.title, project.topic, project.source_filename, project.source_copy_path,
                    project.project_json_path, project.scene_count, project.completed_scenes,
                    project.planned_duration_sec, project.actual_duration_sec, project.status,
                    project.combined_wav_path, project.combined_mp3_path, project.updated_at,
                    project.id
                )
            )
            return cursor.rowcount > 0

    def list_script_projects(self, limit: int = 50) -> List[ScriptProjectRecord]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM script_projects ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            )
            return [ScriptProjectRecord(**dict(row)) for row in cursor.fetchall()]

    def delete_script_project(self, project_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM script_projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0



