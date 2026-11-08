"""
VoiceStudio Pro — Media Library & History UI Tab.
Media Library Experience:
- Audio title / text preview, voice profile, language, timestamp, duration.
- Right-hand contextual playback & inspection panel with instant replay and download.
- Technical parameters and telemetry kept accessible in an inspect drawer.
"""
from pathlib import Path
from typing import List
import gradio as gr
from app.services.generation_service import GenerationService

def get_history_rows() -> List[List]:
    service = GenerationService.get_instance()
    records = service.list_history(limit=50)
    rows = []
    for r in records:
        short_txt = (r.target_text[:35] + "...") if len(r.target_text) > 35 else r.target_text
        rows.append([
            r.id,
            r.created_at[:19],
            r.mode,
            r.voice_name,
            r.language,
            f"{r.duration_sec}s",
            f"{r.generation_time_sec}s",
            f"{r.rtf}x",
            short_txt,
            r.output_audio_path
        ])
    return rows

def select_history_record(evt: gr.SelectData, history_data):
    if not history_data or evt.index[0] >= len(history_data):
        return None, "Select a valid recording."
    row = history_data[evt.index[0]]
    audio_path = row[9]
    gen_id = row[0]
    
    details_md = f"""
<div style="background: var(--studio-surface-card); border: 1px solid var(--studio-border); border-radius: var(--radius-md); padding: 16px;">
    <div style="font-size: 15px; font-weight: 700; color: var(--studio-text-primary); margin-bottom: 6px;">🎙️ Recording: {row[3]} ({row[4]})</div>
    <div style="font-size: 12.5px; color: var(--studio-text-secondary); margin-bottom: 12px;">ID: <code>{gen_id}</code> • Created: {row[1]}</div>
    
    <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--studio-text-muted); margin-bottom: 4px;">Script Transcript:</div>
    <div style="font-size: 14px; line-height: 1.6; color: var(--studio-text-primary); background: var(--studio-surface-elevated); padding: 10px 12px; border-radius: 6px; border: 1px solid var(--studio-border-subtle); margin-bottom: 12px;">
        "{row[8]}"
    </div>

    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; font-size: 12px;">
        <div style="background: var(--studio-surface-elevated); padding: 6px 10px; border-radius: 6px;">
            <span style="color: var(--studio-text-muted);">Duration:</span> <strong>{row[5]}</strong>
        </div>
        <div style="background: var(--studio-surface-elevated); padding: 6px 10px; border-radius: 6px;">
            <span style="color: var(--studio-text-muted);">Real-Time Factor:</span> <strong>{row[7]}</strong>
        </div>
    </div>
</div>
"""
    player_path = audio_path if Path(audio_path).exists() else None
    return player_path, details_md

def create_history_tab():
    with gr.Tab("📜 Generation History", id="tab_history"):
        # Header
        with gr.Row(elem_classes=["studio-canvas-card"]):
            gr.Markdown(
                """
                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <div style="font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">Media Library & History</div>
                        <div style="font-size: 13px; color: var(--studio-text-secondary); margin-top: 2px;">
                            Review past syntheses, replay 48kHz audio clips, and inspect generation telemetry.
                        </div>
                    </div>
                    <div>
                        <span class="studio-pill studio-pill-accent">Offline Media Reel</span>
                    </div>
                </div>
                """
            )

        # Two-Column Media Studio Layout
        with gr.Row():
            # LEFT: Media Catalog List
            with gr.Column(scale=6):
                with gr.Group(elem_classes=["studio-canvas-card"]):
                    with gr.Row():
                        gr.Markdown("#### 📚 Generated Speech Catalog")
                        refresh_hist_btn = gr.Button("🔄 Refresh Catalog", variant="secondary", size="sm")

                    history_table = gr.Dataframe(
                        headers=["Job ID", "Timestamp", "Speaker", "Language", "Duration", "RTF", "Script Snippet", "Audio Path"],
                        datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
                        value=get_history_rows,
                        interactive=False
                    )

            # RIGHT: Contextual Audio Player & Telemetry Inspector
            with gr.Column(scale=4):
                with gr.Group(elem_classes=["studio-inspector"]):
                    gr.Markdown("#### 🎧 Playback & Recording Details")
                    hist_audio_player = gr.Audio(label="Replay Master Audio", type="filepath", interactive=False)
                    hist_details = gr.HTML(
                        value="<div style='padding: 18px; border-radius: 8px; background: var(--studio-surface-elevated); color: var(--studio-text-muted); text-align: center; font-size: 13px;'>"
                              "Click any row in the catalog on the left to replay and inspect audio."
                              "</div>"
                    )

        refresh_hist_btn.click(fn=get_history_rows, outputs=[history_table])
        history_table.select(
            fn=select_history_record,
            inputs=[history_table],
            outputs=[hist_audio_player, hist_details]
        )
