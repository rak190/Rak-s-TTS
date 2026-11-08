"""Voice Cloning Studio UI tab."""
import gradio as gr
from pathlib import Path
from typing import Tuple
from app.audio.processor import AudioProcessor
from app.config import TEMP_DIR, NATIVE_SAMPLE_RATE
from app.services.voice_service import VoiceProfileService

def inspect_uploaded_audio(file_path: str):
    if not file_path:
        return "Upload an audio file (1–5 minutes) to inspect.", 0.0, 0.0, None

    meta = AudioProcessor.inspect_audio(file_path)
    if not meta.is_valid:
        return f"❌ Invalid audio: {meta.error_message}", 0.0, 0.0, None

    peak_str = f"`{meta.peak_dbfs} dBFS`" if meta.peak_dbfs is not None else "`N/A`"
    rms_str = f"`{meta.rms_dbfs} dBFS`" if meta.rms_dbfs is not None else "`N/A`"

    info_md = f"""
### Audio Inspection:
* **Duration:** `{meta.duration_sec}s` ({round(meta.duration_sec/60, 2)} min)
* **Sample Rate:** `{meta.sample_rate} Hz`
* **Channels:** `{meta.channels} ({'Mono' if meta.channels == 1 else 'Stereo'})`
* **Format:** `{meta.subtype}`
* **Peak Level:** {peak_str}
* **RMS Energy:** {rms_str}
* **File Size:** `{round(meta.file_size_bytes / (1024**2), 2)} MB`

*💡 Note: You can use the entire recording, or select a clean 10–25s "golden slice" below.*
"""
    # Keep full duration as default; trimming remains optional and user-guided
    default_end = meta.duration_sec
    return info_md, 0.0, default_end, file_path

def preview_trimmed_segment(file_path: str, start_sec: float, end_sec: float):
    if not file_path or not Path(file_path).exists():
        return None, "Upload audio first."
    
    meta = AudioProcessor.inspect_audio(file_path)
    if not meta.is_valid:
        return None, f"Cannot trim: {meta.error_message}"

    if start_sec >= end_sec:
        return None, "Start time must be less than end time."

    temp_preview = TEMP_DIR / "preview_slice.wav"
    try:
        AudioProcessor.trim_audio_segment(
            input_path=file_path,
            output_path=temp_preview,
            start_sec=start_sec,
            end_sec=end_sec,
            target_sr=NATIVE_SAMPLE_RATE
        )
        return str(temp_preview), f"Segment trimmed: {round(end_sec - start_sec, 2)}s."
    except Exception as e:
        return None, f"Error trimming audio: {e}"

def handle_create_profile(file_path: str, name: str, desc: str, lang: str, trans: str, start_sec: float, end_sec: float):
    if not file_path:
        return "Please upload an audio recording first."
    if not name or not name.strip():
        return "Please provide a name for the voice profile."

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
        return f"✅ {msg} (Profile ID: {prof.id})"
    return f"❌ {msg}"

def create_cloning_tab():
    with gr.Tab("✂️ Voice Cloning Studio", id="tab_cloning"):
        gr.Markdown("## Voice Cloning Studio")
        gr.Markdown("Upload a 1–5 minute reference recording, trim your desired reference segment, and save as a reusable Voice Profile.")

        with gr.Row():
            with gr.Column(scale=1):
                upload_box = gr.Audio(
                    label="Upload Reference Audio (1–5 min WAV, MP3, M4A)",
                    type="filepath"
                )
                inspection_view = gr.Markdown(value="Upload an audio file to inspect.")

            with gr.Column(scale=1):
                gr.Markdown("### Segment Trimming (Optional)")
                gr.Markdown("Trim a clean, continuous segment of speech (e.g. 10–25s) for optimal cloning.")
                
                with gr.Row():
                    trim_start = gr.Number(label="Start Time (seconds)", value=0.0, step=0.5)
                    trim_end = gr.Number(label="End Time (seconds)", value=20.0, step=0.5)
                
                preview_trim_btn = gr.Button("🎧 Trim & Preview Segment", variant="secondary")
                preview_player = gr.Audio(label="Trimmed Segment Preview", type="filepath")
                preview_msg = gr.Label(label="Trim Status", value="Ready")

        gr.Markdown("---")
        with gr.Row():
            with gr.Column(scale=1):
                prof_name = gr.Textbox(label="Voice Profile Name (Required)", placeholder="e.g. Sokha Natural Voice")
                prof_desc = gr.Textbox(label="Description", placeholder="e.g. Calm, articulate Khmer narrator")
                prof_lang = gr.Radio(choices=["multilingual", "khmer", "english"], value="multilingual", label="Speaker Primary Language")
            with gr.Column(scale=1):
                prof_trans = gr.Textbox(
                    label="Exact Verbatim Transcript of Segment (Recommended for Ultimate Cloning)",
                    placeholder="Enter what is spoken in the trimmed reference slice...",
                    lines=4
                )
                create_prof_btn = gr.Button("✨ Create Voice Profile", variant="primary")
                create_status = gr.Label(label="Creation Result", value="Ready")

        # Events
        upload_box.change(
            fn=inspect_uploaded_audio,
            inputs=[upload_box],
            outputs=[inspection_view, trim_start, trim_end, preview_player]
        )

        preview_trim_btn.click(
            fn=preview_trimmed_segment,
            inputs=[upload_box, trim_start, trim_end],
            outputs=[preview_player, preview_msg]
        )

        create_prof_btn.click(
            fn=handle_create_profile,
            inputs=[upload_box, prof_name, prof_desc, prof_lang, prof_trans, trim_start, trim_end],
            outputs=[create_status]
        )
