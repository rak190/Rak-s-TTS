"""Automated unit tests for ModelManager singleton and thread limits."""
import unittest
import torch
from app.engines.model_manager import ModelManager
from app.config import DEFAULT_CPU_THREADS

class TestModelManager(unittest.TestCase):
    def test_singleton_instance(self):
        mgr1 = ModelManager.get_instance()
        mgr2 = ModelManager.get_instance()
        self.assertIs(mgr1, mgr2, "ModelManager must be a singleton")

    def test_thread_limit_configuration(self):
        mgr = ModelManager.get_instance()
        mgr._configure_cpu_environment()
        current_threads = torch.get_num_threads()
        self.assertEqual(
            current_threads,
            DEFAULT_CPU_THREADS,
            f"PyTorch CPU threads ({current_threads}) must match DEFAULT_CPU_THREADS ({DEFAULT_CPU_THREADS})"
        )

    def test_status_reporting(self):
        mgr = ModelManager.get_instance()
        status = mgr.get_status()
        self.assertIn("is_loaded", status)
        self.assertIn("process_rss_mb", status)
        self.assertIn("system_available_gb", status)
        self.assertIn("sample_rate_hz", status)
        self.assertIsInstance(status["process_rss_mb"], float)

if __name__ == "__main__":
    unittest.main()
