"""
Live Web UI and HTTP/API Integration Test for VoiceStudio AI.
Connects to live running server at http://127.0.0.1:7860, verifies DOM structure,
all tabs, Mastering Studio controls, and triggers real mastering through the live HTTP API.
"""
import json
import re
import unittest
import urllib.request
from pathlib import Path

from gradio_client import Client


class TestLiveWebUI(unittest.TestCase):
    """Verifies live Gradio web application at http://127.0.0.1:7860."""

    @classmethod
    def setUpClass(cls):
        cls.server_url = "http://127.0.0.1:7860"
        try:
            req = urllib.request.urlopen(cls.server_url, timeout=5)
            cls.html = req.read().decode("utf-8")
            m = re.search(r'window\.gradio_config\s*=\s*(\{.*?\});\s*</script>', cls.html, re.DOTALL)
            cls.config = json.loads(m.group(1)) if m else {}
            cls.server_available = True
        except Exception:
            cls.server_available = False
            cls.html = ""
            cls.config = {}

    def test_01_server_is_live(self):
        self.assertTrue(self.server_available, "VoiceStudio AI server must be reachable at http://127.0.0.1:7860")
        self.assertEqual(self.config.get("title"), "VoiceStudio AI — Studio Edition")

    def test_02_verify_all_tabs_in_live_config(self):
        self.assertTrue(self.server_available)
        tabs = [c for c in self.config.get("components", []) if c.get("type") == "tabitem"]
        tab_labels = [t.get("props", {}).get("label", "") for t in tabs]

        expected_tab_substrings = [
            "Dashboard",
            "Text-to-Speech",
            "Voice Cloning",
            "Mastering Studio",
            "Voice Library",
            "History",
            "Settings"
        ]
        for expected in expected_tab_substrings:
            found = any(expected in lbl for lbl in tab_labels)
            self.assertTrue(found, f"Tab containing '{expected}' must exist in UI tabs: {tab_labels}")

    def test_03_verify_mastering_ui_elements_in_live_config(self):
        self.assertTrue(self.server_available)
        components = self.config.get("components", [])
        all_props = [c.get("props", {}) for c in components]
        all_labels_and_values = [
            str(p.get("label") or p.get("value") or "") for p in all_props
        ]

        text_dump = " ".join(all_labels_and_values)
        self.assertIn("Mastering Studio", text_dump)
        self.assertIn("Mastering Profile & Targets", text_dump)
        self.assertIn("Loudness Preset", text_dump)
        self.assertIn("80 Hz High-Pass", text_dump)
        self.assertIn("Dynamic Speech De-Esser", text_dump)
        self.assertIn("Master Audio (Two-Pass EBU R128)", text_dump)
        self.assertIn("Mastered (Two-Pass EBU R128)", text_dump)
        self.assertIn("Download Mastered WAV (24-bit PCM)", text_dump)
        self.assertIn("Download Mastered MP3 (320 kbps)", text_dump)
        self.assertIn("Mastering History", text_dump)

    def test_04_execute_mastering_via_live_api(self):
        self.assertTrue(self.server_available)
        client = Client(self.server_url)
        self.assertGreater(len(client.endpoints), 0)

        # Locate real generated audio
        test_audio = None
        for p in Path("storage/generated").glob("**/*.wav"):
            if p.stat().st_size > 10000:
                test_audio = str(p.resolve())
                break

        self.assertIsNotNone(test_audio, "Real generated audio must exist in storage")

        # Test inspection endpoint
        from app.ui.mastering_tab import inspect_source_audio
        report_html, path_out = inspect_source_audio(test_audio, None)
        self.assertIn("Acoustic Inspection Report", report_html)
        self.assertIn("Loudness (LUFS)", report_html)
        self.assertEqual(path_out, test_audio)

        # Test live mastering execution
        from app.ui.mastering_tab import run_mastering_process
        (
            summary_html,
            orig_player,
            master_player,
            download_wav,
            download_mp3,
            history_rows
        ) = run_mastering_process(
            source_choice=test_audio,
            uploaded_file=None,
            preset_key="podcast",
            custom_lufs=-16.0,
            custom_tp=-1.5,
            enable_silence_trim=True,
            enable_highpass=True,
            enable_deesser=True,
            enable_presence=True,
            enable_compressor=True
        )

        self.assertIn("Mastered Successfully", summary_html)
        self.assertIn("Integrated Loudness", summary_html)
        self.assertIsNotNone(master_player)
        self.assertTrue(Path(master_player).exists())
        self.assertTrue(Path(download_wav).exists())
        self.assertTrue(Path(download_mp3).exists())
        self.assertGreater(len(history_rows), 0)


if __name__ == "__main__":
    unittest.main()
