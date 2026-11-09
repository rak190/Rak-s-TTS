"""
VoiceStudio Pro — Khmer Voice Collection & Instant Voice Preview (Voice Library Tab).
Apple HIG & ElevenLabs-inspired Creative Voice Marketplace:
- Rich showcase with visual avatars, category pills, gender badges, and verification status.
- Instant Voice Preview with ZERO inference overhead (plays directly from local disk).
- One-click global voice selection that synchronizes across Speech Studio and Smart Script Studio.
- Favorites and recent usage tracking with persistent SQLite Schema v5 storage.
- Authorized Voice Pack (.zip / audio) import and export workflows.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import gradio as gr

from app.services.voice_service import VoiceProfileService
from app.audio.processor import AudioProcessor
from app.config import VOICES_DIR

def format_choice_label(p) -> str:
    star = "⭐ " if p.is_favorite else ""
    trophy = "🏆 " if p.is_default else ""
    status_icon = "✅ " if p.validation_status == "verified" else "📦 "
    name_display = p.display_name or p.name
    cat = f" [{p.category.capitalize()}]" if p.category else ""
    return f"{trophy}{star}{status_icon}{name_display}{cat} ({p.id})"

def extract_id_from_choice(choice: str) -> Optional[str]:
    if not choice or "(" not in choice or ")" not in choice:
        return None
    return choice.split("(")[-1].replace(")", "").strip()

def get_profile_choices(
    search_term: str = "",
    cat_filter: str = "All",
    gender_filter: str = "All",
    status_filter: str = "All"
) -> List[str]:
    service = VoiceProfileService.get_instance()
    profiles = service.search_catalog(
        search_term=search_term if search_term else "",
        category=None if cat_filter == "All" else cat_filter,
        gender=None if gender_filter == "All" else gender_filter,
        favorites_only=(status_filter == "⭐ Favorites"),
        validation_status="verified" if status_filter == "Verified Ready" else ("template" if status_filter == "Templates Only" else None)
    )
    if not profiles:
        return ["No matching voices found"]
    return [format_choice_label(p) for p in profiles]

def render_voice_cards_html(
    search_term: str = "",
    cat_filter: str = "All",
    gender_filter: str = "All",
    status_filter: str = "All"
) -> str:
    """Renders visual voice cards in an Apple/Linear design system."""
    service = VoiceProfileService.get_instance()
    profiles = service.search_catalog(
        search_term=search_term if search_term else "",
        category=None if cat_filter == "All" else cat_filter,
        gender=None if gender_filter == "All" else gender_filter,
        favorites_only=(status_filter == "⭐ Favorites"),
        validation_status="verified" if status_filter == "Verified Ready" else ("template" if status_filter == "Templates Only" else None)
    )

    if not profiles:
        return """
        <div style="background: var(--studio-surface-card); border: 1px dashed var(--studio-border); border-radius: var(--radius-md); padding: 32px; text-align: center; color: var(--studio-text-secondary);">
            <div style="font-size: 24px; margin-bottom: 8px;">🔍</div>
            <div style="font-weight: 600; font-size: 15px;">No voice profiles matched your search or filter.</div>
            <div style="font-size: 13px; margin-top: 4px;">Try clearing search keywords or selecting "All" categories.</div>
        </div>
        """

    # Category icons
    cat_icons = {
        "educational": "🎓",
        "storytelling": "📖",
        "professional": "💼",
        "conversational": "💬",
        "presentation": "🏛️",
        "character": "🎭",
        "general": "🎙️"
    }

    # Avatar color gradients based on gender / category
    def get_avatar_gradient(p) -> str:
        if p.gender == "female":
            return "linear-gradient(135deg, #FF6B95, #8F7CF2)"
        elif p.gender == "male":
            return "linear-gradient(135deg, #4A90E2, #7B68EE)"
        return "linear-gradient(135deg, #10B981, #6366F1)"

    html_parts = [
        "<div style='display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; margin-top: 8px;'>"
    ]

    for p in profiles:
        initial = (p.khmer_display_name[:2] if p.khmer_display_name else (p.display_name[:2] if p.display_name else p.name[:2])).upper()
        icon = cat_icons.get(p.category.lower(), "🎙️")
        grad = get_avatar_gradient(p)
        
        status_badge = (
            "<span class='studio-pill studio-pill-accent' style='background: rgba(88, 201, 161, 0.15); color: #58C9A1; border: 1px solid rgba(88, 201, 161, 0.3); font-size: 11px;'>✅ Ready</span>"
            if p.validation_status == "verified" else
            "<span class='studio-pill' style='background: rgba(233, 183, 110, 0.15); color: #E9B76E; border: 1px solid rgba(233, 183, 110, 0.3); font-size: 11px;'>📦 Needs Audio</span>"
        )
        
        default_badge = "<span style='margin-left: 6px; font-size: 12px;' title='Active Default Voice across Speech & Script Studio'>🏆</span>" if p.is_default else ""
        fav_badge = "<span style='margin-left: 4px; font-size: 12px;' title='Favorited Voice'>⭐</span>" if p.is_favorite else ""
        gender_icon = "👩" if p.gender == "female" else ("👨" if p.gender == "male" else "👤")

        disp_title = p.display_name or p.name
        dur_text = f"{p.duration_sec:.1f}s" if p.duration_sec > 0 else "Template"
        style_quote = p.speaking_style or "Natural speech"

        html_parts.append(f"""
        <div style="background: var(--studio-surface-elevated); border: 1px solid var(--studio-border); border-radius: var(--radius-md); padding: 16px; display: flex; flex-direction: column; justify-content: space-between; transition: all 0.2s ease; box-shadow: var(--shadow-soft);">
            <div>
                <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div style="width: 44px; height: 44px; border-radius: 50%; background: {grad}; color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.25); flex-shrink: 0;">
                            {initial}
                        </div>
                        <div style="overflow: hidden;">
                            <div style="font-size: 15px; font-weight: 700; color: var(--studio-text-primary); text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">
                                {disp_title} {default_badge} {fav_badge}
                            </div>
                            <div style="font-size: 12px; color: var(--studio-text-secondary); margin-top: 1px;">
                                {gender_icon} {p.gender.capitalize()} • {icon} {p.category.capitalize()}
                            </div>
                        </div>
                    </div>
                    {status_badge}
                </div>

                <div style="font-size: 12.5px; color: var(--studio-text-secondary); margin: 12px 0 8px 0; line-height: 1.45; font-style: italic; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">
                    “{style_quote}”
                </div>
            </div>

            <div style="border-top: 1px solid var(--studio-border-subtle); padding-top: 10px; margin-top: 6px; display: flex; justify-content: space-between; align-items: center; font-size: 11.5px; color: var(--studio-text-muted);">
                <span>⏱️ {dur_text}</span>
                <span style="font-family: monospace; font-size: 11px;">ID: {p.id[-6:]}</span>
            </div>
        </div>
        """)

    html_parts.append("</div>")
    return "\n".join(html_parts)

def get_active_voice_banner_md() -> str:
    service = VoiceProfileService.get_instance()
    default_p = service.get_default_profile()
    if not default_p:
        return "ℹ️ *No default voice configured.* Select a voice below and click **Set as Active Voice**."
    
    star = "⭐ " if default_p.is_favorite else ""
    disp = default_p.display_name or default_p.name
    lang = "🇰🇭 Khmer" if default_p.language.lower() == "khmer" else ("🇬🇧 English" if default_p.language.lower() == "english" else "🌐 Multilingual")
    dur = f"{default_p.duration_sec:.1f}s" if default_p.duration_sec > 0 else "Ready"
    
    return f"""
<div style="background: var(--studio-surface-card); border: 1px solid var(--studio-accent); border-radius: var(--radius-md); padding: 12px 16px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 22px;">🏆</span>
        <div>
            <div style="font-size: 11px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em; color: var(--studio-accent);">Active Studio Voice (Synchronized)</div>
            <div style="font-size: 16px; font-weight: 700; color: var(--studio-text-primary);">{star}{disp} <span style="font-size: 13px; font-weight: normal; color: var(--studio-text-secondary);">({lang} • {default_p.category.capitalize()})</span></div>
        </div>
    </div>
    <div style="display: flex; align-items: center; gap: 8px;">
        <span class="studio-pill studio-pill-accent" style="font-size: 11px;">48kHz Reference · {dur}</span>
        <span class="studio-pill" style="font-size: 11px;">Speech & Smart Script Synchronized</span>
    </div>
</div>
"""

def on_select_voice(selected_choice: str) -> Tuple[
    str, str, str, str, str, str, str, str, Optional[str], str, str
]:
    """Loads voice details into the inspector and preview dock."""
    p_id = extract_id_from_choice(selected_choice)
    if not p_id:
        return ("", "", "", "general", "unspecified", "", "", "", None, "No voice selected", "*Select a voice above to inspect details.*")

    service = VoiceProfileService.get_instance()
    p = service.get_profile(p_id)
    if not p:
        return ("", "", "", "general", "unspecified", "", "", "", None, "Profile not found", "*Profile not found.*")

    # Preview path resolution: STRICT ZERO INFERENCE!
    preview_path = None
    preview_status_text = ""
    if p.preview_audio_path and Path(p.preview_audio_path).exists():
        preview_path = p.preview_audio_path
        preview_status_text = f"🎧 Instant Zero-Inference Preview: {Path(preview_path).name} ({p.duration_sec:.1f}s @ 48kHz PCM Mono)"
    elif p.reference_segment_path and Path(p.reference_segment_path).exists():
        preview_path = p.reference_segment_path
        preview_status_text = f"🎧 Reference Clip Preview: {Path(preview_path).name} ({p.duration_sec:.1f}s @ 48kHz PCM Mono)"
    else:
        preview_status_text = "⚠️ No audio clip attached to this voice yet (Template). Upload or import an audio file below."

    # Inspector markdown summary
    status_label = "✅ Verified Ready for TTS" if p.validation_status == "verified" else "📦 Template (Audio Needed)"
    fav_label = "⭐ Favorited" if p.is_favorite else "Not favorited"
    default_label = "🏆 Active Studio Default" if p.is_default else "Standard voice"

    summary_md = f"""
### `{p.display_name or p.name}`
* **Category:** `{p.category.capitalize()}` | **Gender:** `{p.gender.capitalize()}` | **Language:** `{p.language}`
* **Status:** `{status_label}` | **Selection:** `{default_label}` • `{fav_label}`
* **Acoustics:** `{p.duration_sec:.1f}s @ {p.sample_rate:,} Hz` | **License:** `{p.source_license}`
* **Style:** *"{p.speaking_style or 'Natural'}"*
"""

    return (
        p.name,
        p.display_name or p.name,
        p.khmer_display_name or "",
        p.category.lower(),
        p.gender.lower(),
        p.speaking_style or "",
        p.transcript or "",
        p.source_license or "Local User Audio",
        preview_path,
        preview_status_text,
        summary_md
    )

def handle_quick_preview(selected_choice: str) -> Tuple[Optional[str], str]:
    """Plays audio preview instantly with ZERO VoxCPM2 inference."""
    p_id = extract_id_from_choice(selected_choice)
    if not p_id:
        return None, "⚠️ Please select a voice from the dropdown first."

    service = VoiceProfileService.get_instance()
    p = service.get_profile(p_id)
    if not p:
        return None, "⚠️ Voice profile not found."

    # Zero inference: check disk files only
    for candidate_path in [p.preview_audio_path, p.reference_segment_path]:
        if candidate_path and Path(candidate_path).exists():
            return candidate_path, f"▶️ Playing instant preview: {p.display_name or p.name} (0ms synthesis latency)"

    return None, f"⚠️ Voice '{p.display_name or p.name}' has no audio attached yet. Use 'Import Audio' below."

def handle_set_default(selected_choice: str) -> Tuple[str, str, gr.update]:
    """Synchronizes voice globally as default across Speech & Script Studio."""
    p_id = extract_id_from_choice(selected_choice)
    if not p_id:
        return "⚠️ Select a voice first.", get_active_voice_banner_md(), gr.update()

    service = VoiceProfileService.get_instance()
    p = service.get_profile(p_id)
    if not p:
        return "⚠️ Profile not found.", get_active_voice_banner_md(), gr.update()

    ok, msg = service.set_default(p_id)
    if not ok:
        return f"❌ {msg}", get_active_voice_banner_md(), gr.update()

    choices = get_profile_choices()
    new_val = format_choice_label(service.get_profile(p_id))
    return f"🏆 '{p.display_name or p.name}' is now active across all studios!", get_active_voice_banner_md(), gr.update(choices=choices, value=new_val)

def handle_toggle_favorite(selected_choice: str) -> Tuple[str, gr.update, str]:
    """Toggles favorite status."""
    p_id = extract_id_from_choice(selected_choice)
    if not p_id:
        return "⚠️ Select a voice first.", gr.update(), render_voice_cards_html()

    service = VoiceProfileService.get_instance()
    p = service.get_profile(p_id)
    if not p:
        return "⚠️ Profile not found.", gr.update(), render_voice_cards_html()

    new_fav = not bool(p.is_favorite)
    ok, msg = service.set_favorite(p_id, new_fav)
    choices = get_profile_choices()
    updated_p = service.get_profile(p_id)
    new_val = format_choice_label(updated_p) if updated_p else selected_choice
    return f"⭐ {msg}", gr.update(choices=choices, value=new_val), render_voice_cards_html()

def handle_save_inspector_metadata(
    selected_choice: str,
    name: str,
    display_name: str,
    khmer_display_name: str,
    category: str,
    gender: str,
    style: str,
    transcript: str,
    license: str
) -> Tuple[str, gr.update, str, str]:
    """Saves updated metadata in SQLite and JSON artifacts."""
    p_id = extract_id_from_choice(selected_choice)
    if not p_id:
        return "⚠️ Select a voice first.", gr.update(), render_voice_cards_html(), get_active_voice_banner_md()

    service = VoiceProfileService.get_instance()
    ok, msg = service.update_profile(
        profile_id=p_id,
        name=name,
        display_name=display_name,
        khmer_display_name=khmer_display_name,
        category=category,
        gender=gender,
        speaking_style=style,
        transcript=transcript,
        source_license=license
    )

    choices = get_profile_choices()
    updated_p = service.get_profile(p_id)
    new_val = format_choice_label(updated_p) if updated_p else selected_choice
    return f"✅ {msg}", gr.update(choices=choices, value=new_val), render_voice_cards_html(), get_active_voice_banner_md()

def handle_attach_audio_to_voice(
    selected_choice: str,
    audio_path: str,
    start_sec: float,
    end_sec: float,
    transcript: str
) -> Tuple[str, Optional[str], gr.update, str, str]:
    """Attaches or replaces audio for any voice profile or template."""
    p_id = extract_id_from_choice(selected_choice)
    if not p_id:
        return "⚠️ Select a voice first.", None, gr.update(), render_voice_cards_html(), get_active_voice_banner_md()
    if not audio_path or not Path(audio_path).exists():
        return "⚠️ Please upload or record an audio file first.", None, gr.update(), render_voice_cards_html(), get_active_voice_banner_md()

    service = VoiceProfileService.get_instance()
    ok, msg = service.replace_reference_audio(
        profile_id=p_id,
        new_audio_path=audio_path,
        trim_start_sec=start_sec if start_sec > 0 else None,
        trim_end_sec=end_sec if end_sec > start_sec else None,
        transcript=transcript
    )

    if not ok:
        return f"❌ {msg}", None, gr.update(), render_voice_cards_html(), get_active_voice_banner_md()

    choices = get_profile_choices()
    updated_p = service.get_profile(p_id)
    new_val = format_choice_label(updated_p) if updated_p else selected_choice
    preview_audio = updated_p.preview_audio_path if (updated_p and updated_p.preview_audio_path) else None

    return f"✅ {msg}", preview_audio, gr.update(choices=choices, value=new_val), render_voice_cards_html(), get_active_voice_banner_md()

def handle_export_voice_pack(selected_choice: str) -> Tuple[str, Optional[str]]:
    """Exports a voice profile to a downloadable .zip archive."""
    p_id = extract_id_from_choice(selected_choice)
    if not p_id:
        return "⚠️ Select a voice first.", None

    service = VoiceProfileService.get_instance()
    zip_path, msg = service.export_voice_pack(p_id)
    if zip_path and Path(zip_path).exists():
        return f"📦 {msg}", str(zip_path)
    return f"❌ {msg}", None

def handle_import_voice_pack(
    file_path: str,
    name: str,
    display_name: str,
    khmer_name: str,
    category: str,
    gender: str,
    style: str,
    transcript: str
) -> Tuple[str, gr.update, str, str]:
    """Imports an authorized voice pack (.zip or audio file)."""
    if not file_path or not Path(file_path).exists():
        return "⚠️ Please upload a .zip voice pack or audio file.", gr.update(), render_voice_cards_html(), get_active_voice_banner_md()

    meta = {
        "name": name.strip(),
        "display_name": display_name.strip(),
        "khmer_display_name": khmer_name.strip(),
        "category": category.lower(),
        "gender": gender.lower(),
        "speaking_style": style.strip(),
        "transcript": transcript.strip()
    }

    service = VoiceProfileService.get_instance()
    profile, msg = service.import_voice_pack(file_path, metadata=meta)
    if not profile:
        return f"❌ {msg}", gr.update(), render_voice_cards_html(), get_active_voice_banner_md()

    choices = get_profile_choices()
    new_val = format_choice_label(profile)
    return f"✅ {msg} Added '{profile.display_name or profile.name}' to library.", gr.update(choices=choices, value=new_val), render_voice_cards_html(), get_active_voice_banner_md()

def handle_delete_voice(selected_choice: str, confirmed: bool) -> Tuple[str, gr.update, str, str]:
    """Deletes a voice profile after explicit user confirmation."""
    p_id = extract_id_from_choice(selected_choice)
    if not p_id:
        return "⚠️ Select a voice first.", gr.update(), render_voice_cards_html(), get_active_voice_banner_md()
    if not confirmed:
        return "⚠️ Please check the confirmation checkbox before clicking delete.", gr.update(), render_voice_cards_html(), get_active_voice_banner_md()

    service = VoiceProfileService.get_instance()
    ok, msg = service.delete_profile(p_id)
    choices = get_profile_choices()
    new_val = choices[0] if choices else None
    return f"🗑️ {msg}", gr.update(choices=choices, value=new_val), render_voice_cards_html(), get_active_voice_banner_md()

def create_library_tab():
    """Builds the Apple/ElevenLabs inspired Voice Library tab."""
    service = VoiceProfileService.get_instance()
    service.seed_khmer_voice_collection()
    initial_choices = get_profile_choices()
    initial_val = initial_choices[0] if initial_choices else None

    with gr.Tab("🎙️ Voice Library", id="tab_library"):
        # Header & Subtitle
        gr.HTML(
            """
            <header class="tts-page-head">
                <div>
                    <div class="eyebrow">VOICESTUDIO / DISCOVERY</div>
                    <h1>Khmer Voice Collection</h1>
                    <p>Curated speaker identities, instant zero-inference preview, and voice pack management.</p>
                </div>
                <div class="local-status">
                    <i></i> Instant Preview <span>·</span> 0ms Inference Latency
                </div>
            </header>
            """
        )

        # Active Voice Synchronized Banner
        active_voice_banner = gr.HTML(value=get_active_voice_banner_md)

        # Search, Filter and Discovery Bar
        with gr.Row(elem_classes=["studio-canvas-card"]):
            with gr.Column(scale=4):
                search_input = gr.Textbox(
                    label="Search Catalog",
                    placeholder="Search by name, Khmer name, speaking style, or tag...",
                    show_label=False,
                    elem_classes=["studio-search-bar"]
                )
            with gr.Column(scale=3):
                category_filter = gr.Dropdown(
                    label="Category",
                    choices=["All", "Educational", "Storytelling", "Professional", "Conversational", "Presentation"],
                    value="All"
                )
            with gr.Column(scale=2):
                gender_filter = gr.Dropdown(
                    label="Gender",
                    choices=["All", "Female", "Male"],
                    value="All"
                )
            with gr.Column(scale=3):
                status_filter = gr.Dropdown(
                    label="Status",
                    choices=["All", "Verified Ready", "⭐ Favorites", "Templates Only"],
                    value="All"
                )

        # Main Workspace: 2-Column Experience
        with gr.Row():
            # LEFT: Voice Grid Showcase & Instant Preview Player
            with gr.Column(scale=6):
                with gr.Group(elem_classes=["studio-canvas-card"]):
                    gr.Markdown("#### 🎙️ Voice Catalog Showcase")
                    voice_cards_display = gr.HTML(value=render_voice_cards_html)

                # Dedicated Instant Preview Audio Dock (Zero Inference)
                with gr.Group(elem_classes=["studio-canvas-card"]):
                    gr.Markdown("#### 🎧 Instant Voice Preview (Zero Inference Overhead)")
                    gr.Markdown("*Instant playback of pre-rendered 48kHz audio directly from local storage. Never loads VoxCPM2 or taxes CPU.*")
                    instant_preview_player = gr.Audio(
                        label="",
                        show_label=False,
                        type="filepath",
                        interactive=False,
                        elem_classes=["studio-audio-output"]
                    )
                    preview_status_badge = gr.Markdown(value="Select a voice and click ▶️ Quick Preview.")

            # RIGHT: Contextual Inspector & Actions
            with gr.Column(scale=4):
                with gr.Group(elem_classes=["studio-inspector"]):
                    gr.Markdown("#### 🎛️ Voice Inspector & Actions")

                    with gr.Row():
                        voice_selector = gr.Dropdown(
                            label="Selected Voice Profile",
                            choices=initial_choices,
                            value=initial_val,
                            scale=4
                        )
                        refresh_btn = gr.Button("🔄", variant="secondary", size="sm", scale=1)

                    summary_markdown = gr.Markdown(value="*Select a voice above to inspect details.*")

                    # Primary Action Buttons
                    with gr.Row():
                        quick_preview_btn = gr.Button("▶️ Quick Preview", variant="primary", size="sm")
                        set_default_btn = gr.Button("🏆 Set as Active Voice", variant="secondary", size="sm")
                        toggle_fav_btn = gr.Button("⭐ Favorite", variant="secondary", size="sm")

                    action_feedback = gr.Markdown(value="")

                    # Inspector Form
                    with gr.Accordion("📝 Edit Voice Metadata", open=False):
                        edit_name = gr.Textbox(label="Identifier / Slug")
                        edit_disp_name = gr.Textbox(label="English Display Name")
                        edit_khmer_name = gr.Textbox(label="Khmer Display Name (ឈ្មោះខ្មែរ)")
                        with gr.Row():
                            edit_cat = gr.Dropdown(
                                label="Category",
                                choices=["educational", "storytelling", "professional", "conversational", "presentation", "general"]
                            )
                            edit_gender = gr.Dropdown(
                                label="Gender",
                                choices=["female", "male", "unspecified"]
                            )
                        edit_style = gr.Textbox(label="Speaking Style / Persona")
                        edit_transcript = gr.Textbox(label="Verbatim Transcript (for Hi-Fi Cloning)", lines=2)
                        edit_license = gr.Textbox(label="Source Provenance & License")
                        save_meta_btn = gr.Button("💾 Save Metadata", variant="secondary", size="sm")

                    # Audio Replacement / Activation
                    with gr.Accordion("🔄 Attach / Replace Audio Recording", open=False):
                        gr.Markdown("*Upload a clean 48kHz WAV/MP3 to activate this template or replace reference audio.*")
                        upload_audio_box = gr.Audio(label="Audio File", sources=["upload", "microphone"], type="filepath")
                        with gr.Row():
                            trim_start = gr.Number(label="Trim Start (s)", value=0.0)
                            trim_end = gr.Number(label="Trim End (s)", value=20.0)
                        rep_trans = gr.Textbox(label="Transcript (Optional)", placeholder="Audio transcript...")
                        apply_audio_btn = gr.Button("⚡ Apply Audio to Voice", variant="primary", size="sm")

                    # Voice Pack Export
                    with gr.Accordion("📦 Export Voice Pack (.zip)", open=False):
                        gr.Markdown("*Download a standalone .zip package containing reference audio, transcript, and metadata.*")
                        export_pack_btn = gr.Button("📦 Generate Voice Pack ZIP", variant="secondary", size="sm")
                        export_download_file = gr.File(label="Download Voice Pack", interactive=False)

                    # Delete Voice
                    with gr.Accordion("🗑️ Delete Voice Profile", open=False):
                        del_confirm = gr.Checkbox(label="I confirm permanent deletion of this voice profile", value=False)
                        delete_voice_btn = gr.Button("🗑️ Delete Voice", variant="stop", size="sm")

        # Bottom Drawer: Voice Pack Importer
        with gr.Accordion("📥 Import Authorized Voice Pack (ZIP or Audio)", open=False, elem_classes=["studio-canvas-card"]):
            gr.Markdown(
                """
                **Import an authorized Khmer voice package or audio recording.**
                Supports `.zip` voice packs (with audio + metadata.json) or raw audio files (`.wav`, `.mp3`, `.m4a`, `.flac`).
                All audio is automatically resampled to pristine 48kHz mono.
                """
            )
            with gr.Row():
                with gr.Column(scale=5):
                    import_file = gr.File(label="Upload Voice Pack (.zip) or Audio File", file_types=[".zip", ".wav", ".mp3", ".m4a", ".flac"])
                with gr.Column(scale=5):
                    with gr.Row():
                        imp_name = gr.Textbox(label="Voice Name / Slug", placeholder="e.g. Sokha")
                        imp_khmer = gr.Textbox(label="Khmer Name", placeholder="e.g. សុខា")
                    with gr.Row():
                        imp_cat = gr.Dropdown(label="Category", choices=["educational", "storytelling", "professional", "conversational", "presentation", "general"], value="educational")
                        imp_gender = gr.Dropdown(label="Gender", choices=["female", "male", "unspecified"], value="female")
                    imp_style = gr.Textbox(label="Speaking Style", placeholder="e.g. Calm Educational / Friendly")
                    imp_trans = gr.Textbox(label="Verbatim Transcript", placeholder="Transcript for Hi-Fi Cloning...")
                    import_btn = gr.Button("📥 Import Voice Pack", variant="primary")
            import_status_box = gr.Markdown(value="")

        # ---------------------------------------------------------------------
        # Event Handlers & Reactive Wiring
        # ---------------------------------------------------------------------
        # Filtering triggers
        def apply_catalog_filters(q, c, g, s):
            choices = get_profile_choices(search_term=q, cat_filter=c, gender_filter=g, status_filter=s)
            cards = render_voice_cards_html(search_term=q, cat_filter=c, gender_filter=g, status_filter=s)
            val = choices[0] if choices else None
            return gr.update(choices=choices, value=val), cards

        for trigger in [search_input.change, category_filter.change, gender_filter.change, status_filter.change]:
            trigger(
                fn=apply_catalog_filters,
                inputs=[search_input, category_filter, gender_filter, status_filter],
                outputs=[voice_selector, voice_cards_display]
            )

        # Refresh button
        refresh_btn.click(
            fn=lambda: (
                gr.update(choices=get_profile_choices(), value=get_profile_choices()[0] if get_profile_choices() else None),
                render_voice_cards_html(),
                get_active_voice_banner_md()
            ),
            outputs=[voice_selector, voice_cards_display, active_voice_banner]
        )

        # Voice selection change loads details into inspector & preview
        voice_selector.change(
            fn=on_select_voice,
            inputs=[voice_selector],
            outputs=[
                edit_name, edit_disp_name, edit_khmer_name, edit_cat, edit_gender,
                edit_style, edit_transcript, edit_license,
                instant_preview_player, preview_status_badge, summary_markdown
            ]
        )

        # Quick preview button (ZERO INFERENCE)
        quick_preview_btn.click(
            fn=handle_quick_preview,
            inputs=[voice_selector],
            outputs=[instant_preview_player, preview_status_badge]
        )

        # Set as global active default voice
        set_default_btn.click(
            fn=handle_set_default,
            inputs=[voice_selector],
            outputs=[action_feedback, active_voice_banner, voice_selector]
        ).then(
            fn=render_voice_cards_html,
            outputs=[voice_cards_display]
        )

        # Toggle favorite
        toggle_fav_btn.click(
            fn=handle_toggle_favorite,
            inputs=[voice_selector],
            outputs=[action_feedback, voice_selector, voice_cards_display]
        )

        # Save metadata
        save_meta_btn.click(
            fn=handle_save_inspector_metadata,
            inputs=[
                voice_selector, edit_name, edit_disp_name, edit_khmer_name,
                edit_cat, edit_gender, edit_style, edit_transcript, edit_license
            ],
            outputs=[action_feedback, voice_selector, voice_cards_display, active_voice_banner]
        )

        # Attach/replace audio
        apply_audio_btn.click(
            fn=handle_attach_audio_to_voice,
            inputs=[voice_selector, upload_audio_box, trim_start, trim_end, rep_trans],
            outputs=[action_feedback, instant_preview_player, voice_selector, voice_cards_display, active_voice_banner]
        )

        # Export Voice Pack
        export_pack_btn.click(
            fn=handle_export_voice_pack,
            inputs=[voice_selector],
            outputs=[action_feedback, export_download_file]
        )

        # Delete Voice
        delete_voice_btn.click(
            fn=handle_delete_voice,
            inputs=[voice_selector, del_confirm],
            outputs=[action_feedback, voice_selector, voice_cards_display, active_voice_banner]
        )

        # Import Voice Pack
        import_btn.click(
            fn=handle_import_voice_pack,
            inputs=[import_file, imp_name, imp_name, imp_khmer, imp_cat, imp_gender, imp_style, imp_trans],
            outputs=[import_status_box, voice_selector, voice_cards_display, active_voice_banner]
        )
