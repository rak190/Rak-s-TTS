"""Voice Library UI tab implementing Stage 3 Profile Management."""
from pathlib import Path
from typing import List, Tuple
import gradio as gr

from app.services.voice_service import VoiceProfileService
from app.config import VOICES_DIR

def get_profile_choices() -> List[str]:
    service = VoiceProfileService.get_instance()
    profiles = service.list_profiles()
    return [f"{p.name} ({p.id})" for p in profiles] if profiles else ["No profiles created yet"]

def load_profile_details(selected: str):
    if not selected or selected == "No profiles created yet":
        return "", "", "", "", None, None, "Select a profile to view details."

    profile_id = selected.split("(")[-1].replace(")", "").strip()
    service = VoiceProfileService.get_instance()
    p = service.get_profile(profile_id)
    if not p:
        return "", "", "", "", None, None, "Profile not found."

    prof_dir = VOICES_DIR / p.id
    trans_exists = (prof_dir / "transcript.txt").exists()
    meta_exists = (prof_dir / "metadata.json").exists()

    details_md = f"""
### Voice Profile: `{p.name}`
| Attribute | Value |
| :--- | :--- |
| **Profile ID** | `{p.id}` |
| **Primary Language** | `{p.language}` |
| **Reference Duration** | `{p.duration_sec}s` (Native 48,000 Hz) |
| **Sample Rate** | `{p.sample_rate} Hz (PCM_16 Mono)` |
| **Created At** | `{p.created_at[:19]}` |
| **Last Updated** | `{p.updated_at[:19]}` |
| **Artifacts** | `transcript.txt: {'✅' if trans_exists else '⚪'}` | `metadata.json: {'✅' if meta_exists else '⚪'}` |
| **Storage Directory** | `{prof_dir}` |
"""
    return (
        p.name,
        p.description,
        p.language,
        p.transcript,
        p.reference_segment_path if p.reference_segment_path and Path(p.reference_segment_path).exists() else None,
        p.original_audio_path if p.original_audio_path and Path(p.original_audio_path).exists() else None,
        details_md
    )

def handle_update_profile(selected: str, name: str, desc: str, lang: str, trans: str):
    if not selected or selected == "No profiles created yet":
        return "No profile selected to update.", gr.update()
    profile_id = selected.split("(")[-1].replace(")", "").strip()
    service = VoiceProfileService.get_instance()
    ok, msg = service.update_profile(profile_id, name=name, description=desc, language=lang, transcript=trans)
    choices = get_profile_choices()
    val = f"{name} ({profile_id})" if ok else selected
    return msg, gr.update(choices=choices, value=val)

def handle_replace_audio(selected: str, new_audio: str, start_sec: float, end_sec: float, new_trans: str):
    if not selected or selected == "No profiles created yet":
        return "Select a profile first."
    if not new_audio or not Path(new_audio).exists():
        return "Upload or record replacement audio first."

    profile_id = selected.split("(")[-1].replace(")", "").strip()
    service = VoiceProfileService.get_instance()
    ok, msg = service.replace_reference_audio(
        profile_id=profile_id,
        new_audio_path=new_audio,
        trim_start_sec=start_sec,
        trim_end_sec=end_sec,
        new_transcript=new_trans
    )
    return f"✅ {msg}" if ok else f"❌ {msg}"

def handle_delete_profile(selected: str, confirm: bool):
    if not selected or selected == "No profiles created yet":
        return "No profile selected to delete.", gr.update()
    if not confirm:
        return "⚠️ Check the confirmation checkbox before clicking delete.", gr.update()

    profile_id = selected.split("(")[-1].replace(")", "").strip()
    service = VoiceProfileService.get_instance()
    ok, msg = service.delete_profile(profile_id)
    new_choices = get_profile_choices()
    default_val = new_choices[0] if new_choices else None
    return msg, gr.update(choices=new_choices, value=default_val)

def create_library_tab():
    with gr.Tab("🎙️ Voice Library", id="tab_library"):
        with gr.Column(elem_classes=["cu-card"]):
            gr.Markdown("## 🎙️ Voice Profile Library & Asset Management")
            gr.Markdown("Inspect saved voices, preview 48kHz reference clips, edit transcripts, and replace reference audio.")

        with gr.Row():
            with gr.Column(scale=1, elem_classes=["cu-card"]):
                profile_selector = gr.Dropdown(
                    label="Select Voice Profile",
                    choices=get_profile_choices(),
                    value=get_profile_choices()[0] if get_profile_choices() else None
                )
                refresh_lib_btn = gr.Button("🔄 Refresh Library", variant="secondary")
                summary_view = gr.Markdown(value="Select a profile to view details.")

            with gr.Column(scale=2, elem_classes=["cu-card"]):
                with gr.Group():
                    gr.Markdown("### Profile Metadata Editor")
                    edit_name = gr.Textbox(label="Profile Name")
                    edit_desc = gr.Textbox(label="Description", lines=2)
                    edit_lang = gr.Radio(choices=["multilingual", "khmer", "english"], label="Speaker Language")
                    edit_trans = gr.Textbox(label="Verbatim Transcript (for Hi-Fi / Ultimate Cloning)", lines=3)

                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("#### Reference Segment (Used for Inference)")
                            ref_player = gr.Audio(label="Reference Segment (48kHz WAV)", type="filepath")
                        with gr.Column():
                            gr.Markdown("#### Full Original Recording")
                            orig_player = gr.Audio(label="Full Original Recording", type="filepath")

                    with gr.Accordion("🔄 Replace Reference Audio Recording", open=False):
                        gr.Markdown("Replace this profile's source recording without changing its profile ID:")
                        replace_audio_box = gr.Audio(label="New Audio File", sources=["upload", "microphone"], type="filepath")
                        with gr.Row():
                            rep_trim_start = gr.Number(label="Trim Start Time (s)", value=0.0)
                            rep_trim_end = gr.Number(label="Trim End Time (s)", value=20.0)
                        rep_trans = gr.Textbox(label="New Transcript (Optional)", placeholder="Leave blank to keep existing transcript...")
                        replace_audio_btn = gr.Button("🔄 Apply Audio Replacement", variant="secondary")
                        replace_status = gr.Label(label="Replacement Status", value="Ready")

                    with gr.Row():
                        save_btn = gr.Button("💾 Save Metadata Changes", variant="primary")
                        with gr.Column():
                            confirm_del = gr.Checkbox(label="I confirm I want to permanently delete this profile", value=False)
                            delete_btn = gr.Button("🗑️ Delete Profile", variant="stop")

                    lib_status = gr.Label(label="Operation Status", value="Ready")

        # Event Handlers
        profile_selector.change(
            fn=load_profile_details,
            inputs=[profile_selector],
            outputs=[edit_name, edit_desc, edit_lang, edit_trans, ref_player, orig_player, summary_view]
        )

        refresh_lib_btn.click(
            fn=lambda: gr.update(choices=get_profile_choices()),
            outputs=[profile_selector]
        )

        save_btn.click(
            fn=handle_update_profile,
            inputs=[profile_selector, edit_name, edit_desc, edit_lang, edit_trans],
            outputs=[lib_status, profile_selector]
        )

        replace_audio_btn.click(
            fn=handle_replace_audio,
            inputs=[profile_selector, replace_audio_box, rep_trim_start, rep_trim_end, rep_trans],
            outputs=[replace_status]
        ).then(
            fn=load_profile_details,
            inputs=[profile_selector],
            outputs=[edit_name, edit_desc, edit_lang, edit_trans, ref_player, orig_player, summary_view]
        )

        delete_btn.click(
            fn=handle_delete_profile,
            inputs=[profile_selector, confirm_del],
            outputs=[lib_status, profile_selector]
        )
