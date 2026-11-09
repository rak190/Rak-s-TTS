"""
VoiceStudio Pro — Smart Script-to-Speech Studio UI Tab.
Apple-inspired 4-Zone Storyboard & Multi-Speaker Narration Workspace:
- LEFT PANEL: Scene navigation, scene numbers, duration targets, completion status, scene reordering.
- CENTER PANEL: Spoken dialogue blocks, narration editor, split/merge segment tools, spoken preview,
  excluded production notes inspector, and scene playback.
- RIGHT INSPECTOR: Multi-speaker role mapping, voice profile assignment, cloning mode, delivery style,
  speaking pace, Hi-Fi mode compatibility guardrails, and advanced synthesis settings.
- BOTTOM BAR: Timeline duration comparison table, complete narration playback, and 7-format export suite.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr

from app.config import BASE_DIR
from app.services.script_parser import (
    SUPPORTED_DELIVERY_STYLES,
    SUPPORTED_PACES,
    SUPPORTED_SPEAKER_ROLES,
    ScriptProject,
    StoryboardScene,
    VoiceDirectionValidator,
)
from app.services.script_project_service import ScriptProjectService
from app.services.voice_service import VoiceProfileService
from app.utils.text_processor import TextProcessor

SAMPLE_DOCX_FIXTURE = BASE_DIR / "tests" / "fixtures" / "ICT_Grade8_AI_Animation_Video_Storyboard_KM.docx"


def get_voice_choices() -> List[str]:
    profiles = VoiceProfileService.get_instance().list_profiles()
    choices = ["Default Voice (No Profile)"]
    for p in profiles:
        choices.append(f"{p.name} ({p.id})")
    return choices


def mode_internal_to_ui(mode: str) -> str:
    m = (mode or "tts").lower()
    if m == "cloning":
        return "Voice Cloning"
    if m == "ultimate_cloning":
        return "Ultimate Cloning"
    return "Ordinary TTS"


def mode_ui_to_internal(ui_mode: str) -> str:
    if ui_mode == "Voice Cloning":
        return "cloning"
    if ui_mode == "Ultimate Cloning":
        return "ultimate_cloning"
    return "tts"


def format_project_header_md(project: Optional[ScriptProject]) -> str:
    if not project:
        return "### 📄 No Storyboard Loaded\nImport a `.docx`, `.txt`, or `.md` storyboard, load the Grade 8 AI Sample, or paste a script."

    md = f"### 🎬 {project.title}\n"
    meta_parts = []
    if project.topic:
        meta_parts.append(f"**Topic:** {project.topic}")
    if project.audience:
        meta_parts.append(f"**Audience:** {project.audience}")
    if project.planned_duration_label:
        meta_parts.append(f"**Planned Duration:** {project.planned_duration_label} ({project.planned_duration_sec:.0f}s)")
    if project.aspect_ratio:
        meta_parts.append(f"**Format:** {project.aspect_ratio}")
    if meta_parts:
        md += " &nbsp;•&nbsp; ".join(meta_parts) + "\n\n"

    if project.validation_warnings:
        for w in project.validation_warnings:
            md += f"> {w}\n\n"

    return md


def format_scene_nav_choices(project: Optional[ScriptProject]) -> List[str]:
    if not project or not project.scenes:
        return []
    choices = []
    for sc in project.scenes:
        icon = "✅" if sc.status == "completed" else ("⚠️" if sc.status == "partial" else "⏳")
        choices.append(
            f"{sc.scene_id} | #{sc.scene_number} {icon} [{sc.target_start_time}–{sc.target_end_time}] {sc.title[:34]}"
        )
    return choices


def extract_scene_id_from_choice(choice: Optional[str]) -> Optional[str]:
    if not choice:
        return None
    return choice.split("|")[0].strip()


def format_scene_nav_table(project: Optional[ScriptProject]) -> List[List[Any]]:
    if not project:
        return []
    rows = []
    for sc in project.scenes:
        actual_str = f"{sc.actual_duration_sec:.1f}s" if sc.actual_duration_sec > 0 else "—"
        rows.append(
            [
                sc.scene_number,
                sc.title,
                f"{sc.target_start_time}–{sc.target_end_time}",
                f"{sc.target_duration_sec:.0f}s",
                actual_str,
                sc.status.upper(),
            ]
        )
    return rows


def format_segment_choices(scene: Optional[StoryboardScene]) -> List[str]:
    if not scene or not scene.dialogue_segments:
        return []
    out = []
    for seg in scene.dialogue_segments:
        preview = seg.text[:36] + ("..." if len(seg.text) > 36 else "")
        out.append(f"{seg.segment_id} | #{seg.index + 1} [{seg.speaker_role}] {preview}")
    return out


def extract_segment_id_from_choice(choice: Optional[str]) -> Optional[str]:
    if not choice:
        return None
    return choice.split("|")[0].strip()


def format_dialogue_blocks_md(scene: Optional[StoryboardScene]) -> str:
    if not scene:
        return "*Select a scene on the left to inspect and edit its spoken dialogue blocks.*"
    if not scene.dialogue_segments:
        return "⚠️ *No spoken dialogue blocks in this scene.*"

    lines = [
        f"#### 🗣️ Scene {scene.scene_number}: {scene.title} &nbsp; `[{scene.target_start_time}–{scene.target_end_time}]` (Target: `{scene.target_duration_sec:.0f}s`)"
    ]
    for seg in scene.dialogue_segments:
        st_icon = "✅" if seg.status == "completed" else ("❌" if seg.status == "failed" else "🎙️")
        dur_badge = f" • `{seg.duration_sec:.1f}s`" if seg.duration_sec > 0 else ""
        lines.append(
            f"- **{st_icon} Block {seg.index + 1} — `{seg.speaker_role}`** "
            f"*(Voice: `{seg.voice_name}` · Mode: `{mode_internal_to_ui(seg.mode)}` · Style: `{seg.delivery_style}` · Pace: `{seg.pace}`{dur_badge})*\n"
            f"  > {seg.text}"
        )
    if scene.validation_warnings:
        lines.append("\n**Scene Warnings:**")
        for w in scene.validation_warnings:
            lines.append(f"- ⚠️ {w}")
    return "\n".join(lines)


def format_production_metadata_md(project: Optional[ScriptProject], scene: Optional[StoryboardScene]) -> str:
    if not project or not scene:
        return "*Non-spoken visual, music, SFX, and checklist notes appear here.*"

    kw_str = ", ".join(f"`{k}`" for k in scene.keywords) if scene.keywords else "*None*"
    md = f"""**🔒 Strictly Excluded from Speech Synthesis (Production Metadata Only):**
- **🎬 Visual & Animation (`រូបភាព និងចលនា៖`):** {scene.visual_notes or '*None*'}
- **🏷️ On-Screen Keywords (`ពាក្យគន្លឹះ៖`):** {kw_str}
- **🔊 Scene SFX Notes:** {scene.sfx_notes or '*None*'}
- **🎵 Music Direction (`តន្ត្រី៖`):** {scene.music_notes or project.music_production_notes or '*None*'}
- **👩‍🏫 Voice Direction (`សំឡេង៖`):** {project.voice_production_notes or '*None*'}
"""
    if project.checklist_items:
        md += "\n**📋 Pre-Export Checklist (`៣. ការត្រួតពិនិត្យមុន Export` — Excluded from Speech):**\n"
        for item in project.checklist_items:
            md += f"- ☐ {item}\n"
    return md


def format_timeline_comparison_table(project: Optional[ScriptProject]) -> List[List[Any]]:
    if not project:
        return []
    svc = ScriptProjectService.get_instance()
    rows_dict = svc.get_timeline_comparison(project)
    table = []
    for r in rows_dict:
        table.append(
            [
                r["scene_number"],
                r["title"],
                r["window"],
                r["target_sec"],
                r["actual_sec"] if r["actual_sec"] > 0 else 0.0,
                r["diff_str"],
                r["status_badge"],
                r["recommendation"],
            ]
        )
    return table


def build_scene_ui_state(
    project: Optional[ScriptProject],
    selected_scene_id: Optional[str] = None,
    selected_seg_id: Optional[str] = None,
    status_msg: str = "✅ Project ready.",
):
    """Builds a complete tuple of Gradio UI updates for a project/scene/segment state."""
    if not project or not project.scenes:
        return (
            None,
            format_project_header_md(None),
            gr.update(choices=[], value=None),
            [],
            "*No scene loaded.*",
            gr.update(choices=[], value=None),
            "",
            "Narrator",
            "Default Voice (No Profile)",
            "Ordinary TTS",
            "Natural",
            "Medium",
            False,
            280,
            "",
            "*No production notes.*",
            "",
            "00:00",
            "00:00",
            400,
            1.0,
            None,
            [],
            status_msg,
        )

    scene = project.scenes[0]
    if selected_scene_id:
        for sc in project.scenes:
            if sc.scene_id == selected_scene_id:
                scene = sc
                break

    nav_choices = format_scene_nav_choices(project)
    selected_nav_val = next(
        (c for c in nav_choices if c.startswith(f"{scene.scene_id} |")),
        nav_choices[0] if nav_choices else None,
    )

    seg_choices = format_segment_choices(scene)
    seg = scene.dialogue_segments[0] if scene.dialogue_segments else None
    if selected_seg_id and scene.dialogue_segments:
        for s in scene.dialogue_segments:
            if s.segment_id == selected_seg_id:
                seg = s
                break

    selected_seg_val = (
        next(
            (c for c in seg_choices if c.startswith(f"{seg.segment_id} |")),
            seg_choices[0] if seg_choices else None,
        )
        if seg
        else None
    )

    seg_text = seg.text if seg else ""
    seg_role = seg.speaker_role if seg else "Teacher"
    voice_choices = get_voice_choices()
    seg_voice_val = "Default Voice (No Profile)"
    if seg and seg.voice_profile_id:
        for vc in voice_choices:
            if f"({seg.voice_profile_id})" in vc:
                seg_voice_val = vc
                break
    seg_mode_ui = mode_internal_to_ui(seg.mode) if seg else "Ordinary TTS"
    seg_style = seg.delivery_style if seg else "Educational"
    seg_pace = seg.pace if seg else "Medium"
    seg_style_prefix = bool(seg.enable_style_prefix) if seg else False
    seg_pause = int(seg.pause_after_ms) if seg else 280

    synth_preview, compat_msg = (
        VoiceDirectionValidator.build_synthesis_prompt(
            spoken_text=seg_text,
            delivery_style=seg_style,
            pace=seg_pace,
            mode=seg.mode if seg else "tts",
            enable_style_prefix=seg_style_prefix,
        )
        if seg
        else ("", "")
    )

    scene_audio = (
        scene.scene_wav_path
        if (scene.scene_wav_path and Path(scene.scene_wav_path).exists())
        else None
    )

    return (
        project.project_id,
        format_project_header_md(project),
        gr.update(choices=nav_choices, value=selected_nav_val),
        format_scene_nav_table(project),
        format_dialogue_blocks_md(scene),
        gr.update(choices=seg_choices, value=selected_seg_val),
        seg_text,
        seg_role,
        gr.update(choices=voice_choices, value=seg_voice_val),
        seg_mode_ui,
        seg_style,
        seg_pace,
        seg_style_prefix,
        seg_pause,
        synth_preview,
        format_production_metadata_md(project, scene),
        scene.title,
        scene.target_start_time,
        scene.target_end_time,
        scene.pause_after_scene_ms,
        scene.stretch_ratio,
        scene_audio,
        format_timeline_comparison_table(project),
        f"{status_msg} &nbsp;•&nbsp; {compat_msg}",
    )


def create_script_studio_tab():
    """Creates the Smart Script-to-Speech Studio tab inside VoiceStudio Pro."""
    svc = ScriptProjectService.get_instance()
    saved_projects = svc.list_projects()
    saved_choices = [f"{p.title} ({p.id})" for p in saved_projects]

    with gr.Tab("Smart Script Studio", id="tab_smart_script"):
        current_project_id = gr.State(value=None)

        gr.HTML(
            """
            <header class="tts-page-head">
                <div>
                    <div class="eyebrow">VOICESTUDIO / STORYBOARD & MULTI-SPEAKER NARRATION</div>
                    <h1>Smart Script Studio</h1>
                    <p>Import structured DOCX storyboards, separate spoken narration from visual directions, assign character voices, and synthesize timed scenes.</p>
                </div>
                <div class="local-status"><i></i> Khmer &amp; Bilingual NLP <span>·</span> 48 kHz</div>
            </header>
            """
        )

        # Top Import & Project Bar
        with gr.Row(elem_classes=["studio-canvas-card"]):
            with gr.Column(scale=4):
                doc_upload = gr.File(
                    label="Import Storyboard (.docx, .txt, .md)",
                    file_types=[".docx", ".txt", ".md"],
                    height=88,
                )
            with gr.Column(scale=4):
                load_sample_btn = gr.Button(
                    "🎓 Load Grade 8 AI Storyboard (Acceptance Fixture)",
                    variant="primary",
                    size="sm",
                )
                saved_project_dropdown = gr.Dropdown(
                    label="Saved Storyboard Projects",
                    choices=saved_choices,
                    value=saved_choices[0] if saved_choices else None,
                    interactive=True,
                )
                load_saved_btn = gr.Button("📂 Open Selected Project", variant="secondary", size="sm")
            with gr.Column(scale=4):
                with gr.Accordion("📋 Or Paste Raw Storyboard / Script Text", open=False):
                    paste_title_input = gr.Textbox(label="Project Title", value="Custom Storyboard")
                    paste_script_box = gr.Textbox(
                        label="Paste Script with សំឡេងអាន៖ / រូបភាព និងចលនា៖",
                        lines=4,
                        placeholder="1. HOOK [00:00–00:22]\nសំឡេងអាន៖ ...\nរូបភាព និងចលនា៖ ...",
                    )
                    parse_paste_btn = gr.Button("✨ Parse Pasted Storyboard", variant="secondary", size="sm")

        project_header_md = gr.Markdown(value=format_project_header_md(None))

        # 3-Column Core Workspace (Left: Scene Nav, Center: Dialogue Canvas, Right: Voice/Role Inspector)
        with gr.Row(elem_classes=["smart-script-workspace"]):
            # LEFT PANEL: Scene Navigation & Status
            with gr.Column(scale=3, min_width=270, elem_classes=["smart-left-nav"]):
                gr.Markdown("### 🎞️ Scene Navigator")
                scene_selector = gr.Dropdown(
                    label="Select Scene",
                    choices=[],
                    value=None,
                    interactive=True,
                )
                with gr.Row():
                    move_up_btn = gr.Button("⬆️ Move Up", variant="secondary", size="sm")
                    move_down_btn = gr.Button("⬇️ Move Down", variant="secondary", size="sm")

                scene_nav_table = gr.Dataframe(
                    headers=["#", "Title", "Window", "Target", "Actual", "Status"],
                    datatype=["number", "str", "str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                    label="Storyboard Scenes",
                )

            # CENTER PANEL: Dialogue Blocks, Narration Editor & Scene Playback
            with gr.Column(scale=6, min_width=460, elem_classes=["smart-center-canvas"]):
                dialogue_blocks_display = gr.Markdown(
                    value="*Select or import a storyboard project to view scene dialogue blocks.*"
                )

                gr.Markdown("#### ✏️ Edit Selected Dialogue Segment")
                segment_selector = gr.Dropdown(
                    label="Active Dialogue Block",
                    choices=[],
                    value=None,
                    interactive=True,
                )
                segment_text_editor = gr.Textbox(
                    label="Spoken Narration / Dialogue Text (Synthesized)",
                    lines=4,
                    placeholder="Spoken Khmer / English text for this segment...",
                )
                with gr.Row():
                    save_seg_btn = gr.Button("💾 Save Block Edit", variant="primary", size="sm")
                    split_seg_btn = gr.Button("✂️ Split Dialogue Block", variant="secondary", size="sm")
                    merge_seg_btn = gr.Button("🔗 Merge With Adjacent Block", variant="secondary", size="sm")

                synth_prompt_preview = gr.Textbox(
                    label="Exact VoxCPM2 Spoken Payload Preview (Non-spoken directions stripped)",
                    lines=2,
                    interactive=False,
                )

                with gr.Accordion("🎬 Production Directions & Visual Metadata (Excluded from Speech)", open=False):
                    production_meta_md = gr.Markdown(value="*Non-spoken visual, music, and SFX notes appear here.*")
                    with gr.Row():
                        scene_title_input = gr.Textbox(label="Scene Title", scale=2)
                        scene_start_input = gr.Textbox(label="Target Start (MM:SS)", scale=1)
                        scene_end_input = gr.Textbox(label="Target End (MM:SS)", scale=1)
                    save_scene_meta_btn = gr.Button("💾 Update Scene Target Window", variant="secondary", size="sm")

                gr.Markdown("#### 🔊 Scene Audio Preview")
                scene_audio_player = gr.Audio(
                    label="Selected Scene Audio (48kHz WAV)",
                    type="filepath",
                    interactive=False,
                )
                with gr.Row():
                    gen_scene_btn = gr.Button(
                        "🎙️ Generate Selected Scene",
                        variant="primary",
                        size="md",
                    )
                    queue_scene_btn = gr.Button(
                        "📥 Queue Selected Scene",
                        variant="secondary",
                        size="md",
                    )

            # RIGHT INSPECTOR: Speaker Role, Voice Profile, Mode & Delivery Style
            with gr.Column(scale=3, min_width=280, elem_classes=["smart-right-inspector"]):
                gr.Markdown("### 🎛️ Voice & Delivery Inspector")
                speaker_role_dropdown = gr.Dropdown(
                    label="Speaker Role",
                    choices=SUPPORTED_SPEAKER_ROLES,
                    value="Teacher",
                    interactive=True,
                )
                voice_profile_dropdown = gr.Dropdown(
                    label="Assigned Voice Profile",
                    choices=get_voice_choices(),
                    value="Default Voice (No Profile)",
                    interactive=True,
                )
                refresh_voices_btn = gr.Button("🔄 Refresh Voice Profiles", variant="secondary", size="sm")

                cloning_mode_radio = gr.Radio(
                    label="Synthesis Mode",
                    choices=["Ordinary TTS", "Voice Cloning", "Ultimate Cloning"],
                    value="Ordinary TTS",
                    interactive=True,
                )
                delivery_style_dropdown = gr.Dropdown(
                    label="Delivery Style",
                    choices=SUPPORTED_DELIVERY_STYLES,
                    value="Educational",
                    interactive=True,
                )
                pace_dropdown = gr.Radio(
                    label="Speaking Pace",
                    choices=SUPPORTED_PACES,
                    value="Medium",
                    interactive=True,
                )
                enable_style_prefix_chk = gr.Checkbox(
                    label="Inject VoxCPM2 Style Prefix (Off by default for Khmer safety)",
                    value=False,
                    interactive=True,
                )
                seg_pause_slider = gr.Slider(
                    minimum=0,
                    maximum=1500,
                    value=280,
                    step=20,
                    label="Pause After Block (ms)",
                )

                with gr.Row():
                    apply_seg_voice_btn = gr.Button(
                        "Apply to This Block",
                        variant="primary",
                        size="sm",
                    )
                    apply_role_all_btn = gr.Button(
                        "Apply to All Blocks of This Role",
                        variant="secondary",
                        size="sm",
                    )

                with gr.Accordion("⏱️ Scene Timing & Model Parameters", open=False):
                    scene_pause_slider = gr.Slider(
                        minimum=0,
                        maximum=3000,
                        value=400,
                        step=50,
                        label="Pause After Scene (ms)",
                    )
                    stretch_ratio_slider = gr.Slider(
                        minimum=0.85,
                        maximum=1.20,
                        value=1.00,
                        step=0.01,
                        label="Modest Time-Stretch Ratio (1.00 = Natural Duration)",
                    )
                    cfg_slider = gr.Slider(
                        minimum=1.0,
                        maximum=5.0,
                        value=2.0,
                        step=0.1,
                        label="Guidance Scale (CFG)",
                    )
                    steps_slider = gr.Slider(
                        minimum=5,
                        maximum=30,
                        value=10,
                        step=1,
                        label="Inference Timesteps",
                    )

        # BOTTOM BAR: Timeline Duration Comparison, Complete Playback & Export Controls
        with gr.Column(elem_classes=["smart-bottom-dock"]):
            with gr.Row():
                gr.Markdown("### ⏱️ Storyboard Timeline & Complete Narration Export")
                smart_status_banner = gr.Markdown(value="Ready.")
            with gr.Row():
                gen_all_scenes_btn = gr.Button(
                    "🚀 Generate All Scenes & Stitch Master",
                    variant="primary",
                    size="lg",
                )
                queue_all_scenes_btn = gr.Button(
                    "📥 Add Full Storyboard to Batch Queue",
                    variant="secondary",
                    size="lg",
                )
                export_bundle_btn = gr.Button(
                    "📦 Export All Formats (WAV, MP3, JSON, CSV, Approx SRT)",
                    variant="secondary",
                    size="lg",
                )

            timeline_table = gr.Dataframe(
                headers=[
                    "Scene #",
                    "Scene Title",
                    "Target Window",
                    "Target (s)",
                    "Actual (s)",
                    "Delta",
                    "Timeline Status",
                    "Duration Recommendation",
                ],
                datatype=["number", "str", "str", "number", "number", "str", "str", "str"],
                interactive=False,
                wrap=True,
                label="Planned vs. Actual Duration Analysis",
            )

            with gr.Row():
                complete_audio_player = gr.Audio(
                    label="Complete Storyboard Narration Master (48kHz WAV)",
                    type="filepath",
                    interactive=False,
                    scale=2,
                )
                with gr.Column(scale=3):
                    with gr.Row():
                        export_complete_wav = gr.File(label="C. Complete WAV", height=72, interactive=False)
                        export_complete_mp3 = gr.File(label="D. Complete MP3", height=72, interactive=False)
                        export_scenes_wav_zip = gr.File(label="A. Scene WAVs (ZIP)", height=72, interactive=False)
                        export_scenes_mp3_zip = gr.File(label="B. Scene MP3s (ZIP)", height=72, interactive=False)
                    with gr.Row():
                        export_json_file = gr.File(label="E. Project JSON", height=72, interactive=False)
                        export_csv_file = gr.File(label="F. Cue Sheet CSV", height=72, interactive=False)
                        export_srt_file = gr.File(label="G. Approx SRT Draft", height=72, interactive=False)

        # ------------------------------------------------------------------
        # UI Event Callbacks
        # ------------------------------------------------------------------
        state_outputs = [
            current_project_id,
            project_header_md,
            scene_selector,
            scene_nav_table,
            dialogue_blocks_display,
            segment_selector,
            segment_text_editor,
            speaker_role_dropdown,
            voice_profile_dropdown,
            cloning_mode_radio,
            delivery_style_dropdown,
            pace_dropdown,
            enable_style_prefix_chk,
            seg_pause_slider,
            synth_prompt_preview,
            production_meta_md,
            scene_title_input,
            scene_start_input,
            scene_end_input,
            scene_pause_slider,
            stretch_ratio_slider,
            scene_audio_player,
            timeline_table,
            smart_status_banner,
        ]

        def handle_import_file(file_obj):
            if not file_obj:
                return build_scene_ui_state(None, status_msg="⚠️ Please select a file to import.")
            file_path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
            proj = ScriptProjectService.get_instance().import_document(file_path)
            return build_scene_ui_state(
                proj,
                status_msg=f"✅ Imported '{proj.source_filename}' ({len(proj.scenes)} scenes parsed).",
            )

        def handle_load_sample():
            if not SAMPLE_DOCX_FIXTURE.exists():
                return build_scene_ui_state(
                    None,
                    status_msg=f"❌ Sample fixture not found at {SAMPLE_DOCX_FIXTURE}",
                )
            proj = ScriptProjectService.get_instance().import_document(SAMPLE_DOCX_FIXTURE)
            return build_scene_ui_state(
                proj,
                status_msg=f"🎓 Loaded Grade 8 AI Storyboard ({len(proj.scenes)} scenes, spoken vs. visual separated).",
            )

        def handle_load_saved(saved_choice: str):
            if not saved_choice or "(" not in saved_choice:
                return build_scene_ui_state(None, status_msg="⚠️ Select a saved project first.")
            pid = saved_choice.split("(")[-1].rstrip(")").strip()
            proj = ScriptProjectService.get_instance().load_project(pid)
            return build_scene_ui_state(proj, status_msg=f"📂 Opened project '{proj.title}'." if proj else "❌ Project not found.")

        def handle_parse_pasted(title: str, raw_text: str):
            if not raw_text or not raw_text.strip():
                return build_scene_ui_state(None, status_msg="⚠️ Paste storyboard text before parsing.")
            proj = ScriptProjectService.get_instance().import_pasted_text(raw_text=raw_text, title=title)
            return build_scene_ui_state(proj, status_msg=f"✨ Parsed '{proj.title}' ({len(proj.scenes)} scenes).")

        def handle_select_scene(proj_id: str, scene_choice: str):
            if not proj_id:
                return build_scene_ui_state(None)
            proj = ScriptProjectService.get_instance().load_project(proj_id)
            sc_id = extract_scene_id_from_choice(scene_choice)
            return build_scene_ui_state(proj, selected_scene_id=sc_id, status_msg=f"Selected {sc_id}.")

        def handle_select_segment(proj_id: str, scene_choice: str, seg_choice: str):
            if not proj_id:
                return build_scene_ui_state(None)
            proj = ScriptProjectService.get_instance().load_project(proj_id)
            sc_id = extract_scene_id_from_choice(scene_choice)
            sg_id = extract_segment_id_from_choice(seg_choice)
            return build_scene_ui_state(
                proj,
                selected_scene_id=sc_id,
                selected_seg_id=sg_id,
                status_msg=f"Editing block {sg_id}.",
            )

        def handle_save_segment(
            proj_id: str,
            scene_choice: str,
            seg_choice: str,
            new_text: str,
            role: str,
            voice_prof: str,
            ui_mode: str,
            style: str,
            pace: str,
            style_prefix: bool,
            pause_ms: int,
        ):
            if not proj_id:
                return build_scene_ui_state(None, status_msg="⚠️ No active project.")
            service = ScriptProjectService.get_instance()
            proj = service.load_project(proj_id)
            sc_id = extract_scene_id_from_choice(scene_choice)
            sg_id = extract_segment_id_from_choice(seg_choice)
            proj = service.update_segment(
                project=proj,
                scene_id=sc_id,
                segment_id=sg_id,
                text=new_text,
                speaker_role=role,
                voice_profile_id=voice_prof,
                mode=mode_ui_to_internal(ui_mode),
                delivery_style=style,
                pace=pace,
                pause_after_ms=int(pause_ms),
                enable_style_prefix=bool(style_prefix),
            )
            return build_scene_ui_state(
                proj,
                selected_scene_id=sc_id,
                selected_seg_id=sg_id,
                status_msg=f"💾 Saved dialogue block {sg_id}.",
            )

        def handle_split_segment(proj_id: str, scene_choice: str, seg_choice: str):
            if not proj_id:
                return build_scene_ui_state(None)
            service = ScriptProjectService.get_instance()
            proj = service.load_project(proj_id)
            sc_id = extract_scene_id_from_choice(scene_choice)
            sg_id = extract_segment_id_from_choice(seg_choice)
            proj = service.split_segment(proj, sc_id, sg_id)
            return build_scene_ui_state(
                proj,
                selected_scene_id=sc_id,
                selected_seg_id=sg_id,
                status_msg=f"✂️ Split block {sg_id} into two dialogue turns.",
            )

        def handle_merge_segment(proj_id: str, scene_choice: str, seg_choice: str):
            if not proj_id:
                return build_scene_ui_state(None)
            service = ScriptProjectService.get_instance()
            proj = service.load_project(proj_id)
            sc_id = extract_scene_id_from_choice(scene_choice)
            sg_id = extract_segment_id_from_choice(seg_choice)
            proj = service.merge_segments(proj, sc_id, sg_id)
            return build_scene_ui_state(
                proj,
                selected_scene_id=sc_id,
                status_msg=f"🔗 Merged adjacent dialogue blocks in {sc_id}.",
            )

        def handle_move_scene(proj_id: str, scene_choice: str, direction: str):
            if not proj_id:
                return build_scene_ui_state(None)
            service = ScriptProjectService.get_instance()
            proj = service.load_project(proj_id)
            sc_id = extract_scene_id_from_choice(scene_choice)
            proj = service.reorder_scene(proj, sc_id, direction=direction)
            return build_scene_ui_state(
                proj,
                selected_scene_id=sc_id,
                status_msg=f"Moved {sc_id} {direction}.",
            )

        def handle_apply_role_all(
            proj_id: str,
            scene_choice: str,
            seg_choice: str,
            role: str,
            voice_prof: str,
            ui_mode: str,
            style: str,
            pace: str,
        ):
            if not proj_id:
                return build_scene_ui_state(None)
            service = ScriptProjectService.get_instance()
            proj = service.load_project(proj_id)
            sc_id = extract_scene_id_from_choice(scene_choice)
            sg_id = extract_segment_id_from_choice(seg_choice)
            proj = service.assign_role_voice(
                project=proj,
                speaker_role=role,
                voice_profile_id=voice_prof,
                mode=mode_ui_to_internal(ui_mode),
                delivery_style=style,
                pace=pace,
                apply_to_existing_segments=True,
            )
            return build_scene_ui_state(
                proj,
                selected_scene_id=sc_id,
                selected_seg_id=sg_id,
                status_msg=f"✅ Assigned role '{role}' across all scenes.",
            )

        def handle_save_scene_meta(
            proj_id: str,
            scene_choice: str,
            title: str,
            start_tc: str,
            end_tc: str,
            scene_pause_ms: int,
            stretch_r: float,
        ):
            if not proj_id:
                return build_scene_ui_state(None)
            service = ScriptProjectService.get_instance()
            proj = service.load_project(proj_id)
            sc_id = extract_scene_id_from_choice(scene_choice)
            proj = service.update_scene_metadata(
                project=proj,
                scene_id=sc_id,
                title=title,
                target_start_time=start_tc,
                target_end_time=end_tc,
                pause_after_scene_ms=int(scene_pause_ms),
                stretch_ratio=float(stretch_r),
            )
            return build_scene_ui_state(
                proj,
                selected_scene_id=sc_id,
                status_msg=f"💾 Updated timing & metadata for {sc_id}.",
            )

        def handle_generate_scene(proj_id: str, scene_choice: str, cfg: float, steps: int):
            if not proj_id:
                return build_scene_ui_state(None, status_msg="⚠️ Load a project first.")
            service = ScriptProjectService.get_instance()
            sc_id = extract_scene_id_from_choice(scene_choice)
            res = service.generate_scene(
                project_id=proj_id,
                scene_id=sc_id,
                cfg_value=float(cfg),
                inference_timesteps=int(steps),
                retry_failed_only=True,
            )
            proj = service.load_project(proj_id)
            return build_scene_ui_state(
                proj,
                selected_scene_id=sc_id,
                status_msg=(
                    f"✅ Scene {sc_id} synthesized: {res['actual_duration_sec']}s "
                    f"(Target: {res['target_duration_sec']}s, Diff: {res['duration_diff_sec']:+.2f}s)."
                ),
            )

        def handle_queue_scene(proj_id: str, scene_choice: str, cfg: float, steps: int):
            if not proj_id:
                return "⚠️ Load a project first."
            sc_id = extract_scene_id_from_choice(scene_choice)
            job_id, msg = ScriptProjectService.get_instance().submit_to_batch_queue(
                project_id=proj_id,
                scene_id=sc_id,
                cfg_value=float(cfg),
                inference_timesteps=int(steps),
            )
            return f"📥 {msg} (Job ID: `{job_id}`)"

        def handle_queue_all_scenes(proj_id: str, cfg: float, steps: int):
            if not proj_id:
                return "⚠️ Load a project first."
            job_id, msg = ScriptProjectService.get_instance().submit_to_batch_queue(
                project_id=proj_id,
                scene_id=None,
                cfg_value=float(cfg),
                inference_timesteps=int(steps),
            )
            return f"📥 {msg} (Job ID: `{job_id}`)"

        def handle_generate_all_and_export(proj_id: str, scene_choice: str, cfg: float, steps: int):
            if not proj_id:
                return (*build_scene_ui_state(None, status_msg="⚠️ Load a project first."), None, None, None, None, None, None, None, None)
            service = ScriptProjectService.get_instance()
            sc_id = extract_scene_id_from_choice(scene_choice)
            res = service.generate_all_scenes(
                project_id=proj_id,
                cfg_value=float(cfg),
                inference_timesteps=int(steps),
                retry_failed_only=True,
            )
            bundle = service.export_project_bundle(proj_id)
            proj = service.load_project(proj_id)
            base_state = build_scene_ui_state(
                proj,
                selected_scene_id=sc_id,
                status_msg=(
                    f"🚀 Completed all {len(proj.scenes)} scenes! Total duration: "
                    f"{res.get('actual_total_duration_sec', 0.0)}s vs {proj.planned_duration_sec}s planned."
                ),
            )
            return (
                *base_state,
                bundle.get("combined_wav_path"),
                bundle.get("combined_wav_path"),
                bundle.get("combined_mp3_path"),
                bundle.get("scenes_wav_zip"),
                bundle.get("scenes_mp3_zip"),
                bundle.get("project_json_path"),
                bundle.get("cue_sheet_csv_path"),
                bundle.get("approximate_srt_path"),
            )

        def handle_export_bundle_only(proj_id: str):
            if not proj_id:
                return None, None, None, None, None, None, None, None, "⚠️ Load a project first."
            bundle = ScriptProjectService.get_instance().export_project_bundle(proj_id)
            return (
                bundle.get("combined_wav_path"),
                bundle.get("combined_wav_path"),
                bundle.get("combined_mp3_path"),
                bundle.get("scenes_wav_zip"),
                bundle.get("scenes_mp3_zip"),
                bundle.get("project_json_path"),
                bundle.get("cue_sheet_csv_path"),
                bundle.get("approximate_srt_path"),
                "📦 Exported Scene WAVs, Scene MP3s, Complete WAV/MP3, Project JSON, CSV Cue Sheet, and Approximate SRT Draft.",
            )

        # Wire Events
        doc_upload.change(fn=handle_import_file, inputs=[doc_upload], outputs=state_outputs)
        load_sample_btn.click(fn=handle_load_sample, inputs=[], outputs=state_outputs)
        load_saved_btn.click(fn=handle_load_saved, inputs=[saved_project_dropdown], outputs=state_outputs)
        parse_paste_btn.click(
            fn=handle_parse_pasted,
            inputs=[paste_title_input, paste_script_box],
            outputs=state_outputs,
        )
        scene_selector.change(
            fn=handle_select_scene,
            inputs=[current_project_id, scene_selector],
            outputs=state_outputs,
        )
        segment_selector.change(
            fn=handle_select_segment,
            inputs=[current_project_id, scene_selector, segment_selector],
            outputs=state_outputs,
        )
        save_seg_btn.click(
            fn=handle_save_segment,
            inputs=[
                current_project_id,
                scene_selector,
                segment_selector,
                segment_text_editor,
                speaker_role_dropdown,
                voice_profile_dropdown,
                cloning_mode_radio,
                delivery_style_dropdown,
                pace_dropdown,
                enable_style_prefix_chk,
                seg_pause_slider,
            ],
            outputs=state_outputs,
        )
        apply_seg_voice_btn.click(
            fn=handle_save_segment,
            inputs=[
                current_project_id,
                scene_selector,
                segment_selector,
                segment_text_editor,
                speaker_role_dropdown,
                voice_profile_dropdown,
                cloning_mode_radio,
                delivery_style_dropdown,
                pace_dropdown,
                enable_style_prefix_chk,
                seg_pause_slider,
            ],
            outputs=state_outputs,
        )
        apply_role_all_btn.click(
            fn=handle_apply_role_all,
            inputs=[
                current_project_id,
                scene_selector,
                segment_selector,
                speaker_role_dropdown,
                voice_profile_dropdown,
                cloning_mode_radio,
                delivery_style_dropdown,
                pace_dropdown,
            ],
            outputs=state_outputs,
        )
        split_seg_btn.click(
            fn=handle_split_segment,
            inputs=[current_project_id, scene_selector, segment_selector],
            outputs=state_outputs,
        )
        merge_seg_btn.click(
            fn=handle_merge_segment,
            inputs=[current_project_id, scene_selector, segment_selector],
            outputs=state_outputs,
        )
        move_up_btn.click(
            fn=lambda pid, sc: handle_move_scene(pid, sc, "up"),
            inputs=[current_project_id, scene_selector],
            outputs=state_outputs,
        )
        move_down_btn.click(
            fn=lambda pid, sc: handle_move_scene(pid, sc, "down"),
            inputs=[current_project_id, scene_selector],
            outputs=state_outputs,
        )
        save_scene_meta_btn.click(
            fn=handle_save_scene_meta,
            inputs=[
                current_project_id,
                scene_selector,
                scene_title_input,
                scene_start_input,
                scene_end_input,
                scene_pause_slider,
                stretch_ratio_slider,
            ],
            outputs=state_outputs,
        )
        refresh_voices_btn.click(
            fn=lambda: gr.update(choices=get_voice_choices()),
            inputs=[],
            outputs=[voice_profile_dropdown],
        )
        gen_scene_btn.click(
            fn=handle_generate_scene,
            inputs=[current_project_id, scene_selector, cfg_slider, steps_slider],
            outputs=state_outputs,
        )
        queue_scene_btn.click(
            fn=handle_queue_scene,
            inputs=[current_project_id, scene_selector, cfg_slider, steps_slider],
            outputs=[smart_status_banner],
        )
        queue_all_scenes_btn.click(
            fn=handle_queue_all_scenes,
            inputs=[current_project_id, cfg_slider, steps_slider],
            outputs=[smart_status_banner],
        )
        gen_all_scenes_btn.click(
            fn=handle_generate_all_and_export,
            inputs=[current_project_id, scene_selector, cfg_slider, steps_slider],
            outputs=[
                *state_outputs,
                complete_audio_player,
                export_complete_wav,
                export_complete_mp3,
                export_scenes_wav_zip,
                export_scenes_mp3_zip,
                export_json_file,
                export_csv_file,
                export_srt_file,
            ],
        )
        export_bundle_btn.click(
            fn=handle_export_bundle_only,
            inputs=[current_project_id],
            outputs=[
                complete_audio_player,
                export_complete_wav,
                export_complete_mp3,
                export_scenes_wav_zip,
                export_scenes_mp3_zip,
                export_json_file,
                export_csv_file,
                export_srt_file,
                smart_status_banner,
            ],
        )
