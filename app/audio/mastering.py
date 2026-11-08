"""
Professional Audio Mastering Engine for VoiceStudio AI.
Two-Pass ITU-R BS.1770-4 Loudness Normalization, True-Peak Limiting, Voice Polish Filters,
Non-destructive processing, and Dual WAV/MP3 Export.
"""
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import soundfile as sf

from app.audio.filters import VoicePolishFilters, VoicePolishOptions
from app.audio.loudness import LoudnessAnalyzer, LoudnessMetrics
from app.audio.quality import AcousticQualityReport, QualityAnalyzer
from app.audio.silence import SilenceProcessor

logger = logging.getLogger(__name__)


@dataclass
class MasteringPreset:
    """Pre-configured standard broadcast and publishing loudness profiles."""
    name: str
    target_lufs: float
    true_peak_dbtp: float
    target_lra: float
    description: str


MASTERING_PRESETS: Dict[str, MasteringPreset] = {
    "podcast": MasteringPreset(
        name="Podcast / Streaming",
        target_lufs=-16.0,
        true_peak_dbtp=-1.5,
        target_lra=11.0,
        description="Standard for YouTube, Spotify, Apple Podcasts (-16 LUFS, -1.5 dBTP)"
    ),
    "audiobook": MasteringPreset(
        name="Audiobook / ACX",
        target_lufs=-18.0,
        true_peak_dbtp=-1.5,
        target_lra=9.0,
        description="Complies with Audible / ACX submission guidelines (-18 LUFS, -1.5 dBTP)"
    ),
    "soft": MasteringPreset(
        name="Soft / Natural",
        target_lufs=-20.0,
        true_peak_dbtp=-2.0,
        target_lra=14.0,
        description="Warm, natural, dynamic speech for relaxed listening (-20 LUFS, -2.0 dBTP)"
    ),
    "custom": MasteringPreset(
        name="Custom Mastering",
        target_lufs=-16.0,
        true_peak_dbtp=-1.5,
        target_lra=11.0,
        description="Fully user-configurable target loudness and peak ceilings"
    )
}


@dataclass
class MasteringResult:
    """Detailed outcome of an audio mastering run."""
    input_path: str
    output_wav_path: str
    output_mp3_path: str
    preset_name: str
    target_lufs: float
    target_tp: float
    initial_metrics: AcousticQualityReport
    final_metrics: AcousticQualityReport
    processing_time_sec: float
    silence_trimmed_lead_sec: float = 0.0
    silence_trimmed_trail_sec: float = 0.0
    filters_applied: List[str] = field(default_factory=list)
    success: bool = True
    error_message: str = ""


class AudioMasterer:
    """Orchestrates professional speech post-processing and loudness mastering."""

    @staticmethod
    def get_preset(preset_key: str) -> MasteringPreset:
        """Retrieves a preset by name or defaults to podcast."""
        key = preset_key.lower().strip()
        if "audiobook" in key or "acx" in key:
            return MASTERING_PRESETS["audiobook"]
        elif "soft" in key or "natural" in key:
            return MASTERING_PRESETS["soft"]
        elif "custom" in key:
            return MASTERING_PRESETS["custom"]
        return MASTERING_PRESETS["podcast"]

    @staticmethod
    def master_audio(
        input_path: Path | str,
        output_wav_path: Path | str,
        output_mp3_path: Optional[Path | str] = None,
        preset_key: str = "podcast",
        custom_target_lufs: Optional[float] = None,
        custom_true_peak: Optional[float] = None,
        enable_silence_trim: bool = True,
        voice_polish_options: Optional[VoicePolishOptions] = None
    ) -> MasteringResult:
        """
        Executes non-destructive, professional mastering:
        1. Comprehensive initial acoustic analysis.
        2. Optional intelligent silence edge trimming.
        3. Optional voice polish DSP (rumble cut, de-esser, presence EQ, speech compressor).
        4. True two-pass ITU-R BS.1770-4 loudness normalization via FFmpeg loudnorm.
        5. Dual export: Broadcast-grade 24-bit PCM WAV + 320 kbps MP3.
        6. Comprehensive final acoustic verification.
        """
        start_time = time.time()
        in_p = Path(input_path)
        out_wav = Path(output_wav_path)
        out_wav.parent.mkdir(parents=True, exist_ok=True)

        if not in_p.exists():
            raise FileNotFoundError(f"Input audio does not exist: {in_p}")

        # Resolve target parameters
        preset = AudioMasterer.get_preset(preset_key)
        target_i = custom_target_lufs if custom_target_lufs is not None else preset.target_lufs
        target_tp = custom_true_peak if custom_true_peak is not None else preset.true_peak_dbtp
        target_lra = preset.target_lra

        # 1. Initial Analysis
        initial_metrics = QualityAnalyzer.analyze_audio(in_p)
        applied_filters = []
        lead_trimmed = 0.0
        trail_trimmed = 0.0

        # Create temporary working directory for non-destructive intermediate stages
        temp_dir = out_wav.parent / f"_temp_master_{int(start_time * 1000)}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        current_working_audio = temp_dir / "step_input.wav"

        try:
            # Copy input to working audio
            shutil.copy2(str(in_p), str(current_working_audio))

            # 2. Silence Edge Trimming (if enabled)
            if enable_silence_trim:
                audio, sr = sf.read(str(current_working_audio), dtype="float32")
                trimmed_audio, lead_trimmed, trail_trimmed = SilenceProcessor.trim_silence_edges(
                    audio, sr,
                    threshold_db=-45.0,
                    leading_margin_sec=0.12,
                    trailing_margin_sec=0.22
                )
                if (lead_trimmed + trail_trimmed) > 0.02:
                    step_trimmed = temp_dir / "step_silence.wav"
                    sf.write(str(step_trimmed), trimmed_audio, sr, subtype="PCM_16")
                    current_working_audio = step_trimmed
                    applied_filters.append(f"Silence Edge Trim (-{lead_trimmed:.2f}s lead, -{trail_trimmed:.2f}s trail)")

            # 3. Voice Polish DSP (if requested)
            if voice_polish_options is not None:
                audio, sr = sf.read(str(current_working_audio), dtype="float32")
                polished = VoicePolishFilters.polish_audio(audio, sr, voice_polish_options)
                
                step_polished = temp_dir / "step_polish.wav"
                sf.write(str(step_polished), polished, sr, subtype="PCM_16")
                current_working_audio = step_polished

                if voice_polish_options.enable_highpass:
                    applied_filters.append(f"High-pass Rumble ({voice_polish_options.highpass_cutoff_hz}Hz)")
                if voice_polish_options.enable_deesser:
                    applied_filters.append("Dynamic De-Esser (5.5-8.5kHz)")
                if voice_polish_options.enable_presence:
                    applied_filters.append(f"Vocal Presence EQ (+{voice_polish_options.presence_gain_db}dB @ {voice_polish_options.presence_freq_hz}Hz)")
                if voice_polish_options.enable_compressor:
                    applied_filters.append("Speech Dynamic Compressor (2:1)")

            # 4. Two-Pass Loudness Normalization
            # Pass 1: Measure current audio metrics
            loudness_p1 = LoudnessAnalyzer.measure_loudness(
                current_working_audio, target_i=target_i, target_tp=target_tp, target_lra=target_lra
            )

            # Pass 2: Apply normalization with measured values
            m_i = loudness_p1.integrated_lufs
            m_tp = loudness_p1.true_peak_dbtp
            m_lra = loudness_p1.loudness_range_lra
            m_thresh = loudness_p1.threshold_lufs
            offset = loudness_p1.target_offset
            is_linear = (loudness_p1.normalization_type == "linear")
            linear_flag = "true" if is_linear else "false"

            loudnorm_pass2_filter = (
                f"loudnorm=I={target_i:.1f}:TP={target_tp:.1f}:LRA={target_lra:.1f}:"
                f"measured_I={m_i:.2f}:measured_TP={m_tp:.2f}:measured_LRA={m_lra:.2f}:"
                f"measured_thresh={m_thresh:.2f}:offset={offset:.2f}:linear={linear_flag}"
            )

            # Normalize and output as 24-bit PCM WAV (or 16-bit) at 48000 Hz
            cmd_norm = [
                "ffmpeg", "-y", "-nostats", "-i", str(current_working_audio),
                "-af", loudnorm_pass2_filter,
                "-ar", "48000",
                "-c:a", "pcm_s24le",
                str(out_wav)
            ]
            subprocess.run(cmd_norm, capture_output=True, check=True)
            applied_filters.append(f"ITU-R BS.1770-4 Normalization ({target_i:.1f} LUFS, {target_tp:.1f} dBTP)")

            # 5. Dual MP3 Export (if requested or by default alongside WAV)
            if output_mp3_path is None:
                output_mp3 = out_wav.with_suffix(".mp3")
            else:
                output_mp3 = Path(output_mp3_path)
            output_mp3.parent.mkdir(parents=True, exist_ok=True)

            cmd_mp3 = [
                "ffmpeg", "-y", "-nostats", "-i", str(out_wav),
                "-c:a", "libmp3lame",
                "-b:a", "320k",
                "-ar", "48000",
                str(output_mp3)
            ]
            subprocess.run(cmd_mp3, capture_output=True, check=True)

            # 6. Final Quality Verification
            final_metrics = QualityAnalyzer.analyze_audio(out_wav)
            processing_dur = round(time.time() - start_time, 2)

            return MasteringResult(
                input_path=str(in_p),
                output_wav_path=str(out_wav),
                output_mp3_path=str(output_mp3),
                preset_name=preset.name,
                target_lufs=target_i,
                target_tp=target_tp,
                initial_metrics=initial_metrics,
                final_metrics=final_metrics,
                processing_time_sec=processing_dur,
                silence_trimmed_lead_sec=lead_trimmed,
                silence_trimmed_trail_sec=trail_trimmed,
                filters_applied=applied_filters,
                success=True
            )

        except Exception as e:
            logger.error("Mastering failed on %s: %s", in_p, e, exc_info=True)
            return MasteringResult(
                input_path=str(in_p),
                output_wav_path=str(out_wav),
                output_mp3_path="",
                preset_name=preset.name,
                target_lufs=target_i,
                target_tp=target_tp,
                initial_metrics=initial_metrics,
                final_metrics=initial_metrics,
                processing_time_sec=round(time.time() - start_time, 2),
                success=False,
                error_message=str(e)
            )
        finally:
            # Clean up temporary directory safely
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
