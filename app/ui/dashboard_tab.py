"""Dashboard UI tab."""
import gradio as gr
from app.engines.model_manager import ModelManager
from app.queue.generation_queue import GenerationQueue
from app.database.connection import DatabaseManager
from app.utils.system_info import get_system_telemetry

def get_dashboard_metrics():
    """Fetches real-time system and engine metrics."""
    mgr = ModelManager.get_instance()
    status = mgr.get_status()
    telemetry = get_system_telemetry()
    db = DatabaseManager.get_instance()
    queue = GenerationQueue.get_instance().get_queue_stats()

    profiles = db.list_voice_profiles()
    generations = db.list_generations(limit=100)

    model_badge = "🟢 LOADED IN RAM" if status["is_loaded"] else ("🟡 LOADING..." if status["is_loading"] else "⚪ NOT LOADED")

    summary_md = f"""
### System & Engine Status: **{model_badge}**

| Metric | Current Value | Note |
| :--- | :--- | :--- |
| **Model Status** | `{model_badge}` | VoxCPM2 (2B Parameters, bfloat16) |
| **Model Load Time** | `{status['load_time_sec']}s` | Loaded on Demand from Drive D: |
| **Output Sample Rate**| `{status['sample_rate_hz']} Hz` | 48kHz Studio Quality (AudioVAE V2) |
| **Process RAM RSS** | `{status['process_rss_mb']} MB` | Safe limit (16GB RAM Laptop) |
| **System Available RAM** | `{telemetry['ram_available_gb']} GB` | Windows Operating Buffer |
| **CPU Utilization** | `{telemetry['cpu_percent']}%` | Limited to 4 Performance Cores |
| **Drive D: Free Space** | `{telemetry['disk_free_gb']} GB free` | Models & Storage on Drive D: |
| **Voice Profiles Saved** | `{len(profiles)}` | Managed in SQLite |
| **Total Generations** | `{len(generations)}` | Audio saved in `storage/generated/` |
| **Queue Depth** | `{queue['queue_depth']}` | Single-worker FIFO Queue |
"""
    return summary_md

def manual_load_model():
    """Explicitly pre-loads the model."""
    mgr = ModelManager.get_instance()
    try:
        mgr.load_model()
        return "Model loaded successfully into RAM (48kHz AudioVAE V2 ready)."
    except Exception as e:
        return f"Error loading model: {e}"

def manual_unload_model():
    """Unloads model to reclaim RAM."""
    mgr = ModelManager.get_instance()
    mgr.unload_model()
    return "Model unloaded from RAM. System memory freed."

def create_dashboard_tab():
    with gr.Tab("📊 Dashboard", id="tab_dashboard"):
        gr.Markdown("## VoiceStudio AI — Local System Dashboard")
        
        status_markdown = gr.Markdown(value=get_dashboard_metrics)
        refresh_btn = gr.Button("🔄 Refresh Status", variant="secondary")

        with gr.Row():
            load_btn = gr.Button("🚀 Pre-Load VoxCPM2 Model", variant="primary")
            unload_btn = gr.Button("🛑 Unload Model from RAM", variant="stop")
            
        action_msg = gr.Label(label="Action Feedback", value="Ready")

        refresh_btn.click(fn=get_dashboard_metrics, outputs=[status_markdown])
        load_btn.click(fn=manual_load_model, outputs=[action_msg]).then(fn=get_dashboard_metrics, outputs=[status_markdown])
        unload_btn.click(fn=manual_unload_model, outputs=[action_msg]).then(fn=get_dashboard_metrics, outputs=[status_markdown])
