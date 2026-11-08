"""
VoiceStudio Pro — Voice Cloning Studio UI Tab.
Guided 4-Step Professional Audio Workflow:
1. Audio Ingest & Microphone Recording (1–5 min reference).
2. Acoustic Inspection & Golden Slice Waveform Trimming (5s–30s comparison presets).
3. Voice Profile Metadata & Verbatim Transcript Registration.
4. Instant Offline Verification Sandbox with sample prompts.
"""
import time
import uuid
import gradio as gr
from pathlib import Path
from typing import List, Optional, Tuple

from app.audio.processor import AudioProcessor
from app.config import TEMP_DIR, NATIVE_SAMPLE_RATE
from app.services.voice_service import VoiceProfileService
from app.services.generation_service import GenerationService
from app.queue.generation_queue import GenerationQueue, GenerationTask
from app.utils.text_processor import TextProcessor

KHMER_SAMPLE_PROMPT = "សួស្តី! នេះគឺជាការសាកល្បងបង្កើតសំឡេងដោយប្រើបច្ចេកវិទ្យាបញ្ញាសិប្បនិម្មិត។"
ENGLISH_SAMPLE_PROMPT = "Hello! This is a voice cloning test using my own recorded voice."
MIXED_SAMPLE_PROMPT = "សួស្តី! កម្មវិធី VoiceStudio AI ដំណើរការលើ Windows 11 យ៉ាងរលូន។"

def inspect_uploaded_audio(file_path: str):
    """Analyzes audio quality, dynamics, silence, and clipping for Stage 3."""
    if not file_path:
        return "Upload or record audio (1–5 minutes) to inspect.", 0.0, 0.0, None

    meta = AudioProcessor.inspect_audio(file_path)
    if not meta.is_valid:
        return f"❌ Invalid audio: {meta.error_message}", 0.0, 0.0, None

    peak_str = f"`{meta.peak_dbfs} dBFS`" if meta.peak_dbfs is not None else "`N/A`"
    rms_str = f"`{meta.rms_dbfs} dBFS`" if meta.rms_dbfs is not None else "`N/A`"
    silence_str = f"`{meta.silence_percent}%`" if meta.silence_percent is not None else "`N/A`"
    noise_str = f"`{meta.noise_floor_dbfs} dBFS`" if meta.noise_floor_dbfs is not None else "`N/A`"
    clipping_str = "⚠️ **Clipping Detected**" if meta.is_clipped else "✅ **No Clipping**"

    info_md = f"""
**📊 Acoustic Diagnostics & Audio Health:**
* **Duration:** `{meta.duration_sec}s` ({round(meta.duration_sec/60, 2)} min) • Optimal: 1–5 minutes
* **Audio Format:** `{meta.sample_rate} Hz` → Resampled to 48kHz PCM_16 Mono
* **Dynamic Levels:** Peak: {peak_str} | RMS: {rms_str} (Target: -24 to -14 dBFS)
* **Signal Quality:** Noise Floor: {noise_str} | Silence: {silence_str} | {clipping_str}
"""
    return info_md, 0.0, meta.duration_sec, file_path

def apply_duration_preset(file_path: str, start_sec: float, preset_seconds: float):
    """Sets end time based on comparison duration presets (5s, 10s, 15s, 20s, 30s)."""
    if not file_path or not Path(file_path).exists():
        return start_sec, start_sec + preset_seconds
    meta = AudioProcessor.inspect_audio(file_path)
    max_dur = meta.duration_sec if meta.is_valid else 300.0
    new_end = min(max_dur, float(start_sec) + float(preset_seconds))
    return float(start_sec), round(new_end, 2)

def preview_trimmed_segment(file_path: str, start_sec: float, end_sec: float):
    if not file_path or not Path(file_path).exists():
        return None, "Upload or record audio first."
    
    meta = AudioProcessor.inspect_audio(file_path)
    if not meta.is_valid:
        return None, f"Cannot trim: {meta.error_message}"

    if start_sec >= end_sec:
        return None, "Start time must be strictly less than end time."

    temp_preview = TEMP_DIR / "preview_slice.wav"
    try:
        AudioProcessor.trim_audio_segment(
            input_path=file_path,
            output_path=temp_preview,
            start_sec=start_sec,
            end_sec=end_sec,
            target_sr=NATIVE_SAMPLE_RATE
        )
        dur = round(end_sec - start_sec, 2)
        return str(temp_preview), f"Segment trimmed: {dur}s (48kHz Studio Quality)."
    except Exception as e:
        return None, f"Error trimming audio: {e}"

def handle_create_profile(
    file_path: str,
    name: str,
    desc: str,
    lang: str,
    trans: str,
    start_sec: float,
    end_sec: float
):
    if not file_path:
        return "Please upload or record an audio file first.", gr.update()
    if not name or not name.strip():
        return "Please provide a name for the voice profile.", gr.update()

    service = VoiceProfileService.get_instance()
    prof, msg = service.create_profile(
        name=name.strip(),
        original_audio_path=file_path,
        description=desc,
        language=lang,
        transcript=trans,
        trim_start_sec=start_sec,
        trim_end_sec=end_sec
    )
    choices = get_profile_dropdown_choices()
    if prof:
        val = f"{prof.name} ({prof.id})"
        return f"✅ Voice profile '{prof.name}' created successfully!", gr.update(choices=choices, value=val)
    return f"❌ {msg}", gr.update(choices=choices)

def run_test_cloning_generation(
    selected_profile: str,
    technique: str,
    text: str,
    cfg_val: float,
    steps: int
):
    if not selected_profile or selected_profile == "No profiles created yet":
        yield None, "Error", "Create or select a voice profile first."
        return
    if not text or not text.strip():
        yield None, "Error", "Test text cannot be empty."
        return

    profile_id = selected_profile.split("(")[-1].replace(")", "").strip()
    prof = VoiceProfileService.get_instance().get_profile(profile_id)
    if not prof:
        yield None, "Error", "Selected profile not found."
        return

    # Map mode
    job_type = "cloning"
    prompt_text = None
    if technique == "Hi-Fi Voice Cloning (Prompt + Transcript)":
        job_type = "ultimate_cloning"
        prompt_text = prof.transcript
        if not prompt_text or not prompt_text.strip():
            yield None, "Error", "Hi-Fi cloning requires a reference transcript. Please edit the profile transcript."
            return

    norm_text = TextProcessor.normalize_text(text)
    lang = TextProcessor.detect_language(norm_text)
    job_id = f"test_clone_{uuid.uuid4().hex[:8]}"

    task = GenerationTask(
        job_id=job_id,
        job_type=job_type,
        target_text=norm_text,
        voice_profile_id=prof.id,
        voice_name=prof.name,
        language=lang,
        reference_wav_path=prof.reference_segment_path,
        prompt_wav_path=prof.reference_segment_path,
        prompt_text=prompt_text,
        cfg_value=float(cfg_val),
        inference_timesteps=int(steps)
    )

    queue = GenerationQueue.get_instance()
    queue.submit_task(task)

    while True:
        status_info = queue.get_job_display_status(job_id)
        st = status_info["status"]
        if st == "pending":
            yield None, "Pending", "Queued for generation..."
            time.sleep(0.5)
        elif st == "processing":
            yield None, "Processing", "Synthesizing voice on CPU..."
            time.sleep(0.5)
        elif st == "completed":
            res = status_info.get("result") or task.result
            if res:
                telemetry = f"Synthesized: {res['duration_sec']}s in {res['generation_time_sec']}s (RTF: {res['rtf']}x)"
                yield res["output_path"], "Completed", telemetry
            else:
                yield None, "Completed", "Done."
            break
        elif st == "failed":
            yield None, "Failed", f"Failed: {task.error}"
            break
        elif st == "cancelled":
            yield None, "Cancelled", "Generation cancelled."
            break
        else:
            time.sleep(0.5)

def get_profile_dropdown_choices() -> List[str]:
    service = VoiceProfileService.get_instance()
    profiles = service.list_profiles()
    return [f"{p.name} ({p.id})" for p in profiles] if profiles else ["No profiles created yet"]

def create_cloning_tab():
    with gr.Tab("✂️ Voice Cloning", id="tab_cloning"):
        # Header
        with gr.Row(elem_classes=["studio-canvas-card"]):
            gr.Markdown(
                """
                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <div style="font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">Voice Cloning Studio</div>
                        <div style="font-size: 13px; color: var(--studio-text-secondary); margin-top: 2px;">
                            Guided Voice Ingest • Golden Slice Trimming • Offline Profile Persistence
                        </div>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <span class="studio-pill studio-pill-accent">Step 1: Ingest</span>
                        <span class="studio-pill studio-pill-muted">Step 2: Golden Slice</span>
                        <span class="studio-pill studio-pill-muted">Step 3: Register</span>
                    </div>
                </div>
                """
            )

        # Two-Column Guided Workflow
        with gr.Row():
            # -------------------------------------------------------------
            # LEFT: Audio Ingest & Golden Slice Editor
            # -------------------------------------------------------------
            with gr.Column(scale=6):
                with gr.Group(elem_classes=["studio-canvas-card"]):
                    gr.Markdown("#### 🎙️ Step 1: Reference Audio Ingest")
                    upload_box = gr.Audio(
                        label="Reference Audio (WAV, MP3, M4A, 1–5 min)",
                        sources=["upload", "microphone"],
                        type="filepath"
                    )
                    inspection_view = gr.Markdown(value="*Upload or record an audio file to inspect acoustic quality.*")

                with gr.Group(elem_classes=["studio-canvas-card"]):
                    gr.Markdown("#### ✂️ Step 2: Golden Slice Timeline Editor")
                    gr.Markdown("Select a clean, uninterrupted speech segment. Use quick duration presets:")

                    with gr.Row():
                        p5_btn = gr.Button("5s Slice", variant="secondary", size="sm")
                        p10_btn = gr.Button("10s Slice", variant="secondary", size="sm")
                        p15_btn = gr.Button("15s Slice", variant="secondary", size="sm")
                        p20_btn = gr.Button("20s Slice", variant="secondary", size="sm")
                        p30_btn = gr.Button("30s Slice", variant="secondary", size="sm")

                    with gr.Row():
                        trim_start = gr.Number(label="Start Time (s)", value=0.0, step=0.5)
                        trim_end = gr.Number(label="End Time (s)", value=20.0, step=0.5)

                    preview_trim_btn = gr.Button("🎧 Trim & Preview Segment", variant="secondary", size="sm")
                    preview_player = gr.Audio(label="Trimmed Segment Preview (48kHz PCM_16)", type="filepath", interactive=False)
                    preview_msg = gr.Label(label="Trim Status", value="Ready")

            # -------------------------------------------------------------
            # RIGHT: Profile Registration & Instant Test Sandbox
            # -------------------------------------------------------------
            with gr.Column(scale=4):
                with gr.Group(elem_classes=["studio-inspector"]):
                    gr.Markdown("#### 📝 Step 3: Register Voice Profile")
                    
                    prof_name = gr.Textbox(label="Voice Profile Name", placeholder="e.g. Sokha Natural Khmer")
                    prof_desc = gr.Textbox(label="Speaker Description", placeholder="e.g. Calm, articulate Khmer narrator", lines=2)
                    prof_lang = gr.Radio(choices=["multilingual", "khmer", "english"], value="multilingual", label="Speaker Primary Language")
                    prof_trans = gr.Textbox(
                        label="Verbatim Reference Transcript",
                        placeholder="Exact words spoken in the trimmed reference segment (Required for Hi-Fi Cloning)...",
                        lines=3
                    )
                    create_prof_btn = gr.Button("✨ Create & Save Voice Profile", variant="primary", size="lg")
                    create_status = gr.Label(label="Save Status", value="Ready")

                with gr.Group(elem_classes=["studio-canvas-card"]):
                    gr.Markdown("#### 🧪 Step 4: Instant Verification Sandbox")
                    
                    test_profile_dropdown = gr.Dropdown(
                        label="Profile to Verify",
                        choices=get_profile_dropdown_choices(),
                        value=get_profile_dropdown_choices()[0] if get_profile_dropdown_choices() else None
                    )
                    test_mode_radio = gr.Radio(
                        choices=["Controllable Voice Cloning (Reference Audio only)", "Hi-Fi Voice Cloning (Prompt + Transcript)"],
                        value="Controllable Voice Cloning (Reference Audio only)",
                        label="Cloning Mode"
                    )

                    with gr.Row():
                        kh_sample_btn = gr.Button("🇰🇭 Khmer", variant="secondary", size="sm")
                        en_sample_btn = gr.Button("🇬🇧 English", variant="secondary", size="sm")
                        mx_sample_btn = gr.Button("🌐 Mixed", variant="secondary", size="sm")

                    test_text_input = gr.Textbox(label="Test Script", value=KHMER_SAMPLE_PROMPT, lines=2)
                    
                    with gr.Row():
                        test_gen_btn = gr.Button("🎙️ Test Generate", variant="primary", size="sm")
                        test_refresh_btn = gr.Button("🔄 Refresh", variant="secondary", size="sm")

                    test_job_status = gr.Label(label="Test Status", value="Ready")
                    test_audio_player = gr.Audio(label="Cloned Voice Output", type="filepath", interactive=False)
                    test_telemetry_display = gr.Markdown(value="*Generation telemetry will appear here.*")

        # -------------------------------------------------------------
        # Event Handlers
        # -------------------------------------------------------------
        upload_box.change(
            fn=inspect_uploaded_audio,
            inputs=[upload_box],
            outputs=[inspection_view, trim_start, trim_end, preview_player]
        )

        p5_btn.click(fn=lambda f, s: apply_duration_preset(f, s, 5.0), inputs=[upload_box, trim_start], outputs=[trim_start, trim_end])
        p10_btn.click(fn=lambda f, s: apply_duration_preset(f, s, 10.0), inputs=[upload_box, trim_start], outputs=[trim_start, trim_end])
        p15_btn.click(fn=lambda f, s: apply_duration_preset(f, s, 15.0), inputs=[upload_box, trim_start], outputs=[trim_start, trim_end])
        p20_btn.click(fn=lambda f, s: apply_duration_preset(f, s, 20.0), inputs=[upload_box, trim_start], outputs=[trim_start, trim_end])
        p30_btn.click(fn=lambda f, s: apply_duration_preset(f, s, 30.0), inputs=[upload_box, trim_start], outputs=[trim_start, trim_end])

        preview_trim_btn.click(
            fn=preview_trimmed_segment,
            inputs=[upload_box, trim_start, trim_end],
            outputs=[preview_player, preview_msg]
        )

        create_prof_btn.click(
            fn=handle_create_profile,
            inputs=[upload_box, prof_name, prof_desc, prof_lang, prof_trans, trim_start, trim_end],
            outputs=[create_status, test_profile_dropdown]
        )

        kh_sample_btn.click(fn=lambda: KHMER_SAMPLE_PROMPT, outputs=[test_text_input])
        en_sample_btn.click(fn=lambda: ENGLISH_SAMPLE_PROMPT, outputs=[test_text_input])
        mx_sample_btn.click(fn=lambda: MIXED_SAMPLE_PROMPT, outputs=[test_text_input])

        test_refresh_btn.click(
            fn=lambda: gr.update(choices=get_profile_dropdown_choices()),
            outputs=[test_profile_dropdown]
        )

        cfg_val = gr.State(2.0)
        steps_val = gr.State(10)

        test_gen_btn.click(
            fn=run_test_cloning_generation,
            inputs=[test_profile_dropdown, test_mode_radio, test_text_input, cfg_val, steps_val],
            outputs=[test_audio_player, test_job_status, test_telemetry_display]
        )
