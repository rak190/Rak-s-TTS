"""Main UI layout assembling all tabs into a unified Gradio Blocks app with iPhone-inspired Cupertino design."""
import gradio as gr
from app.ui.dashboard_tab import create_dashboard_tab
from app.ui.library_tab import create_library_tab
from app.ui.cloning_tab import create_cloning_tab
from app.ui.tts_tab import create_tts_tab
from app.ui.mastering_tab import create_mastering_tab
from app.ui.history_tab import create_history_tab
from app.ui.settings_tab import create_settings_tab
from app.ui.styles import IPHONE_INSPIRED_CSS

def build_app_ui() -> gr.Blocks:
    """Builds and returns the main VoiceStudio AI Gradio interface."""
    with gr.Blocks(title="VoiceStudio AI — Studio Edition") as demo:
        with gr.Column(elem_classes=["app-header"]):
            gr.Markdown(
                """
                # 🎙️ VoiceStudio AI
                ### Multilingual Speech & Voice Cloning Studio (Khmer & English)
                *High-Fidelity Offline AI Generation on Intel Core i5 | Powered by OpenBMB VoxCPM2*
                """
            )

        with gr.Tabs():
            create_dashboard_tab()
            create_tts_tab()
            create_cloning_tab()
            create_mastering_tab()
            create_library_tab()
            create_history_tab()
            create_settings_tab()

        gr.Markdown(
            """
            ---
            <div style="text-align: center; color: #86868b; font-size: 13px;">
                VoiceStudio AI Studio Edition (Stage 4) • Local-Only Processing (127.0.0.1) • Zero Cloud Dependencies
            </div>
            """
        )

    return demo
