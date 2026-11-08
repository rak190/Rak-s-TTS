"""Generation History UI tab."""
import gradio as gr
from pathlib import Path
from typing import List
from app.services.generation_service import GenerationService

def get_history_rows() -> List[List]:
    service = GenerationService.get_instance()
    records = service.list_history(limit=50)
    rows = []
    for r in records:
        rows.append([
            r.id,
            r.created_at[:19],
            r.mode,
            r.voice_name,
            r.language,
            f"{r.duration_sec}s",
            f"{r.generation_time_sec}s",
            f"{r.rtf}x",
            r.target_text[:40] + ("..." if len(r.target_text) > 40 else ""),
            r.output_audio_path
        ])
    return rows

def select_history_record(evt: gr.SelectData, history_data):
    if not history_data or evt.index[0] >= len(history_data):
        return None, "Select a valid record."
    row = history_data[evt.index[0]]
    audio_path = row[9]
    gen_id = row[0]
    
    details_md = f"""
### Record ID: `{gen_id}`
* **Created:** `{row[1]}`
* **Mode:** `{row[2]}`
* **Voice:** `{row[3]}`
* **Language:** `{row[4]}`
* **Duration:** `{row[5]}`
* **Generation Time:** `{row[6]}`
* **RTF:** `{row[7]}`
* **Full Text:** {row[8]}
* **File Path:** `{audio_path}`
"""
    player_path = audio_path if Path(audio_path).exists() else None
    return player_path, details_md

def handle_delete_history(evt: gr.SelectData, history_data):
    if not history_data or evt.index[0] >= len(history_data):
        return get_history_rows(), "Select a record first."
    gen_id = history_data[evt.index[0]][0]
    service = GenerationService.get_instance()
    service.delete_history_item(gen_id)
    return get_history_rows(), f"Record {gen_id} deleted."

def create_history_tab():
    with gr.Tab("📜 Generation History", id="tab_history"):
        gr.Markdown("## Speech Generation History")
        gr.Markdown("Review past syntheses, replay audio, inspect telemetry, and manage disk files.")

        with gr.Row():
            refresh_hist_btn = gr.Button("🔄 Refresh History", variant="secondary")

        history_table = gr.Dataframe(
            headers=["ID", "Timestamp", "Mode", "Voice", "Lang", "Duration", "Gen Time", "RTF", "Text Snippet", "Audio Path"],
            datatype=["str", "str", "str", "str", "str", "str", "str", "str", "str", "str"],
            value=get_history_rows,
            interactive=False
        )

        with gr.Row():
            with gr.Column(scale=1):
                hist_audio_player = gr.Audio(label="Replay Audio", type="filepath")
            with gr.Column(scale=2):
                hist_details = gr.Markdown(value="Click a row above to inspect generation details.")

        refresh_hist_btn.click(fn=get_history_rows, outputs=[history_table])
        history_table.select(
            fn=select_history_record,
            inputs=[history_table],
            outputs=[hist_audio_player, hist_details]
        )
