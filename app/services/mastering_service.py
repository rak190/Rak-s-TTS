"""
Mastering Service orchestrating non-destructive speech mastering,
storage lifecycle management, and SQLite job logging.
"""
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.audio.filters import VoicePolishFilters, VoicePolishOptions
from app.audio.mastering import AudioMasterer, MasteringResult, MASTERING_PRESETS
from app.audio.quality import AcousticQualityReport, QualityAnalyzer
from app.config import STORAGE_DIR
from app.database.connection import DatabaseManager
from app.database.models import MasteringJobRecord

logger = logging.getLogger(__name__)


class MasteringService:
    """Service providing end-to-end mastering operations for single generations, longform jobs, and custom audio."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self.mastered_dir = STORAGE_DIR / "mastered"
        self.mastered_dir.mkdir(parents=True, exist_ok=True)

    def master_generation(
        self,
        generation_id: str,
        preset_key: str = "podcast",
        custom_target_lufs: Optional[float] = None,
        custom_true_peak: Optional[float] = None,
        enable_silence_trim: bool = True,
        voice_polish_options: Optional[VoicePolishOptions] = None
    ) -> MasteringResult:
        """Masters the output audio of an existing single generation."""
        gen = self.db.get_generation(generation_id)
        if not gen or not gen.output_audio_path:
            raise ValueError(f"Generation {generation_id} not found or has no audio.")

        in_p = Path(gen.output_audio_path)
        if not in_p.exists():
            raise FileNotFoundError(f"Source audio file not found: {in_p}")

        # Non-destructive destination
        target_dir = self.mastered_dir / generation_id
        target_dir.mkdir(parents=True, exist_ok=True)
        out_wav = target_dir / "mastered.wav"
        out_mp3 = target_dir / "mastered.mp3"

        return self._execute_and_log_mastering(
            source_type="generation",
            source_id=generation_id,
            input_path=in_p,
            out_wav=out_wav,
            out_mp3=out_mp3,
            preset_key=preset_key,
            custom_target_lufs=custom_target_lufs,
            custom_true_peak=custom_true_peak,
            enable_silence_trim=enable_silence_trim,
            voice_polish_options=voice_polish_options
        )

    def master_longform_job(
        self,
        longform_job_id: str,
        preset_key: str = "podcast",
        custom_target_lufs: Optional[float] = None,
        custom_true_peak: Optional[float] = None,
        enable_silence_trim: bool = True,
        voice_polish_options: Optional[VoicePolishOptions] = None
    ) -> MasteringResult:
        """Masters the stitched full audio of an existing longform job."""
        job = self.db.get_longform_job(longform_job_id)
        if not job or not job.output_wav_path:
            raise ValueError(f"Long-form job {longform_job_id} not found or has no output audio.")

        in_p = Path(job.output_wav_path)
        if not in_p.exists():
            raise FileNotFoundError(f"Source longform audio not found: {in_p}")

        # Store inside job folder under non-destructive mastered/ subfolder
        target_dir = in_p.parent / "mastered"
        target_dir.mkdir(parents=True, exist_ok=True)
        out_wav = target_dir / "mastered.wav"
        out_mp3 = target_dir / "mastered.mp3"

        return self._execute_and_log_mastering(
            source_type="longform",
            source_id=longform_job_id,
            input_path=in_p,
            out_wav=out_wav,
            out_mp3=out_mp3,
            preset_key=preset_key,
            custom_target_lufs=custom_target_lufs,
            custom_true_peak=custom_true_peak,
            enable_silence_trim=enable_silence_trim,
            voice_polish_options=voice_polish_options
        )

    def master_file(
        self,
        file_path: Path | str,
        preset_key: str = "podcast",
        custom_target_lufs: Optional[float] = None,
        custom_true_peak: Optional[float] = None,
        enable_silence_trim: bool = True,
        voice_polish_options: Optional[VoicePolishOptions] = None
    ) -> MasteringResult:
        """Masters an arbitrary uploaded or selected audio file non-destructively."""
        in_p = Path(file_path)
        if not in_p.exists():
            raise FileNotFoundError(f"Source audio file not found: {in_p}")

        custom_id = f"custom_{uuid.uuid4().hex[:12]}"
        target_dir = self.mastered_dir / custom_id
        target_dir.mkdir(parents=True, exist_ok=True)
        out_wav = target_dir / "mastered.wav"
        out_mp3 = target_dir / "mastered.mp3"

        return self._execute_and_log_mastering(
            source_type="custom",
            source_id=custom_id,
            input_path=in_p,
            out_wav=out_wav,
            out_mp3=out_mp3,
            preset_key=preset_key,
            custom_target_lufs=custom_target_lufs,
            custom_true_peak=custom_true_peak,
            enable_silence_trim=enable_silence_trim,
            voice_polish_options=voice_polish_options
        )

    def _execute_and_log_mastering(
        self,
        source_type: str,
        source_id: str,
        input_path: Path,
        out_wav: Path,
        out_mp3: Path,
        preset_key: str,
        custom_target_lufs: Optional[float],
        custom_true_peak: Optional[float],
        enable_silence_trim: bool,
        voice_polish_options: Optional[VoicePolishOptions]
    ) -> MasteringResult:
        """Executes audio mastering pipeline and records job record in SQLite."""
        job_id = f"mst_{uuid.uuid4().hex[:12]}"

        res = AudioMasterer.master_audio(
            input_path=input_path,
            output_wav_path=out_wav,
            output_mp3_path=out_mp3,
            preset_key=preset_key,
            custom_target_lufs=custom_target_lufs,
            custom_true_peak=custom_true_peak,
            enable_silence_trim=enable_silence_trim,
            voice_polish_options=voice_polish_options
        )

        # Log into SQLite
        filters_str = ", ".join(res.filters_applied)
        record = MasteringJobRecord(
            id=job_id,
            source_type=source_type,
            source_id=source_id,
            input_audio_path=str(input_path),
            output_wav_path=str(out_wav) if res.success else "",
            output_mp3_path=str(out_mp3) if res.success else "",
            preset=res.preset_name,
            target_lufs=res.target_lufs,
            target_tp=res.target_tp,
            measured_input_lufs=res.initial_metrics.integrated_lufs,
            measured_output_lufs=res.final_metrics.integrated_lufs if res.success else None,
            measured_input_tp=res.initial_metrics.true_peak_dbtp,
            measured_output_tp=res.final_metrics.true_peak_dbtp if res.success else None,
            filters_applied=filters_str,
            duration_sec=res.final_metrics.duration_sec if res.success else res.initial_metrics.duration_sec,
            processing_time_sec=res.processing_time_sec,
            status="completed" if res.success else "failed",
            error_message=res.error_message
        )
        self.db.create_mastering_job(record)
        return res

    def list_mastering_history(self, limit: int = 50) -> List[MasteringJobRecord]:
        """Returns recent mastering records."""
        return self.db.list_mastering_jobs(limit=limit)

    def inspect_audio(self, audio_path: Path | str) -> AcousticQualityReport:
        """Fast non-destructive inspection of an audio file."""
        return QualityAnalyzer.analyze_audio(audio_path)
