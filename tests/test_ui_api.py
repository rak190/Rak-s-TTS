"""Automated verification of the VoiceStudio AI Gradio interface and backend endpoints."""
import json
import unittest
import urllib.request
from pathlib import Path

from app.config import SERVER_HOST, SERVER_PORT, BASE_DIR
from app.ui.dashboard_tab import get_dashboard_metrics, manual_load_model, manual_unload_model
from app.ui.library_tab import get_profile_choices, load_profile_details
from app.ui.cloning_tab import inspect_uploaded_audio, preview_trimmed_segment
from app.ui.tts_tab import on_text_changed, get_available_profiles, run_tts_generation, cancel_current_generation
from app.ui.history_tab import get_history_rows
from app.ui.settings_tab import get_settings_markdown

class TestVoiceStudioUI(unittest.TestCase):
    """Verifies that all Gradio UI components, tab backends, and endpoints execute properly."""

    def test_01_tab_modules_and_layout_exports(self):
        from app.ui.layout import build_app_ui
        from app.ui.dashboard_tab import create_dashboard_tab
        from app.ui.tts_tab import create_tts_tab
        from app.ui.cloning_tab import create_cloning_tab
        from app.ui.library_tab import create_library_tab
        from app.ui.mastering_tab import create_mastering_tab
        from app.ui.history_tab import create_history_tab
        from app.ui.settings_tab import create_settings_tab

        self.assertTrue(callable(build_app_ui))
        self.assertTrue(callable(create_dashboard_tab))
        self.assertTrue(callable(create_tts_tab))
        self.assertTrue(callable(create_cloning_tab))
        self.assertTrue(callable(create_mastering_tab))
        self.assertTrue(callable(create_library_tab))
        self.assertTrue(callable(create_history_tab))
        self.assertTrue(callable(create_settings_tab))

    def test_02_dashboard_tab_backend(self):
        metrics_md = get_dashboard_metrics()
        self.assertIn("System & Engine Status", metrics_md)
        self.assertIn("VoxCPM2", metrics_md)
        self.assertIn("Performance Cores", metrics_md)
        self.assertIn("Drive D:", metrics_md)

    def test_03_tts_tab_language_detection(self):
        # Khmer
        msg_kh = on_text_changed("សួស្តីកម្ពុជា")
        self.assertIn("Khmer", msg_kh)
        
        # English
        msg_en = on_text_changed("Hello world, this is a test.")
        self.assertIn("English", msg_en)
        
        # Mixed
        msg_mixed = on_text_changed("សួស្តី Hello World")
        self.assertIn("Mixed", msg_mixed)
        
        # Empty
        msg_empty = on_text_changed("")
        self.assertIn("Waiting", msg_empty)

    def test_04_tts_tab_profiles_list(self):
        profiles = get_available_profiles()
        self.assertIsInstance(profiles, list)
        self.assertGreater(len(profiles), 0)

    def test_05_cloning_tab_inspection_and_trimming(self):
        # Test inspecting missing file
        info, start, end, p = inspect_uploaded_audio("non_existent_audio.wav")
        self.assertIn("Invalid audio", info)
        
        # Test trimming with invalid range
        out_wav, msg = preview_trimmed_segment("dummy.wav", 10.0, 5.0)
        self.assertIsNone(out_wav)
        self.assertIn("audio first", msg)

    def test_06_voice_library_tab_backend(self):
        choices = get_profile_choices()
        self.assertIsInstance(choices, list)
        if choices and choices[0] != "No profiles created yet":
            name, desc, lang, trans, ref_p, orig_p, details = load_profile_details(choices[0])
            self.assertTrue(len(name) > 0)
            self.assertIn("Profile:", details)

    def test_07_history_tab_backend(self):
        rows = get_history_rows()
        self.assertIsInstance(rows, list)
        # Should have rows from integration test runs
        if rows:
            first_row = rows[0]
            self.assertEqual(len(first_row), 10)
            self.assertTrue(first_row[0].startswith("gen_"))

    def test_08_settings_tab_backend(self):
        settings_md = get_settings_markdown()
        self.assertIn(str(BASE_DIR), settings_md)
        self.assertIn("48000 Hz", settings_md)
        self.assertIn("127.0.0.1", settings_md)
        self.assertIn("100% Local Inference", settings_md)

    def test_09_tts_tab_generator_and_cancel(self):
        # Empty text error test
        gen = run_tts_generation("", "Ordinary TTS", "", 2.0, 10)
        first_yield = next(gen)
        self.assertIsNone(first_yield[0])
        self.assertIn("cannot be empty", first_yield[1])

        # Cancel when no active job
        msg = cancel_current_generation()
        self.assertIn("No active job", msg)

    def test_10_longform_ui_controls(self):
        from app.ui.tts_tab import analyze_longform_chunks, run_longform_synthesis
        # Test chunk preview
        preview = analyze_longform_chunks("Sentence one. Sentence two.")
        self.assertIn("Chunk Plan", preview)
        self.assertIn("Chunks Total", preview)

        # Empty preview test
        empty_preview = analyze_longform_chunks("")
        self.assertIn("Enter long text", empty_preview)

        # Empty text synthesis error test
        gen = run_longform_synthesis("Test Title", "", "Ordinary TTS", "", 2.0, 10)
        res = next(gen)
        self.assertIsNone(res[0])
        self.assertIn("cannot be empty", res[2])

    def test_11_mastering_tab_ui_controls(self):
        from app.ui.mastering_tab import (
            create_mastering_tab,
            get_audio_source_choices,
            get_mastering_history_rows,
            inspect_source_audio,
            run_mastering_process
        )
        self.assertTrue(callable(create_mastering_tab))

        # Check source choices
        choices = get_audio_source_choices()
        self.assertIsInstance(choices, list)
        self.assertGreater(len(choices), 0)

        # Check history rows
        rows = get_mastering_history_rows()
        self.assertIsInstance(rows, list)
        if rows:
            self.assertEqual(len(rows[0]), 9)

        # Check inspection with invalid / empty
        html, path = inspect_source_audio("", None)
        self.assertIn("Select an audio file", html)
        self.assertIsNone(path)

        # Check inspection on real file if available
        real_file = None
        for c in choices:
            if c[1] and Path(c[1]).exists():
                real_file = c[1]
                break

        if real_file:
            html, path = inspect_source_audio(real_file, None)
            self.assertIn("Acoustic Inspection Report", html)
            self.assertIn("Loudness (LUFS)", html)
            self.assertEqual(path, real_file)

        # Test empty input error in mastering process
        res = run_mastering_process(
            "", None, "podcast", -16.0, -1.5, True, True, True, True, True
        )
        self.assertIn("Please select a generated audio file", res[0])

    def test_12_settings_and_backup_ui_controls(self):
        from app.ui.settings_tab import (
            get_voice_choices,
            get_backup_table_rows,
            get_backup_choices,
            handle_save_preferences,
            handle_create_db_backup,
            handle_create_full_backup,
            handle_restore_backup,
            handle_open_folder
        )

        # Voice choices
        voices = get_voice_choices()
        self.assertIsInstance(voices, list)
        self.assertGreaterEqual(len(voices), 1)

        # Save preferences
        msg = handle_save_preferences("km", "", "dark", "wav", True, False)
        self.assertIn("Preferences saved", msg)

        # Folder opening
        res = handle_open_folder("generated")
        self.assertIn("generated", res.lower())

        # Backup creation via UI handlers
        msg_db, rows_db, drop_db = handle_create_db_backup()
        self.assertIn("Database backup created", msg_db)
        self.assertGreater(len(rows_db), 0)

        msg_full, rows_full, drop_full = handle_create_full_backup()
        self.assertIn("Full Studio Archive created", msg_full)
        self.assertGreater(len(rows_full), 0)

        # Unconfirmed restore attempt
        choices = get_backup_choices()
        self.assertGreater(len(choices), 0)
        res_unconfirmed, _ = handle_restore_backup(choices[0][1], False)
        self.assertIn("Confirmation required", res_unconfirmed)

if __name__ == "__main__":
    unittest.main()
