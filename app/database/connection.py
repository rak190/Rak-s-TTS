"""SQLite connection manager and repository queries."""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from app.config import DB_PATH
from app.database.schema import initialize_database
from app.database.models import VoiceProfile, GenerationRecord, QueueJob

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
