"""Main UI layout assembling all tabs into a unified Gradio Blocks app."""
import gradio as gr
from app.ui.dashboard_tab import create_dashboard_tab
from app.ui.library_tab import create_library_tab
from app.ui.cloning_tab import create_cloning_tab
from app.ui.tts_tab import create_tts_tab
from app.ui.history_tab import create_history_tab
from app.ui.settings_tab import create_settings_tab

def build_app_ui() -> gr.Blocks:
    """Builds and returns the main VoiceStudio AI Gradio interface."""
    with gr.Blocks(title="VoiceStudio AI — Local Edition") as demo:
        gr.Markdown(
            """
            # 🎙️ VoiceStudio AI — Local Edition
            *Multilingual Text-to-Speech & Voice Cloning Studio (Khmer & English) | Powered by OpenBMB VoxCPM2*
            """
        )

        with gr.Tabs():
            create_dashboard_tab()
            create_tts_tab()
            create_cloning_tab()
            create_library_tab()
            create_history_tab()
            create_settings_tab()

        gr.Markdown(
            """
            ---
            *VoiceStudio AI Local Foundation (Stage 2B) | Bound strictly to `127.0.0.1` | No Cloud GPU / No Paid APIs*
            """
        )

    return demo
