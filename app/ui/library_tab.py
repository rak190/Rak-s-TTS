"""Voice Library UI tab."""
import gradio as gr
from typing import List, Tuple
from app.services.voice_service import VoiceProfileService

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

    details_md = f"""
### Profile: `{p.name}`
* **ID:** `{p.id}`
* **Language:** `{p.language}`
* **Duration:** `{p.duration_sec}s`
* **Sample Rate:** `{p.sample_rate} Hz`
* **Created:** `{p.created_at[:19]}`
"""
    return (
        p.name,
        p.description,
        p.language,
        p.transcript,
        p.reference_segment_path if p.reference_segment_path else None,
        p.original_audio_path if p.original_audio_path else None,
        details_md
    )

def handle_update_profile(selected: str, name: str, desc: str, lang: str, trans: str):
    if not selected or selected == "No profiles created yet":
        return "No profile selected to update."
    profile_id = selected.split("(")[-1].replace(")", "").strip()
    service = VoiceProfileService.get_instance()
    ok, msg = service.update_profile(profile_id, name=name, description=desc, language=lang, transcript=trans)
    return msg

def handle_delete_profile(selected: str):
    if not selected or selected == "No profiles created yet":
        return "No profile selected to delete.", gr.update(choices=get_profile_choices())
    profile_id = selected.split("(")[-1].replace(")", "").strip()
    service = VoiceProfileService.get_instance()
    ok, msg = service.delete_profile(profile_id)
    new_choices = get_profile_choices()
    default_val = new_choices[0] if new_choices else None
    return msg, gr.update(choices=new_choices, value=default_val)

def create_library_tab():
    with gr.Tab("🎙️ Voice Library", id="tab_library"):
        gr.Markdown("## Voice Profile Library")
        gr.Markdown("Manage your saved voices, preview reference clips, and edit transcripts.")

        with gr.Row():
            with gr.Column(scale=1):
                profile_selector = gr.Dropdown(
                    label="Select Voice Profile",
                    choices=get_profile_choices(),
                    value=get_profile_choices()[0] if get_profile_choices() else None
                )
                refresh_lib_btn = gr.Button("🔄 Refresh Library", variant="secondary")
                summary_view = gr.Markdown(value="Select a profile to view details.")

            with gr.Column(scale=2):
                with gr.Group():
                    gr.Markdown("### Profile Metadata")
                    edit_name = gr.Textbox(label="Profile Name")
                    edit_desc = gr.Textbox(label="Description", lines=2)
                    edit_lang = gr.Radio(choices=["multilingual", "khmer", "english"], label="Language")
                    edit_trans = gr.Textbox(label="Verbatim Transcript (for Ultimate Cloning)", lines=3)

                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("#### Reference Segment (Used for Inference)")
                            ref_player = gr.Audio(label="Reference Segment", type="filepath")
                        with gr.Column():
                            gr.Markdown("#### Original Uploaded Recording")
                            orig_player = gr.Audio(label="Full Original Recording", type="filepath")

                    with gr.Row():
                        save_btn = gr.Button("💾 Save Changes", variant="primary")
                        delete_btn = gr.Button("🗑️ Delete Profile", variant="stop")
                    lib_status = gr.Label(label="Status", value="Ready")

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
            outputs=[lib_status]
        )

        delete_btn.click(
            fn=handle_delete_profile,
            inputs=[profile_selector],
            outputs=[lib_status, profile_selector]
        )
