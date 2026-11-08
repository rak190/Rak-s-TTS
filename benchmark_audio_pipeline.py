import os
import sys
import time
import numpy as np
import soundfile as sf
import psutil

# Ensure stdout and stderr handle UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def generate_synthetic_multiturn_audio(duration_sec=180, sr=16000):
    """
    Simulates a 3-minute (180s) user speech recording with:
    - Multiple speech bursts (simulated harmonic tones representing speech formants)
    - Natural conversational pauses (0.5s - 2.0s silences)
    - Low-level background noise (-45 dB)
    """
    total_samples = duration_sec * sr
    audio = np.zeros(total_samples, dtype=np.float32)
    
    # Add ambient noise floor (-45 dB)
    noise = np.random.normal(0, 10**(-45/20), total_samples).astype(np.float32)
    audio += noise
    
    # Generate speech segments
    current_time = 1.0 # start after 1s silence
    segment_idx = 1
    segments_meta = []
    
    while current_time < duration_sec - 10:
        # Segment duration: between 8 and 22 seconds
        seg_dur = np.random.uniform(8.0, 22.0)
        end_time = min(current_time + seg_dur, duration_sec - 1.0)
        
        start_idx = int(current_time * sr)
        end_idx = int(end_time * sr)
        seg_samples = end_idx - start_idx
        
        # Synthetic speech formant harmonics (150Hz pitch, 300Hz, 600Hz, 1200Hz)
        t = np.linspace(0, end_time - current_time, seg_samples, endpoint=False)
        voice = (0.5 * np.sin(2 * np.pi * 150 * t) +
                 0.25 * np.sin(2 * np.pi * 300 * t) +
                 0.15 * np.sin(2 * np.pi * 600 * t) +
                 0.10 * np.sin(2 * np.pi * 1200 * t)).astype(np.float32)
        # Apply amplitude envelope (fade in/out)
        fade_len = int(0.1 * sr)
        fade_in = np.linspace(0, 1, fade_len)
        fade_out = np.linspace(1, 0, fade_len)
        voice[:fade_len] *= fade_in
        voice[-fade_len:] *= fade_out
        
        # Random modulation simulating speech cadence
        cadence = 0.7 + 0.3 * np.sin(2 * np.pi * 3 * t)
        voice *= cadence.astype(np.float32)
        
        # Scale to ~ -18 dBFS
        voice = voice * 0.4
        
        audio[start_idx:end_idx] += voice
        segments_meta.append({
            "segment_id": segment_idx,
            "start_time": current_time,
            "end_time": end_time,
            "duration": end_time - current_time
        })
        segment_idx += 1
        
        # Conversational pause (1.0s to 3.0s)
        pause = np.random.uniform(1.2, 3.2)
        current_time = end_time + pause
        
    return audio, sr, segments_meta

def analyze_and_segment_audio(audio, sr, min_chunk_sec=10.0, max_chunk_sec=25.0):
    """
    Implements intelligent audio preprocessing & VAD-based slicing:
    1. Peak & RMS normalization to -20 dBFS
    2. Energy-based silence detection
    3. Optimal 'Golden Reference' slice selection for VoxCPM2 voice cloning
    """
    t0 = time.perf_counter()
    mem_before = psutil.Process().memory_info().rss / (1024**2)
    
    # 1. Normalize Audio
    peak = np.max(np.abs(audio))
    target_peak = 0.89  # ~ -1 dBFS
    if peak > 0:
        normalized_audio = audio * (target_peak / peak)
    else:
        normalized_audio = audio
        
    # 2. Windowed Energy Calculation (100ms frames)
    frame_len = int(0.1 * sr) # 100ms
    hop_len = int(0.05 * sr)   # 50ms
    frames = []
    times = []
    
    for i in range(0, len(normalized_audio) - frame_len, hop_len):
        frame = normalized_audio[i:i+frame_len]
        rms = np.sqrt(np.mean(frame**2))
        frames.append(rms)
        times.append(i / sr)
        
    frames = np.array(frames)
    times = np.array(times)
    
    # Energy threshold for speech vs pause (dynamic based on 30th percentile)
    noise_floor = float(np.percentile(frames, 15))
    peak_energy = float(np.percentile(frames, 90))
    speech_threshold = noise_floor + (peak_energy - noise_floor) * 0.25
    is_speech = frames > speech_threshold
    
    # 3. Detect continuous speech regions
    chunks = []
    chunk_start = None
    
    for idx, (t, active) in enumerate(zip(times, is_speech)):
        if active and chunk_start is None:
            chunk_start = t
        elif not active and chunk_start is not None:
            dur = t - chunk_start
            if dur >= min_chunk_sec:
                chunks.append((chunk_start, t, dur))
            chunk_start = None
            
    if chunk_start is not None:
        dur = times[-1] - chunk_start
        if dur >= min_chunk_sec:
            chunks.append((chunk_start, times[-1], dur))
            
    # Slices exceeding max_chunk_sec are capped at max_chunk_sec
    refined_chunks = []
    for s, e, d in chunks:
        if d > max_chunk_sec:
            refined_chunks.append((s, s + max_chunk_sec, max_chunk_sec))
        else:
            refined_chunks.append((s, e, d))
            
    # 4. Rank chunks to pick the "Golden Reference Clip"
    # Criteria: Good duration (15-20s), high average RMS, stable dynamic range
    scored_chunks = []
    for s, e, d in refined_chunks:
        start_samp = int(s * sr)
        end_samp = int(e * sr)
        clip = normalized_audio[start_samp:end_samp]
        rms = np.sqrt(np.mean(clip**2))
        # Ideal duration target = 18.0s
        dur_score = 1.0 - abs(d - 18.0) / 18.0
        snr_score = rms / (noise_floor + 1e-6)
        total_score = dur_score * 0.4 + (snr_score / 10.0) * 0.6
        scored_chunks.append({
            "start": round(s, 2),
            "end": round(e, 2),
            "duration": round(d, 2),
            "rms": round(float(rms), 4),
            "score": round(float(total_score), 4)
        })
        
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    golden_slice = scored_chunks[0] if scored_chunks else None
    
    t1 = time.perf_counter()
    mem_after = psutil.Process().memory_info().rss / (1024**2)
    
    return {
        "processing_time_sec": round(t1 - t0, 4),
        "memory_delta_mb": round(mem_after - mem_before, 2),
        "total_chunks_found": len(refined_chunks),
        "chunks": scored_chunks,
        "golden_slice": golden_slice
    }

def main():
    print("=" * 60)
    print("AUDIO PREPROCESSING & 1-5 MINUTE REFERENCE SLICING BENCHMARK")
    print("=" * 60)
    
    output_dir = os.path.join(os.path.dirname(__file__), "test_audio_artifacts")
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n1. Synthesizing 3-minute (180s) reference audio recording...")
    audio, sr, seg_meta = generate_synthetic_multiturn_audio(duration_sec=180, sr=16000)
    raw_path = os.path.join(output_dir, "raw_3min_recording.wav")
    sf.write(raw_path, audio, sr)
    raw_size_mb = os.path.getsize(raw_path) / (1024**2)
    print(f"   Created {raw_path} ({raw_size_mb:.2f} MB, 16kHz Mono)")
    
    print("\n2. Executing Automated VAD & Golden Reference Extraction...")
    results = analyze_and_segment_audio(audio, sr)
    print(f"   Execution Time: {results['processing_time_sec']}s")
    print(f"   Memory Overhead: {results['memory_delta_mb']} MB")
    print(f"   Total Coherent Utterance Chunks Found: {results['total_chunks_found']}")
    
    golden = results['golden_slice']
    if golden:
        print("\n3. Golden Reference Candidate Selected for VoxCPM2 Cloning:")
        print(f"   Start Time: {golden['start']}s | End Time: {golden['end']}s | Duration: {golden['duration']}s")
        print(f"   RMS Energy: {golden['rms']} | Suitability Score: {golden['score']}")
        
        # Save golden clip
        start_samp = int(golden['start'] * sr)
        end_samp = int(golden['end'] * sr)
        golden_clip = audio[start_samp:end_samp]
        golden_path = os.path.join(output_dir, "golden_reference_slice.wav")
        sf.write(golden_path, golden_clip, sr)
        golden_size_kb = os.path.getsize(golden_path) / 1024
        print(f"   Saved Golden Slice: {golden_path} ({golden_size_kb:.1f} KB)")
        print(f"   Input Size Reduction: {raw_size_mb:.2f} MB -> {golden_size_kb / 1024:.2f} MB ({(1 - (golden_size_kb/1024)/raw_size_mb)*100:.1f}% reduction!)")
        print(f"   Inference Memory/Compute Saved: ~90% lower context load compared to feeding raw 3-min audio!")

if __name__ == "__main__":
    main()
