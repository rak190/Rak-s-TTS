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

    def test_01_http_server_and_config(self):
        url = f"http://{SERVER_HOST}:{SERVER_PORT}/config"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("VoiceStudio AI", data.get("title", ""))
            
            # Verify components
            components = data.get("components", [])
            self.assertGreater(len(components), 50, "Expected at least 50 UI components")
            
            # Check tabs exist in layout
            component_types = [c.get("type") for c in components]
            self.assertIn("tabitem", component_types)
            self.assertIn("textbox", component_types)
            self.assertIn("audio", component_types)
            self.assertIn("button", component_types)
            self.assertIn("slider", component_types)

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
        self.assertIn("Upload audio first", msg)

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

if __name__ == "__main__":
    unittest.main()
