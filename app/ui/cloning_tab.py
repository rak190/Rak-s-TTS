"""Voice Cloning Studio UI tab implementing Stage 3 comprehensive workflow."""
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
### 📊 Audio Quality & Acoustic Inspection:
| Metric | Measured Value | Guidance / Status |
| :--- | :--- | :--- |
| **Duration** | `{meta.duration_sec}s` ({round(meta.duration_sec/60, 2)} min) | Optimal: 1–5 minutes reference recording |
| **Sample Rate** | `{meta.sample_rate} Hz` | Will be standardized to 48kHz PCM_16 |
| **Channels** | `{meta.channels} ({'Mono' if meta.channels == 1 else 'Stereo'})` | Multi-channel is downmixed to clean mono |
| **Peak Level** | {peak_str} | Target: -3.0 dBFS to -0.5 dBFS |
| **Loudness (RMS)**| {rms_str} | Target: -24 dBFS to -14 dBFS |
| **Silence Ratio** | {silence_str} | High silence (>40%) may dilute reference timbre |
| **Noise Floor** | {noise_str} | Estimated background noise level |
| **Clipping** | {clipping_str} | Digital distortion check |
| **Health Notes**| `{meta.quality_notes}` | Pre-inference acoustic profile |

*💡 Tip: Use the full recording, or select a clean 10–25s "golden slice" below.*
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
        name=name,
        original_audio_path=file_path,
        description=desc,
        language=lang,
        transcript=trans,
        trim_start_sec=start_sec,
        trim_end_sec=end_sec
    )
    if prof:
        choices = [f"{p.name} ({p.id})" for p in service.list_profiles()]
        return f"✅ {msg} (Profile ID: {prof.id})", gr.update(choices=choices, value=f"{prof.name} ({prof.id})")
    return f"❌ {msg}", gr.update()

def run_test_cloning_generation(
    selected_profile: str,
    mode: str,
    target_text: str,
    cfg_value: float,
    timesteps: int
):
    """Executes a real voice cloning test directly within the Cloning Studio."""
    if not target_text or not target_text.strip():
        yield None, "Error: Target text cannot be empty.", "Enter sample text above."
        return

    if not selected_profile or selected_profile == "No profiles created yet":
        yield None, "Error: Select or create a Voice Profile first.", "No voice profile selected."
        return

    profile_id = selected_profile.split("(")[-1].replace(")", "").strip()
    prof = VoiceProfileService.get_instance().get_profile(profile_id)
    if not prof:
        yield None, "Error: Selected voice profile not found.", "Profile lookup failed."
        return

    norm_text = TextProcessor.normalize_text(target_text)
    lang = TextProcessor.detect_language(norm_text)

    # Determine cloning mode
    if mode == "Hi-Fi Voice Cloning (Prompt + Transcript)":
        if not prof.transcript or not prof.transcript.strip():
            yield None, "Error: Hi-Fi Voice Cloning strictly requires a verbatim transcript. Edit transcript in Voice Library or switch to Controllable Cloning.", "Transcript required for Hi-Fi."
            return
        job_type = "ultimate_cloning"
    else:
        job_type = "cloning"

    job_id = f"job_clone_test_{uuid.uuid4().hex[:8]}"
    task = GenerationTask(
        job_id=job_id,
        job_type=job_type,
        target_text=norm_text,
        voice_profile_id=prof.id,
        voice_name=prof.name,
        language=lang,
        reference_wav_path=prof.reference_segment_path,
        prompt_wav_path=prof.reference_segment_path,
        prompt_text=prof.transcript,
        cfg_value=float(cfg_value),
        inference_timesteps=int(timesteps)
    )

    queue = GenerationQueue.get_instance()
    queue.submit_task(task)

    while True:
        status_info = queue.get_job_display_status(job_id)
        st = status_info["status"]
        badge = status_info["badge"]
        msg = status_info["message"]

        if st == "pending":
            yield None, badge, f"⏳ {msg}..."
            time.sleep(0.5)
        elif st == "processing":
            yield None, badge, f"⚙️ {msg} (Synthesizing on CPU...)"
            time.sleep(0.5)
        elif st == "completed":
            res = status_info.get("result") or task.result
            if res:
                telemetry_md = f"""
### 📊 Voice Cloning Telemetry:
* **Target Voice:** `{prof.name}`
* **Cloning Mode:** `{mode}`
* **Audio Duration:** `{res['duration_sec']}s`
* **Synthesis Time:** `{res['generation_time_sec']}s`
* **Real-Time Factor (RTF):** `{res['rtf']}x`
* **Sample Rate:** `{res['sample_rate']} Hz (Studio Quality)`
* **Output Path:** `{res['output_path']}`
"""
                status_msg = f"✅ Voice cloning complete! ({res['duration_sec']}s audio in {res['generation_time_sec']}s)"
                yield res['output_path'], status_msg, telemetry_md
            else:
                yield None, "✅ Completed", "Synthesis complete."
            break
        elif st == "failed":
            err = status_info.get("error_message") or task.error or "Unknown error"
            yield None, "❌ Failed", f"### ❌ Cloning Failed\n\n`{err}`"
            break
        elif st == "cancelled":
            yield None, "🚫 Cancelled", "Generation cancelled."
            break
        else:
            time.sleep(0.5)

def get_profile_dropdown_choices() -> List[str]:
    service = VoiceProfileService.get_instance()
    profiles = service.list_profiles()
    return [f"{p.name} ({p.id})" for p in profiles] if profiles else ["No profiles created yet"]

def create_cloning_tab():
    with gr.Tab("✂️ Voice Cloning Studio", id="tab_cloning"):
        gr.Markdown("## 🎙️ Voice Cloning Studio & Reference Audio Management")
        gr.Markdown(
            "Upload or record reference speech (1–5 minutes), inspect acoustic quality, "
            "select an optimal reference slice, and save a reusable Voice Profile for offline cloning."
        )

        # -------------------------------------------------------------
        # STEP 1 & 2: Audio Source & Acoustic Quality Inspection
        # -------------------------------------------------------------
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Step 1: Audio Source (Upload or Microphone)")
                upload_box = gr.Audio(
                    label="Reference Audio (WAV, MP3, M4A, 1–5 min)",
                    sources=["upload", "microphone"],
                    type="filepath"
                )
                inspection_view = gr.Markdown(value="Upload or record an audio file to inspect acoustic quality.")

            with gr.Column(scale=1):
                gr.Markdown("### Step 2: Reference Segment Trimming (Optional)")
                gr.Markdown("Select a clean, continuous speech segment. Use comparison presets or customize:")

                with gr.Row():
                    p5_btn = gr.Button("5s Slice", variant="secondary")
                    p10_btn = gr.Button("10s Slice", variant="secondary")
                    p15_btn = gr.Button("15s Slice", variant="secondary")
                    p20_btn = gr.Button("20s Slice", variant="secondary")
                    p30_btn = gr.Button("30s Slice", variant="secondary")

                with gr.Row():
                    trim_start = gr.Number(label="Start Time (seconds)", value=0.0, step=0.5)
                    trim_end = gr.Number(label="End Time (seconds)", value=20.0, step=0.5)

                preview_trim_btn = gr.Button("🎧 Trim & Preview Segment", variant="secondary")
                preview_player = gr.Audio(label="Trimmed Segment Preview (48kHz PCM_16)", type="filepath")
                preview_msg = gr.Label(label="Trim Status", value="Ready")

        gr.Markdown("---")

        # -------------------------------------------------------------
        # STEP 3: Voice Profile Creation & Metadata
        # -------------------------------------------------------------
        gr.Markdown("### Step 3: Voice Profile Metadata & Persistence")
        with gr.Row():
            with gr.Column(scale=1):
                prof_name = gr.Textbox(label="Voice Profile Name (Required)", placeholder="e.g. Sokha Natural Voice")
                prof_desc = gr.Textbox(label="Description", placeholder="e.g. Articulate, calm Khmer documentary speaker", lines=2)
                prof_lang = gr.Radio(choices=["multilingual", "khmer", "english"], value="multilingual", label="Speaker Primary Language")

            with gr.Column(scale=1):
                prof_trans = gr.Textbox(
                    label="Exact Verbatim Transcript of Reference Segment",
                    placeholder="Enter what is spoken in the reference segment. Required for Hi-Fi / Ultimate Cloning...",
                    lines=4
                )
                create_prof_btn = gr.Button("✨ Create & Save Voice Profile", variant="primary")
                create_status = gr.Label(label="Creation Status", value="Ready")

        gr.Markdown("---")

        # -------------------------------------------------------------
        # STEP 4: Built-in Voice Cloning Test Generation Area
        # -------------------------------------------------------------
        gr.Markdown("### Step 4: Test Voice Cloning (Immediate Offline Verification)")
        gr.Markdown("Generate speech immediately with your newly created or saved voice profile:")

        with gr.Row():
            with gr.Column(scale=1):
                test_profile_dropdown = gr.Dropdown(
                    label="Target Voice Profile",
                    choices=get_profile_dropdown_choices(),
                    value=get_profile_dropdown_choices()[0] if get_profile_dropdown_choices() else None
                )
                test_mode_radio = gr.Radio(
                    choices=[
                        "Controllable Voice Cloning (Reference Audio only)",
                        "Hi-Fi Voice Cloning (Prompt + Transcript)"
                    ],
                    value="Controllable Voice Cloning (Reference Audio only)",
                    label="Cloning Technique"
                )

                gr.Markdown("#### Quick Sample Prompts:")
                with gr.Row():
                    kh_sample_btn = gr.Button("🇰🇭 Khmer Sample", variant="secondary")
                    en_sample_btn = gr.Button("🇬🇧 English Sample", variant="secondary")
                    mx_sample_btn = gr.Button("🌐 Mixed Sample", variant="secondary")

                test_text_input = gr.Textbox(
                    label="Test Text to Synthesize",
                    value=KHMER_SAMPLE_PROMPT,
                    lines=3
                )

                with gr.Row():
                    test_gen_btn = gr.Button("🎙️ Test Generate Speech (CPU Queue)", variant="primary")
                    test_refresh_btn = gr.Button("🔄 Refresh Profile List", variant="secondary")

            with gr.Column(scale=1):
                test_job_status = gr.Label(label="Generation Status", value="Ready to generate.")
                test_audio_player = gr.Audio(label="Cloned Speech Output (48kHz WAV)", type="filepath")
                test_telemetry_display = gr.Markdown(value="Telemetry metrics will appear here after generation.")

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
