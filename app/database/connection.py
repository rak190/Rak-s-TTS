"""SQLite connection manager and repository queries."""
import sqlite3
import threading
from contextlib import contextmanager
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
    MasteringJobRecord
)

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
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.id, profile.name, profile.description, profile.language,
                    profile.original_audio_path, profile.reference_segment_path,
                    profile.transcript, profile.duration_sec, profile.sample_rate,
                    profile.created_at, profile.updated_at
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
            cursor.execute("SELECT * FROM voice_profiles ORDER BY created_at DESC")
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
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    profile.name, profile.description, profile.language,
                    profile.original_audio_path, profile.reference_segment_path,
                    profile.transcript, profile.duration_sec, profile.sample_rate,
                    profile.updated_at, profile.id
                )
            )
            return cursor.rowcount > 0

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
    # Jobs Repository
    # -------------------------------------------------------------
    def create_job(self, job: QueueJob) -> QueueJob:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO jobs (
                    id, job_type, status, progress, status_message,
                    error_message, generation_id, created_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id, job.job_type, job.status, job.progress, job.status_message,
                    job.error_message, job.generation_id, job.created_at, job.started_at,
                    job.completed_at
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
                    error_message = ?, generation_id = ?,
                    started_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    job.status, job.progress, job.status_message, job.error_message,
                    job.generation_id, job.started_at, job.completed_at, job.id
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
            return QueueJob(**dict(row))

    def list_jobs(self, limit: int = 30) -> List[QueueJob]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            return [QueueJob(**dict(row)) for row in cursor.fetchall()]

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

