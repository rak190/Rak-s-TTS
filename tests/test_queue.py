"""Automated unit tests for asynchronous generation queue."""
import time
import tempfile
import unittest
from pathlib import Path

from app.database.connection import DatabaseManager
from app.queue.generation_queue import GenerationQueue, GenerationTask

class TestGenerationQueue(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "queue_test.db"
        self.db = DatabaseManager.get_instance(self.db_path)
        self.queue = GenerationQueue(db_manager=self.db)

    def tearDown(self):
        self.queue.shutdown()
        self.temp_dir.cleanup()

    def test_queue_task_submission(self):
        # Use lightweight mock executor without foreign key violations
        task = GenerationTask(
            job_id="test_job_001",
            job_type="tts",
            target_text="Testing submission",
            language="english",
            executor=lambda t: {"generation_time_sec": 0.05}
        )
        job = self.queue.submit_task(task)
        self.assertEqual(job.id, "test_job_001")

        # Wait for worker to finish mock task
        time.sleep(0.3)
        updated_job = self.queue.get_job_status("test_job_001")
        self.assertEqual(updated_job.status, "completed")

    def test_queue_cancellation(self):
        # Simulate a longer task to test in-flight cancellation
        def slow_executor(t):
            for _ in range(10):
                if t.cancel_event.is_set():
                    return {}
                time.sleep(0.1)
            return {}

        task = GenerationTask(
            job_id="test_job_cancel",
            job_type="tts",
            target_text="To be cancelled",
            language="english",
            executor=slow_executor
        )
        self.queue.submit_task(task)
        time.sleep(0.05)  # Ensure worker picks it up
        cancelled = self.queue.cancel_job("test_job_cancel")
        self.assertTrue(cancelled)

        time.sleep(0.2)
        job = self.queue.get_job_status("test_job_cancel")
        self.assertEqual(job.status, "cancelled")

    def test_queue_stats(self):
        stats = self.queue.get_queue_stats()
        self.assertIn("queue_depth", stats)
        self.assertIn("is_processing", stats)

if __name__ == "__main__":
    unittest.main()
