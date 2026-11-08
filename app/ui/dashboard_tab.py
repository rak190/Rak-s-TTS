"""Dashboard UI tab with Cupertino iPhone-inspired telemetry and metric cards."""
import gradio as gr
from app.engines.model_manager import ModelManager
from app.queue.generation_queue import GenerationQueue
from app.database.connection import DatabaseManager
from app.utils.system_info import get_system_telemetry

def get_dashboard_metrics() -> str:
    """Fetches real-time system and engine metrics and renders Cupertino metric cards."""
    mgr = ModelManager.get_instance()
    status = mgr.get_status()
    telemetry = get_system_telemetry()
    db = DatabaseManager.get_instance()
    queue = GenerationQueue.get_instance().get_queue_stats()

    profiles = db.list_voice_profiles()
    generations = db.list_generations(limit=100)

    model_badge_class = "cu-badge cu-badge-green" if status["is_loaded"] else ("cu-badge cu-badge-orange" if status["is_loading"] else "cu-badge")
    model_badge_text = "🟢 LOADED IN RAM" if status["is_loaded"] else ("🟡 LOADING..." if status["is_loading"] else "⚪ NOT LOADED")

    summary_html = f"""
<div style="margin-bottom: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <h3 style="margin: 0; font-size: 18px; font-weight: 600;">System & Engine Status</h3>
        <span class="{model_badge_class}">{model_badge_text}</span>
    </div>

    <div class="cu-metric-grid">
        <div class="cu-metric-card">
            <div class="cu-metric-label">AI Engine Status</div>
            <div class="cu-metric-value" style="font-size: 16px;">{model_badge_text}</div>
            <div class="cu-metric-note">VoxCPM2 (2B bfloat16) • Load: {status['load_time_sec']}s</div>
        </div>

        <div class="cu-metric-card">
            <div class="cu-metric-label">Audio Sample Rate</div>
            <div class="cu-metric-value">{status['sample_rate_hz']} Hz</div>
            <div class="cu-metric-note">Studio Quality (AudioVAE V2)</div>
        </div>

        <div class="cu-metric-card">
            <div class="cu-metric-label">System Available RAM</div>
            <div class="cu-metric-value">{telemetry['ram_available_gb']} GB</div>
            <div class="cu-metric-note">Process RSS: {status['process_rss_mb']} MB (Safe for 16GB)</div>
        </div>

        <div class="cu-metric-card">
            <div class="cu-metric-label">CPU Utilization</div>
            <div class="cu-metric-value">{telemetry['cpu_percent']}%</div>
            <div class="cu-metric-note">Capped at 4 Performance Cores</div>
        </div>

        <div class="cu-metric-card">
            <div class="cu-metric-label">Drive D: Free Space</div>
            <div class="cu-metric-value">{telemetry['disk_free_gb']} GB</div>
            <div class="cu-metric-note">Local models & outputs verified</div>
        </div>

        <div class="cu-metric-card">
            <div class="cu-metric-label">Saved Voice Profiles</div>
            <div class="cu-metric-value">{len(profiles)}</div>
            <div class="cu-metric-note">Generations: {len(generations)} | Queue: {queue['queue_depth']}</div>
        </div>
    </div>
</div>

<div class="cu-card" style="padding: 14px; margin-top: 10px;">
    <h4 style="margin: 0 0 8px 0; font-size: 14px; font-weight: 600; color: var(--ios-text-secondary);">DETAILED SYSTEM SPECIFICATIONS</h4>
    <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
        <tr>
            <td style="padding: 6px 0; color: var(--ios-text-secondary); width: 35%;"><strong>Inference Architecture:</strong></td>
            <td style="padding: 6px 0;">Official OpenBMB VoxCPM2 (PyTorch CPU, bfloat16)</td>
        </tr>
        <tr>
            <td style="padding: 6px 0; color: var(--ios-text-secondary);"><strong>Target Hardware:</strong></td>
            <td style="padding: 6px 0;">Intel Core i5-1240P (HP ENVY x360), 16GB RAM, Iris Xe</td>
        </tr>
        <tr>
            <td style="padding: 6px 0; color: var(--ios-text-secondary);"><strong>Supported Languages:</strong></td>
            <td style="padding: 6px 0;">Khmer (ភាសាខ្មែរ) & English (Native & Mixed Code-Switching)</td>
        </tr>
        <tr>
            <td style="padding: 6px 0; color: var(--ios-text-secondary);"><strong>Local Binding:</strong></td>
            <td style="padding: 6px 0;"><code>http://127.0.0.1:7860</code> (Strictly local, no remote access)</td>
        </tr>
    </table>
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
        with gr.Column(elem_classes=["cu-card"]):
            gr.Markdown(
                """
                ## 📊 VoiceStudio AI — Local System Dashboard
                *Real-time monitoring of VoxCPM2 model status, Intel Core i5 CPU threads, RAM footprint, and storage.*
                """
            )
        
        status_html = gr.HTML(value=get_dashboard_metrics)
        refresh_btn = gr.Button("🔄 Refresh Status", variant="secondary")

        with gr.Row():
            load_btn = gr.Button("🚀 Pre-Load VoxCPM2 Model", variant="primary")
            unload_btn = gr.Button("🛑 Unload Model from RAM", variant="stop")
            
        action_msg = gr.Label(label="Action Feedback", value="Ready")

        refresh_btn.click(fn=get_dashboard_metrics, outputs=[status_html])
        load_btn.click(fn=manual_load_model, outputs=[action_msg]).then(fn=get_dashboard_metrics, outputs=[status_html])
        unload_btn.click(fn=manual_unload_model, outputs=[action_msg]).then(fn=get_dashboard_metrics, outputs=[status_html])
