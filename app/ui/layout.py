"""Main UI layout assembling all tabs into a unified Gradio Blocks app with VoiceStudio Pro design."""
import gradio as gr
from typing import Optional
from app.ui.dashboard_tab import create_dashboard_tab
from app.ui.library_tab import create_library_tab
from app.ui.cloning_tab import create_cloning_tab
from app.ui.tts_tab import create_tts_tab
from app.ui.mastering_tab import create_mastering_tab
from app.ui.history_tab import create_history_tab
from app.ui.settings_tab import create_settings_tab
from app.ui.styles import STUDIO_PRO_CSS

def build_app_ui(default_tab: Optional[str] = None) -> gr.Blocks:
    """Builds and returns the main VoiceStudio Pro Gradio interface."""
    with gr.Blocks(title="VoiceStudio Pro — Apple Creative Workspace") as demo:
        # Embed design system stylesheet directly to guarantee full rendering across Gradio 6 runtimes
        gr.HTML(
            f"""
            <style id='voicestudio-pro-design-system'>{STUDIO_PRO_CSS}</style>
            <div class="studio-app-header">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 17px; font-weight: 700; letter-spacing: -0.025em; color: var(--studio-text-primary);">🎙️ VoiceStudio Pro</span>
                    <span class="studio-pill studio-pill-accent">Creative Studio</span>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span class="studio-pill studio-pill-muted">48kHz AudioVAE V2</span>
                    <span class="studio-pill studio-pill-success">🔒 100% Offline • 4 P-Cores</span>
                </div>
            </div>
            """
        )

        with gr.Tabs(selected=default_tab or "tab_tts", elem_classes=["main-studio-tabs"], overflow_behavior="wrap"):
            create_tts_tab()
            create_cloning_tab()
            create_mastering_tab()
            create_library_tab()
            create_history_tab()
            create_dashboard_tab()
            create_settings_tab()

    return demo
