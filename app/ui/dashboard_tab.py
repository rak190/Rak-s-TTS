"""
VoiceStudio Pro — Dashboard Home Screen.
Personal creative studio home screen prioritizing:
- Welcome and quick creative studio actions (Speech Studio, Voice Cloning).
- Recent generated audio showcase.
- Compact engine status and Drive D: storage telemetry.
- Detailed system hardware diagnostics placed in collapsible accordion.
"""
from pathlib import Path
import gradio as gr
from app.engines.model_manager import ModelManager
from app.queue.generation_queue import GenerationQueue
from app.database.connection import DatabaseManager
from app.utils.system_info import get_system_telemetry

def get_dashboard_metrics() -> str:
    """Fetches real-time system and engine metrics and renders Studio Pro home cards."""
    mgr = ModelManager.get_instance()
    status = mgr.get_status()
    telemetry = get_system_telemetry()
    db = DatabaseManager.get_instance()
    queue = GenerationQueue.get_instance().get_queue_stats()

    profiles = db.list_voice_profiles()
    generations = db.list_generations(limit=5)

    model_pill_class = "studio-pill studio-pill-success" if status["is_loaded"] else ("studio-pill studio-pill-accent" if status["is_loading"] else "studio-pill studio-pill-muted")
    model_pill_text = "🟢 READY IN RAM" if status["is_loaded"] else ("🟡 LOADING..." if status["is_loading"] else "⚪ STANDBY (ON-DEMAND)")

    recent_html = ""
    if generations:
        for g in generations[:3]:
            short_txt = (g.target_text[:35] + "...") if len(g.target_text) > 35 else g.target_text
            recent_html += f"""
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--studio-surface-elevated); border: 1px solid var(--studio-border-subtle); border-radius: var(--radius-sm); margin-bottom: 6px;">
                <div>
                    <span style="font-weight: 600; font-size: 13px; color: var(--studio-text-primary);">{g.voice_name}</span>
                    <span style="font-size: 11.5px; color: var(--studio-text-secondary); margin-left: 8px;">({g.language})</span>
                    <div style="font-size: 12px; color: var(--studio-text-muted); margin-top: 2px;">"{short_txt}"</div>
                </div>
                <div style="text-align: right;">
                    <span class="studio-pill studio-pill-muted">{g.duration_sec}s audio</span>
                    <div style="font-size: 11px; color: var(--studio-text-muted); margin-top: 2px;">{g.created_at[:10]}</div>
                </div>
            </div>
            """
    else:
        recent_html = "<div style='color: var(--studio-text-muted); font-size: 13px;'>No audio generated yet. Open Speech Studio to create your first speech clip.</div>"

    summary_html = f"""
<div style="margin-bottom: 18px;">
    <!-- Welcome Header -->
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
        <div>
            <h2 style="margin: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.025em; color: var(--studio-text-primary);">🎙️ VoiceStudio Pro Workspace</h2>
            <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--studio-text-secondary);">Personal Speech Synthesis & Voice Cloning Studio • Offline Intel Core i5 Engine (4 Performance Cores)</p>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
            <span class="{model_pill_class}">{model_pill_text}</span>
            <span class="studio-pill studio-pill-accent">⚡ 48kHz Studio</span>
        </div>
    </div>

    <!-- System & Engine Status Cards -->
    <h3 style="margin: 0 0 10px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--studio-text-secondary);">System & Engine Status</h3>
    
    <div class="studio-metric-grid">
        <div class="studio-metric-card">
            <div class="studio-metric-label">AI Engine</div>
            <div class="studio-metric-value" style="font-size: 15px;">{model_pill_text}</div>
            <div class="studio-metric-sub">VoxCPM2 (2B) • Load: {status['load_time_sec']}s</div>
        </div>

        <div class="studio-metric-card">
            <div class="studio-metric-label">Voice Profiles</div>
            <div class="studio-metric-value">{len(profiles)}</div>
            <div class="studio-metric-sub">Ready for cloning & TTS</div>
        </div>

        <div class="studio-metric-card">
            <div class="studio-metric-label">Audio Generations</div>
            <div class="studio-metric-value">{len(generations)}</div>
            <div class="studio-metric-sub">Queue Depth: {queue['queue_depth']}</div>
        </div>

        <div class="studio-metric-card">
            <div class="studio-metric-label">Available RAM</div>
            <div class="studio-metric-value">{telemetry['ram_available_gb']} GB</div>
            <div class="studio-metric-sub">Process: {status['process_rss_mb']} MB (Safe for 16GB)</div>
        </div>

        <div class="studio-metric-card">
            <div class="studio-metric-label">Drive D: Free Space</div>
            <div class="studio-metric-value">{telemetry['disk_free_gb']} GB</div>
            <div class="studio-metric-sub">Ample SSD storage buffer</div>
        </div>
    </div>

    <!-- Recent Creations Reel -->
    <div style="background: var(--studio-surface); border: 1px solid var(--studio-border); border-radius: var(--radius-md); padding: 16px; margin-top: 14px;">
        <div style="font-size: 13.5px; font-weight: 600; color: var(--studio-text-primary); margin-bottom: 10px;">Recent Creations</div>
        {recent_html}
    </div>
</div>
"""
    return summary_html

def manual_load_model() -> str:
    """Explicitly pre-loads the model."""
    mgr = ModelManager.get_instance()
    try:
        mgr.load_model()
        return "Model loaded successfully into RAM (48kHz AudioVAE V2 ready)."
    except Exception as e:
        return f"Error loading model: {e}"

def manual_unload_model() -> str:
    """Unloads model to reclaim RAM."""
    mgr = ModelManager.get_instance()
    mgr.unload_model()
    return "Model unloaded from RAM. System memory freed."

def create_dashboard_tab():
    with gr.Tab("📊 Dashboard", id="tab_dashboard"):
        status_html = gr.HTML(value=get_dashboard_metrics)
        
        with gr.Row():
            refresh_btn = gr.Button("🔄 Refresh Status", variant="secondary", size="sm")

        with gr.Accordion("⚙️ Hardware Diagnostics & Memory Controls", open=False):
            gr.Markdown(
                """
                | Parameter | Value |
                | :--- | :--- |
                | **Inference Hardware** | Intel Core i5-1240P (HP ENVY x360), Iris Xe |
                | **CPU Allocation** | 4 Performance Cores (bfloat16 PyTorch CPU) |
                | **AudioVAE Sample Rate** | 48,000 Hz Native Mono (PCM_16) |
                | **Local Address** | `http://127.0.0.1:7860` (100% Offline) |
                """
            )
            with gr.Row():
                load_btn = gr.Button("🚀 Pre-Load VoxCPM2 Model", variant="secondary", size="sm")
                unload_btn = gr.Button("🛑 Free RAM (Unload Model)", variant="stop", size="sm")
            action_msg = gr.Label(label="Diagnostic Action Status", value="Ready")

            load_btn.click(fn=manual_load_model, outputs=[action_msg]).then(fn=get_dashboard_metrics, outputs=[status_html])
            unload_btn.click(fn=manual_unload_model, outputs=[action_msg]).then(fn=get_dashboard_metrics, outputs=[status_html])

        refresh_btn.click(fn=get_dashboard_metrics, outputs=[status_html])
