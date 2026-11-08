"""Unit tests for Windows desktop launcher pre-flight port checks and instance detection."""
import socket
import unittest
from unittest.mock import patch, MagicMock

from app.main import check_port_and_existing_instance


class TestDesktopLauncher(unittest.TestCase):
    """Verifies pre-flight instance detection and port conflict diagnostics."""

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
        # Simulate active VoiceStudio AI response
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html><title>VoiceStudio AI - Studio Edition</title></html>"
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


if __name__ == "__main__":
    unittest.main()
