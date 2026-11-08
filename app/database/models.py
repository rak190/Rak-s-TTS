"""Data models for SQLite entities."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class VoiceProfile:
    id: str
    name: str
    original_audio_path: str
    reference_segment_path: str
    description: str = ""
    language: str = "multilingual"
    transcript: str = ""
    duration_sec: float = 0.0
    sample_rate: int = 48000
    created_at: str = field(default_factory=utc_iso_now)
    updated_at: str = field(default_factory=utc_iso_now)

@dataclass
class GenerationRecord:
    id: str
    target_text: str
    mode: str
    voice_profile_id: Optional[str] = None
    voice_name: str = "Default Voice"
    language: str = "multilingual"
    output_audio_path: str = ""
    duration_sec: float = 0.0
    generation_time_sec: float = 0.0
    rtf: float = 0.0
    sample_rate: int = 48000
    status: str = "completed"
    error_message: str = ""
    created_at: str = field(default_factory=utc_iso_now)

@dataclass
class QueueJob:
    id: str
    job_type: str
    status: str = "pending"
    progress: float = 0.0
    status_message: str = "Queued"
    error_message: str = ""
    generation_id: Optional[str] = None
    created_at: str = field(default_factory=utc_iso_now)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

@dataclass
class LongformJob:
    id: str
    title: str
    voice_profile_id: Optional[str] = None
    voice_name: str = "Default Voice"
    mode: str = "tts"
    language: str = "multilingual"
    total_chunks: int = 0
    completed_chunks: int = 0
    status: str = "pending"  # pending, processing, paused, completed, failed, cancelled
    output_wav_path: Optional[str] = None
    output_mp3_path: Optional[str] = None
    total_duration_sec: float = 0.0
    total_generation_time_sec: float = 0.0
    created_at: str = field(default_factory=utc_iso_now)
    updated_at: str = field(default_factory=utc_iso_now)

@dataclass
class LongformChunkRecord:
    id: str
    job_id: str
    chunk_index: int
    text: str
    char_count: int
    pause_after_ms: int = 300
    status: str = "pending"  # pending, processing, completed, failed
    output_wav_path: Optional[str] = None
    duration_sec: float = 0.0
    generation_time_sec: float = 0.0
    error_message: str = ""
    created_at: str = field(default_factory=utc_iso_now)
    completed_at: Optional[str] = None
