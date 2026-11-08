"""Database schema definitions and migrations."""
import sqlite3
from datetime import datetime, timezone

CURRENT_SCHEMA_VERSION = 4

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voice_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    language TEXT NOT NULL DEFAULT 'multilingual',
    original_audio_path TEXT NOT NULL,
    reference_segment_path TEXT NOT NULL,
    transcript TEXT DEFAULT '',
    duration_sec REAL DEFAULT 0.0,
    sample_rate INTEGER DEFAULT 48000,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generations (
    id TEXT PRIMARY KEY,
    voice_profile_id TEXT,
    voice_name TEXT DEFAULT 'Default Voice',
    target_text TEXT NOT NULL,
    mode TEXT NOT NULL,
    language TEXT DEFAULT 'multilingual',
    output_audio_path TEXT,
    duration_sec REAL DEFAULT 0.0,
    generation_time_sec REAL DEFAULT 0.0,
    rtf REAL DEFAULT 0.0,
    sample_rate INTEGER DEFAULT 48000,
    status TEXT NOT NULL DEFAULT 'completed',
    error_message TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (voice_profile_id) REFERENCES voice_profiles(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    progress REAL DEFAULT 0.0,
    status_message TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    generation_id TEXT,
    title TEXT DEFAULT 'Untitled Job',
    target_text TEXT DEFAULT '',
    voice_profile_id TEXT,
    voice_name TEXT DEFAULT 'Default Voice',
    language TEXT DEFAULT 'multilingual',
    mode TEXT DEFAULT 'tts',
    cfg_value REAL DEFAULT 2.0,
    inference_timesteps INTEGER DEFAULT 10,
    total_chunks INTEGER DEFAULT 1,
    completed_chunks INTEGER DEFAULT 0,
    output_wav_path TEXT,
    output_mp3_path TEXT,
    retry_count INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 100,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE SET NULL,
    FOREIGN KEY (voice_profile_id) REFERENCES voice_profiles(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS longform_jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    voice_profile_id TEXT,
    voice_name TEXT DEFAULT 'Default Voice',
    mode TEXT NOT NULL DEFAULT 'tts',
    language TEXT DEFAULT 'multilingual',
    total_chunks INTEGER NOT NULL DEFAULT 0,
    completed_chunks INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    output_wav_path TEXT,
    output_mp3_path TEXT,
    total_duration_sec REAL DEFAULT 0.0,
    total_generation_time_sec REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (voice_profile_id) REFERENCES voice_profiles(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS longform_chunks (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    pause_after_ms INTEGER DEFAULT 300,
    status TEXT NOT NULL DEFAULT 'pending',
    output_wav_path TEXT,
    duration_sec REAL DEFAULT 0.0,
    generation_time_sec REAL DEFAULT 0.0,
    error_message TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (job_id) REFERENCES longform_jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mastering_jobs (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT,
    input_audio_path TEXT NOT NULL,
    output_wav_path TEXT NOT NULL,
    output_mp3_path TEXT,
    preset TEXT NOT NULL,
    target_lufs REAL NOT NULL,
    target_tp REAL NOT NULL,
    measured_input_lufs REAL,
    measured_output_lufs REAL,
    measured_input_tp REAL,
    measured_output_tp REAL,
    filters_applied TEXT DEFAULT '',
    duration_sec REAL DEFAULT 0.0,
    processing_time_sec REAL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'completed',
    error_message TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_generations_created ON generations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_voice_profiles_created ON voice_profiles(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_longform_jobs_created ON longform_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_longform_chunks_job ON longform_chunks(job_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_mastering_jobs_created ON mastering_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mastering_jobs_source ON mastering_jobs(source_type, source_id);

"""

def migrate_v3_to_v4(cursor: sqlite3.Cursor):
    """Safely adds batch queue columns to jobs table without data loss."""
    cursor.execute("PRAGMA table_info(jobs)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    columns_to_add = [
        ("title", "TEXT DEFAULT 'Untitled Job'"),
        ("target_text", "TEXT DEFAULT ''"),
        ("voice_profile_id", "TEXT"),
        ("voice_name", "TEXT DEFAULT 'Default Voice'"),
        ("language", "TEXT DEFAULT 'multilingual'"),
        ("mode", "TEXT DEFAULT 'tts'"),
        ("cfg_value", "REAL DEFAULT 2.0"),
        ("inference_timesteps", "INTEGER DEFAULT 10"),
        ("total_chunks", "INTEGER DEFAULT 1"),
        ("completed_chunks", "INTEGER DEFAULT 0"),
        ("output_wav_path", "TEXT"),
        ("output_mp3_path", "TEXT"),
        ("retry_count", "INTEGER DEFAULT 0"),
        ("priority", "INTEGER DEFAULT 100"),
        ("updated_at", "TEXT")
    ]
    for col_name, col_type in columns_to_add:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_priority_created ON jobs(status, priority DESC, created_at ASC)")

def initialize_database(conn: sqlite3.Connection):
    """Initializes tables and records schema version safely without destructive drops."""
    cursor = conn.cursor()
    
    # Check current schema version before executing scripts
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    has_ver_table = cursor.fetchone() is not None
    current_ver = 0
    if has_ver_table:
        cursor.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        current_ver = row[0] if row and row[0] is not None else 0

    cursor.executescript(SCHEMA_SQL)
    
    if current_ver < 4:
        migrate_v3_to_v4(cursor)

    if current_ver < CURRENT_SCHEMA_VERSION:
        cursor.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (CURRENT_SCHEMA_VERSION, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
