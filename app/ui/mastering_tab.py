"""
Mastering Studio UI tab with Cupertino iPhone-inspired design.
Two-Pass ITU-R BS.1770-4 loudness mastering, voice polish filters,
before/after acoustic comparison, and non-destructive WAV/MP3 downloads.
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
    """Returns dropdown choices from generation history and longform jobs."""
    choices = [("Select a generated speech audio...", "")]
    db = DatabaseManager.get_instance()

    # 1. Single Generations
    gens = db.list_generations(limit=25)
    for g in gens:
        if g.output_audio_path and Path(g.output_audio_path).exists():
            label = f"[Single] {g.created_at[:10]} | {g.voice_name} | {g.target_text[:30]}... ({g.duration_sec}s)"
            choices.append((label, g.output_audio_path))

    # 2. Longform Jobs
    long_jobs = db.list_longform_jobs(limit=15)
    for j in long_jobs:
        if j.output_wav_path and Path(j.output_wav_path).exists():
            label = f"[Longform] {j.created_at[:10]} | {j.title} | {j.voice_name} ({j.total_duration_sec}s)"
            choices.append((label, j.output_wav_path))

    return choices


def get_mastering_history_rows() -> List[List]:
    """Retrieves recent mastering records from SQLite."""
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
    """Inspects the selected audio file and renders the acoustic report."""
    target_path = uploaded_file if uploaded_file else history_path
    if not target_path or not Path(target_path).exists():
        return (
            "<div style='padding: 12px; border-radius: 12px; background: rgba(0,0,0,0.03); color: #86868b;'>"
            "Select an audio file or upload one to inspect its acoustic properties."
            "</div>",
            None
        )

    try:
        report = QualityAnalyzer.analyze_audio(target_path)
        p = Path(target_path)

        badge_color = "#34c759" if report.quality_grade == "Excellent" else ("#ff9500" if report.quality_grade == "Needs Mastering" else "#ff3b30")
        notes_html = "".join(f"<li>{n}</li>" for n in report.notes)

        html = f"""
        <div style="background: rgba(255, 255, 255, 0.7); border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 14px; padding: 18px; margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h3 style="margin: 0; font-size: 16px; font-weight: 600;">📊 Acoustic Inspection Report</h3>
                <span style="background: {badge_color}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">
                    {report.quality_grade}
                </span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 14px;">
                <div style="background: rgba(0, 0, 0, 0.03); padding: 10px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 11px; color: #86868b; text-transform: uppercase;">Loudness (LUFS)</div>
                    <div style="font-size: 18px; font-weight: 700; color: #0071e3;">{report.integrated_lufs:.1f}</div>
                </div>
                <div style="background: rgba(0, 0, 0, 0.03); padding: 10px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 11px; color: #86868b; text-transform: uppercase;">True Peak</div>
                    <div style="font-size: 18px; font-weight: 700;">{report.true_peak_dbtp:.1f} dBTP</div>
                </div>
                <div style="background: rgba(0, 0, 0, 0.03); padding: 10px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 11px; color: #86868b; text-transform: uppercase;">LRA Range</div>
                    <div style="font-size: 18px; font-weight: 700;">{report.loudness_range_lra:.1f} LU</div>
                </div>
                <div style="background: rgba(0, 0, 0, 0.03); padding: 10px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 11px; color: #86868b; text-transform: uppercase;">Silence %</div>
                    <div style="font-size: 18px; font-weight: 700;">{report.silence_percent:.1f}%</div>
                </div>
                <div style="background: rgba(0, 0, 0, 0.03); padding: 10px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 11px; color: #86868b; text-transform: uppercase;">Crest Factor</div>
                    <div style="font-size: 18px; font-weight: 700;">{report.crest_factor_db:.1f} dB</div>
                </div>
                <div style="background: rgba(0, 0, 0, 0.03); padding: 10px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 11px; color: #86868b; text-transform: uppercase;">Lead / Trail Silence</div>
                    <div style="font-size: 16px; font-weight: 600;">{report.leading_silence_sec}s / {report.trailing_silence_sec}s</div>
                </div>
            </div>
            <div style="font-size: 13px; color: #515154;">
                <ul style="margin: 0; padding-left: 20px;">
                    {notes_html}
                </ul>
            </div>
        </div>
        """
        return html, target_path
    except Exception as e:
        logger.error("Inspection error: %s", e)
        return f"<div style='color: #ff3b30;'>Inspection error: {e}</div>", None


def run_mastering_process(
    source_choice: str,
    uploaded_file: Optional[str],
    preset_key: str,
    custom_lufs: float,
    custom_tp: float,
    enable_silence_trim: bool,
    enable_highpass: bool,
    enable_deesser: bool,
    enable_presence: bool,
    enable_compressor: bool,
    progress=gr.Progress()
):
    """Executes mastering pipeline, records job in database, and returns before/after comparisons."""
    target_path = uploaded_file if uploaded_file else source_choice
    if not target_path or not Path(target_path).exists():
        return (
            "⚠️ Please select a generated audio file or upload a file first.",
            None, None, None, None,
            get_mastering_history_rows()
        )

    progress(0.1, desc="Analyzing initial acoustics...")
    svc = MasteringService()

    voice_options = VoicePolishOptions(
        enable_highpass=enable_highpass,
        highpass_cutoff_hz=80.0,
        enable_deesser=enable_deesser,
        deesser_threshold_db=-22.0,
        enable_presence=enable_presence,
        presence_freq_hz=3500.0,
        presence_gain_db=1.2,
        enable_compressor=enable_compressor,
        compressor_threshold_db=-20.0,
        compressor_ratio=2.0,
        enable_limiter=True,
        ceiling_dbfs=custom_tp if "custom" in preset_key.lower() else -1.5
    )

    progress(0.4, desc="Applying voice polish & silence trimming...")
    actual_lufs = custom_lufs if "custom" in preset_key.lower() else None
    actual_tp = custom_tp if "custom" in preset_key.lower() else None

    progress(0.7, desc="Two-pass EBU R128 loudness normalization...")
    res = svc.master_file(
        file_path=target_path,
        preset_key=preset_key,
        custom_target_lufs=actual_lufs,
        custom_true_peak=actual_tp,
        enable_silence_trim=enable_silence_trim,
        voice_polish_options=voice_options
    )

    progress(1.0, desc="Mastering complete!")
    if not res.success:
        return (
            f"❌ Mastering failed: {res.error_message}",
            None, None, None, None,
            get_mastering_history_rows()
        )

    # Build comparison summary HTML
    gain_change = res.final_metrics.integrated_lufs - res.initial_metrics.integrated_lufs
    gain_sign = "+" if gain_change >= 0 else ""
    filters_list_html = "".join(f"<li>{f}</li>" for f in res.filters_applied)

    comparison_html = f"""
    <div style="background: rgba(255, 255, 255, 0.7); border: 1px solid rgba(0, 113, 227, 0.2); border-radius: 14px; padding: 18px; margin-bottom: 15px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <h3 style="margin: 0; font-size: 17px; font-weight: 600; color: #0071e3;">
                ✅ Mastered Successfully ({res.preset_name})
            </h3>
            <span style="font-size: 13px; color: #86868b; background: rgba(0,0,0,0.05); padding: 4px 10px; border-radius: 10px;">
                ⚡ Processed in {res.processing_time_sec}s
            </span>
        </div>

        <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 14px;">
            <thead>
                <tr style="border-bottom: 1px solid rgba(0,0,0,0.1); text-align: left; color: #86868b;">
                    <th style="padding: 6px 8px;">Metric</th>
                    <th style="padding: 6px 8px;">Before</th>
                    <th style="padding: 6px 8px;">After Master</th>
                    <th style="padding: 6px 8px;">Change / Status</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid rgba(0,0,0,0.05);">
                    <td style="padding: 8px; font-weight: 600;">Integrated Loudness</td>
                    <td style="padding: 8px;">{res.initial_metrics.integrated_lufs:.1f} LUFS</td>
                    <td style="padding: 8px; font-weight: 700; color: #0071e3;">{res.final_metrics.integrated_lufs:.1f} LUFS</td>
                    <td style="padding: 8px; color: #34c759; font-weight: 600;">{gain_sign}{gain_change:.1f} dB (Target: {res.target_lufs:.1f})</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(0,0,0,0.05);">
                    <td style="padding: 8px; font-weight: 600;">True Peak Ceiling</td>
                    <td style="padding: 8px;">{res.initial_metrics.true_peak_dbtp:.1f} dBTP</td>
                    <td style="padding: 8px; font-weight: 700;">{res.final_metrics.true_peak_dbtp:.1f} dBTP</td>
                    <td style="padding: 8px; color: #34c759;">Safe (&lt;= {res.target_tp:.1f} dBTP)</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(0,0,0,0.05);">
                    <td style="padding: 8px; font-weight: 600;">Loudness Range (LRA)</td>
                    <td style="padding: 8px;">{res.initial_metrics.loudness_range_lra:.1f} LU</td>
                    <td style="padding: 8px; font-weight: 700;">{res.final_metrics.loudness_range_lra:.1f} LU</td>
                    <td style="padding: 8px; color: #86868b;">Natural Dynamics Preserved</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(0,0,0,0.05);">
                    <td style="padding: 8px; font-weight: 600;">RMS Level</td>
                    <td style="padding: 8px;">{res.initial_metrics.rms_dbfs:.1f} dBFS</td>
                    <td style="padding: 8px; font-weight: 700;">{res.final_metrics.rms_dbfs:.1f} dBFS</td>
                    <td style="padding: 8px;">Speech Core Boosted</td>
                </tr>
            </tbody>
        </table>

        <div style="font-size: 12px; color: #515154;">
            <strong>Filters & Signal Enhancements Applied:</strong>
            <ul style="margin: 4px 0 0 0; padding-left: 20px;">
                {filters_list_html}
            </ul>
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


def create_mastering_tab():
    """Assembles the Mastering Studio UI tab."""
    with gr.Tab("🎚️ Mastering Studio", id="tab_mastering"):
        with gr.Column(elem_classes=["cu-card"]):
            gr.Markdown(
                """
                ## 🎚️ Speech Loudness Mastering & Audio Polish
                *Two-pass ITU-R BS.1770-4 loudness normalization, rumble filtering, de-essing, and dual WAV/MP3 export.*
                """
            )

        with gr.Row():
            # Left Column: Source Selection & Mastering Settings
            with gr.Column(scale=1):
                with gr.Group(elem_classes=["cu-card"]):
                    gr.Markdown("### 1. Select Audio Source")
                    source_dropdown = gr.Dropdown(
                        label="From Generated Speech History",
                        choices=get_audio_source_choices(),
                        value="",
                        interactive=True
                    )
                    refresh_sources_btn = gr.Button("🔄 Refresh Sources", variant="secondary", size="sm")
                    gr.Markdown("<div style='text-align:center; color:#86868b; font-size:12px;'>— OR —</div>")
                    file_uploader = gr.Audio(
                        label="Upload Audio File (WAV, MP3, M4A)",
                        type="filepath",
                        sources=["upload"]
                    )
                    inspect_btn = gr.Button("🔍 Inspect Audio Acoustics", variant="secondary")

                with gr.Group(elem_classes=["cu-card"]):
                    gr.Markdown("### 2. Mastering Profile & Targets")
                    preset_radio = gr.Radio(
                        label="Loudness Preset",
                        choices=[
                            ("Podcast / Streaming (-16 LUFS)", "podcast"),
                            ("Audiobook / ACX (-18 LUFS)", "audiobook"),
                            ("Soft / Natural (-20 LUFS)", "soft"),
                            ("Custom Targets", "custom")
                        ],
                        value="podcast"
                    )

                    with gr.Row():
                        custom_lufs_slider = gr.Slider(
                            minimum=-24.0, maximum=-12.0, step=0.5, value=-16.0,
                            label="Target Loudness (LUFS)",
                            interactive=True
                        )
                        custom_tp_slider = gr.Slider(
                            minimum=-3.0, maximum=-0.5, step=0.1, value=-1.5,
                            label="True Peak Ceiling (dBTP)",
                            interactive=True
                        )

                with gr.Group(elem_classes=["cu-card"]):
                    gr.Markdown("### 3. Voice Polish & Enhancements")
                    trim_silence_chk = gr.Checkbox(
                        label="Intelligent Silence Edge Trimming (120ms lead, 220ms trail)",
                        value=True
                    )
                    highpass_chk = gr.Checkbox(
                        label="80 Hz High-Pass Rumble Filter (Sub-vocal cleanup)",
                        value=True
                    )
                    deesser_chk = gr.Checkbox(
                        label="Dynamic Speech De-Esser (Tames sharp 5.5-8.5 kHz sibilance)",
                        value=True
                    )
                    presence_chk = gr.Checkbox(
                        label="Vocal Presence EQ (+1.2 dB boost @ 3.5 kHz for clarity)",
                        value=True
                    )
                    compressor_chk = gr.Checkbox(
                        label="Speech Dynamic Leveler (Gentle 2:1 compression)",
                        value=True
                    )

                master_btn = gr.Button("🎛️ Master Audio (Two-Pass EBU R128)", variant="primary", size="lg")

            # Right Column: Acoustic Inspection, Comparisons, and Players
            with gr.Column(scale=1):
                inspection_display = gr.HTML(
                    value="<div style='padding: 16px; border-radius: 12px; background: rgba(0,0,0,0.03); color: #86868b; text-align: center;'>"
                          "Select an audio file and click 'Inspect Audio Acoustics' or 'Master Audio'."
                          "</div>"
                )

                master_status_display = gr.HTML()

                with gr.Group(elem_classes=["cu-card"]):
                    gr.Markdown("### 🔊 A/B Audio Comparison")
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("**Original Audio**")
                            player_original = gr.Audio(label="Raw Audio", type="filepath", interactive=False)
                        with gr.Column():
                            gr.Markdown("**Mastered Speech**")
                            player_mastered = gr.Audio(label="Mastered (Two-Pass EBU R128)", type="filepath", interactive=False)

                    with gr.Row():
                        download_wav = gr.File(label="Download Mastered WAV (24-bit PCM)", interactive=False)
                        download_mp3 = gr.File(label="Download Mastered MP3 (320 kbps)", interactive=False)

        # History Section
        with gr.Row():
            with gr.Column():
                with gr.Group(elem_classes=["cu-card"]):
                    with gr.Row():
                        gr.Markdown("### 📜 Mastering History")
                        refresh_hist_btn = gr.Button("🔄 Refresh Table", variant="secondary", size="sm")

                    mastering_table = gr.Dataframe(
                        headers=["Job ID", "Timestamp", "Preset", "Target LUFS", "Output LUFS", "Output True-Peak", "Process Time", "Mastered WAV", "Mastered MP3"],
                        datatype=["str", "str", "str", "str", "str", "str", "str", "str", "str"],
                        value=get_mastering_history_rows,
                        interactive=False
                    )

        # Event Handlers
        refresh_sources_btn.click(
            fn=get_audio_source_choices,
            outputs=[source_dropdown]
        )

        inspect_btn.click(
            fn=inspect_source_audio,
            inputs=[source_dropdown, file_uploader],
            outputs=[inspection_display, player_original]
        )

        master_btn.click(
            fn=run_mastering_process,
            inputs=[
                source_dropdown,
                file_uploader,
                preset_radio,
                custom_lufs_slider,
                custom_tp_slider,
                trim_silence_chk,
                highpass_chk,
                deesser_chk,
                presence_chk,
                compressor_chk
            ],
            outputs=[
                master_status_display,
                player_original,
                player_mastered,
                download_wav,
                download_mp3,
                mastering_table
            ]
        )

        refresh_hist_btn.click(
            fn=get_mastering_history_rows,
            outputs=[mastering_table]
        )
