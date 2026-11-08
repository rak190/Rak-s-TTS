"""
VoiceStudio Pro — Batch Queue & Overnight Background Generation Tab.
Apple Creative Workspace & Linear-inspired queue monitor:
- Real chunk progress bar and elapsed/ETA metrics.
- Full persistent job lifecycle: Queued, Processing, Paused, Interrupted, Completed, Failed.
- Cooperative pause-after-chunk, resume, cancellation, retry.
- Windows sleep inhibitor toggle and opt-in overnight power policies.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import gradio as gr

from app.database.connection import DatabaseManager
from app.queue.generation_queue import GenerationQueue
from app.services.batch_service import BatchService
from app.utils.power_manager import WindowsPowerManager

logger = logging.getLogger(__name__)

def format_queue_metrics_html(summary: Dict) -> str:
    """Generates 4 Apple/Linear styled metric cards for the queue header."""
    is_proc = summary.get("is_processing", False)
    is_paused = summary.get("is_paused", False)
    q_depth = summary.get("queue_depth", 0)
    completed = summary.get("completed_count", 0)
    interrupted = summary.get("interrupted_count", 0)
    sleep_inh = summary.get("sleep_inhibited", False)

    if is_paused:
        status_pill = "<span class='studio-pill studio-pill-warning'>⏸️ Paused</span>"
    elif is_proc:
        status_pill = "<span class='studio-pill studio-pill-accent'>⚙️ Active</span>"
    else:
        status_pill = "<span class='studio-pill studio-pill-muted'>Idle</span>"

    power_pill = (
        "<span class='studio-pill studio-pill-success'>🔒 Sleep Inhibited</span>"
        if sleep_inh
        else "<span class='studio-pill studio-pill-muted'>💤 Normal Power</span>"
    )

    return f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 20px;">
        <div class="studio-card" style="padding: 16px; border-radius: 12px; background: var(--studio-bg-card);">
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--studio-text-secondary); margin-bottom: 6px;">Engine State</div>
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="font-size: 18px; font-weight: 700; color: var(--studio-text-primary);">{status_pill}</span>
                <span style="font-size: 12px; color: var(--studio-text-muted);">1 Concurrency</span>
            </div>
        </div>
        <div class="studio-card" style="padding: 16px; border-radius: 12px; background: var(--studio-bg-card);">
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--studio-text-secondary); margin-bottom: 6px;">Pending In Queue</div>
            <div style="display: flex; align-items: baseline; gap: 8px;">
                <span style="font-size: 24px; font-weight: 700; color: var(--studio-accent);">{q_depth}</span>
                <span style="font-size: 12px; color: var(--studio-text-secondary);">jobs waiting</span>
            </div>
        </div>
        <div class="studio-card" style="padding: 16px; border-radius: 12px; background: var(--studio-bg-card);">
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--studio-text-secondary); margin-bottom: 6px;">Completed & Recovered</div>
            <div style="display: flex; align-items: baseline; gap: 8px;">
                <span style="font-size: 24px; font-weight: 700; color: #10b981;">{completed}</span>
                <span style="font-size: 12px; color: var(--studio-text-secondary);">{f'• {interrupted} interrupted' if interrupted > 0 else 'finished'}</span>
            </div>
        </div>
        <div class="studio-card" style="padding: 16px; border-radius: 12px; background: var(--studio-bg-card);">
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--studio-text-secondary); margin-bottom: 6px;">Overnight Guard</div>
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <span>{power_pill}</span>
                <span style="font-size: 11px; color: var(--studio-text-muted);">AwayMode</span>
            </div>
        </div>
    </div>
    """

def format_active_job_html(active_job: Optional[Dict]) -> str:
    """Formats the active job card with real completed/total chunk progress."""
    if not active_job or active_job.get("status") not in ("processing", "paused"):
        return """
        <div style="padding: 24px; text-align: center; border: 1px dashed var(--studio-border); border-radius: 12px; background: rgba(255,255,255,0.01); color: var(--studio-text-secondary);">
            <div style="font-size: 28px; margin-bottom: 8px;">☕</div>
            <div style="font-weight: 600; font-size: 15px; color: var(--studio-text-primary);">No speech job currently synthesizing</div>
            <div style="font-size: 12px; margin-top: 4px;">Submit scripts from Speech Studio to begin batch processing.</div>
        </div>
        """

    title = active_job.get("result", {}).get("title") or active_job.get("message") or "Speech Task"
    tot_chunks = active_job.get("total_chunks", 1) or 1
    done_chunks = active_job.get("completed_chunks", 0)
    pct = int(min(max((done_chunks / tot_chunks) * 100, 0), 100))
    elapsed = active_job.get("elapsed_sec", 0.0)

    # Estimate remaining time based on actual measured chunk rate
    eta_str = ""
    if done_chunks > 0 and elapsed > 0:
        sec_per_chunk = elapsed / done_chunks
        rem_chunks = max(tot_chunks - done_chunks, 0)
        rem_sec = int(sec_per_chunk * rem_chunks)
        eta_str = f"• ~{rem_sec // 60}m {rem_sec % 60}s remaining"

    status_tag = (
        "<span class='studio-pill studio-pill-warning'>⏸️ Pausing at boundary</span>"
        if "Pausing" in active_job.get("message", "")
        else "<span class='studio-pill studio-pill-accent'>⚙️ Processing on CPU (4 P-cores)</span>"
    )

    return f"""
    <div style="padding: 20px; border-radius: 14px; background: var(--studio-bg-card); border: 1px solid var(--studio-border); margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div>
                <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--studio-accent); font-weight: 700;">Active Synthesis</span>
                <h3 style="margin: 4px 0 0 0; font-size: 18px; font-weight: 700; color: var(--studio-text-primary);">{title}</h3>
            </div>
            <div>{status_tag}</div>
        </div>

        <div style="margin: 14px 0 8px 0;">
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px; color: var(--studio-text-secondary);">
                <span>Chunk <b>{done_chunks}</b> of <b>{tot_chunks}</b> ({pct}%)</span>
                <span>{int(elapsed)}s elapsed {eta_str}</span>
            </div>
            <div style="height: 8px; width: 100%; background: var(--studio-bg-page); border-radius: 4px; overflow: hidden;">
                <div style="height: 100%; width: {pct}%; background: linear-gradient(90deg, #6366f1, #8b5cf6); transition: width 0.3s ease;"></div>
            </div>
        </div>
        <div style="font-size: 12px; color: var(--studio-text-muted); margin-top: 8px;">
            {active_job.get('message', '')}
        </div>
    </div>
    """

def get_queue_tables_data() -> Tuple[List[List[str]], List[List[str]]]:
    """Retrieves structured pending and completed/interrupted jobs for Gradio DataFrames."""
    db = DatabaseManager.get_instance()
    all_jobs = db.list_batch_jobs(limit=100)

    pending_rows = []
    history_rows = []

    for j in all_jobs:
        if j.status in ("queued", "pending"):
            pending_rows.append([
                j.id,
                j.title,
                j.voice_name,
                j.mode.upper(),
                j.language.capitalize(),
                f"{j.completed_chunks}/{j.total_chunks}",
                j.created_at[:19].replace("T", " ")
            ])
        else:
            status_icon = {
                "completed": "✅ Completed",
                "interrupted": "⚠️ Interrupted",
                "paused": "⏸️ Paused",
                "failed": "❌ Failed",
                "cancelled": "🚫 Cancelled",
                "processing": "⚙️ Processing"
            }.get(j.status, j.status.capitalize())

            out_audio = j.output_wav_path or j.output_mp3_path or "—"
            history_rows.append([
                j.id,
                j.title,
                status_icon,
                j.voice_name,
                f"{j.completed_chunks}/{j.total_chunks}",
                j.status_message or "—",
                out_audio
            ])

    return pending_rows, history_rows

def get_pending_table_data() -> List[List[str]]:
    p, _ = get_queue_tables_data()
    return p

def get_history_table_data() -> List[List[str]]:
    _, h = get_queue_tables_data()
    return h

def refresh_view():
    svc = BatchService.get_instance()
    summary = svc.get_queue_summary()
    m_html = format_queue_metrics_html(summary)
    a_html = format_active_job_html(summary.get("active_job"))
    p_data, h_data = get_queue_tables_data()
    return m_html, a_html, p_data, h_data

def on_start_or_resume():
    svc = BatchService.get_instance()
    svc.start_or_resume_queue()
    return refresh_view()

def on_pause_queue():
    svc = BatchService.get_instance()
    svc.pause_queue()
    return refresh_view()

def on_cancel_job(job_id: str):
    if not job_id or not job_id.strip():
        return refresh_view()
    svc = BatchService.get_instance()
    svc.cancel_job(job_id.strip())
    return refresh_view()

def on_retry_job(job_id: str):
    if not job_id or not job_id.strip():
        return refresh_view()
    svc = BatchService.get_instance()
    svc.retry_job(job_id.strip())
    return refresh_view()

def on_clear_completed():
    svc = BatchService.get_instance()
    svc.clear_completed_jobs()
    return refresh_view()

def on_post_action_change(action: str):
    queue = GenerationQueue.get_instance()
    queue.set_post_completion_action(action)
    notice = ""
    if "sleep" in action.lower() or "shutdown" in action.lower():
        notice = f"⚠️ Warning: Computer will automatically {action} after the last queued job completes. Unsaved work in other apps will be affected."
    return notice

def create_queue_tab():
    """Builds the Batch Queue interface tab."""
    with gr.Tab("Batch Queue", id="tab_queue"):
        gr.HTML("""<header class="tts-page-head"><div><div class="eyebrow">VOICESTUDIO / QUEUE</div><h1>Batch Queue</h1><p>Sequential, reliable background speech synthesis with crash recovery and sleep prevention.</p></div><div class="local-status"><i></i> Background Engine <span>·</span> Concurrency 1</div></header>""")

        metrics_banner = gr.HTML(value="")
        active_job_display = gr.HTML(value="")

        with gr.Row(elem_classes=["queue-toolbar"]):
            start_btn = gr.Button("▶️ Start / Resume Queue", variant="primary", size="md")
            pause_btn = gr.Button("⏸️ Pause After Chunk", variant="secondary", size="md")
            clear_btn = gr.Button("🧹 Clear Completed", variant="secondary", size="md")
            refresh_btn = gr.Button("🔄 Refresh", variant="secondary", size="md")

        with gr.Accordion("Overnight & Power Options", open=False):
            with gr.Row():
                post_action_dropdown = gr.Dropdown(
                    label="Post-Completion Action",
                    choices=[
                        "Do nothing (Default)",
                        "Play chime notification",
                        "Sleep PC [Opt-in]",
                        "Shutdown PC [Opt-in]"
                    ],
                    value="Do nothing (Default)",
                    info="Windows will stay awake while jobs are processing. Choose what happens when all jobs complete."
                )
            opt_in_notice = gr.Markdown(value="", elem_classes=["opt-in-warning"])

        gr.HTML("<h3 style='margin-top: 24px; font-size: 16px; font-weight: 700; color: var(--studio-text-primary);'>Pending Queue</h3>")
        pending_table = gr.Dataframe(
            headers=["Job ID", "Title", "Voice", "Mode", "Language", "Chunks", "Queued At"],
            datatype=["str", "str", "str", "str", "str", "str", "str"],
            value=get_pending_table_data,
            interactive=False,
            elem_classes=["pending-jobs-table"]
        )

        with gr.Row():
            target_job_input = gr.Textbox(label="Job ID for Action", placeholder="Enter Job ID from table below (e.g. job_... or lf_...)", scale=6)
            cancel_btn = gr.Button("🛑 Cancel Job", variant="secondary", size="sm", scale=2)
            retry_btn = gr.Button("🔁 Resume / Retry Job", variant="secondary", size="sm", scale=2)

        gr.HTML("<h3 style='margin-top: 28px; font-size: 16px; font-weight: 700; color: var(--studio-text-primary);'>Job History & Checkpoints</h3>")
        history_table = gr.Dataframe(
            headers=["Job ID", "Title", "Status", "Voice", "Progress", "Message", "Output File"],
            datatype=["str", "str", "str", "str", "str", "str", "str"],
            value=get_history_table_data,
            interactive=False,
            elem_classes=["history-jobs-table"]
        )

        # Wire callbacks
        start_btn.click(fn=on_start_or_resume, outputs=[metrics_banner, active_job_display, pending_table, history_table])
        pause_btn.click(fn=on_pause_queue, outputs=[metrics_banner, active_job_display, pending_table, history_table])
        clear_btn.click(fn=on_clear_completed, outputs=[metrics_banner, active_job_display, pending_table, history_table])
        refresh_btn.click(fn=refresh_view, outputs=[metrics_banner, active_job_display, pending_table, history_table])
        cancel_btn.click(fn=on_cancel_job, inputs=[target_job_input], outputs=[metrics_banner, active_job_display, pending_table, history_table])
        retry_btn.click(fn=on_retry_job, inputs=[target_job_input], outputs=[metrics_banner, active_job_display, pending_table, history_table])
        post_action_dropdown.change(fn=on_post_action_change, inputs=[post_action_dropdown], outputs=[opt_in_notice])
