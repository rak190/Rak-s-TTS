"""Service managing generation execution, file output, and history recording."""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import soundfile as sf

from app.config import GENERATED_DIR, NATIVE_SAMPLE_RATE
from app.database.connection import DatabaseManager
from app.database.models import GenerationRecord
from app.engines.voxcpm_adapter import VoxCPM2Adapter

def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class GenerationService:
    """Orchestrates speech generation, disk persistence, and database tracking."""
    _instance: Optional["GenerationService"] = None

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        tts_engine: Optional[VoxCPM2Adapter] = None
    ):
        self.db = db_manager or DatabaseManager.get_instance()
        self.engine = tts_engine or VoxCPM2Adapter()

    @classmethod
    def get_instance(cls) -> "GenerationService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def execute_generation_task(self, task) -> Dict:
        """
        Executes a queued generation task via VoxCPM2Adapter, records metrics,
        and saves output WAV file to Drive D:.
        """
        text = task.target_text.strip()
        if not text:
            raise ValueError("Target text cannot be empty.")

        # Determine target output path partitioned by date
        date_folder = datetime.now(timezone.utc).strftime("%Y%m%d")
        dest_dir = GENERATED_DIR / date_folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        gen_id = f"gen_{uuid.uuid4().hex[:12]}"
        output_wav_path = dest_dir / f"{gen_id}.wav"

        # Dispatch by generation mode
        if task.job_type == "tts":
            wav_np, sample_rate, elapsed_sec = self.engine.generate_tts(
                text=text,
                cfg_value=task.cfg_value,
                inference_timesteps=task.inference_timesteps
            )
        elif task.job_type == "cloning":
            if not task.reference_wav_path or not Path(task.reference_wav_path).exists():
                raise FileNotFoundError(f"Reference audio missing: {task.reference_wav_path}")
            wav_np, sample_rate, elapsed_sec = self.engine.generate_voice_cloning(
                text=text,
                reference_wav_path=task.reference_wav_path,
                cfg_value=task.cfg_value,
                inference_timesteps=task.inference_timesteps
            )
        elif task.job_type == "ultimate_cloning":
            if not task.prompt_wav_path or not Path(task.prompt_wav_path).exists():
                raise FileNotFoundError(f"Prompt audio missing: {task.prompt_wav_path}")
            if not task.prompt_text:
                raise ValueError("Ultimate cloning strictly requires prompt transcript.")
            wav_np, sample_rate, elapsed_sec = self.engine.generate_ultimate_cloning(
                text=text,
                prompt_wav_path=task.prompt_wav_path,
                prompt_text=task.prompt_text,
                reference_wav_path=task.reference_wav_path or task.prompt_wav_path,
                cfg_value=task.cfg_value,
                inference_timesteps=task.inference_timesteps
            )
        else:
            raise ValueError(f"Unknown generation mode: {task.job_type}")

        # Write output WAV as uncompressed 16-bit PCM
        sf.write(str(output_wav_path), wav_np, sample_rate, subtype="PCM_16")

        audio_duration = round(len(wav_np) / sample_rate, 2)
        rtf = round(elapsed_sec / audio_duration, 2) if audio_duration > 0 else 0.0

        # Save record in database
        record = GenerationRecord(
            id=gen_id,
            voice_profile_id=task.voice_profile_id,
            voice_name=task.voice_name,
            target_text=text,
            mode=task.job_type,
            language=task.language,
            output_audio_path=str(output_wav_path),
            duration_sec=audio_duration,
            generation_time_sec=elapsed_sec,
            rtf=rtf,
            sample_rate=sample_rate,
            status="completed",
            created_at=utc_iso_now()
        )
        self.db.create_generation(record)

        return {
            "generation_id": gen_id,
            "output_path": str(output_wav_path),
            "duration_sec": audio_duration,
            "generation_time_sec": elapsed_sec,
            "rtf": rtf,
            "sample_rate": sample_rate
        }

    def list_history(self, limit: int = 50, offset: int = 0) -> List[GenerationRecord]:
        return self.db.list_generations(limit=limit, offset=offset)

    def delete_history_item(self, generation_id: str) -> bool:
        record = self.db.get_connection()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT output_audio_path FROM generations WHERE id = ?", (generation_id,))
            row = cursor.fetchone()
            if row and row["output_audio_path"]:
                p = Path(row["output_audio_path"])
                if p.exists():
                    try:
                        p.unlink()
                    except Exception:
                        pass
        return self.db.delete_generation(generation_id)
