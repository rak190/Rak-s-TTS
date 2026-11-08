"""
User preferences and application settings service.
Manages persistent configuration in SQLite, folder opening, and defaults.
"""
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.config import STORAGE_DIR
from app.database.connection import DatabaseManager

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS: Dict[str, str] = {
    "default_language": "multilingual",
    "default_voice": "",
    "theme": "system",
    "default_audio_format": "wav",
    "auto_open_browser": "true",
    "preload_model": "false",
    "output_folder": str(STORAGE_DIR / "generated"),
    "mastered_folder": str(STORAGE_DIR / "mastered"),
    "backup_folder": str(STORAGE_DIR / "backups")
}


class SettingsService:
    """Manages application-wide user configuration and desktop system shortcuts."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self._ensure_defaults()

    def _ensure_defaults(self):
        """Ensures default settings exist in SQLite without overwriting user values."""
        current = self.db.get_all_settings()
        for key, val in DEFAULT_SETTINGS.items():
            if key not in current:
                self.db.set_setting(key, val)

    def get_setting(self, key: str, default: Optional[str] = None) -> str:
        """Retrieves a single setting value."""
        fallback = default if default is not None else DEFAULT_SETTINGS.get(key, "")
        val = self.db.get_setting(key, default=fallback)
        return val if val is not None else fallback

    def set_setting(self, key: str, value: Any) -> bool:
        """Saves a single setting value."""
        return self.db.set_setting(key, str(value))

    def get_all_preferences(self) -> Dict[str, str]:
        """Returns all user preferences as a dictionary."""
        all_s = self.db.get_all_settings()
        merged = DEFAULT_SETTINGS.copy()
        merged.update(all_s)
        return merged

    def save_preferences(
        self,
        default_language: str,
        default_voice: str,
        theme: str,
        default_audio_format: str,
        auto_open_browser: bool,
        preload_model: bool
    ) -> Tuple[bool, str]:
        """Saves updated user preferences."""
        try:
            self.set_setting("default_language", default_language)
            self.set_setting("default_voice", default_voice)
            self.set_setting("theme", theme.lower())
            self.set_setting("default_audio_format", default_audio_format.lower())
            self.set_setting("auto_open_browser", "true" if auto_open_browser else "false")
            self.set_setting("preload_model", "true" if preload_model else "false")
            logger.info("User preferences saved successfully.")
            return True, "✅ Preferences saved successfully."
        except Exception as e:
            logger.error("Failed to save preferences: %s", e)
            return False, f"❌ Failed to save preferences: {e}"

    @staticmethod
    def open_system_folder(folder_name: str) -> Tuple[bool, str]:
        """
        Opens a storage folder in Windows File Explorer safely.
        Allowed folders: 'generated', 'mastered', 'voices', 'backups', 'longform'.
        """
        allowed = {
            "generated": STORAGE_DIR / "generated",
            "mastered": STORAGE_DIR / "mastered",
            "voices": STORAGE_DIR / "voices",
            "backups": STORAGE_DIR / "backups",
            "longform": STORAGE_DIR / "longform"
        }

        target = allowed.get(folder_name.lower().strip())
        if not target:
            return False, f"Unknown folder alias: {folder_name}"

        target.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(target))
            else:
                subprocess.Popen(["xdg-open", str(target)])
            return True, f"Opened folder: {target}"
        except Exception as e:
            logger.info("Could not launch explorer GUI directly (%s). Verified directory: %s", e, target)
            return True, f"Verified folder path: {target}"

