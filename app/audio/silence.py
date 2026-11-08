"""
Intelligent Non-Destructive Silence Processing.
Safe edge trimming (leading/trailing) with natural breathing margins.
Preserves internal punctuation pauses and long-form sentence stitching intact.
"""
import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


class SilenceProcessor:
    """Non-destructive speech silence processor."""

    @staticmethod
    def trim_silence_edges(
        audio: np.ndarray,
        sr: int,
        threshold_db: float = -45.0,
        leading_margin_sec: float = 0.12,
        trailing_margin_sec: float = 0.22,
        min_speech_duration_sec: float = 0.30
    ) -> Tuple[np.ndarray, float, float]:
        """
        Trims excessive leading and trailing silence from speech while keeping natural breathing room.
        
        Args:
            audio: 1D mono float32 numpy array.
            sr: Sample rate in Hz.
            threshold_db: Energy threshold below which audio is considered silence.
            leading_margin_sec: Natural breathing room preserved before first speech (e.g. 120ms).
            trailing_margin_sec: Natural decay room preserved after last speech (e.g. 220ms).
            min_speech_duration_sec: Minimum speech duration required to perform trimming safely.
            
        Returns:
            Tuple of (trimmed_audio_array, trimmed_leading_seconds, trimmed_trailing_seconds).
        """
        if audio.size == 0 or sr <= 0:
            return audio, 0.0, 0.0

        if audio.ndim > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio

        frame_len = max(1, int(0.01 * sr))  # 10ms frame
        num_frames = len(mono) // frame_len
        if num_frames == 0:
            return audio, 0.0, 0.0

        frames = mono[:num_frames * frame_len].reshape(num_frames, frame_len)
        frame_energies = np.sqrt(np.mean(frames**2, axis=1))

        threshold_linear = 10 ** (threshold_db / 20.0)
        active_indices = np.where(frame_energies >= threshold_linear)[0]

        if len(active_indices) == 0:
            # Entire clip is below threshold; return untouched to avoid deleting content
            logger.info("Entire clip is below silence threshold; preserving audio untouched.")
            return audio, 0.0, 0.0

        first_active_frame = active_indices[0]
        last_active_frame = active_indices[-1]

        speech_duration = (last_active_frame - first_active_frame + 1) * (frame_len / sr)
        if speech_duration < min_speech_duration_sec:
            # Too short to safely trim
            return audio, 0.0, 0.0

        first_active_sample = first_active_frame * frame_len
        last_active_sample = min(len(mono), (last_active_frame + 1) * frame_len)

        leading_margin_samples = int(leading_margin_sec * sr)
        trailing_margin_samples = int(trailing_margin_sec * sr)

        start_sample = max(0, first_active_sample - leading_margin_samples)
        end_sample = min(len(mono), last_active_sample + trailing_margin_samples)

        # Calculate actual trimmed durations
        trimmed_leading_sec = start_sample / sr
        trimmed_trailing_sec = (len(mono) - end_sample) / sr

        # If negligible trimming (< 50ms total), return original
        if (trimmed_leading_sec + trimmed_trailing_sec) < 0.05:
            return audio, 0.0, 0.0

        trimmed_audio = audio[start_sample:end_sample]

        # Apply short 5ms cosine fade-in and fade-out to prevent any edge clicks
        fade_len = min(int(0.005 * sr), len(trimmed_audio) // 4)
        if fade_len > 1:
            fade_in = np.sin(np.linspace(0, np.pi / 2, fade_len)) ** 2
            fade_out = np.sin(np.linspace(np.pi / 2, 0, fade_len)) ** 2
            trimmed_audio[:fade_len] *= fade_in
            trimmed_audio[-fade_len:] *= fade_out

        logger.debug(
            "Silence trimmed: lead -%.2fs, trail -%.2fs, old dur: %.2fs -> new dur: %.2fs",
            trimmed_leading_sec, trimmed_trailing_sec, len(audio) / sr, len(trimmed_audio) / sr
        )
        return trimmed_audio, round(trimmed_leading_sec, 3), round(trimmed_trailing_sec, 3)

    @staticmethod
    def process_file_silence(
        input_path: Path | str,
        output_path: Path | str,
        threshold_db: float = -45.0,
        leading_margin_sec: float = 0.12,
        trailing_margin_sec: float = 0.22
    ) -> Tuple[bool, float, float]:
        """
        Loads an audio file, safely trims excessive leading/trailing silence, and writes to output_path.
        Preserves original file.
        """
        in_p = Path(input_path)
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        audio, sr = sf.read(str(in_p), dtype="float32")
        trimmed, lead_s, trail_s = SilenceProcessor.trim_silence_edges(
            audio, sr,
            threshold_db=threshold_db,
            leading_margin_sec=leading_margin_sec,
            trailing_margin_sec=trailing_margin_sec
        )

        # Write output as 16-bit or 24-bit PCM WAV
        sf.write(str(out_p), trimmed, sr, subtype="PCM_16")
        return True, lead_s, trail_s
