"""Unit tests for Windows desktop launcher pre-flight port checks, runner scripts, and shortcuts."""
import os
import socket
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config import BASE_DIR
from app.main import check_port_and_existing_instance


class TestDesktopLauncher(unittest.TestCase):
    """Verifies pre-flight instance detection, port conflict diagnostics, and launcher scripts."""

    def test_01_detects_free_port(self):
        # Bind and close an ephemeral port to ensure it's free
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]
        s.close()

        status, details = check_port_and_existing_instance("127.0.0.1", free_port)
        self.assertEqual(status, "free")
        self.assertIsNone(details)

    def test_02_detects_foreign_process_on_port(self):
        # Open a dummy non-VoiceStudio socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        busy_port = s.getsockname()[1]

        try:
            status, details = check_port_and_existing_instance("127.0.0.1", busy_port)
            self.assertEqual(status, "foreign")
            self.assertIsNotNone(details)
            self.assertTrue(len(details) > 0)
        finally:
            s.close()

    @patch("urllib.request.urlopen")
    def test_03_detects_running_voicestudio_instance(self, mock_urlopen):
        # Simulate active VoiceStudio response
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html><title>VoiceStudio Pro</title></html>"
        mock_urlopen.return_value = mock_resp

        # Open socket to simulate listening port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        vs_port = s.getsockname()[1]

        try:
            status, details = check_port_and_existing_instance("127.0.0.1", vs_port)
            self.assertEqual(status, "voicestudio")
            self.assertIn(str(vs_port), details)
        finally:
            s.close()

    def test_04_launcher_files_exist(self):
        """Verifies that all runner and desktop launcher files exist with valid contents."""
        run_bat = BASE_DIR / "run.bat"
        start_bat = BASE_DIR / "start.bat"
        run_silent_vbs = BASE_DIR / "run_silent.vbs"
        run_voicestudio_bat = BASE_DIR / "run_voicestudio.bat"
        create_shortcut_ps1 = BASE_DIR / "create_desktop_shortcut.ps1"
        studio_icon = BASE_DIR / "assets" / "voicestudio.ico"

        self.assertTrue(run_bat.exists(), "run.bat must exist in project root.")
        self.assertTrue(start_bat.exists(), "start.bat must exist in project root.")
        self.assertTrue(run_silent_vbs.exists(), "run_silent.vbs must exist in project root.")
        self.assertTrue(run_voicestudio_bat.exists(), "run_voicestudio.bat must exist in project root.")
        self.assertTrue(create_shortcut_ps1.exists(), "create_desktop_shortcut.ps1 must exist in project root.")
        self.assertTrue(studio_icon.exists(), "assets/voicestudio.ico must exist.")

        run_bat_content = run_bat.read_text(encoding="utf-8")
        self.assertIn("VOICESTUDIO PRO", run_bat_content)
        self.assertIn("choice /c 12345Q", run_bat_content)
        self.assertIn("--now", run_bat_content)
        self.assertIn("--fast", run_bat_content)

        vbs_content = run_silent_vbs.read_text(encoding="utf-8")
        self.assertIn("WScript.Shell", vbs_content)
        self.assertIn("app.main", vbs_content)

    def test_05_run_bat_help_command(self):
        """Verifies run.bat --help returns clean help output with exit code 0."""
        res = subprocess.run(
            ["cmd.exe", "/c", str(BASE_DIR / "run.bat"), "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(BASE_DIR),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("VoiceStudio Pro Launcher Commands", res.stdout)
        self.assertIn("--now", res.stdout)
        self.assertIn("--silent", res.stdout)

    def test_06_desktop_shortcut_script_execution(self):
        """Verifies create_desktop_shortcut.ps1 creates shortcuts without errors."""
        res = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(BASE_DIR / "create_desktop_shortcut.ps1"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(BASE_DIR),
        )
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        self.assertIn("VoiceStudio Pro", res.stdout)
        self.assertIn("Desktop Shortcut Created", res.stdout)


if __name__ == "__main__":
    unittest.main()
