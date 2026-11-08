# VoiceStudio AI — System Architecture Document
**Version:** 0.4.0 (Stage 4 Long-Form Speech Studio & Cupertino UI)  
**Host Environment:** Windows 11 64-bit | Intel Core i5-1240P | Intel Iris Xe Graphics | 16GB RAM  
**Repository Location:** `D:\Coding\Rak'sTTS`  

---

## 1. High-Level Architecture Overview

VoiceStudio AI is designed as a local-only, decoupled desktop speech studio engineered around the constraints of modern foundation AI models running on consumer mobile CPU hardware without CUDA acceleration.

```mermaid
flowchart TD
    subgraph UI_Layer["User Interface Layer (Gradio 6.31 + Cupertino CSS)"]
        Browser["Local Web Browser<br>(http://127.0.0.1:7860)"]
        DashTab["Dashboard Tab"]
        TTSTab["Text-to-Speech Studio<br>(Standard TTS & Long-Form Studio)"]
        CloneTab["Cloning Studio Tab"]
        LibTab["Voice Library Tab"]
        HistTab["History Tab"]
        SetTab["Settings Tab"]
    end

    subgraph Service_Layer["Application Services Layer"]
        VoiceSvc["VoiceProfileService<br>• Profile CRUD & Trimming<br>• 4-Artifact Persistence<br>• Reference Replacement"]
        GenSvc["GenerationService<br>• Orchestration & WAV Writing"]
        LFService["LongformService<br>• Persistent Checkpoints & Resume<br>• Multi-Chunk Orchestration<br>• Consistent Speaker Timbre"]
        Chunker["SentenceAwareChunker<br>• Khmer '។' & Phrase Space Splitting<br>• English Sentence & Clause Boundary<br>• Punctuation Pause Tuning"]
        Stitcher["AudioStitcher<br>• Raised-Cosine De-Clicking<br>• Crossfading & Inter-Sentence Pauses<br>• Dual WAV/MP3 320k Export"]
        AudioProc["AudioProcessor<br>• Acoustic Inspection<br>• 48kHz Mono Resampling<br>• Non-Destructive Slicing"]
    end

    subgraph Queue_Layer["Asynchronous Concurrency Control"]
        GenQueue["GenerationQueue (FIFO Worker)<br>• Single-Inference Concurrency Lock<br>• Cancellation & Memory Hygiene<br>• Job Progress Tracking"]
    end

    subgraph Engine_Layer["Decoupled AI Engine Layer"]
        Adapter["VoxCPM2Adapter (implements BaseTTSEngine)<br>• generate_tts()<br>• generate_voice_cloning()<br>• generate_ultimate_cloning()"]
        ModelMgr["ModelManager (Singleton)<br>• Thread Capping (4 Threads)<br>• Memory Reuse & OOM Safeguards"]
        VoxCPM["Official OpenBMB VoxCPM2<br>• MiniCPM-4 Backbone<br>• CFM Diffusion DiT<br>• AudioVAE V2 (48kHz)"]
    end

    subgraph Storage_Layer["Local Storage Layer (Drive D:)"]
        SQLite["SQLite Database<br>(voicestudio.db v2 with WAL)"]
        VoiceDir["storage/voices/<id>/<br>• original.wav<br>• reference.wav<br>• transcript.txt<br>• metadata.json"]
        GenDir["storage/generated/YYYYMMDD/<br>(48kHz PCM_16 WAV)"]
        LFDir["storage/longform/<job_id>/<br>• chunks/chunk_*.wav<br>• full_audio.wav<br>• full_audio.mp3"]
        ModelDir["models/VoxCPM2/<br>(4.62 GB Safetensors & VAE)"]
    end

    Browser --> UI_Layer
    UI_Layer --> Service_Layer
    Service_Layer --> GenQueue
    GenQueue --> Engine_Layer
    Engine_Layer --> VoxCPM
    Service_Layer --> Storage_Layer
    Engine_Layer --> Storage_Layer
```

---

## 2. Component Design & Responsibilities

### 2.1 Model Manager (`app/engines/model_manager.py`)
* **Singleton Lifecycle:** Manages a single cached instance of `openbmb/VoxCPM2`.
* **Thread Capping:** Restricts PyTorch intra-op parallelism to **4 threads** (`torch.set_num_threads(4)`), reserving the remaining 8 threads and E-cores for Windows OS tasks, browser responsiveness, and thermal stability.
* **Cold Load Latency:** Loads weights in **21–25 seconds** from Drive D: NVMe SSD.
* **Memory Management:** Keeps model loaded in RAM (~5.65 to 6.3 GB) across requests to eliminate repetitive load latency, with explicit manual unload capability if memory is required for other applications.

### 2.2 TTS Runtime Adapter (`app/engines/voxcpm_adapter.py`)
* **Decoupled Interface:** Inherits from `BaseTTSEngine`, isolating official `voxcpm` library calls behind generic `generate_tts`, `generate_voice_cloning`, and `generate_ultimate_cloning` methods.
* **Controllable Voice Cloning Mode:** Calls `model.generate(text=..., reference_wav_path=...)` using reference audio timbre without requiring a transcript.
* **Hi-Fi / Ultimate Voice Cloning Mode:** Calls `model.generate(text=..., prompt_wav_path=..., prompt_text=..., reference_wav_path=...)` using reference audio paired with its verbatim transcript for enhanced fidelity.
* **Output Format:** Extracts native 48kHz audio array directly from AudioVAE V2 and formats uncompressed 16-bit PCM WAV files (`PCM_16`).

### 2.3 Audio Processor (`app/audio/processor.py`)
* **Non-Destructive Design:** Uploaded reference recordings are preserved in their pristine original format.
* **Acoustic Quality Inspection:** Analyzes audio before cloning, measuring peak level (`dBFS`), RMS loudness (`dBFS`), silence percentage, sample clipping detection ($\ge 0.999$), and noise floor estimation.
* **Safe Normalization:** Converts audio into standardized 48kHz mono 16-bit PCM with peak normalization to -1.0 dBFS.

### 2.4 Voice Profile Service (`app/services/voice_service.py`)
* **4-Artifact Persistence:** Each profile directory in `storage/voices/<id>/` strictly persists:
  1. `original.wav`: Complete unedited source upload/recording
  2. `reference.wav`: Clean 48kHz 16-bit PCM reference segment
  3. `transcript.txt`: Verbatim text transcript of the reference slice
  4. `metadata.json`: Complete profile parameters, timestamps, and audio metrics
* **Dynamic Reference Replacement:** `replace_reference_audio` allows updating source audio and re-extracting reference slices without breaking existing profile IDs or historical references.

### 2.5 Sentence-Aware Chunker (`app/utils/chunker.py`)
* **Khmer-Aware Segmentation:** Breaks on Khmer Khan (`។`), Bariyoosan (`៕`), and phrase spaces while preserving syllable cluster integrity.
* **English Segmentation:** Breaks on sentences (`.`, `!`, `?`) and secondary clauses (`,`, `;`, `:`).
* **Length Budgeting:** Keeps chunks within optimal 60–140 character targets to prevent diffusion collapse or attention degradation.
* **Pause Annotation:** Dynamically assigns inter-chunk pauses (180ms to 500ms) based on terminal punctuation.

### 2.6 Audio Stitcher & Dual Exporter (`app/audio/stitcher.py`)
* **De-Clicking:** Applies raised-cosine (Hann) fade-in/out windows (10ms) at chunk boundaries.
* **Seamless Concatenation:** Merges chunks with calculated inter-sentence pauses.
* **Dual Export:** Writes studio-quality uncompressed 48kHz 16-bit PCM WAV (`full_audio.wav`) and high-bitrate 320kbps MP3 (`full_audio.mp3`) via system FFmpeg.

### 2.7 Long-Form Service (`app/services/longform_service.py`)
* **Persistent Checkpointing:** Each completed chunk is saved immediately to disk and SQLite.
* **Resume Capability:** If execution pauses or fails, synthesis seamlessly resumes from the next unfinished chunk without re-generating completed audio.
* **Memory Hygiene:** Explicit garbage collection (`gc.collect()`) runs between chunk boundaries.
* **Consistent Speaker Conditioning:** Carries the same voice profile reference audio latents across all chunks to maintain stable timbre across long chapters.

### 2.8 Cupertino iPhone-Inspired Design Theme (`app/ui/styles.py`)
* **Typography & Surfaces:** SF Pro / Inter typography stack, frosted glass backdrop filters, subtle translucent borders, and soft 16px corner radii.
* **Pill Segmented Controls:** Cupertino-style tab controls, pill action buttons, and clean telemetry cards.

### 2.9 Database & Storage Architecture (`app/database/`)
* **SQLite with WAL Mode (Schema v2):** Fast, zero-lock concurrency using Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) and 30-second busy timeout.
* **Tables:** `voice_profiles`, `generations`, `jobs`, `longform_jobs`, `longform_chunks`, and `settings`.
* **Separation of Concerns:** Binary WAV and MP3 files reside strictly on the local filesystem (`D:\Coding\Rak'sTTS\storage\`), while metadata and progress state are tracked in SQLite.
