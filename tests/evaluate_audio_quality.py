"""
Stage 5A - Audio Quality & A/B Comparison Objective Measurement Suite.
Extracts Pitch (F0), Spectral Flatness, Crest Factor, Spectral Roll-off,
and Mel Spectral Envelope Similarity to complement human perceptual listening.
"""
import sys
from pathlib import Path
import numpy as np
import soundfile as sf

# Force UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def compute_f0_autocorr(signal: np.ndarray, sr: int, fmin: float = 75.0, fmax: float = 350.0):
    """Estimates mean pitch (F0) using normalized autocorrelation over 30ms frames."""
    frame_len = int(0.03 * sr)
    hop_len = int(0.015 * sr)
    min_lag = int(sr / fmax)
    max_lag = int(sr / fmin)
    
    f0_values = []
    for i in range(0, len(signal) - frame_len, hop_len):
        frame = signal[i:i + frame_len]
        frame = frame - np.mean(frame)
        if np.std(frame) < 1e-4:
            continue
        corr = np.correlate(frame, frame, mode='full')
        corr = corr[len(corr) // 2:]
        if len(corr) > max_lag:
            peak_lag = min_lag + np.argmax(corr[min_lag:max_lag])
            if corr[peak_lag] > 0.3 * corr[0]:
                f0 = sr / peak_lag
                f0_values.append(f0)
    return float(np.median(f0_values)) if f0_values else 0.0, float(np.std(f0_values)) if f0_values else 0.0

def compute_spectral_features(signal: np.ndarray, sr: int):
    """Computes spectral centroid, 85% roll-off, and spectral flatness."""
    fft_mag = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(len(signal), 1.0 / sr)
    total_energy = np.sum(fft_mag) + 1e-12
    
    # Spectral Centroid
    centroid = np.sum(freqs * fft_mag) / total_energy
    
    # Spectral Roll-off (85% cumulative energy)
    cum_energy = np.cumsum(fft_mag)
    rolloff_idx = np.searchsorted(cum_energy, 0.85 * total_energy)
    rolloff = freqs[min(rolloff_idx, len(freqs) - 1)]
    
    # Spectral Flatness (Wiener entropy: geometric mean / arithmetic mean)
    log_energy = np.mean(np.log(fft_mag + 1e-12))
    geo_mean = np.exp(log_energy)
    ari_mean = np.mean(fft_mag) + 1e-12
    flatness = geo_mean / ari_mean

    return centroid, rolloff, flatness

def compute_crest_factor(signal: np.ndarray):
    """Peak to RMS ratio in dB."""
    peak = np.max(np.abs(signal))
    rms = np.sqrt(np.mean(signal ** 2)) + 1e-12
    crest_db = 20 * np.log10(peak / rms)
    rms_dbfs = 20 * np.log10(rms)
    peak_dbfs = 20 * np.log10(peak + 1e-12)
    return peak_dbfs, rms_dbfs, crest_db

def analyze_file(filepath: Path):
    data, sr = sf.read(str(filepath))
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    
    f0_med, f0_std = compute_f0_autocorr(data, sr)
    centroid, rolloff, flatness = compute_spectral_features(data, sr)
    peak_db, rms_db, crest_db = compute_crest_factor(data)
    dur = len(data) / sr

    return {
        "file": filepath.name,
        "duration": round(dur, 2),
        "f0_median": round(f0_med, 1),
        "f0_std": round(f0_std, 1),
        "centroid_hz": round(centroid, 1),
        "rolloff_hz": round(rolloff, 1),
        "flatness": round(flatness, 4),
        "peak_dbfs": round(peak_db, 2),
        "rms_dbfs": round(rms_db, 2),
        "crest_db": round(crest_db, 2)
    }

def run_audio_audit():
    print("=" * 80)
    print("VOICESTUDIO AI - STAGE 5A MULTI-DIMENSIONAL ACOUSTIC & A/B COMPARISON AUDIT")
    print("=" * 80)

    # 1. Reference Audios
    ref_en = PROJECT_ROOT / "storage" / "voices" / "prof_1b30778f90fa" / "reference.wav"
    ref_kh = PROJECT_ROOT / "storage" / "voices" / "prof_d0fd33d8bdc7" / "reference.wav"

    # 2. Cloned Audios
    cloned_en = PROJECT_ROOT / "storage" / "generated" / "20261108" / "gen_dc37950482a9.wav"
    hifi_en = PROJECT_ROOT / "storage" / "generated" / "20261108" / "gen_b17a487f7ed9.wav"
    cloned_kh = PROJECT_ROOT / "storage" / "generated" / "20261108" / "gen_885869e4ad19.wav"

    # 3. 5-Chunk Long-Form Master & Consecutive Chunks
    lf_job = PROJECT_ROOT / "storage" / "longform" / "lf_4d5cc4a7500f"
    lf_master = lf_job / "full_audio.wav"
    chk0 = lf_job / "chunks" / "chunk_000.wav"
    chk1 = lf_job / "chunks" / "chunk_001.wav"
    chk2 = lf_job / "chunks" / "chunk_002.wav"
    chk3 = lf_job / "chunks" / "chunk_003.wav"
    chk4 = lf_job / "chunks" / "chunk_004.wav"

    targets = [
        ("Reference EN", ref_en),
        ("Cloned EN (Controllable)", cloned_en),
        ("Cloned EN (Hi-Fi)", hifi_en),
        ("Reference KH", ref_kh),
        ("Cloned KH (Hi-Fi)", cloned_kh),
        ("LF Master (5-Chunk)", lf_master),
        ("LF Chunk 0 (Khmer)", chk0),
        ("LF Chunk 1 (Khmer)", chk1),
        ("LF Chunk 2 (English)", chk2),
        ("LF Chunk 3 (English)", chk3),
        ("LF Chunk 4 (Mixed)", chk4)
    ]

    results = []
    print(f"{'Label':<25} | {'Dur(s)':<6} | {'F0 (Hz)':<8} | {'Centroid':<9} | {'Roll-off':<9} | {'Flatness':<8} | {'Crest(dB)':<9}")
    print("-" * 85)
    for label, path in targets:
        if path.exists():
            res = analyze_file(path)
            res["label"] = label
            results.append(res)
            print(f"{label:<25} | {res['duration']:<6} | {res['f0_median']:<8} | {res['centroid_hz']:<9} | {res['rolloff_hz']:<9} | {res['flatness']:<8} | {res['crest_db']:<9}")
        else:
            print(f"{label:<25} | MISSING FILE: {path}")

    print("=" * 80)
    print("ACOUSTIC AUDIT COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    run_audio_audit()
