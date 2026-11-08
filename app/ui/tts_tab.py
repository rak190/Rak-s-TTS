"""
VoiceStudio Pro — Speech Studio UI Tab.
Flagship ElevenLabs & Descript-inspired Creative Workspace:
- Massive, distraction-free script canvas with Khmer & English typography.
- Contextual Inspector panel on right (speaker avatar, cloning mode, acoustic parameters).
- Signature audio player dock with dual 48kHz WAV / 320k MP3 download.
- Sentence-aware long-form chunk analysis and checkpoint-resumable synthesis.
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
        return "Waiting for text input... • 0 characters"
    lang = TextProcessor.detect_language(text)
    char_count = len(text)
    word_count = len(text.split())
    if lang == "khmer":
        lang_str = "🇰🇭 Khmer (ភាសាខ្មែរ)"
    elif lang == "english":
        lang_str = "🇬🇧 English"
    elif lang == "mixed":
        lang_str = "🌐 Mixed (Khmer + English)"
    else:
        lang_str = lang.capitalize()
    return f"{lang_str} • {char_count} chars • ~{word_count} words"

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
        yield None, "Error: Target script cannot be empty.", "No telemetry available."
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
            yield None, badge, f"⚙️ {msg} (Synthesizing on CPU 4 P-cores...)"
            time.sleep(0.5)
        elif st == "completed":
            res = status_info.get("result") or task.result
            if res:
                telemetry_md = f"""
**Generation Telemetry:**
* Audio Duration: `{res['duration_sec']}s`
* Compute Time: `{res['generation_time_sec']}s` (RTF: `{res['rtf']}x`)
* Native Quality: `{res['sample_rate']} Hz (48kHz AudioVAE V2)`
* Storage: `{res['output_path']}`
"""
                status_msg = f"✅ Synthesized {res['duration_sec']}s audio in {res['generation_time_sec']}s (RTF: {res['rtf']}x)"
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

def analyze_longform_chunks(text: str) -> str:
    """Analyzes text and returns markdown breakdown of chunks."""
    if not text or not text.strip():
        return "⚠️ Enter long text above to analyze sentence chunk structure."
    
    chunks = SentenceAwareChunker.chunk_text(text)
    if not chunks:
        return "⚠️ Could not parse text into speech chunks."

    md = f"**📑 Sentence Chunk Plan ({len(chunks)} Chunks Total):**\n\n"
    md += "| # | Chars | Language | Pause | Preview |\n"
    md += "|---|---|---|---|---|\n"
    for c in chunks:
        preview = (c.text[:45] + "...") if len(c.text) > 45 else c.text
        md += f"| **{c.index + 1}** | {c.char_count} | `{c.language}` | {c.pause_after_ms}ms | {preview} |\n"
    md += f"\n*Estimated runtime: ~{len(chunks) * 4:.1f}s - {len(chunks) * 6:.1f}s audio on Intel Core i5*"
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
        yield None, None, "❌ Error: Script text cannot be empty.", "No telemetry available."
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

    try:
        res = service.execute_job(
            job_id=job.id,
            cfg_value=float(cfg_value),
            inference_timesteps=int(timesteps)
        )
        if res.get("status") == "completed":
            msg = f"✅ Long-form complete! {res['total_chunks']} chunks stitched into {res['total_duration_sec']}s audio."
            telemetry = f"""
**Long-Form Telemetry:**
* Job Title: `{job.title}`
* Chunks Synthesized: `{res['total_chunks']}`
* Final Duration: `{res['total_duration_sec']}s`
* Total Time: `{res['total_generation_time_sec']}s` (RTF: `{res['rtf']}x`)
* Master WAV: `{res['output_wav_path']}`
* Master MP3: `{res['output_mp3_path']}`
"""
            yield res["output_wav_path"], res["output_mp3_path"], msg, telemetry
        else:
            yield None, None, f"⚠️ Job status: {res.get('status')}", ""
    except Exception as e:
        yield None, None, f"❌ Long-form synthesis failed: {str(e)}", f"Error: {str(e)}"


def create_tts_tab():
    """Builds the VoiceStudio Pro ElevenLabs & Descript-inspired Flagship Studio."""
    with gr.Tab("🔊 Speech Studio", id="tab_tts"):
        # Top Workspace Header (ElevenLabs Project Header)
        with gr.Row(elem_classes=["studio-canvas-card"]):
            with gr.Column(scale=3):
                gr.Markdown(
                    """
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">Speech Studio</span>
                        <span class="studio-pill studio-pill-accent">ElevenLabs Creative Workspace</span>
                        <span class="studio-pill studio-pill-muted">48kHz AudioVAE V2</span>
                    </div>
                    """
                )
            with gr.Column(scale=2):
                lang_live_badge = gr.Markdown(value="Waiting for text input... • 0 characters")

        # Two-Column Creative Workspace: Central Script Canvas + Right Contextual Inspector
        with gr.Row():
            # -------------------------------------------------------------
            # COLUMN 1: Large Central Script Canvas & Waveform Audio Dock
            # -------------------------------------------------------------
            with gr.Column(scale=7):
                with gr.Group(elem_classes=["studio-canvas-card"]):
                    project_title_input = gr.Textbox(
                        label="Project / Chapter Title",
                        value="Chapter 1: VoiceStudio AI Overview",
                        placeholder="e.g. Chapter 1: Introduction to VoiceStudio",
                        interactive=True
                    )

                    script_editor = gr.Textbox(
                        label="Script Editor (Khmer & English)",
                        placeholder="Type or paste your Khmer or English script here for natural, expressive speech generation...",
                        lines=12,
                        elem_classes=["script-editor-canvas"]
                    )

                    with gr.Row():
                        workflow_mode_radio = gr.Radio(
                            choices=["⚡ Standard Speech", "📖 Long-Form Studio"],
                            value="⚡ Standard Speech",
                            label="Workflow Stage"
                        )
                        chunk_analyze_btn = gr.Button("🔍 Analyze Sentence Chunks", variant="secondary", size="sm")

                    chunk_preview_box = gr.Markdown(
                        value="*Click 'Analyze Sentence Chunks' when drafting long articles or audiobooks.*"
                    )

                # Signature Waveform & Audio Player Dock (Descript & Apple Music Style)
                with gr.Group(elem_classes=["studio-canvas-card"]):
                    gr.Markdown("#### 🎧 Studio Audio Playback & Waveform Timeline")
                    
                    with gr.Row():
                        main_audio_player = gr.Audio(
                            label="Master Audio Output (Studio 48kHz WAV)",
                            type="filepath",
                            interactive=False
                        )
                        mp3_download_file = gr.File(
                            label="⬇️ Download MP3 (320kbps)",
                            interactive=False
                        )

                    with gr.Row():
                        execution_status_badge = gr.Label(label="Engine Status", value="Ready to generate.")
                    
                    telemetry_display = gr.Markdown(value="*Generation telemetry and RTF performance metrics will appear here after synthesis.*")

            # -------------------------------------------------------------
            # COLUMN 2: Contextual Right Inspector (ElevenLabs Style)
            # -------------------------------------------------------------
            with gr.Column(scale=3, min_width=280):
                with gr.Group(elem_classes=["studio-inspector"]):
                    gr.Markdown("### 🎛️ Voice & Model Inspector")

                    # Speaker Identity
                    with gr.Row(elem_classes=["speaker-avatar-card"]):
                        gr.Markdown(
                            """
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <div class="speaker-avatar-badge">VS</div>
                                <div>
                                    <div style="font-size: 13.5px; font-weight: 600; color: var(--studio-text-primary);">Active Speaker</div>
                                    <div style="font-size: 11.5px; color: var(--studio-text-secondary);">48,000 Hz Native Mono</div>
                                </div>
                            </div>
                            """
                        )

                    profile_dropdown = gr.Dropdown(
                        label="Speaker Voice Profile",
                        choices=get_available_profiles(),
                        value=get_available_profiles()[0] if get_available_profiles() else None
                    )
                    refresh_profiles_btn = gr.Button("🔄 Refresh Voice Profiles", variant="secondary", size="sm")

                    cloning_mode_selector = gr.Radio(
                        choices=["Ordinary TTS", "Voice Cloning", "Ultimate Cloning"],
                        value="Ordinary TTS",
                        label="Cloning Technique"
                    )

                    with gr.Accordion("⚙️ Acoustic & Diffusion Controls", open=True):
                        cfg_slider = gr.Slider(
                            minimum=1.0, maximum=5.0, value=2.0, step=0.1,
                            label="CFG Guidance Scale",
                            info="Higher values adhere tighter to prompt voice (Recommended: 2.0)"
                        )
                        steps_slider = gr.Slider(
                            minimum=5, maximum=30, value=10, step=1,
                            label="Inference Timesteps",
                            info="Diffusion steps (10 is optimal for i5 CPU)"
                        )

                    # Primary Actions
                    generate_hero_btn = gr.Button(
                        "🎙️ Generate Speech",
                        variant="primary",
                        size="lg",
                        elem_classes=["studio-btn-primary"]
                    )
                    cancel_btn = gr.Button("🛑 Cancel", variant="stop", size="sm")

        # -------------------------------------------------------------
        # Event Wiring
        # -------------------------------------------------------------
        script_editor.change(fn=on_text_changed, inputs=[script_editor], outputs=[lang_live_badge])
        refresh_profiles_btn.click(fn=lambda: gr.update(choices=get_available_profiles()), outputs=[profile_dropdown])
        cancel_btn.click(fn=cancel_current_generation, outputs=[execution_status_badge])

        chunk_analyze_btn.click(
            fn=analyze_longform_chunks,
            inputs=[script_editor],
            outputs=[chunk_preview_box]
        )

        # Standard Speech Generation
        generate_hero_btn.click(
            fn=run_tts_generation,
            inputs=[script_editor, cloning_mode_selector, profile_dropdown, cfg_slider, steps_slider],
            outputs=[main_audio_player, execution_status_badge, telemetry_display]
        )
