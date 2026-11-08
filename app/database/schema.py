"""Database schema definitions and migrations."""
import sqlite3
from datetime import datetime, timezone

CURRENT_SCHEMA_VERSION = 2

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
    status TEXT NOT NULL DEFAULT 'pending',
    progress REAL DEFAULT 0.0,
    status_message TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    generation_id TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE SET NULL
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

CREATE INDEX IF NOT EXISTS idx_generations_created ON generations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_voice_profiles_created ON voice_profiles(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_longform_jobs_created ON longform_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_longform_chunks_job ON longform_chunks(job_id, chunk_index);
"""

def initialize_database(conn: sqlite3.Connection):
    """Initializes tables and records schema version safely without destructive drops."""
    cursor = conn.cursor()
    cursor.executescript(SCHEMA_SQL)
    
    # Check current schema version
    cursor.execute("SELECT MAX(version) FROM schema_version")
    row = cursor.fetchone()
    current_ver = row[0] if row and row[0] is not None else 0
    
    if current_ver < CURRENT_SCHEMA_VERSION:
        cursor.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (CURRENT_SCHEMA_VERSION, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
