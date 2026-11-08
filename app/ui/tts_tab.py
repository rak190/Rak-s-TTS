"""Text-to-Speech Studio UI tab."""
import time
import uuid
import gradio as gr
from typing import List, Tuple
from pathlib import Path

from app.services.voice_service import VoiceProfileService
from app.services.generation_service import GenerationService
from app.queue.generation_queue import GenerationQueue, GenerationTask
from app.utils.text_processor import TextProcessor

def get_available_profiles() -> List[str]:
    service = VoiceProfileService.get_instance()
    profiles = service.list_profiles()
    return [f"{p.name} ({p.id})" for p in profiles] if profiles else ["Default Voice (No Profile)"]

def on_text_changed(text: str):
    if not text:
        return "Language: Waiting for input..."
    lang = TextProcessor.detect_language(text)
    if lang == "khmer":
        return "Detected Language: 🇰🇭 Khmer"
    elif lang == "english":
        return "Detected Language: 🇬🇧 English"
    elif lang == "mixed":
        return "Detected Language: 🌐 Mixed (Khmer + English Code-Switching)"
    return f"Detected Language: {lang.capitalize()}"

def cancel_current_generation():
    queue = GenerationQueue.get_instance()
    stats = queue.get_queue_stats()
    curr_id = stats.get("current_job_id")
    if curr_id:
        queue.cancel_job(curr_id)
        return "🛑 Cancellation requested for active job."
    return "ℹ️ No active job running."

def run_tts_generation(
    text: str,
    mode: str,
    selected_profile: str,
    cfg_value: float,
    timesteps: int
):
    if not text or not text.strip():
        yield None, "Error: Target text cannot be empty.", "No telemetry available."
        return

    norm_text = TextProcessor.normalize_text(text)
    lang = TextProcessor.detect_language(norm_text)
    
    # Resolve Voice Profile
    profile_id = None
    voice_name = "Default Voice"
    ref_audio_path = None
    prompt_audio_path = None
    prompt_text = None

    if selected_profile and selected_profile != "Default Voice (No Profile)":
        profile_id = selected_profile.split("(")[-1].replace(")", "").strip()
        prof = VoiceProfileService.get_instance().get_profile(profile_id)
        if prof:
            voice_name = prof.name
            ref_audio_path = prof.reference_segment_path
            prompt_audio_path = prof.reference_segment_path
            prompt_text = prof.transcript

    # Map UI mode to internal mode
    job_type = "tts"
    if mode == "Voice Cloning":
        if not ref_audio_path:
            yield None, "Error: Voice Cloning requires selecting a Voice Profile with reference audio.", "No telemetry available."
            return
        job_type = "cloning"
    elif mode == "Ultimate Cloning":
        if not ref_audio_path:
            yield None, "Error: Ultimate Cloning requires a Voice Profile with reference audio.", "No telemetry available."
            return
        if not prompt_text or not prompt_text.strip():
            yield None, "Error: Ultimate Cloning strictly requires an exact verbatim transcript for the reference segment. Please edit the profile transcript in Voice Library.", "No telemetry available."
            return
        job_type = "ultimate_cloning"

    # Single-inference FIFO queue submission
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    task = GenerationTask(
        job_id=job_id,
        job_type=job_type,
        target_text=norm_text,
        voice_profile_id=profile_id,
        voice_name=voice_name,
        language=lang,
        reference_wav_path=ref_audio_path,
        prompt_wav_path=prompt_audio_path,
        prompt_text=prompt_text,
        cfg_value=float(cfg_value),
        inference_timesteps=int(timesteps)
    )

    queue = GenerationQueue.get_instance()
    queue.submit_task(task)

    # Stream real-time status updates via Gradio generator
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
### 📊 Generation Telemetry:
* **Audio Duration:** `{res['duration_sec']}s`
* **Generation Time:** `{res['generation_time_sec']}s`
* **Real-Time Factor (RTF):** `{res['rtf']}x`
* **Sample Rate:** `{res['sample_rate']} Hz (Studio Quality)`
* **Output Path:** `{res['output_path']}`
"""
                status_msg = f"✅ Speech generation complete! ({res['duration_sec']}s audio generated in {res['generation_time_sec']}s)"
                yield res['output_path'], status_msg, telemetry_md
            else:
                yield None, "✅ Completed", "Audio synthesized successfully."
            break
        elif st == "failed":
            err = status_info.get("error_message") or task.error or "Unknown synthesis error"
            yield None, "❌ Failed", f"### ❌ Generation Failed\n\n`{err}`"
            break
        elif st == "cancelled":
            yield None, "🚫 Cancelled", "Generation was cancelled."
            break
        else:
            time.sleep(0.5)

def create_tts_tab():
    with gr.Tab("🔊 Text-to-Speech Studio", id="tab_tts"):
        gr.Markdown("## Text-to-Speech & Voice Cloning Studio")
        gr.Markdown("Synthesize natural speech in Khmer, English, or Mixed code-switching using your cloned voices.")

        with gr.Row():
            with gr.Column(scale=2):
                text_input = gr.Textbox(
                    label="Input Text (Khmer, English, or Mixed)",
                    placeholder="Enter text to synthesize here...",
                    lines=5
                )
                lang_badge = gr.Markdown(value="Language: Waiting for input...")
                
                with gr.Row():
                    mode_radio = gr.Radio(
                        choices=["Ordinary TTS", "Voice Cloning", "Ultimate Cloning"],
                        value="Ordinary TTS",
                        label="Generation Mode"
                    )
                    profile_dropdown = gr.Dropdown(
                        label="Target Voice Profile",
                        choices=get_available_profiles(),
                        value=get_available_profiles()[0] if get_available_profiles() else None
                    )

                with gr.Accordion("⚙️ Inference Parameters (Advanced)", open=False):
                    with gr.Row():
                        cfg_slider = gr.Slider(minimum=1.0, maximum=5.0, value=2.0, step=0.1, label="CFG Guidance Scale")
                        steps_slider = gr.Slider(minimum=5, maximum=30, value=10, step=1, label="Inference Timesteps (Diffusion)")

                with gr.Row():
                    gen_btn = gr.Button("🎙️ Generate Speech (Offline CPU Queue)", variant="primary")
                    cancel_btn = gr.Button("🛑 Cancel Generation", variant="stop")
                refresh_profiles_btn = gr.Button("🔄 Refresh Profile List", variant="secondary")

            with gr.Column(scale=2):
                job_status = gr.Label(label="Execution Status", value="Ready to generate.")
                audio_player = gr.Audio(label="Generated Audio Output (48kHz WAV)", type="filepath")
                telemetry_display = gr.Markdown(value="Telemetry metrics will appear here after generation.")

        # Events
        text_input.change(fn=on_text_changed, inputs=[text_input], outputs=[lang_badge])
        refresh_profiles_btn.click(fn=lambda: gr.update(choices=get_available_profiles()), outputs=[profile_dropdown])
        cancel_btn.click(fn=cancel_current_generation, outputs=[job_status])
        
        gen_btn.click(
            fn=run_tts_generation,
            inputs=[text_input, mode_radio, profile_dropdown, cfg_slider, steps_slider],
            outputs=[audio_player, job_status, telemetry_display]
        )
