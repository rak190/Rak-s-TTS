"""
VoiceStudio Pro — Voice Library UI Tab.
Visual Speaker Cards & Identity Management:
- Card-based showcase with abstract avatar graphics and language pills.
- Dedicated Right-Side Contextual Inspector for transcript and reference segment editing.
- Audio replacement and safe deletion with confirmation.
"""
from pathlib import Path
from typing import List, Tuple
import gradio as gr

from app.services.voice_service import VoiceProfileService
from app.config import VOICES_DIR

def get_profile_choices() -> List[str]:
    service = VoiceProfileService.get_instance()
    profiles = service.list_profiles()
    return [f"{p.name} ({p.id})" for p in profiles] if profiles else ["No profiles created yet"]

def get_voice_cards_html() -> str:
    """Renders visual speaker cards for the voice library."""
    service = VoiceProfileService.get_instance()
    profiles = service.list_profiles()
    if not profiles:
        return "<div style='color: var(--studio-text-muted); font-size: 13.5px; padding: 20px 0;'>No voice profiles created yet. Use Voice Cloning to create your first voice profile.</div>"

    cards_html = "<div style='display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; margin-top: 8px;'>"
    for p in profiles:
        initials = "".join([part[0].upper() for part in p.name.split()[:2]]) or "VP"
        lang_flag = "🇰🇭" if p.language.lower() == "khmer" else ("🇬🇧" if p.language.lower() == "english" else "🌐")
        cards_html += f"""
        <div style="background: var(--studio-surface-elevated); border: 1px solid var(--studio-border); border-radius: var(--radius-md); padding: 14px; transition: transform 0.15s ease;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <div class="speaker-avatar-badge" style="width: 36px; height: 36px; font-size: 13px;">{initials}</div>
                <div style="overflow: hidden;">
                    <div style="font-size: 14px; font-weight: 600; color: var(--studio-text-primary); text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">{p.name}</div>
                    <div style="font-size: 11.5px; color: var(--studio-text-secondary);">{lang_flag} {p.language.capitalize()}</div>
                </div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px; font-size: 11.5px; color: var(--studio-text-muted); border-top: 1px solid var(--studio-border-subtle); padding-top: 8px;">
                <span>Duration: {p.duration_sec}s</span>
                <span class="studio-pill studio-pill-accent" style="font-size: 10.5px; padding: 1px 6px;">48kHz PCM</span>
            </div>
        </div>
        """
    cards_html += "</div>"
    return cards_html

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
**Voice Profile: `{p.name}`**
* **ID:** `{p.id}` | **Language:** `{p.language}`
* **Reference Audio:** `{p.duration_sec}s @ 48,000 Hz Mono`
* **Artifacts:** `transcript.txt: {'✅' if trans_exists else '⚪'}` • `metadata.json: {'✅' if meta_exists else '⚪'}`
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
        return "No profile selected to update.", gr.update(), get_voice_cards_html()
    profile_id = selected.split("(")[-1].replace(")", "").strip()
    service = VoiceProfileService.get_instance()
    ok, msg = service.update_profile(profile_id, name=name, description=desc, language=lang, transcript=trans)
    choices = get_profile_choices()
    val = f"{name} ({profile_id})" if ok else selected
    return msg, gr.update(choices=choices, value=val), get_voice_cards_html()

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
        return "No profile selected to delete.", gr.update(), get_voice_cards_html()
    if not confirm:
        return "⚠️ Check the confirmation checkbox before clicking delete.", gr.update(), get_voice_cards_html()

    profile_id = selected.split("(")[-1].replace(")", "").strip()
    service = VoiceProfileService.get_instance()
    ok, msg = service.delete_profile(profile_id)
    new_choices = get_profile_choices()
    default_val = new_choices[0] if new_choices else None
    return msg, gr.update(choices=new_choices, value=default_val), get_voice_cards_html()

def create_library_tab():
    with gr.Tab("🎙️ Voice Library", id="tab_library"):
        # Header
        with gr.Row(elem_classes=["studio-canvas-card"]):
            gr.Markdown(
                """
                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <div style="font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">Voice Library</div>
                        <div style="font-size: 13px; color: var(--studio-text-secondary); margin-top: 2px;">
                            Speaker Identities • 48kHz Reference Audio • Verbatim Transcripts
                        </div>
                    </div>
                    <div>
                        <span class="studio-pill studio-pill-accent">Studio Voices Active</span>
                    </div>
                </div>
                """
            )

        # Two-Column Library Experience
        with gr.Row():
            # LEFT: Visual Voice Cards Showcase
            with gr.Column(scale=5):
                with gr.Group(elem_classes=["studio-canvas-card"]):
                    gr.Markdown("#### 👥 Speaker Profile Showcase")
                    voice_cards_display = gr.HTML(value=get_voice_cards_html)
                    
                    with gr.Row():
                        profile_selector = gr.Dropdown(
                            label="Select Profile to Inspect & Edit",
                            choices=get_profile_choices(),
                            value=get_profile_choices()[0] if get_profile_choices() else None
                        )
                        refresh_lib_btn = gr.Button("🔄 Refresh", variant="secondary", size="sm")

                    summary_view = gr.Markdown(value="*Select a profile above to inspect.*")

            # RIGHT: Contextual Speaker Inspector & Editor
            with gr.Column(scale=5):
                with gr.Group(elem_classes=["studio-inspector"]):
                    gr.Markdown("#### 🎛️ Speaker Inspector & Metadata")
                    
                    edit_name = gr.Textbox(label="Speaker Name")
                    edit_desc = gr.Textbox(label="Description", lines=2)
                    edit_lang = gr.Radio(choices=["multilingual", "khmer", "english"], label="Language")
                    edit_trans = gr.Textbox(
                        label="Verbatim Transcript (Required for Hi-Fi Cloning)",
                        lines=3
                    )

                    with gr.Row():
                        ref_player = gr.Audio(label="Reference Segment (48kHz WAV)", type="filepath", interactive=False)
                        orig_player = gr.Audio(label="Original Source Recording", type="filepath", interactive=False)

                    with gr.Accordion("🔄 Replace Reference Audio Recording", open=False):
                        replace_audio_box = gr.Audio(label="Replacement Audio File", sources=["upload", "microphone"], type="filepath")
                        with gr.Row():
                            rep_trim_start = gr.Number(label="Start Time (s)", value=0.0)
                            rep_trim_end = gr.Number(label="End Time (s)", value=20.0)
                        rep_trans = gr.Textbox(label="New Transcript (Optional)", placeholder="Leave blank to keep current...")
                        replace_audio_btn = gr.Button("🔄 Apply Audio Replacement", variant="secondary", size="sm")
                        replace_status = gr.Label(label="Replacement Status", value="Ready")

                    with gr.Row():
                        save_btn = gr.Button("💾 Save Changes", variant="primary")
                    
                    with gr.Row():
                        confirm_del = gr.Checkbox(label="I confirm permanent deletion of this profile", value=False)
                        delete_btn = gr.Button("🗑️ Delete Profile", variant="stop", size="sm")

                    lib_status = gr.Label(label="Action Feedback", value="Ready")

        # Event Handlers
        profile_selector.change(
            fn=load_profile_details,
            inputs=[profile_selector],
            outputs=[edit_name, edit_desc, edit_lang, edit_trans, ref_player, orig_player, summary_view]
        )

        refresh_lib_btn.click(
            fn=lambda: (gr.update(choices=get_profile_choices()), get_voice_cards_html()),
            outputs=[profile_selector, voice_cards_display]
        )

        save_btn.click(
            fn=handle_update_profile,
            inputs=[profile_selector, edit_name, edit_desc, edit_lang, edit_trans],
            outputs=[lib_status, profile_selector, voice_cards_display]
        )

        replace_audio_btn.click(
            fn=handle_replace_audio,
            inputs=[profile_selector, replace_audio_box, rep_trim_start, rep_trim_end, rep_trans],
            outputs=[replace_status]
        ).then(
            fn=load_profile_details,
            inputs=[profile_selector],
            outputs=[edit_name, edit_desc, edit_lang, edit_trans, ref_player, orig_player, summary_view]
        ).then(
            fn=get_voice_cards_html,
            outputs=[voice_cards_display]
        )

        delete_btn.click(
            fn=handle_delete_profile,
            inputs=[profile_selector, confirm_del],
            outputs=[lib_status, profile_selector, voice_cards_display]
        )
