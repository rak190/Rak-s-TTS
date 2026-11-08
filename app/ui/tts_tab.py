"""
Text-to-Speech Studio UI tab.
Provides Standard Single-Pass Speech Synthesis and Intelligent Long-Form Article/Audiobook Studio
with sentence-aware chunking, persistent checkpoints, resume, and dual WAV/MP3 export.
"""
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import gradio as gr

from app.services.voice_service import VoiceProfileService
from app.services.generation_service import GenerationService
from app.services.longform_service import LongformService
from app.queue.generation_queue import GenerationQueue, GenerationTask
from app.utils.text_processor import TextProcessor
from app.utils.chunker import SentenceAwareChunker

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

# -------------------------------------------------------------
# Long-Form Handlers (Stage 4)
# -------------------------------------------------------------
def analyze_longform_chunks(text: str) -> str:
    """Analyzes text and returns markdown breakdown of chunks."""
    if not text or not text.strip():
        return "⚠️ Enter long text above to analyze chunk structure."
    
    chunks = SentenceAwareChunker.chunk_text(text)
    if not chunks:
        return "⚠️ Could not parse text into speech chunks."

    md = f"### 📑 Intelligent Sentence-Aware Chunk Plan ({len(chunks)} Chunks Total)\n\n"
    md += "| # | Chars | Language | Pause After | Chunk Text Preview |\n"
    md += "|---|---|---|---|---|\n"
    for c in chunks:
        preview = (c.text[:55] + "...") if len(c.text) > 55 else c.text
        md += f"| **{c.index + 1}** | {c.char_count} | `{c.language}` | {c.pause_after_ms}ms | {preview} |\n"
    md += f"\n*Estimated audio duration: ~{len(chunks) * 4:.1f}s - {len(chunks) * 6:.1f}s | Target chunk size: 60–140 chars*"
    return md

def run_longform_synthesis(
    title: str,
    text: str,
    mode: str,
    selected_profile: str,
    cfg_value: float,
    timesteps: int
):
    """Executes long-form synthesis with progress updates and checkpointing."""
    if not text or not text.strip():
        yield None, None, "❌ Error: Text cannot be empty.", "No telemetry available."
        return

    profile_id = None
    if selected_profile and selected_profile != "Default Voice (No Profile)":
        profile_id = selected_profile.split("(")[-1].replace(")", "").strip()

    internal_mode = "tts"
    if mode == "Voice Cloning":
        internal_mode = "cloning"
    elif mode == "Ultimate Cloning":
        internal_mode = "ultimate_cloning"

    service = LongformService.get_instance()
    job, err = service.prepare_job(
        title=title,
        text=text,
        voice_profile_id=profile_id,
        mode=internal_mode
    )
    if err or not job:
        yield None, None, f"❌ Error: {err}", "No telemetry available."
        return

    yield None, None, f"⏳ Prepared {job.total_chunks} chunks. Starting synthesis on CPU queue...", f"Job ID: `{job.id}`"

    # Execute job
    try:
        res = service.execute_job(
            job_id=job.id,
            cfg_value=float(cfg_value),
            inference_timesteps=int(timesteps)
        )
        if res.get("status") == "completed":
            msg = f"✅ Long-form synthesis completed! ({res['total_chunks']} chunks stitched into {res['total_duration_sec']}s audio)"
            telemetry = f"""
### 📊 Long-Form Synthesis Telemetry:
* **Job Title:** `{job.title}`
* **Total Chunks Synthesized:** `{res['total_chunks']}`
* **Final Master Duration:** `{res['total_duration_sec']}s`
* **Total Generation Time:** `{res['total_generation_time_sec']}s`
* **Average RTF:** `{res['rtf']}x`
* **Master WAV Output:** `{res['output_wav_path']}`
* **Master MP3 Output:** `{res['output_mp3_path']}`
"""
            yield res["output_wav_path"], res["output_mp3_path"], msg, telemetry
        else:
            yield None, None, f"⚠️ Job status: {res.get('status')}", ""
    except Exception as e:
        yield None, None, f"❌ Long-form synthesis failed: {str(e)}", f"Error: {str(e)}"

def create_tts_tab():
    with gr.Tab("🔊 Text-to-Speech Studio", id="tab_tts"):
        gr.Markdown("## 🎙️ Multilingual Text-to-Speech Studio")
        gr.Markdown(
            "Synthesize natural speech in Khmer, English, or Mixed code-switching. "
            "Choose between fast single-pass synthesis or the long-form audiobook & article studio."
        )

        with gr.Tabs():
            # ---------------------------------------------------------
            # SUB-TAB 1: Standard Single-Pass TTS
            # ---------------------------------------------------------
            with gr.TabItem("⚡ Standard Speech Synthesis"):
                with gr.Row():
                    with gr.Column(scale=2):
                        text_input = gr.Textbox(
                            label="Input Text (Khmer, English, or Mixed)",
                            placeholder="Enter text to synthesize here...",
                            lines=4
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

                        with gr.Accordion("⚙️ Advanced Inference Parameters", open=False):
                            with gr.Row():
                                cfg_slider = gr.Slider(minimum=1.0, maximum=5.0, value=2.0, step=0.1, label="CFG Guidance Scale")
                                steps_slider = gr.Slider(minimum=5, maximum=30, value=10, step=1, label="Inference Timesteps")

                        with gr.Row():
                            gen_btn = gr.Button("🎙️ Generate Speech (Offline CPU Queue)", variant="primary")
                            cancel_btn = gr.Button("🛑 Cancel Generation", variant="stop")
                        refresh_profiles_btn = gr.Button("🔄 Refresh Profile List", variant="secondary")

                    with gr.Column(scale=2):
                        job_status = gr.Label(label="Execution Status", value="Ready to generate.")
                        audio_player = gr.Audio(label="Generated Audio Output (48kHz WAV)", type="filepath")
                        telemetry_display = gr.Markdown(value="Telemetry metrics will appear here after generation.")

            # ---------------------------------------------------------
            # SUB-TAB 2: Long-Form Studio (Stage 4)
            # ---------------------------------------------------------
            with gr.TabItem("📖 Long-Form Studio (Articles & Audiobooks)"):
                gr.Markdown(
                    "Synthesize long articles, chapters, and scripts without audio collapse. "
                    "Text is partitioned into intelligent sentence chunks, synthesized with persistent checkpoints, "
                    "and seamlessly stitched with inter-sentence pauses into studio WAV and 320k MP3."
                )

                with gr.Row():
                    with gr.Column(scale=2):
                        lf_title = gr.Textbox(
                            label="Project / Chapter Title",
                            placeholder="e.g. Chapter 1: Introduction to VoiceStudio",
                            value="Chapter 1: VoiceStudio AI Overview"
                        )
                        lf_text = gr.Textbox(
                            label="Long-Form Input Text (Khmer or English)",
                            placeholder="Paste your long text, article, or chapter here...",
                            lines=7
                        )
                        with gr.Row():
                            lf_analyze_btn = gr.Button("🔍 Analyze & Preview Sentence Chunks", variant="secondary")
                            lf_refresh_prof_btn = gr.Button("🔄 Refresh Profiles", variant="secondary")

                        with gr.Row():
                            lf_mode_radio = gr.Radio(
                                choices=["Ordinary TTS", "Voice Cloning", "Ultimate Cloning"],
                                value="Voice Cloning",
                                label="Cloning Mode"
                            )
                            lf_profile_dropdown = gr.Dropdown(
                                label="Consistent Speaker Voice",
                                choices=get_available_profiles(),
                                value=get_available_profiles()[0] if get_available_profiles() else None
                            )

                        lf_preview_view = gr.Markdown(value="Click 'Analyze & Preview Sentence Chunks' to inspect chunk plan.")

                        with gr.Row():
                            lf_start_btn = gr.Button("🎙️ Start Long-Form Synthesis (CPU Queue)", variant="primary")

                    with gr.Column(scale=2):
                        lf_status = gr.Label(label="Long-Form Status", value="Ready to synthesize.")
                        lf_master_wav = gr.Audio(label="Full Stitched Master Audio (48kHz Studio WAV)", type="filepath")
                        with gr.Row():
                            lf_download_wav = gr.File(label="⬇️ Download WAV (PCM_16 Uncompressed)")
                            lf_download_mp3 = gr.File(label="⬇️ Download MP3 (320kbps High Quality)")
                        lf_telemetry = gr.Markdown(value="Long-form generation telemetry will appear here.")

        # Events - Standard TTS
        text_input.change(fn=on_text_changed, inputs=[text_input], outputs=[lang_badge])
        refresh_profiles_btn.click(fn=lambda: gr.update(choices=get_available_profiles()), outputs=[profile_dropdown])
        cancel_btn.click(fn=cancel_current_generation, outputs=[job_status])
        
        gen_btn.click(
            fn=run_tts_generation,
            inputs=[text_input, mode_radio, profile_dropdown, cfg_slider, steps_slider],
            outputs=[audio_player, job_status, telemetry_display]
        )

        # Events - Long-Form TTS
        lf_analyze_btn.click(
            fn=analyze_longform_chunks,
            inputs=[lf_text],
            outputs=[lf_preview_view]
        )
        lf_refresh_prof_btn.click(
            fn=lambda: gr.update(choices=get_available_profiles()),
            outputs=[lf_profile_dropdown]
        )
        
        cfg_val_default = gr.State(2.0)
        steps_val_default = gr.State(10)

        lf_start_btn.click(
            fn=run_longform_synthesis,
            inputs=[lf_title, lf_text, lf_mode_radio, lf_profile_dropdown, cfg_val_default, steps_val_default],
            outputs=[lf_master_wav, lf_download_mp3, lf_status, lf_telemetry]
        )
