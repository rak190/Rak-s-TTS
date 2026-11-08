"""
VoiceStudio Pro — Mastering Studio UI Tab.
Professional Audio Production Layout:
- Left Column: Audio Source selection, ITU-R BS.1770-4 Presets, and Voice Polish Filters.
- Right Column: Acoustic Inspection, Before/After A/B Comparative Players, and Dual WAV/MP3 Downloads.
- Lower Area: Mastering Processing History.
"""
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import gradio as gr

from app.audio.filters import VoicePolishOptions
from app.audio.mastering import MASTERING_PRESETS
from app.audio.quality import QualityAnalyzer
from app.database.connection import DatabaseManager
from app.services.generation_service import GenerationService
from app.services.longform_service import LongformService
from app.services.mastering_service import MasteringService

logger = logging.getLogger(__name__)

def get_audio_source_choices() -> List[Tuple[str, str]]:
    choices = [("Select a generated speech audio...", "")]
    db = DatabaseManager.get_instance()

    gens = db.list_generations(limit=25)
    for g in gens:
        if g.output_audio_path and Path(g.output_audio_path).exists():
            label = f"[Single] {g.created_at[:10]} | {g.voice_name} | {g.target_text[:30]}... ({g.duration_sec}s)"
            choices.append((label, g.output_audio_path))

    long_jobs = db.list_longform_jobs(limit=15)
    for j in long_jobs:
        if j.output_wav_path and Path(j.output_wav_path).exists():
            label = f"[Longform] {j.created_at[:10]} | {j.title} | {j.voice_name} ({j.total_duration_sec}s)"
            choices.append((label, j.output_wav_path))

    return choices

def get_mastering_history_rows() -> List[List]:
    svc = MasteringService()
    records = svc.list_mastering_history(limit=50)
    rows = []
    for r in records:
        rows.append([
            r.id,
            r.created_at[:19],
            r.preset,
            f"{r.target_lufs} LUFS",
            f"{r.measured_output_lufs:.1f} LUFS" if r.measured_output_lufs is not None else "N/A",
            f"{r.measured_output_tp:.1f} dBTP" if r.measured_output_tp is not None else "N/A",
            f"{r.processing_time_sec:.2f}s",
            r.output_wav_path,
            r.output_mp3_path or ""
        ])
    return rows

def inspect_source_audio(history_path: str, uploaded_file: Optional[str]) -> Tuple[str, Optional[str]]:
    target_path = uploaded_file if uploaded_file else history_path
    if not target_path or not Path(target_path).exists():
        return (
            "<div style='padding: 14px; border-radius: 10px; background: var(--studio-surface-elevated); color: var(--studio-text-muted); text-align: center;'>"
            "Select an audio file or upload one to inspect its acoustic properties."
            "</div>",
            None
        )

    try:
        report = QualityAnalyzer.analyze_audio(target_path)
        badge_color = "var(--studio-success)" if report.quality_grade == "Excellent" else "var(--studio-warning)"

        html = f"""
        <div style="background: var(--studio-surface-card); border: 1px solid var(--studio-border); border-radius: var(--radius-md); padding: 16px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <span style="font-size: 14px; font-weight: 600; color: var(--studio-text-primary);">📊 Acoustic Inspection Report</span>
                <span class="studio-pill studio-pill-accent">{report.quality_grade}</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;">
                <div style="background: var(--studio-surface-elevated); padding: 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 10.5px; color: var(--studio-text-muted); text-transform: uppercase;">Loudness (LUFS)</div>
                    <div style="font-size: 16px; font-weight: 700; color: var(--studio-accent);">{report.integrated_lufs:.1f} LUFS</div>
                </div>
                <div style="background: var(--studio-surface-elevated); padding: 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 10.5px; color: var(--studio-text-muted); text-transform: uppercase;">True Peak (dBTP)</div>
                    <div style="font-size: 16px; font-weight: 700;">{report.true_peak_dbtp:.1f} dBTP</div>
                </div>
                <div style="background: var(--studio-surface-elevated); padding: 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 10.5px; color: var(--studio-text-muted); text-transform: uppercase;">Dynamic Range (LU)</div>
                    <div style="font-size: 16px; font-weight: 700;">{report.loudness_range_lra:.1f} LU</div>
                </div>
            </div>
        </div>
        """
        return html, target_path
    except Exception as e:
        return f"<div style='color: var(--studio-error);'>Error inspecting audio: {e}</div>", None

def run_mastering_job(
    history_path: str,
    uploaded_file: Optional[str],
    preset: str,
    custom_lufs: float,
    custom_tp: float,
    trim_silence: bool,
    highpass: bool,
    deesser: bool,
    presence: bool,
    compressor: bool
):
    target_path = uploaded_file if uploaded_file else history_path
    if not target_path or not Path(target_path).exists():
        return (
            "<div style='color: var(--studio-error);'>Error: Please select a generated audio file or upload one first.</div>",
            None, None, None, None,
            get_mastering_history_rows()
        )

    target_lufs = custom_lufs if preset == "custom" else MASTERING_PRESETS.get(preset, {}).get("target_lufs", -16.0)
    target_tp = custom_tp if preset == "custom" else MASTERING_PRESETS.get(preset, {}).get("target_peak_dbtp", -1.5)

    filters = VoicePolishOptions(
        enable_highpass=highpass,
        highpass_freq_hz=80.0,
        enable_deesser=deesser,
        deesser_center_hz=5500.0,
        enable_presence_eq=presence,
        presence_freq_hz=3500.0,
        presence_gain_db=1.2,
        enable_leveler=compressor,
        trim_silence=trim_silence
    )

    svc = MasteringService()
    res, err = svc.master_audio(
        input_audio_path=target_path,
        preset=preset,
        target_lufs=target_lufs,
        target_tp=target_tp,
        filters=filters
    )

    if err or not res:
        return (
            f"<div style='color: var(--studio-error);'>Mastering Failed: {err}</div>",
            None, None, None, None,
            get_mastering_history_rows()
        )

    out_lufs_str = f"{res.final_metrics.integrated_lufs:.1f} LUFS" if res.final_metrics.integrated_lufs is not None else "N/A"
    out_tp_str = f"{res.final_metrics.true_peak_dbtp:.1f} dBTP" if res.final_metrics.true_peak_dbtp is not None else "N/A"

    comparison_html = f"""
    <div style="background: var(--studio-surface-card); border: 1px solid var(--studio-border); border-radius: var(--radius-md); padding: 16px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 14px; font-weight: 600; color: var(--studio-success);">✅ Two-Pass EBU R128 Mastering Complete</span>
            <span class="studio-pill studio-pill-accent">{preset.upper()} Preset</span>
        </div>
        <div style="font-size: 13px; color: var(--studio-text-secondary);">
            Mastered in {res.processing_time_sec:.2f}s • Integrated Loudness: <strong>{out_lufs_str}</strong> • Ceiling: <strong>{out_tp_str}</strong>
        </div>
    </div>
    """

    out_wav_path = res.output_wav_path if Path(res.output_wav_path).exists() else None
    out_mp3_path = res.output_mp3_path if Path(res.output_mp3_path).exists() else None

    return (
        comparison_html,
        target_path,
        out_wav_path,
        out_wav_path,
        out_mp3_path,
        get_mastering_history_rows()
    )

# Function alias for UI API compatibility
run_mastering_process = run_mastering_job

def create_mastering_tab():
    with gr.Tab("🎚️ Audio Mastering", id="tab_mastering"):
        # Header
        with gr.Row(elem_classes=["studio-canvas-card"]):
            gr.Markdown(
                """
                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <div style="font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">Audio Mastering Studio</div>
                        <div style="font-size: 13px; color: var(--studio-text-secondary); margin-top: 2px;">
                            Two-Pass ITU-R BS.1770-4 Normalization • De-Essing • 80Hz Rumble Filter • EBU R128 Standards
                        </div>
                    </div>
                    <div>
                        <span class="studio-pill studio-pill-accent">Broadcast Standards Engine</span>
                    </div>
                </div>
                """
            )

        # Two-Column Production Layout
        with gr.Row():
            # LEFT: Source Audio, Presets & Voice Polish Controls
            with gr.Column(scale=5):
                with gr.Group(elem_classes=["studio-canvas-card"]):
                    gr.Markdown("#### 1. Audio Source")
                    source_dropdown = gr.Dropdown(
                        label="From Speech Generation History",
                        choices=get_audio_source_choices(),
                        value=""
                    )
                    file_uploader = gr.Audio(label="Or Upload External Audio (WAV, MP3, M4A)", type="filepath", sources=["upload"])
                    with gr.Row():
                        inspect_btn = gr.Button("🔍 Inspect Acoustics", variant="secondary", size="sm")
                        refresh_sources_btn = gr.Button("🔄 Refresh Sources", variant="secondary", size="sm")

                with gr.Group(elem_classes=["studio-inspector"]):
                    gr.Markdown("#### 2. Mastering Preset & Signal Polish")
                    preset_radio = gr.Radio(
                        label="Loudness Target",
                        choices=[
                            ("Podcast / Streaming (-16 LUFS)", "podcast"),
                            ("Audiobook / ACX (-18 LUFS)", "audiobook"),
                            ("Soft / Natural (-20 LUFS)", "soft"),
                            ("Custom Targets", "custom")
                        ],
                        value="podcast"
                    )

                    with gr.Row():
                        custom_lufs_slider = gr.Slider(minimum=-24.0, maximum=-12.0, step=0.5, value=-16.0, label="Target LUFS")
                        custom_tp_slider = gr.Slider(minimum=-3.0, maximum=-0.5, step=0.1, value=-1.5, label="True Peak dBTP")

                    trim_silence_chk = gr.Checkbox(label="Edge Silence Trimming (120ms lead, 220ms trail)", value=True)
                    highpass_chk = gr.Checkbox(label="80 Hz High-Pass Rumble Filter", value=True)
                    deesser_chk = gr.Checkbox(label="Dynamic Speech De-Esser (5.5 kHz)", value=True)
                    presence_chk = gr.Checkbox(label="Vocal Presence EQ (+1.2 dB @ 3.5 kHz)", value=True)
                    compressor_chk = gr.Checkbox(label="Speech Dynamic Leveler (2:1 gentle compression)", value=True)

                    master_btn = gr.Button("🎛️ Master Audio (Two-Pass EBU R128)", variant="primary", size="lg")

            # RIGHT: Acoustic Analysis, Before/After A/B Player & Export
            with gr.Column(scale=5):
                inspection_display = gr.HTML(
                    value="<div style='padding: 16px; border-radius: 10px; background: var(--studio-surface-elevated); color: var(--studio-text-muted); text-align: center;'>"
                          "Select audio and click 'Inspect Acoustics' or 'Master Audio'."
                          "</div>"
                )

                with gr.Group(elem_classes=["studio-canvas-card"]):
                    gr.Markdown("#### 🔊 A/B Audio Comparison")
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("**Raw Original Audio**")
                            player_original = gr.Audio(label="Source", type="filepath", interactive=False)
                        with gr.Column():
                            gr.Markdown("**Mastered EBU R128**")
                            player_mastered = gr.Audio(label="Mastered", type="filepath", interactive=False)

                    with gr.Row():
                        download_wav = gr.File(label="⬇️ Mastered WAV (24-bit PCM)", interactive=False)
                        download_mp3 = gr.File(label="⬇️ Mastered MP3 (320kbps)", interactive=False)

        # LOWER: Processing History
        with gr.Row():
            with gr.Column():
                with gr.Accordion("📜 Mastering Production History", open=False):
                    with gr.Row():
                        refresh_hist_btn = gr.Button("🔄 Refresh Table", variant="secondary", size="sm")

                    mastering_table = gr.Dataframe(
                        headers=["ID", "Timestamp", "Preset", "Target LUFS", "Output LUFS", "Output dBTP", "Time (s)", "Master WAV", "Master MP3"],
                        datatype=["str", "str", "str", "str", "str", "str", "str", "str", "str"],
                        value=get_mastering_history_rows,
                        interactive=False
                    )

        # Events
        refresh_sources_btn.click(fn=lambda: gr.update(choices=get_audio_source_choices()), outputs=[source_dropdown])
        inspect_btn.click(
            fn=inspect_source_audio,
            inputs=[source_dropdown, file_uploader],
            outputs=[inspection_display, player_original]
        )
        refresh_hist_btn.click(fn=get_mastering_history_rows, outputs=[mastering_table])

        master_btn.click(
            fn=run_mastering_job,
            inputs=[
                source_dropdown, file_uploader, preset_radio,
                custom_lufs_slider, custom_tp_slider,
                trim_silence_chk, highpass_chk, deesser_chk,
                presence_chk, compressor_chk
            ],
            outputs=[
                inspection_display,
                player_original,
                player_mastered,
                download_wav,
                download_mp3,
                mastering_table
            ]
        )
