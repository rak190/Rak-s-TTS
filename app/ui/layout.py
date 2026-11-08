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

from typing import Optional

def build_app_ui(default_tab: Optional[str] = None) -> gr.Blocks:
    """Builds and returns the main VoiceStudio AI Gradio interface."""
    with gr.Blocks(title="VoiceStudio AI — Studio Edition", css=IPHONE_INSPIRED_CSS) as demo:
        with gr.Column(elem_classes=["app-header"]):
            gr.Markdown(
                """
                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
                    <div>
                        <h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.03em;">🎙️ VoiceStudio AI</h1>
                        <h3 style="margin: 4px 0 8px 0; font-size: 15px; font-weight: 500; color: var(--ios-blue);">Multilingual Speech & Voice Cloning Studio</h3>
                        <p style="margin: 0; font-size: 13px; color: var(--ios-text-secondary);">High-Fidelity Offline AI Generation on Intel Core i5 | Powered by OpenBMB VoxCPM2</p>
                    </div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
                        <span class="cu-badge cu-badge-green">🔒 100% Local</span>
                        <span class="cu-badge cu-badge-blue">🇰🇭 Khmer & 🇬🇧 English</span>
                        <span class="cu-badge cu-badge-blue">⚡ 48kHz Studio</span>
                    </div>
                </div>
                """
            )

        with gr.Tabs(selected=default_tab):
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
            <div style="text-align: center; color: var(--ios-text-secondary); font-size: 13px; padding: 8px 0;">
                VoiceStudio AI Studio Edition (Stage 5C) • Local-Only Processing (127.0.0.1:7860) • Zero Cloud Dependencies
            </div>
            """
        )

    return demo
