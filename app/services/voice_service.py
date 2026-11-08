"""Service managing Voice Profile creation, storage, and lifecycle."""
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from app.config import VOICES_DIR, NATIVE_SAMPLE_RATE
from app.audio.processor import AudioProcessor
from app.database.connection import DatabaseManager
from app.database.models import VoiceProfile

def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class VoiceProfileService:
    """Manages voice profiles, safe file storage, and segment references."""
    _instance: Optional["VoiceProfileService"] = None

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    @classmethod
    def get_instance(cls) -> "VoiceProfileService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_profile(
        self,
        name: str,
        original_audio_path: str | Path,
        description: str = "",
        language: str = "multilingual",
        transcript: str = "",
        trim_start_sec: Optional[float] = None,
        trim_end_sec: Optional[float] = None
    ) -> Tuple[Optional[VoiceProfile], str]:
        """
        Creates a new voice profile, saving both the original audio and the processed
        reference segment in dedicated storage on Drive D:.
        """
        clean_name = name.strip()
        if not clean_name:
            return None, "Voice profile name cannot be empty."

        # Check for existing profile name
        existing = self.db.get_voice_profile_by_name(clean_name)
        if existing:
            return None, f"A voice profile named '{clean_name}' already exists."

        in_p = Path(original_audio_path)
        valid, msg = AudioProcessor.validate_audio(in_p, min_duration=1.0, max_duration=360.0)
        if not valid:
            return None, f"Audio validation failed: {msg}"

        profile_id = f"prof_{uuid.uuid4().hex[:12]}"
        prof_dir = VOICES_DIR / profile_id
        prof_dir.mkdir(parents=True, exist_ok=True)

        # 1. Safely store original audio (preserve pristine uploaded recording)
        orig_dest = prof_dir / f"original{in_p.suffix.lower()}"
        shutil.copy2(str(in_p), str(orig_dest))

        # 2. Extract or convert reference segment
        ref_dest = prof_dir / "reference.wav"
        orig_meta = AudioProcessor.inspect_audio(orig_dest)

        if trim_start_sec is not None and trim_end_sec is not None and trim_end_sec > trim_start_sec:
            ref_meta = AudioProcessor.trim_audio_segment(
                input_path=orig_dest,
                output_path=ref_dest,
                start_sec=trim_start_sec,
                end_sec=trim_end_sec,
                target_sr=NATIVE_SAMPLE_RATE
            )
        else:
            ref_meta = AudioProcessor.convert_to_pcm16_mono(
                input_path=orig_dest,
                output_path=ref_dest,
                target_sr=NATIVE_SAMPLE_RATE
            )

        now = utc_iso_now()
        profile = VoiceProfile(
            id=profile_id,
            name=clean_name,
            description=description.strip(),
            language=language,
            original_audio_path=str(orig_dest),
            reference_segment_path=str(ref_dest),
            transcript=transcript.strip(),
            duration_sec=ref_meta.duration_sec,
            sample_rate=ref_meta.sample_rate,
            created_at=now,
            updated_at=now
        )

        self.db.create_voice_profile(profile)
        return profile, "Voice profile created successfully."

    def list_profiles(self) -> List[VoiceProfile]:
        return self.db.list_voice_profiles()

    def get_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        return self.db.get_voice_profile(profile_id)

    def update_profile(
        self,
        profile_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        language: Optional[str] = None,
        transcript: Optional[str] = None,
        new_trim_start: Optional[float] = None,
        new_trim_end: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Updates profile metadata or re-trims reference slice without losing original audio."""
        prof = self.db.get_voice_profile(profile_id)
        if not prof:
            return False, "Profile not found."

        if name and name.strip() != prof.name:
            existing = self.db.get_voice_profile_by_name(name.strip())
            if existing and existing.id != profile_id:
                return False, f"Name '{name}' is already used by another profile."
            prof.name = name.strip()

        if description is not None:
            prof.description = description.strip()
        if language is not None:
            prof.language = language
        if transcript is not None:
            prof.transcript = transcript.strip()

        # Re-trim reference slice from preserved original audio if requested
        if new_trim_start is not None and new_trim_end is not None and new_trim_end > new_trim_start:
            ref_dest = Path(prof.reference_segment_path)
            meta = AudioProcessor.trim_audio_segment(
                input_path=prof.original_audio_path,
                output_path=ref_dest,
                start_sec=new_trim_start,
                end_sec=new_trim_end,
                target_sr=NATIVE_SAMPLE_RATE
            )
            prof.duration_sec = meta.duration_sec
            prof.sample_rate = meta.sample_rate

        prof.updated_at = utc_iso_now()
        self.db.update_voice_profile(prof)
        return True, "Profile updated successfully."

    def delete_profile(self, profile_id: str) -> Tuple[bool, str]:
        """Deletes voice profile record and cleans associated disk files safely."""
        prof = self.db.get_voice_profile(profile_id)
        if not prof:
            return False, "Profile not found."

        prof_dir = VOICES_DIR / profile_id
        if prof_dir.exists():
            try:
                shutil.rmtree(prof_dir)
            except Exception as e:
                pass

        self.db.delete_voice_profile(profile_id)
        return True, f"Voice profile '{prof.name}' deleted successfully."
