"""Unit tests for SettingsService and user preferences persistence."""
import unittest
from app.services.settings_service import SettingsService, DEFAULT_SETTINGS
from app.database.connection import DatabaseManager


class TestSettingsService(unittest.TestCase):
    """Verifies settings CRUD, defaults, and folder opening aliases."""

    def setUp(self):
        self.svc = SettingsService()

    def test_01_default_settings_initialized(self):
        prefs = self.svc.get_all_preferences()
        self.assertIn("default_language", prefs)
        self.assertIn("theme", prefs)
        self.assertIn("default_audio_format", prefs)
        self.assertIn("auto_open_browser", prefs)
        self.assertIn("preload_model", prefs)

    def test_02_save_and_retrieve_preferences(self):
        ok, msg = self.svc.save_preferences(
            default_language="km",
            default_voice="Integration Test Voice",
            theme="dark",
            default_audio_format="mp3",
            auto_open_browser=False,
            preload_model=True
        )
        self.assertTrue(ok)
        self.assertIn("saved successfully", msg)

        # Verify values in database
        self.assertEqual(self.svc.get_setting("default_language"), "km")
        self.assertEqual(self.svc.get_setting("default_voice"), "Integration Test Voice")
        self.assertEqual(self.svc.get_setting("theme"), "dark")
        self.assertEqual(self.svc.get_setting("default_audio_format"), "mp3")
        self.assertEqual(self.svc.get_setting("auto_open_browser"), "false")
        self.assertEqual(self.svc.get_setting("preload_model"), "true")

        # Reset back to defaults for clean state
        self.svc.save_preferences(
            default_language="multilingual",
            default_voice="",
            theme="system",
            default_audio_format="wav",
            auto_open_browser=True,
            preload_model=False
        )

    def test_03_folder_aliases_validation(self):
        ok_gen, _ = SettingsService.open_system_folder("generated")
        self.assertTrue(ok_gen)

        ok_bad, msg_bad = SettingsService.open_system_folder("invalid_folder_name")
        self.assertFalse(ok_bad)
        self.assertIn("Unknown folder alias", msg_bad)


if __name__ == "__main__":
    unittest.main()
