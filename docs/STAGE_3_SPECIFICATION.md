<USER_REQUEST>
# VOICESTUDIO AI — STAGE 3
# Complete Voice Cloning Studio & Reference Audio Management

## ROLE

Act as a Senior AI Speech Engineer, Python Software Architect, Audio Processing Engineer, Gradio Developer, and QA Engineer.

You are continuing the existing VoiceStudio AI application after Stage 2A and Stage 2B.

Your responsibility is to implement a complete, reliable, and user-friendly Voice Cloning Studio using the existing application architecture and the validated VoxCPM2 CPU runtime.

This is an implementation task, not just a research or planning task.

However, you MUST inspect the existing repository and verify the Stage 2 prerequisites before modifying any code.

---

# 1. PROJECT CONTEXT

Project: VoiceStudio AI

Deployment: Local Windows 11

Hardware:
- Intel Core i5-1240P
- Intel Iris Xe Graphics
- 16 GB RAM
- No NVIDIA GPU
- No CUDA

Application Stack:
- Python 3.12
- Gradio
- SQLite
- Local file storage
- FFmpeg
- SoundFile
- Official VoxCPM2 PyTorch CPU runtime

Primary AI Model:
https://github.com/OpenBMB/VoxCPM

Official API:
https://voxcpm.readthedocs.io/en/latest/reference/api.html

Official Usage Guide:
https://voxcpm.readthedocs.io/en/latest/usage_guide.html

Expected operating conditions:
- CPU-only inference
- Single model instance
- One inference job at a time
- Asynchronous offline generation
- Khmer and English speech synthesis
- Reference-based voice cloning

The application must remain fully local.

Do not introduce:
- Cloud GPU services
- Paid APIs
- Supabase
- Cloudflare R2
- Public deployment
- Unnecessary external services

Do not replace the validated VoxCPM2 runtime unless a verified technical blocker exists.

---

# 2. CRITICAL RULE — INSPECT BEFORE MODIFYING

Before making changes:

1. Inspect the entire current project structure.
2. Read the existing README and architectural documentation.
3. Identify all Stage 2A and Stage 2B implementations.
4. Locate the existing Model Manager.
5. Locate the TTS Runtime Adapter.
6. Inspect the SQLite schema.
7. Inspect the Voice Profile Manager.
8. Inspect the existing Gradio UI.
9. Inspect the job queue.
10. Identify all working features and incomplete implementations.
11. Check the actual VoxCPM2 Python API available in the installed environment.
12. Identify any pending problems from previous stages.

Create a Git checkpoint before implementation.

IMPORTANT:

Do not rebuild existing working features unnecessarily.

Do not replace the current UI framework.

Do not change the existing design concept or navigation structure.

Do not introduce duplicate services, databases, runtime managers, or independent model instances.

Extend the existing application incrementally.

If critical Stage 2B prerequisites are missing, implement only the minimum necessary corrections before continuing.

Explain any prerequisite fixes in the final report.

---

# 3. STAGE 3 OBJECTIVES

Implement a complete workflow:

1. Upload or record reference audio.
2. Validate audio quality and format.
3. Preserve the original recording.
4. Preview the waveform and recording.
5. Select an appropriate reference segment.
6. Create and save a reusable Voice Profile.
7. Select a Voice Cloning Mode.
8. Enter Khmer or English text.
9. Generate speech using the selected voice.
10. Preview and download generated audio.
11. Save generation history.
12. Reuse voice profiles without uploading the recording again.

The application must perform real inference using VoxCPM2.

Do not implement simulated or fake voice cloning.

---

# 4. VOICE CLONING STUDIO — USER INTERFACE

Create or complete the existing Voice Cloning Studio page.

Preserve the current application's visual identity.

The page should include:

## Section A — Audio Source

Allow users to choose between:

- Upload Audio
- Record from Microphone
- Select Existing Recording

Supported upload formats:
- WAV
- MP3
- M4A

Target recording duration:
- 1 to 5 minutes

Validate the file before processing.

Display:
- File name
- Duration
- Sample rate
- Channel count
- File size
- Validation status

Provide friendly error messages in the UI.

## Section B — Audio Preview

Implement:
- Audio playback
- Waveform visualization
- Timeline
- Selected start time
- Selected end time
- Selected duration
- Play selected segment
- Reset selection

Users must be able to listen to the reference before saving it.

## Section C — Audio Quality Information

Provide practical quality indicators:

- Audio duration
- Silence percentage
- Clipping detection
- Peak level
- Approximate loudness
- Possible background noise

Clearly distinguish measured indicators from heuristic quality estimates.

Do not claim to measure voice similarity at this stage.

Do not automatically delete low-quality recordings.

Show a warning and allow the user to choose another segment.

---

# 5. REFERENCE AUDIO PROCESSING

Build a reliable preprocessing pipeline.

Requirements:

1. Preserve original audio.
2. Validate file integrity.
3. Decode audio using FFmpeg or another existing validated decoder.
4. Convert to the model-required sample rate.
5. Convert to mono only when appropriate.
6. Detect silence.
7. Detect clipping.
8. Allow manual segment extraction.
9. Save the selected reference segment.
10. Preserve metadata.

Do not overwrite the original file.

Avoid destructive normalization or aggressive noise reduction.

Noise reduction should be optional.

Do not automatically assume that a 15–20 second Golden Slice is optimal.

Implement a flexible reference selection process.

Suggested experimental durations:
- 5 seconds
- 10 seconds
- 15 seconds
- 20 seconds
- 30 seconds

These are comparison presets, not guarantees of optimal cloning quality.

Check actual model requirements before enforcing reference duration restrictions.

Do not automatically use the entire 1–5 minute recording as the prompt for every inference call.

---

# 6. VOICE CLONING MODES

Implement both supported VoxCPM2 cloning modes.

## Mode A — Controllable Voice Cloning

Goal:
Clone the speaker's vocal timbre from reference audio without requiring a transcript.

Use the official reference-based cloning API.

Expected API pattern:

model.generate(
    text=target_text,
    reference_wav_path=reference_path
)

Verify the exact method signature and installed package version before implementation.

Supported features:
- Reference audio
- Target text
- Voice similarity
- Optional supported style instructions

Do not expose unsupported controls.

## Mode B — Hi-Fi / Ultimate Voice Cloning

Goal:
Achieve higher voice fidelity using reference audio and its exact transcript.

Expected API pattern:

model.generate(
    text=target_text,
    prompt_wav_path=prompt_audio_path,
    prompt_text=exact_transcript,
    reference_wav_path=reference_path
)

Requirements:
- Accurate prompt transcript
- Reference audio
- Transcript editor
- Transcript validation
- Clear explanation of the mode

Do not automatically assume the transcript is correct.

Allow manual editing.

If the reference segment changes, clearly indicate that the transcript must match the new segment.

Do not allow a mismatched transcript to be silently reused.

IMPORTANT:

The reference-only cloning mode and Hi-Fi cloning mode must share the same underlying singleton model instance.

Do not load VoxCPM2 twice.

---

# 7. TRANSCRIPT MANAGEMENT

Implement a transcript editor.

Features:
- Enter transcript manually.
- Edit transcript.
- Save transcript with the selected reference segment.
- Support Khmer Unicode.
- Support English.
- Support mixed Khmer-English transcripts.
- Preview associated reference audio.

Automatic transcription may be investigated, but do not make Stage 3 dependent on an additional large ASR model.

On this 16 GB RAM laptop, avoid loading an ASR model alongside VoxCPM2 unless memory use is measured and safe.

Manual transcripts must be supported even if automatic transcription is unavailable.

Do not use paid transcription services.

---

# 8. VOICE PROFILE MANAGEMENT

Extend the existing Voice Profile Manager.

Each profile should contain:

- Unique Voice Profile ID
- Voice name
- Description
- Original audio path
- Selected reference audio path
- Transcript path or text
- Language metadata
- Preferred cloning mode
- Creation date
- Last updated date
- Profile status

Supported actions:

1. Create Voice Profile.
2. Open Voice Profile.
3. Edit Voice Profile.
4. Rename Voice Profile.
5. Replace Reference Audio.
6. Change Reference Segment.
7. Edit Transcript.
8. Preview Reference Audio.
9. Delete Voice Profile with confirmation.

When replacing audio, prevent accidental deletion of unrelated files.

When deleting a profile, clearly handle existing generated audio associated with that profile.

Use the existing SQLite database.

Add proper migrations when schema changes are necessary.

Do not reset or destroy existing data.

Use relative or configurable file paths where practical.

Do not store large WAV binaries directly in SQLite.

---

# 9. VOICE CLONING TEST GENERATION

Add a test generation area to the Voice Cloning Studio.

Inputs:
- Selected Voice Profile
- Cloning Mode
- Language
- Target Text

Language options:
- Khmer
- English
- Mixed (Experimental)

Provide sample text.

Khmer example:

"សួស្តី! នេះគឺជាការសាកល្បងបង្កើតសំឡេងដោយប្រើបច្ចេកវិទ្យាបញ្ញាសិប្បនិម្មិត។"

English example:

"Hello! This is a voice cloning test using my own recorded voice."

Generate real audio using VoxCPM2.

Display:
- Generation status
- Queue position where available
- Processing time
- Output duration
- Audio player
- Download WAV
- Save to History

The selected Voice Profile must be used in inference.

Do not generate a generic voice while presenting it as cloned output.

---

# 10. CPU PERFORMANCE REQUIREMENTS

The validated hardware is CPU-only and significantly slower than real time.

The previous benchmark reported approximately 25–37x RTF.

Do not promise real-time generation.

Requirements:

1. Reuse the loaded VoxCPM2 model.
2. Enforce one inference job at a time.
3. Integrate with the existing asynchronous job queue.
4. Keep the UI responsive.
5. Show meaningful job status.
6. Provide elapsed time.
7. Provide safe cancellation where technically supported.
8. Prevent simultaneous memory-intensive operations.
9. Release unnecessary tensors and temporary buffers.
10. Record RAM usage and inference time.

Do not use a fake progress percentage.

If exact inference progress is unavailable, show:
- Queued
- Loading
- Processing
- Saving
- Completed
- Failed

Implement safe cancellation without corrupting the application state.

Do not introduce another TTS model for preview generation.

---

# 11. LOCAL STORAGE AND DATA INTEGRITY

Use the existing application storage structure.

Recommended organization:

storage/
  voices/
    profile_id/
      original.wav
      reference.wav
      transcript.txt
      metadata.json

  generated/
    generation_id.wav

  temp/

Do not create duplicate directories if equivalent structures already exist.

Requirements:

- Unique file identifiers
- Safe filename handling
- Correct UTF-8 support
- Reliable paths on Windows
- Atomic writes when possible
- Temporary file cleanup
- File existence validation
- Database/file consistency

All processing must remain local.

Do not upload voice recordings, transcripts, or generated audio to external services.

---

# 12. UI/UX DESIGN REQUIREMENTS

Preserve the existing VoiceStudio AI design concept.

Do not redesign the application from scratch.

Improve only the components needed for Stage 3.

The workflow should be understandable without technical knowledge.

Suggested flow:

STEP 1: Upload or Record Voice
STEP 2: Preview and Select Reference
STEP 3: Enter Transcript (Optional)
STEP 4: Save Voice Profile
STEP 5: Test Voice Cloning
STEP 6: Play and Download Audio

Design requirements:

- Consistent spacing
- Clear labels
- Responsive layout
- Proper Khmer font rendering
- Clear error and success messages
- Disabled controls when prerequisites are missing
- Loading indicators
- Audio player
- Waveform preview
- Confirmation before destructive actions

Do not add decorative animations that reduce performance.

Do not implement nonfunctional buttons.

---

# 13. TESTING REQUIREMENTS

Create automated unit tests and real integration tests.

## A. Audio Upload Tests

Test:
- Valid WAV
- Valid MP3
- Valid M4A
- Corrupted files
- Unsupported formats
- Empty files
- Invalid duration
- Large files

## B. Audio Processing Tests

Test:
- Mono conversion
- Resampling
- Silence detection
- Segment extraction
- Segment duration
- Original audio preservation

## C. Voice Profile Tests

Test:
- Create
- Read
- Update
- Delete
- Rename
- Replace reference
- Persist after restart
- Maintain database consistency

## D. Voice Cloning Tests

Test:
- Khmer reference-based cloning
- English reference-based cloning
- Khmer Hi-Fi cloning
- English Hi-Fi cloning
- Cross-language generation
- Missing transcript handling
- Invalid reference paths
- Repeated generation

Use only authorized voice recordings.

## E. Performance Tests

Measure:
- Model loading time
- Peak RAM
- Generation time
- RTF
- Repeated generation stability

Do not report invented results.

## F. End-to-End Tests

Verify the complete workflow:

Upload Audio
→ Process Audio
→ Select Reference
→ Create Voice Profile
→ Select Cloning Mode
→ Enter Text
→ Generate Speech
→ Play Audio
→ Download WAV
→ Restart Application
→ Reuse Saved Voice Profile

All critical steps must be tested on the actual hardware.

---

# 14. IMPORTANT RESTRICTIONS

DO NOT:

- Replace the existing application architecture unnecessarily.
- Change the current UI design concept.
- Create another model manager.
- Load two VoxCPM2 instances.
- Replace the CPU runtime with an untested GGUF runtime.
- Introduce cloud dependencies.
- Implement LoRA fine-tuning.
- Add video dubbing.
- Add real-time voice conversion.
- Implement unsupported voice controls.
- Claim voice cloning quality is perfect.
- Claim 100% completion without testing.
- Delete Stage 2A benchmark results.
- Reset the SQLite database.
- Generate fake audio previews.

Implement Stage 3 using real model inference and actual file processing.

---

# 15. REQUIRED FINAL REPORT

After implementation, provide a detailed Stage 3 report containing:

1. Stage 2 prerequisite verification.
2. Existing architecture findings.
3. Files created.
4. Files modified.
5. Database migrations.
6. Voice Cloning Studio features implemented.
7. Controllable Cloning integration results.
8. Hi-Fi Cloning integration results.
9. Audio preprocessing results.
10. Voice Profile persistence results.
11. Khmer test results.
12. English test results.
13. Cross-language test results.
14. CPU performance observations.
15. Automated test results.
16. End-to-end test results.
17. Remaining bugs and limitations.
18. Any features deferred to Stage 4.
19. Overall status: PASS, CONDITIONAL PASS, or FAIL.

Include supporting test evidence and generated sample paths.

Do not mark a feature as complete merely because its UI exists.

---

# 16. EXECUTION STRATEGY

Implement in this order:

PHASE 3A:
Audit existing project and fix critical prerequisites.

PHASE 3B:
Audio upload, recording, processing, and reference selection.

PHASE 3C:
Voice Profile creation and persistence.

PHASE 3D:
Controllable and Hi-Fi Cloning integration.

PHASE 3E:
UI workflow integration.

PHASE 3F:
Real model testing, regression testing, and final audit.

Commit changes at logical milestones.

Do not proceed past unresolved critical blockers.

The final result must be a functional, stable, local Voice Cloning Studio that reuses the existing VoiceStudio AI application.

The priority is correctness, maintainability, and real voice cloning quality—not simply a polished UI.
</USER_REQUEST>
<ADDITIONAL_METADATA>
The current local time is: 2026-11-08T13:25:28+07:00.
</ADDITIONAL_METADATA>