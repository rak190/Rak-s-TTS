"""
Settings, Configuration, and Backup/Restore UI tab for VoiceStudio AI.
Cupertino iPhone-inspired layout with persistent user preferences,
storage folder shortcuts, atomic database backups, and full studio archive management.
"""
import logging
from pathlib import Path
from typing import List, Tuple

import gradio as gr

from app.config import (
    BASE_DIR,
    DB_PATH,
    DEFAULT_CPU_THREADS,
    MODELS_DIR,
    NATIVE_SAMPLE_RATE,
    SERVER_HOST,
    SERVER_PORT,
    STORAGE_DIR
)
from app.database.backup import DatabaseBackupService
from app.services.settings_service import SettingsService
from app.services.voice_service import VoiceProfileService
from app.utils.system_info import get_system_telemetry

logger = logging.getLogger(__name__)


def get_voice_choices() -> List[Tuple[str, str]]:
    """Retrieves available voice profiles for settings dropdown."""
    choices = [("None (Use Default Voice)", "")]
    try:
        profiles = VoiceProfileService.get_instance().list_profiles()
        for p in profiles:
            choices.append((f"{p.name} ({p.language})", p.name))
    except Exception:
        pass
    return choices


def get_backup_table_rows() -> List[List]:
    """Retrieves backup history rows for display."""
    backups = DatabaseBackupService.list_backups()
    rows = []
    for b in backups:
        rows.append([
            b["type"],
            b["filename"],
            b["size"],
            b["created_at"],
            b["path"]
        ])
    return rows


def get_backup_choices() -> List[Tuple[str, str]]:
    """Retrieves list of available backups for restoration dropdown."""
    backups = DatabaseBackupService.list_backups()
    if not backups:
        return [("No backups available yet", "")]
    return [(f"{b['type']}: {b['filename']} ({b['size']})", b["path"]) for b in backups]


def handle_save_preferences(
    lang: str,
    voice: str,
    theme: str,
    fmt: str,
    auto_open: bool,
    preload: bool
) -> str:
    """Saves user preferences to SQLite."""
    svc = SettingsService()
    ok, msg = svc.save_preferences(
        default_language=lang,
        default_voice=voice,
        theme=theme,
        default_audio_format=fmt,
        auto_open_browser=auto_open,
        preload_model=preload
    )
    return msg


def handle_create_db_backup() -> Tuple[str, List[List], gr.Dropdown]:
    """Creates a fast SQLite database snapshot."""
    ok, msg, path = DatabaseBackupService.create_database_backup()
    status_icon = "✅" if ok else "❌"
    choices = get_backup_choices()
    default_val = choices[0][1] if choices and choices[0][1] else None
    return (
        f"{status_icon} {msg}",
        get_backup_table_rows(),
        gr.Dropdown(choices=choices, value=default_val)
    )


def handle_create_full_backup() -> Tuple[str, List[List], gr.Dropdown]:
    """Creates a complete Studio Data Archive (ZIP)."""
    ok, msg, path = DatabaseBackupService.create_full_studio_backup()
    status_icon = "✅" if ok else "❌"
    choices = get_backup_choices()
    default_val = choices[0][1] if choices and choices[0][1] else None
    return (
        f"{status_icon} {msg}",
        get_backup_table_rows(),
        gr.Dropdown(choices=choices, value=default_val)
    )


def handle_restore_backup(backup_path: str, confirmed: bool) -> Tuple[str, List[List]]:
    """Restores database or full archive after safety validation."""
    if not backup_path or not Path(backup_path).exists():
        return "⚠️ Please select a valid backup from the dropdown.", get_backup_table_rows()

    if not confirmed:
        return (
            "⚠️ Confirmation required. Please check 'I confirm I want to restore this backup' before proceeding.",
            get_backup_table_rows()
        )

    ok, msg = DatabaseBackupService.restore_backup(backup_path)
    status_icon = "✅" if ok else "❌"
    return f"{status_icon} {msg}", get_backup_table_rows()


def handle_open_folder(folder_key: str) -> str:
    """Opens a storage folder in Windows File Explorer."""
    ok, msg = SettingsService.open_system_folder(folder_key)
    return msg


def get_settings_markdown() -> str:
    """Generates read-only telemetry markdown."""
    telem = get_system_telemetry()
    return f"""
| Configuration Property | Value / Path |
| :--- | :--- |
| **Project Root** | `{BASE_DIR}` |
| **Storage Directory** | `{STORAGE_DIR}` |
| **Model Weights (Drive D:)** | `{MODELS_DIR}` |
| **SQLite Database** | `{DB_PATH}` (Schema v3) |
| **Local Binding** | `http://{SERVER_HOST}:{SERVER_PORT}` *(100% Local Inference)* |
| **CPU Thread Allocation** | `{DEFAULT_CPU_THREADS} Threads (Performance Cores)` |
| **Audio Sample Rate** | `{NATIVE_SAMPLE_RATE} Hz (Studio 48kHz AudioVAE V2)` |
| **Drive D: Free Space** | `{telem['disk_free_gb']} GB Free / {telem['disk_total_gb']} GB Total` |
| **Inference Engine** | `OpenBMB VoxCPM2 (bfloat16 CPU)` |
"""


def create_settings_tab():
    """Builds the comprehensive Cupertino Settings & Studio Management Tab."""
    svc = SettingsService()
    current_prefs = svc.get_all_preferences()

    with gr.Tab("⚙️ Settings", id="tab_settings"):
        with gr.Column(elem_classes=["cu-card"]):
            gr.Markdown(
                """
                ## ⚙️ Studio Settings & Data Management
                *Configure application defaults, access local files, and manage full studio data backups.*
                """
            )

        with gr.Row():
            # Left Column: User Preferences & Storage Shortcuts
            with gr.Column(scale=1):
                with gr.Group(elem_classes=["cu-card"]):
                    gr.Markdown("### 🎛️ Default Studio Preferences")

                    pref_lang = gr.Dropdown(
                        label="Default Generation Language",
                        choices=[
                            ("Multilingual (Auto-Detect Khmer & English)", "multilingual"),
                            ("Khmer (ភាសាខ្មែរ)", "km"),
                            ("English", "en")
                        ],
                        value=current_prefs.get("default_language", "multilingual")
                    )

                    pref_voice = gr.Dropdown(
                        label="Default Voice Profile",
                        choices=get_voice_choices(),
                        value=current_prefs.get("default_voice", "")
                    )

                    with gr.Row():
                        pref_theme = gr.Dropdown(
                            label="UI Theme Appearance",
                            choices=[
                                ("Follow System Appearance", "system"),
                                ("Cupertino Light Mode", "light"),
                                ("OLED Dark Mode", "dark")
                            ],
                            value=current_prefs.get("theme", "system")
                        )

                        pref_format = gr.Radio(
                            label="Default Export Format",
                            choices=[("WAV (24-bit PCM)", "wav"), ("MP3 (320 kbps)", "mp3")],
                            value=current_prefs.get("default_audio_format", "wav")
                        )

                    with gr.Row():
                        pref_auto_browser = gr.Checkbox(
                            label="Auto-Open Browser on Startup",
                            value=current_prefs.get("auto_open_browser", "true") == "true"
                        )
                        pref_preload = gr.Checkbox(
                            label="Preload AI Model on App Start",
                            value=current_prefs.get("preload_model", "false") == "true"
                        )

                    save_prefs_btn = gr.Button("💾 Save Preferences", variant="primary")
                    prefs_status = gr.Markdown(value="")

                with gr.Group(elem_classes=["cu-card"]):
                    gr.Markdown("### 📂 Open Local Audio Folders")
                    gr.Markdown("Directly access your generated WAV/MP3 files, mastered audio, and voice profiles.")

                    with gr.Row():
                        open_gen_btn = gr.Button("📂 Generated Speech", variant="secondary")
                        open_mst_btn = gr.Button("📂 Mastered Audio", variant="secondary")

                    with gr.Row():
                        open_voi_btn = gr.Button("📂 Voice Profiles", variant="secondary")
                        open_bak_btn = gr.Button("📂 Backups Folder", variant="secondary")

                    folder_status = gr.Markdown(value="")

            # Right Column: Backup, Restore & Telemetry
            with gr.Column(scale=1):
                with gr.Group(elem_classes=["cu-card"]):
                    gr.Markdown("### 🛡️ Studio Backup & Safe Recovery")
                    gr.Markdown(
                        """
                        * **Database Backup (SQLite Only):** Fast snapshot of database records and schema.
                        * **Full Studio Archive (ZIP):** Comprehensive backup of database, voice profiles, references, generated audio, and long-form chunks *(excludes ~6.2GB model weights)*.
                        """
                    )

                    with gr.Row():
                        create_db_bak_btn = gr.Button("💾 Create Database Backup", variant="secondary")
                        create_full_bak_btn = gr.Button("📦 Create Full Studio Archive", variant="primary")

                    backup_status_msg = gr.Markdown(value="")

                    gr.Markdown("#### 📜 Backup Archive History")
                    backup_table = gr.Dataframe(
                        headers=["Backup Type", "Filename", "Size", "Created Date", "File Path"],
                        datatype=["str", "str", "str", "str", "str"],
                        value=get_backup_table_rows,
                        interactive=False
                    )

                    gr.Markdown("#### 🔄 Restore from Backup Archive")
                    restore_dropdown = gr.Dropdown(
                        label="Select Backup to Restore",
                        choices=get_backup_choices(),
                        value=get_backup_choices()[0][1] if get_backup_choices() else ""
                    )
                    restore_confirm_chk = gr.Checkbox(
                        label="⚠️ I confirm I want to restore this backup. (A pre-restore safety snapshot will be created automatically)",
                        value=False
                    )
                    restore_btn = gr.Button("🔄 Restore Selected Backup", variant="stop")
                    restore_status_msg = gr.Markdown(value="")

        # System Telemetry & Privacy Banner
        with gr.Row():
            with gr.Column():
                with gr.Group(elem_classes=["cu-card"]):
                    gr.Markdown("### 📊 System Information & Telemetry")
                    telemetry_display = gr.Markdown(value=get_settings_markdown)
                    refresh_telem_btn = gr.Button("🔄 Refresh Telemetry", variant="secondary", size="sm")

                    gr.Markdown(
                        """
                        ---
                        ### 🔒 100% Offline Local Privacy Guarantee
                        * All synthesis and mastering runs locally on your Intel Core i5 CPU at `127.0.0.1`.
                        * No audio, transcripts, voice biometrics, or embeddings are transmitted to any cloud server or API.
                        """
                    )

        # Event Handlers
        save_prefs_btn.click(
            fn=handle_save_preferences,
            inputs=[
                pref_lang,
                pref_voice,
                pref_theme,
                pref_format,
                pref_auto_browser,
                pref_preload
            ],
            outputs=[prefs_status]
        )

        open_gen_btn.click(fn=lambda: handle_open_folder("generated"), outputs=[folder_status])
        open_mst_btn.click(fn=lambda: handle_open_folder("mastered"), outputs=[folder_status])
        open_voi_btn.click(fn=lambda: handle_open_folder("voices"), outputs=[folder_status])
        open_bak_btn.click(fn=lambda: handle_open_folder("backups"), outputs=[folder_status])

        create_db_bak_btn.click(
            fn=handle_create_db_backup,
            outputs=[backup_status_msg, backup_table, restore_dropdown]
        )

        create_full_bak_btn.click(
            fn=handle_create_full_backup,
            outputs=[backup_status_msg, backup_table, restore_dropdown]
        )

        restore_btn.click(
            fn=handle_restore_backup,
            inputs=[restore_dropdown, restore_confirm_chk],
            outputs=[restore_status_msg, backup_table]
        )

        refresh_telem_btn.click(
            fn=get_settings_markdown,
            outputs=[telemetry_display]
        )
