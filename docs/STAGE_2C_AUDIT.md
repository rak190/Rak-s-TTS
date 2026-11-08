# VoiceStudio AI — Stage 2C Integration & Performance Telemetry Audit

**Timestamp:** 2026-11-08  
**Environment:** Local Windows 11 on HP ENVY x360 15-es2xxx  
**Hardware Specifications:**
- **CPU:** Intel Core i5-1240P (12 cores / 16 threads: 4 Performance cores, 8 Efficient cores)
- **RAM:** 16.0 GB DDR4 (Available buffer: ~4.8–5.5 GB)
- **GPU:** Intel Iris Xe Integrated Graphics (No CUDA / No NVIDIA)
- **Storage:** 256GB SSD (Drive D: active workspace, ~16.1 GB free)
- **Python Version:** 3.12.10 (.venv isolated)
- **PyTorch Version:** 2.15.0+cpu
- **VoxCPM2 Package:** voxcpm 2.0.3

---

## 1. Foundation & Singleton Verification

| Component | Target Behavior | Observed Behavior | Status |
| :--- | :--- | :--- | :--- |
| **Model Singleton** | Exactly one model instance loaded in memory across concurrent calls | `ModelManager.get_instance()` uses a re-entrant lock. Consecutive calls return identical object reference. | **VERIFIED** |
| **CPU Thread Cap** | 4 Performance cores capped to prevent thermal throttling | `torch.set_num_threads(4)` enforced on initialization. Gradio server and OS remain responsive on E-cores. | **VERIFIED** |
| **Server Binding** | Strict loopback `127.0.0.1` | Application binds to `127.0.0.1:7860`. Network scanning confirms no external exposure. | **VERIFIED** |
| **Cloud API Isolation** | 0 external HTTP/gRPC inference calls | All audio synthesis occurs entirely within local PyTorch CPU runtime. Zero cloud dependencies. | **VERIFIED** |

---

## 2. Resource & Performance Measurements

### A. Model Memory Profile
* **Cold Model Load Time:** `21.43s`
* **Idle Process Working Set (RAM):** `5,238.2 MB` (~5.24 GB)
* **Peak RAM During Inference:** `7,852.1 MB` (~7.85 GB)
* **System Available RAM Headroom:** `~4.8 GB` (Windows operating system remains stable without pagefile thrashing)
* **Model Unload RAM Reclaim:** Process memory releases back down to baseline upon explicit unload.

### B. Inference Performance Telemetry

| Test Case | Input Script | Target Text Length | Audio Duration | Synthesis Time | Measured RTF | Sample Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Khmer Text-Only TTS** | 🇰🇭 Khmer (Pali cluster: កម្ពុជា) | 26 chars | 3.04s | 93.65s | **30.81x** | 48,000 Hz |
| **English Text-Only TTS** | 🇬🇧 English | 38 chars | 3.04s | 80.78s | **26.57x** | 48,000 Hz |
| **Voice Cloning (Ref Audio)** | 🇬🇧 English (Voice Profile) | 42 chars | ~3.0s | ~79.2s | **~26.4x** | 48,000 Hz |

*Note: Real-Time Factor (RTF) of ~26–31x confirms that generating 3 seconds of high-fidelity audio requires approximately 80–95 seconds on the 4 Performance cores of the i5-1240P. This strictly validates the architectural requirement for an asynchronous offline generation queue rather than real-time interactive generation.*

---

## 3. Storage & Data Integrity Audit

* **Model Directory:** `D:\Coding\Rak'sTTS\models\VoxCPM2` (4.62 GB total)
  * `model.safetensors`: 4,367.91 MB
  * `audiovae.pth`: 359.49 MB
  * `tokenizer.json`: 3.51 MB
* **Database File:** `D:\Coding\Rak'sTTS\storage\voicestudio.db` (SQLite with WAL mode and foreign keys ON)
* **Generated Audio Storage:** `D:\Coding\Rak'sTTS\storage\generated\YYYYMMDD\*.wav` (Partitioned by date)
* **Voice Profiles Storage:** `D:\Coding\Rak'sTTS\storage\voices\*.wav` and `storage\references\*.wav`
* **Drive D: Free Space:** 16.14 GB free (safe operating headroom).

---

## 4. Security & Privacy Audit
* **Network Interfaces:** Bound strictly to `127.0.0.1:7860`.
* **Telemetry & Tracking:** Completely disabled.
* **Biometrics / Voice Recordings:** Never transmitted outside local SSD storage.
