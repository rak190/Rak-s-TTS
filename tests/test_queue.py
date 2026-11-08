"""Automated unit tests for asynchronous generation queue."""
import time
import threading
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

    def test_queue_position_and_display_badges(self):
        # Block worker with a running task
        block_event = threading.Event()
        running_task = GenerationTask(
            job_id="test_running",
            job_type="tts",
            target_text="running",
            executor=lambda t: (block_event.wait(timeout=2.0), {"generation_time_sec": 0.1})[1]
        )
        self.queue.submit_task(running_task)
        time.sleep(0.05) # ensure running

        # Submit two pending tasks
        task_p1 = GenerationTask(job_id="test_p1", job_type="tts", target_text="p1")
        task_p2 = GenerationTask(job_id="test_p2", job_type="tts", target_text="p2")
        self.queue.submit_task(task_p1)
        self.queue.submit_task(task_p2)

        # Check positions
        pos1 = self.queue.get_job_position("test_p1")
        pos2 = self.queue.get_job_position("test_p2")
        self.assertIsNotNone(pos1)
        self.assertIsNotNone(pos2)
        self.assertEqual(pos1[0], 1) # 1st in pending queue
        self.assertEqual(pos2[0], 2) # 2nd in pending queue
        self.assertEqual(pos1[1], 2) # 2 total pending

        # Check display badges
        disp_running = self.queue.get_job_display_status("test_running")
        disp_p1 = self.queue.get_job_display_status("test_p1")
        self.assertEqual(disp_running["status"], "processing")
        self.assertIn("⚙️ Processing", disp_running["badge"])
        self.assertEqual(disp_p1["status"], "pending")
        self.assertIn("Position 1 of 2", disp_p1["badge"])

        # Test pending job cancellation
        cancelled = self.queue.cancel_job("test_p2")
        self.assertTrue(cancelled)
        disp_p2 = self.queue.get_job_display_status("test_p2")
        self.assertEqual(disp_p2["status"], "cancelled")
        self.assertIn("🚫 Cancelled", disp_p2["badge"])

        # Unblock worker
        block_event.set()
        time.sleep(0.2)

if __name__ == "__main__":
    unittest.main()
