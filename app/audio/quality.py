"""
Comprehensive Audio Quality Analyzer for Speech.
Extracts acoustic metrics: LUFS, True-Peak, RMS, Crest Factor, Silence distribution, DC Offset, Clipping.
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

from app.audio.loudness import LoudnessAnalyzer, LoudnessMetrics

logger = logging.getLogger(__name__)


@dataclass
class AcousticQualityReport:
    """Comprehensive acoustic quality report for an audio recording or generated speech."""
    file_path: str
    duration_sec: float
    sample_rate: int
    channels: int
    
    # Loudness & Dynamics
    integrated_lufs: float
    true_peak_dbtp: float
    rms_dbfs: float
    peak_dbfs: float
    crest_factor_db: float
    loudness_range_lra: float
    
    # Silence & Pauses
    silence_percent: float
    leading_silence_sec: float
    trailing_silence_sec: float
    internal_pauses_count: int
    
    # Signal Integrity
    dc_offset: float
    is_clipped: bool
    clipped_samples: int
    snr_estimate_db: float
    
    # Recommendations & Status
    quality_grade: str  # "Excellent", "Good", "Needs Mastering", "Caution"
    notes: List[str]


class QualityAnalyzer:
    """Non-destructive acoustic quality and signal integrity inspector."""

    @staticmethod
    def analyze_audio(file_path: Path | str) -> AcousticQualityReport:
        """
        Fast in-depth acoustic inspection of speech audio.
        Loads waveform into memory (single-precision float mono) and combines with EBU R128 metrics.
        """
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")

        # 1. Read audio waveform
        audio_data, sr = sf.read(str(p), dtype="float32")
        duration = len(audio_data) / sr if sr > 0 else 0.0

        if audio_data.ndim > 1:
            channels = audio_data.shape[1]
            audio_mono = np.mean(audio_data, axis=1)
        else:
            channels = 1
            audio_mono = audio_data

        if audio_mono.size == 0:
            return AcousticQualityReport(
                file_path=str(p),
                duration_sec=0.0,
                sample_rate=sr,
                channels=channels,
                integrated_lufs=-70.0,
                true_peak_dbtp=-70.0,
                rms_dbfs=-70.0,
                peak_dbfs=-70.0,
                crest_factor_db=0.0,
                loudness_range_lra=0.0,
                silence_percent=100.0,
                leading_silence_sec=0.0,
                trailing_silence_sec=0.0,
                internal_pauses_count=0,
                dc_offset=0.0,
                is_clipped=False,
                clipped_samples=0,
                snr_estimate_db=0.0,
                quality_grade="Caution",
                notes=["Audio file is completely empty."]
            )

        # 2. Basic Signal Metrics
        abs_audio = np.abs(audio_mono)
        peak_linear = float(np.max(abs_audio))
        peak_dbfs = round(20 * np.log10(max(peak_linear, 1e-6)), 2)

        rms_linear = float(np.sqrt(np.mean(audio_mono**2)))
        rms_dbfs = round(20 * np.log10(max(rms_linear, 1e-6)), 2)

        crest_factor_db = round(peak_dbfs - rms_dbfs, 2)
        dc_offset = float(np.mean(audio_mono))

        # Clipping Detection (samples near +-1.0)
        clipped_mask = abs_audio >= 0.999
        clipped_samples = int(np.sum(clipped_mask))
        is_clipped = clipped_samples > 10

        # 3. EBU R128 / ITU-R BS.1770-4 Loudness Metrics via FFmpeg
        try:
            loudness = LoudnessAnalyzer.measure_loudness(p)
            integrated_lufs = round(loudness.integrated_lufs, 2)
            true_peak_dbtp = round(loudness.true_peak_dbtp, 2)
            lra = round(loudness.loudness_range_lra, 2)
        except Exception as e:
            logger.warning("LoudnessAnalyzer error (%s), estimating from RMS.", e)
            integrated_lufs = round(rms_dbfs - 3.0, 2)
            true_peak_dbtp = peak_dbfs
            lra = 8.0

        # 4. Silence & Pause Segmentation
        frame_len = max(1, int(0.02 * sr))  # 20ms frames
        hop_len = max(1, int(0.01 * sr))    # 10ms hop
        num_frames = (len(audio_mono) - frame_len) // hop_len + 1

        silence_thresh_linear = max(1e-4, 10 ** (-45.0 / 20.0))  # -45 dBFS silence gate
        silence_count = 0
        is_frame_silent = []

        for i in range(num_frames):
            frame = audio_mono[i * hop_len : i * hop_len + frame_len]
            frame_rms = np.sqrt(np.mean(frame**2))
            silent = bool(frame_rms < silence_thresh_linear)
            is_frame_silent.append(silent)
            if silent:
                silence_count += 1

        silence_percent = round((silence_count / max(1, num_frames)) * 100, 1)

        # Leading & Trailing silence duration
        leading_silent_frames = 0
        for s in is_frame_silent:
            if s:
                leading_silent_frames += 1
            else:
                break
        leading_silence_sec = round((leading_silent_frames * hop_len) / sr, 3)

        trailing_silent_frames = 0
        for s in reversed(is_frame_silent):
            if s:
                trailing_silent_frames += 1
            else:
                break
        trailing_silence_sec = round((trailing_silent_frames * hop_len) / sr, 3)

        # Internal Pauses (silence runs >= 250ms inside active speech)
        min_pause_frames = int(0.25 / (hop_len / sr))
        internal_pauses = 0
        current_run = 0
        active_speech_started = False

        for s in is_frame_silent[leading_silent_frames : len(is_frame_silent) - trailing_silent_frames]:
            if s:
                current_run += 1
            else:
                if current_run >= min_pause_frames:
                    internal_pauses += 1
                current_run = 0

        # 5. Noise floor & SNR estimate
        sorted_energies = sorted(
            [np.sqrt(np.mean(audio_mono[i * hop_len : i * hop_len + frame_len]**2)) for i in range(num_frames)]
        )
        if sorted_energies:
            noise_floor_linear = max(1e-6, float(np.percentile(sorted_energies, 10)))
            speech_energy_linear = max(1e-5, float(np.percentile(sorted_energies, 90)))
            snr_estimate_db = round(20 * np.log10(speech_energy_linear / noise_floor_linear), 1)
        else:
            snr_estimate_db = 30.0

        # 6. Quality Grade & Diagnostic Notes
        notes = []
        grade = "Excellent"

        if is_clipped:
            grade = "Caution"
            notes.append(f"⚠️ Digital clipping detected ({clipped_samples} peak samples).")
        
        if abs(dc_offset) > 0.01:
            notes.append(f"⚠️ Noticeable DC offset ({dc_offset:+.4f}); high-pass filter recommended.")

        if integrated_lufs < -24.0:
            if grade == "Excellent":
                grade = "Needs Mastering"
            notes.append(f"ℹ️ Speech is quiet ({integrated_lufs} LUFS); target is typically -16 to -18 LUFS.")
        elif integrated_lufs > -14.0:
            if grade == "Excellent":
                grade = "Needs Mastering"
            notes.append(f"⚠️ Speech is overly loud ({integrated_lufs} LUFS); risk of distortion.")

        if true_peak_dbtp > -1.0:
            notes.append(f"⚠️ True-peak ({true_peak_dbtp} dBTP) is close to 0 dBTP limit.")

        if leading_silence_sec > 0.8:
            notes.append(f"ℹ️ Long lead-in silence ({leading_silence_sec}s). Edge trimming suggested.")
        if trailing_silence_sec > 1.2:
            notes.append(f"ℹ️ Long trailing silence ({trailing_silence_sec}s). Edge trimming suggested.")

        if not notes:
            notes.append("✅ Acoustic metrics comply with professional speech broadcast standards.")

        return AcousticQualityReport(
            file_path=str(p),
            duration_sec=round(duration, 2),
            sample_rate=sr,
            channels=channels,
            integrated_lufs=integrated_lufs,
            true_peak_dbtp=true_peak_dbtp,
            rms_dbfs=rms_dbfs,
            peak_dbfs=peak_dbfs,
            crest_factor_db=crest_factor_db,
            loudness_range_lra=lra,
            silence_percent=silence_percent,
            leading_silence_sec=leading_silence_sec,
            trailing_silence_sec=trailing_silence_sec,
            internal_pauses_count=internal_pauses,
            dc_offset=round(dc_offset, 5),
            is_clipped=is_clipped,
            clipped_samples=clipped_samples,
            snr_estimate_db=snr_estimate_db,
            quality_grade=grade,
            notes=notes
        )
