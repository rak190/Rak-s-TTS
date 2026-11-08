"""
VoiceStudio Pro — Speech Studio UI Tab.
Flagship ElevenLabs & Descript-inspired Creative Workspace:
- Massive, distraction-free script canvas with Khmer & English typography.
- Contextual Inspector panel on right (speaker avatar, cloning mode, acoustic parameters).
- Signature audio player dock with dual 48kHz WAV / 320k MP3 download.
- Sentence-aware long-form chunk analysis and checkpoint-resumable synthesis.
- Non-blocking "Add to Batch Queue" button for persistent multi-script workflows.
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

        if st in ("pending", "queued"):
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
    """Build the TTS workstation while keeping generation callbacks unchanged."""
    profiles = get_available_profiles()
    with gr.Tab("Speech Studio", id="tab_tts"):
        gr.HTML("""<header class="tts-page-head"><div><div class="eyebrow">VOICESTUDIO / CREATE</div><h1>Speech Studio</h1><p>Shape a script, choose a voice, and listen to the result.</p></div><div class="local-status"><i></i> Local studio <span>·</span> 48 kHz</div></header>""")
        with gr.Row(elem_classes=["tts-workspace"]):
            with gr.Column(scale=8, min_width=480, elem_classes=["tts-editor-column"]):
                with gr.Row(elem_classes=["project-row"]):
                    project_title_input = gr.Textbox(label="Project", value="Untitled narration", placeholder="Name this narration", elem_classes=["project-title"])
                    lang_live_badge = gr.Markdown(value="Waiting for script  ·  0 characters", elem_classes=["script-count"])
                gr.HTML("<div class='editor-caption'><span>Script</span><span>English &nbsp; · &nbsp; Khmer</span></div>")
                script_editor = gr.Textbox(label="", show_label=False, placeholder="Start writing or paste your narration here…\n\nYour script stays in focus while voice and delivery settings live beside it.", lines=15, elem_classes=["script-editor-canvas"])
                with gr.Row(elem_classes=["editor-footer"]):
                    workflow_mode_radio = gr.Radio(choices=["Standard", "Long-form"], value="Standard", label="Workflow", elem_classes=["workflow-mode"])
                    chunk_analyze_btn = gr.Button("Preview chapters", variant="secondary", size="sm")
                with gr.Accordion("Chapter preview", open=False, elem_classes=["chapter-preview"]):
                    chunk_preview_box = gr.Markdown(value="Long-form preview will appear here.")
                gr.HTML("<div class='section-divider'></div><div class='output-heading'><div><span class='eyebrow'>LISTEN BACK</span><h2>Audio output</h2></div><span class='output-note'>Generated audio appears here</span></div>")
                main_audio_player = gr.Audio(label="", show_label=False, type="filepath", interactive=False, elem_classes=["studio-audio-output"])
                with gr.Row(elem_classes=["audio-actions"]):
                    mp3_download_file = gr.File(label="MP3 export", height=72, interactive=False, elem_classes=["mp3-export"])
                    execution_status_badge = gr.Markdown(value="Ready when you are", elem_classes=["engine-status"])
                    cancel_btn = gr.Button("Cancel", variant="secondary", size="sm")
                telemetry_display = gr.Markdown(value="", elem_classes=["generation-details"])

            with gr.Column(scale=3, min_width=260, elem_classes=["tts-inspector"]):
                gr.HTML("<div class='inspector-heading'><span class='eyebrow'>VOICE & DELIVERY</span><h2>Sound like you</h2></div><div class='voice-mark'><span>V</span><div><b>Voice profile</b><small>Choose a saved voice</small></div></div>")
                profile_dropdown = gr.Dropdown(label="Voice", choices=profiles, value=profiles[0] if profiles else None)
                refresh_profiles_btn = gr.Button("Refresh voices", variant="secondary", size="sm")
                cloning_mode_selector = gr.Radio(choices=["Ordinary TTS", "Voice Cloning", "Ultimate Cloning"], value="Ordinary TTS", label="Generation mode")
                gr.HTML("<div class='inspector-rule'></div><div class='eyebrow'>ADVANCED</div>")
                with gr.Accordion("Voice controls", open=False):
                    cfg_slider = gr.Slider(minimum=1.0, maximum=5.0, value=2.0, step=0.1, label="Guidance", info="Higher values follow the reference voice more closely.")
                    steps_slider = gr.Slider(minimum=5, maximum=30, value=10, step=1, label="Inference steps")
                generate_hero_btn = gr.Button("Generate speech", variant="primary", size="lg", elem_classes=["studio-btn-primary"])
                longform_btn = gr.Button("Generate long-form", variant="primary", size="lg", visible=False, elem_classes=["studio-btn-primary"])
                add_to_queue_btn = gr.Button("📥 Add to Batch Queue", variant="secondary", size="md")

        def handle_add_to_batch(title, text, mode, profile, cfg, steps, workflow):
            from app.services.batch_service import BatchService
            svc = BatchService.get_instance()
            is_lf = (workflow == "Long-form")
            job_id, msg = svc.submit_batch_item(
                title=title,
                text=text,
                voice_profile_id=profile,
                mode=mode,
                cfg_value=cfg,
                inference_timesteps=steps,
                force_longform=is_lf
            )
            if job_id:
                return f"📥 Added to Queue: '{title}' ({msg}). Monitor in Batch Queue tab."
            return f"❌ Could not queue: {msg}"

        script_editor.change(fn=on_text_changed, inputs=[script_editor], outputs=[lang_live_badge])
        workflow_mode_radio.change(
            fn=lambda mode: (gr.update(visible=mode == "Standard"), gr.update(visible=mode == "Long-form")),
            inputs=[workflow_mode_radio], outputs=[generate_hero_btn, longform_btn]
        )
        refresh_profiles_btn.click(fn=lambda: gr.update(choices=get_available_profiles()), outputs=[profile_dropdown])
        cancel_btn.click(fn=cancel_current_generation, outputs=[execution_status_badge])
        chunk_analyze_btn.click(fn=analyze_longform_chunks, inputs=[script_editor], outputs=[chunk_preview_box])
        generate_hero_btn.click(fn=run_tts_generation, inputs=[script_editor, cloning_mode_selector, profile_dropdown, cfg_slider, steps_slider], outputs=[main_audio_player, execution_status_badge, telemetry_display])
        longform_btn.click(fn=run_longform_synthesis, inputs=[project_title_input, script_editor, cloning_mode_selector, profile_dropdown, cfg_slider, steps_slider], outputs=[main_audio_player, mp3_download_file, execution_status_badge, telemetry_display])
        add_to_queue_btn.click(
            fn=handle_add_to_batch,
            inputs=[project_title_input, script_editor, cloning_mode_selector, profile_dropdown, cfg_slider, steps_slider, workflow_mode_radio],
            outputs=[execution_status_badge]
        )
