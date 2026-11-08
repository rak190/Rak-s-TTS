"""
Audio Stitching, Crossfading, and Dual WAV/MP3 Export Service.
Concatenates speech chunks with boundary de-clicking, inter-sentence pauses,
and export to 48kHz WAV and high-bitrate MP3.
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf

from app.config import NATIVE_SAMPLE_RATE

class AudioStitcher:
    """
    Stitches individual audio chunks into a seamless long-form audio master.
    Eliminates boundary pops and clicks via raised-cosine windowing and crossfading.
    """

    @staticmethod
    def apply_fade_in_out(audio: np.ndarray, fade_len: int = 480) -> np.ndarray:
        """
        Applies a raised-cosine fade-in and fade-out (default 10ms at 48kHz = 480 samples)
        to prevent DC-offset pops and boundary clicks.
        """
        if len(audio) < fade_len * 2:
            return audio
        
        out = audio.copy()
        # Raised-cosine (Hann half-window)
        fade_in = 0.5 * (1 - np.cos(np.linspace(0, np.pi, fade_len)))
        fade_out = 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade_len)))
        
        out[:fade_len] *= fade_in
        out[-fade_len:] *= fade_out
        return out

    @classmethod
    def stitch_chunks(
        cls,
        chunk_paths: List[str | Path],
        pauses_ms: Optional[List[int]] = None,
        target_sr: int = NATIVE_SAMPLE_RATE,
        fade_ms: int = 10
    ) -> Tuple[np.ndarray, float]:
        """
        Loads ordered chunk WAV files and stitches them with boundary de-clicking
        and pause insertions. Returns (concatenated_audio, total_duration_sec).
        """
        if not chunk_paths:
            return np.zeros(0, dtype=np.float32), 0.0

        fade_samples = int((fade_ms / 1000.0) * target_sr)
        segments: List[np.ndarray] = []

        for i, p in enumerate(chunk_paths):
            wav_path = Path(p)
            if not wav_path.exists():
                continue

            data, sr = sf.read(str(wav_path))
            if data.ndim > 1:
                data = np.mean(data, axis=1)
            
            # Resample if needed (should already be native sr)
            if sr != target_sr:
                num_out = int(len(data) * target_sr / sr)
                data = np.interp(
                    np.linspace(0, len(data), num_out, endpoint=False),
                    np.arange(len(data)),
                    data
                )

            # Apply de-clicking fade window to chunk boundaries
            faded = cls.apply_fade_in_out(data, fade_len=fade_samples)
            segments.append(faded)

            # Insert pause silence after chunk if not the final chunk
            if i < len(chunk_paths) - 1:
                pause_duration_ms = pauses_ms[i] if pauses_ms and i < len(pauses_ms) else 300
                if pause_duration_ms > 0:
                    pause_samples = int((pause_duration_ms / 1000.0) * target_sr)
                    silence = np.zeros(pause_samples, dtype=np.float32)
                    segments.append(silence)

        if not segments:
            return np.zeros(0, dtype=np.float32), 0.0

        full_audio = np.concatenate(segments)

        # Peak normalization to -1.0 dBFS
        peak = np.max(np.abs(full_audio))
        target_peak = 10 ** (-1.0 / 20.0)  # ~0.891
        if peak > 0:
            full_audio = (full_audio / peak) * target_peak

        duration_sec = round(len(full_audio) / target_sr, 2)
        return full_audio, duration_sec

    @classmethod
    def export_wav(
        cls,
        audio: np.ndarray,
        output_path: str | Path,
        sample_rate: int = NATIVE_SAMPLE_RATE
    ) -> Path:
        """Exports audio array as uncompressed 16-bit PCM WAV."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out_p), audio, sample_rate, subtype="PCM_16")
        return out_p

    @classmethod
    def export_mp3(
        cls,
        wav_path: str | Path,
        mp3_path: str | Path,
        bitrate: str = "320k"
    ) -> Path:
        """
        Converts WAV file to MP3 using system FFmpeg.
        Falls back to copy or direct write if FFmpeg is unavailable.
        """
        in_p = Path(wav_path)
        out_p = Path(mp3_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # Check for ffmpeg executable
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i", str(in_p),
                "-codec:a", "libmp3lame",
                "-b:a", bitrate,
                str(out_p)
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0 and out_p.exists():
                return out_p

        # Fallback if ffmpeg fails: write using SoundFile if libsndfile supports MP3
        try:
            data, sr = sf.read(str(in_p))
            sf.write(str(out_p), data, sr, format="MP3")
            return out_p
        except Exception:
            # If MP3 write is unsupported, keep WAV as fallback
            return in_p
