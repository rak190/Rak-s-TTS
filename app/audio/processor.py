"""Safe audio processing, format conversion, inspection, and trimming."""
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

@dataclass
class AudioMetadata:
    file_path: str
    duration_sec: float
    sample_rate: int
    channels: int
    subtype: str
    file_size_bytes: int
    peak_dbfs: Optional[float] = None
    rms_dbfs: Optional[float] = None
    is_valid: bool = True
    error_message: str = ""

class AudioProcessor:
    """Safe audio inspection and transformation utilities."""

    SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}

    @staticmethod
    def inspect_audio(file_path: Path | str) -> AudioMetadata:
        """Inspects an audio file without loading full waveform into RAM."""
        p = Path(file_path)
        if not p.exists():
            return AudioMetadata(
                file_path=str(p),
                duration_sec=0.0,
                sample_rate=0,
                channels=0,
                subtype="",
                file_size_bytes=0,
                is_valid=False,
                error_message=f"File does not exist: {p}"
            )
            
        file_size = p.stat().st_size
        if file_size == 0:
            return AudioMetadata(
                file_path=str(p),
                duration_sec=0.0,
                sample_rate=0,
                channels=0,
                subtype="",
                file_size_bytes=0,
                is_valid=False,
                error_message="Audio file is empty (0 bytes)."
            )

        try:
            info = sf.info(str(p))
            peak_dbfs = None
            rms_dbfs = None
            if file_size < 50 * 1024 * 1024:
                try:
                    audio_data, _ = sf.read(str(p), dtype="float32")
                    if audio_data.size > 0:
                        peak = float(np.max(np.abs(audio_data)))
                        rms = float(np.sqrt(np.mean(audio_data**2)))
                        peak_dbfs = round(20 * np.log10(max(peak, 1e-6)), 1)
                        rms_dbfs = round(20 * np.log10(max(rms, 1e-6)), 1)
                except Exception:
                    pass

            return AudioMetadata(
                file_path=str(p),
                duration_sec=round(info.duration, 2),
                sample_rate=info.samplerate,
                channels=info.channels,
                subtype=info.subtype,
                file_size_bytes=file_size,
                peak_dbfs=peak_dbfs,
                rms_dbfs=rms_dbfs,
                is_valid=True
            )
        except Exception as e:
            # Fallback inspection via ffprobe if available
            try:
                cmd = [
                    "ffprobe", "-v", "error", "-show_entries",
                    "stream=channels,sample_rate,duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(p)
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                lines = res.stdout.strip().split("\n")
                if len(lines) >= 3:
                    sr = int(lines[0])
                    ch = int(lines[1])
                    dur = float(lines[2])
                    return AudioMetadata(
                        file_path=str(p),
                        duration_sec=round(dur, 2),
                        sample_rate=sr,
                        channels=ch,
                        subtype="FFMPEG_READ",
                        file_size_bytes=file_size,
                        is_valid=True
                    )
            except Exception:
                pass
            return AudioMetadata(
                file_path=str(p),
                duration_sec=0.0,
                sample_rate=0,
                channels=0,
                subtype="",
                file_size_bytes=file_size,
                is_valid=False,
                error_message=f"Failed to parse audio file: {e}"
            )

    @staticmethod
    def validate_audio(file_path: Path | str, min_duration: float = 0.5, max_duration: float = 360.0) -> Tuple[bool, str]:
        """Validates that the audio file is readable, supported, and within valid duration bounds."""
        meta = AudioProcessor.inspect_audio(file_path)
        if not meta.is_valid:
            return False, meta.error_message

        ext = Path(file_path).suffix.lower()
        if ext not in AudioProcessor.SUPPORTED_EXTENSIONS:
            return False, f"Unsupported format '{ext}'. Supported: {', '.join(AudioProcessor.SUPPORTED_EXTENSIONS)}"

        if meta.duration_sec < min_duration:
            return False, f"Audio duration too short ({meta.duration_sec}s). Minimum: {min_duration}s."

        if meta.duration_sec > max_duration:
            return False, f"Audio duration exceeds limit ({meta.duration_sec}s). Maximum allowed: {max_duration}s."

        return True, ""

    @staticmethod
    def convert_to_pcm16_mono(
        input_path: Path | str,
        output_path: Path | str,
        target_sr: int = 48000,
        normalize_peak: bool = True
    ) -> AudioMetadata:
        """
        Converts any supported audio format into 16-bit PCM mono WAV.
        Strictly preserves the original input file without in-place modification.
        """
        in_p = Path(input_path)
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        if not in_p.exists():
            raise FileNotFoundError(f"Input file not found: {in_p}")

        # If already 16-bit PCM mono WAV at target_sr and normalization not requested, copy directly
        meta = AudioProcessor.inspect_audio(in_p)
        if (
            meta.is_valid and
            in_p.suffix.lower() == ".wav" and
            meta.channels == 1 and
            meta.sample_rate == target_sr and
            meta.subtype == "PCM_16" and
            not normalize_peak
        ):
            if in_p.resolve() != out_p.resolve():
                shutil.copy2(str(in_p), str(out_p))
            return AudioProcessor.inspect_audio(out_p)

        # Read audio using soundfile or ffmpeg
        try:
            audio, sr = sf.read(str(in_p), dtype="float32")
        except Exception:
            # Fallback: convert via ffmpeg subprocess to temporary wav
            temp_wav = out_p.with_suffix(".tmp.wav")
            cmd = [
                "ffmpeg", "-y", "-i", str(in_p),
                "-ac", "1", "-ar", str(target_sr),
                str(temp_wav)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            audio, sr = sf.read(str(temp_wav), dtype="float32")
            if temp_wav.exists():
                temp_wav.unlink()

        # Convert to mono if multi-channel
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # Resample if needed
        if sr != target_sr:
            from scipy import signal
            num_target_samples = int(len(audio) * target_sr / sr)
            audio = signal.resample(audio, num_target_samples).astype(np.float32)
            sr = target_sr

        # Peak normalization (-1.0 dBFS)
        if normalize_peak:
            peak = float(np.max(np.abs(audio)))
            if peak > 0:
                audio = audio * (0.89 / peak)

        # Write clean 16-bit PCM WAV
        sf.write(str(out_p), audio, sr, subtype="PCM_16")
        return AudioProcessor.inspect_audio(out_p)

    @staticmethod
    def trim_audio_segment(
        input_path: Path | str,
        output_path: Path | str,
        start_sec: float,
        end_sec: float,
        target_sr: int = 48000
    ) -> AudioMetadata:
        """
        Trims a segment from start_sec to end_sec and saves it to output_path.
        Preserves original input audio intact.
        """
        in_p = Path(input_path)
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        if not in_p.exists():
            raise FileNotFoundError(f"Input audio not found: {in_p}")

        audio, sr = sf.read(str(in_p), dtype="float32")
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        total_dur = len(audio) / sr
        start_sec = max(0.0, float(start_sec))
        end_sec = min(total_dur, float(end_sec))

        if start_sec >= end_sec:
            raise ValueError(f"Invalid trim window: start ({start_sec}s) >= end ({end_sec}s)")

        start_samp = int(start_sec * sr)
        end_samp = int(end_sec * sr)
        trimmed_audio = audio[start_samp:end_samp]

        # Resample to target_sr if required
        if sr != target_sr:
            from scipy import signal
            num_samples = int(len(trimmed_audio) * target_sr / sr)
            trimmed_audio = signal.resample(trimmed_audio, num_samples).astype(np.float32)
            sr = target_sr

        sf.write(str(out_p), trimmed_audio, sr, subtype="PCM_16")
        return AudioProcessor.inspect_audio(out_p)

    @staticmethod
    def detect_speech_segments(
        file_path: Path | str,
        min_segment_sec: float = 2.0,
        max_segment_sec: float = 30.0
    ) -> List[Dict]:
        """
        Optional helper: scans audio for continuous speech regions based on energy,
        giving the user candidate segments to choose from.
        """
        p = Path(file_path)
        if not p.exists():
            return []

        audio, sr = sf.read(str(p), dtype="float32")
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # 100ms frames, 50ms hop
        frame_len = int(0.1 * sr)
        hop_len = int(0.05 * sr)
        energies = []
        timestamps = []

        for i in range(0, len(audio) - frame_len, hop_len):
            frame = audio[i:i + frame_len]
            rms = np.sqrt(np.mean(frame**2))
            energies.append(rms)
            timestamps.append(i / sr)

        if not energies:
            return []

        energies = np.array(energies)
        timestamps = np.array(timestamps)

        noise_floor = float(np.percentile(energies, 15))
        peak_energy = float(np.percentile(energies, 85))
        threshold = noise_floor + (peak_energy - noise_floor) * 0.20
        is_speech = energies > threshold

        segments = []
        seg_start = None
        for t, active in zip(timestamps, is_speech):
            if active and seg_start is None:
                seg_start = t
            elif not active and seg_start is not None:
                dur = t - seg_start
                if dur >= min_segment_sec:
                    clamped_end = min(t, seg_start + max_segment_sec)
                    segments.append({
                        "start": round(seg_start, 2),
                        "end": round(clamped_end, 2),
                        "duration": round(clamped_end - seg_start, 2)
                    })
                seg_start = None

        if seg_start is not None:
            dur = timestamps[-1] - seg_start
            if dur >= min_segment_sec:
                clamped_end = min(timestamps[-1], seg_start + max_segment_sec)
                segments.append({
                    "start": round(seg_start, 2),
                    "end": round(clamped_end, 2),
                    "duration": round(clamped_end - seg_start, 2)
                })

        return segments
