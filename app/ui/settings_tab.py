"""Settings and Configuration UI tab."""
import gradio as gr
from app.config import (
    BASE_DIR,
    STORAGE_DIR,
    MODELS_DIR,
    DB_PATH,
    DEFAULT_CPU_THREADS,
    SERVER_HOST,
    SERVER_PORT,
    NATIVE_SAMPLE_RATE
)
from app.utils.system_info import get_system_telemetry

def get_settings_markdown():
    telem = get_system_telemetry()
    return f"""
### VoiceStudio AI — Configuration & Safety Information

| Configuration Key | Configured Path / Setting |
| :--- | :--- |
| **Project Root** | `{BASE_DIR}` |
| **Storage Directory** | `{STORAGE_DIR}` |
| **Model Weights (Drive D:)** | `{MODELS_DIR}` |
| **SQLite Database** | `{DB_PATH}` |
| **Local Binding** | `http://{SERVER_HOST}:{SERVER_PORT}` *(Local Only)* |
| **CPU Thread Cap** | `{DEFAULT_CPU_THREADS} Threads (Performance Cores)` |
| **Output Sample Rate** | `{NATIVE_SAMPLE_RATE} Hz (Studio 48kHz AudioVAE V2)` |
| **Drive D: Free Space** | `{telem['disk_free_gb']} GB Free / {telem['disk_total_gb']} GB Total` |

---
### 🔒 Security & Privacy Notice
* **100% Local Inference:** No audio recordings, transcripts, or model latents are transmitted over the network or cloud APIs.
* **Server Binding:** The application binds strictly to loopback interface `127.0.0.1`.
* **Biometric & Voice Data:** Voice profiles and audio recordings are stored on your local SSD and can be deleted at any time from the Voice Library tab.
"""

def create_settings_tab():
    with gr.Tab("⚙️ Settings", id="tab_settings"):
        gr.Markdown("## System Settings & Deployment Profile")
        settings_info = gr.Markdown(value=get_settings_markdown)
        refresh_settings_btn = gr.Button("🔄 Refresh Telemetry", variant="secondary")
        refresh_settings_btn.click(fn=get_settings_markdown, outputs=[settings_info])
