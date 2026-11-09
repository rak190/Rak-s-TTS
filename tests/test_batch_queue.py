"""
Automated Unit and Integration Tests for Stage 5D:
Persistent Batch Queue, Crash Recovery, Pause/Resume, and Power Management.
All tests use deterministic Mock inference and execute in seconds without CPU model loading.
"""
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

from app.database.connection import DatabaseManager
from app.database.models import QueueJob, LongformJob, LongformChunkRecord
from app.queue.generation_queue import GenerationQueue, GenerationTask
from app.services.batch_service import BatchService
from app.services.longform_service import LongformService
from app.utils.power_manager import WindowsPowerManager
from tests.mock_voxcpm_adapter import MockVoxCPM2Adapter

class TestBatchQueueAndRecovery(unittest.TestCase):
    def setUp(self):
        GenerationQueue.reset_instance()
        BatchService.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_batch.db"
        self.db = DatabaseManager.get_instance(self.db_path)
        self.mock_engine = MockVoxCPM2Adapter(delay_sec=0.01)

        # Create isolated GenerationQueue with test DB
        self.queue = GenerationQueue(db_manager=self.db)
        # Clear any existing in-memory tasks
        while not self.queue._task_queue.empty():
            try:
                self.queue._task_queue.get_nowait()
            except Exception:
                break

    def tearDown(self):
        self.queue.shutdown()
        GenerationQueue.reset_instance()
        BatchService.reset_instance()
        self.temp_dir.cleanup()

    def test_01_schema_v4_properties(self):
        """Verifies Schema version 4 contains all required batch fields in SQLite."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(version) FROM schema_version")
            ver = cursor.fetchone()[0]
            self.assertGreaterEqual(ver, 4, "Database must be at least schema version 4.")

            cursor.execute("PRAGMA table_info(jobs)")
            cols = {row[1] for row in cursor.fetchall()}
            expected_cols = {
                "id", "job_type", "status", "progress", "title", "target_text",
                "voice_profile_id", "mode", "cfg_value", "inference_timesteps",
                "total_chunks", "completed_chunks", "output_wav_path",
                "output_mp3_path", "retry_count", "priority", "updated_at"
            }
            self.assertTrue(expected_cols.issubset(cols), f"Missing columns: {expected_cols - cols}")

    def test_02_fifo_batch_ordering(self):
        """Verifies multiple submitted jobs execute in strict FIFO sequence."""
        execution_order = []

        def make_executor(idx):
            def executor(task: GenerationTask):
                execution_order.append(idx)
                time.sleep(0.02)
                return {"status": "completed", "output_path": f"/fake/out_{idx}.wav", "duration_sec": 1.0}
            return executor

        task1 = GenerationTask(job_id="job_seq_01", title="Script 1", executor=make_executor(1))
        task2 = GenerationTask(job_id="job_seq_02", title="Script 2", executor=make_executor(2))
        task3 = GenerationTask(job_id="job_seq_03", title="Script 3", executor=make_executor(3))

        self.queue.submit_task(task1)
        self.queue.submit_task(task2)
        self.queue.submit_task(task3)

        # Wait for queue to drain
        timeout = time.time() + 5.0
        while time.time() < timeout and len(execution_order) < 3:
            time.sleep(0.05)

        self.assertEqual(execution_order, [1, 2, 3], "Jobs must execute in strict FIFO order.")

    def test_03_single_worker_concurrency(self):
        """Verifies that at no point do two jobs run simultaneously (concurrency = 1)."""
        running_concurrency = []
        max_seen = [0]

        def tracking_executor(task: GenerationTask):
            running_concurrency.append(1)
            cur = len(running_concurrency)
            if cur > max_seen[0]:
                max_seen[0] = cur
            time.sleep(0.03)
            running_concurrency.pop()
            return {"status": "completed", "output_path": "/fake/out.wav"}

        for i in range(4):
            t = GenerationTask(job_id=f"job_conc_{i}", title=f"Task {i}", executor=tracking_executor)
            self.queue.submit_task(t)

        timeout = time.time() + 5.0
        while time.time() < timeout:
            stats = self.queue.get_queue_stats()
            if stats["queue_depth"] == 0 and not stats["is_processing"]:
                break
            time.sleep(0.05)

        self.assertEqual(max_seen[0], 1, "Concurrency must strictly equal 1 at all times.")

    def test_04_cancel_pending_job(self):
        """Verifies a job sitting in pending queue can be safely cancelled."""
        slow_event = False

        def blocker(task):
            time.sleep(0.15)
            return {"status": "completed"}

        t_active = GenerationTask(job_id="job_active_blocker", title="Active", executor=blocker)
        t_pending = GenerationTask(job_id="job_to_cancel", title="Pending", executor=blocker)

        self.queue.submit_task(t_active)
        self.queue.submit_task(t_pending)

        # Cancel the pending job
        cancelled = self.queue.cancel_job("job_to_cancel")
        self.assertTrue(cancelled, "cancel_job should return True for pending job.")

        job_state = self.queue.get_job_status("job_to_cancel")
        self.assertEqual(job_state.status, "cancelled")

    def test_05_retry_failed_job(self):
        """Verifies failed jobs can be retried with retry limit enforcement."""
        # Pause queue first so the job stays in queued state for inspection
        self.queue.pause_queue()

        failed_job = QueueJob(
            id="job_retry_test",
            job_type="tts",
            status="failed",
            target_text="Valid test script for retry",
            error_message="Simulated failure",
            retry_count=0
        )
        self.db.create_job(failed_job)

        # First retry
        ok, msg = self.queue.retry_job("job_retry_test")
        self.assertTrue(ok)
        job = self.db.get_job("job_retry_test")
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.retry_count, 1)

        # Force retry count to max (3)
        job.retry_count = 3
        job.status = "failed"
        self.db.update_job(job)

        ok2, msg2 = self.queue.retry_job("job_retry_test")
        self.assertFalse(ok2, "Should reject retry when retry limit of 3 is reached.")
        self.assertIn("maximum retry limit", msg2)
        self.queue.resume_queue()

    def test_06_startup_recovery_interrupted_jobs(self):
        """Verifies that uncheckpointed processing jobs are marked 'interrupted' on startup."""
        interrupted_job = QueueJob(
            id="job_crash_sim",
            job_type="tts",
            status="processing",
            title="Crash Test",
            total_chunks=1,
            completed_chunks=0
        )
        self.db.create_job(interrupted_job)

        # Simulate fresh application startup
        self.queue.initialize_on_startup()

        rec = self.db.get_job("job_crash_sim")
        self.assertEqual(rec.status, "interrupted", "Unfinished processing jobs must be marked 'interrupted'.")
        self.assertIn("Interrupted", rec.status_message)

    def test_07_preflight_checks(self):
        """Verifies pre-flight check detects missing reference wav files."""
        bad_task = GenerationTask(
            job_id="job_bad_ref",
            job_type="cloning",
            mode="cloning",
            reference_wav_path="/non_existent/path/to/voice.wav"
        )
        ok, msg = self.queue.check_preflight_safety(bad_task)
        self.assertFalse(ok)
        self.assertIn("not found on disk", msg)

        good_task = GenerationTask(
            job_id="job_good_tts",
            job_type="tts",
            mode="tts"
        )
        ok2, msg2 = self.queue.check_preflight_safety(good_task)
        self.assertTrue(ok2)

    def test_08_windows_power_manager_lifecycle(self):
        """Verifies sleep inhibition and post-completion actions."""
        pm = WindowsPowerManager.get_instance()
        # Test notification action
        ok, msg = pm.execute_post_completion_action("notify")
        self.assertTrue(ok)

        # Test none action
        ok2, msg2 = pm.execute_post_completion_action("none")
        self.assertTrue(ok2)

        # Test sleep inhibition toggle
        if pm.is_windows:
            inhibited = pm.inhibit_sleep("Unit test batch")
            self.assertTrue(inhibited or not pm.is_windows)
            restored = pm.restore_sleep()
            self.assertTrue(restored or not pm.is_windows)

    def test_09_batch_service_integration(self):
        """Verifies high-level BatchService enqueuing and summaries."""
        self.queue.pause_queue()
        batch_svc = BatchService.get_instance()
        batch_svc.db = self.db
        batch_svc.queue = self.queue

        job_id, msg = batch_svc.submit_batch_item(
            title="Short Narration Test",
            text="សួស្តីពិភពលោក Hello world",
            mode="tts"
        )
        self.assertIsNotNone(job_id)
        self.assertIn("Queued", msg)

        summary = batch_svc.get_queue_summary()
        self.assertIsInstance(summary, dict)
        self.assertIn("queue_depth", summary)
        self.assertIn("is_processing", summary)
        self.queue.cancel_job(job_id)
        self.queue.resume_queue()

    def test_10_chunked_pause_and_checkpoint_resume(self):
        """Verifies pause-after-chunk halts cleanly and resume skips already completed chunks."""
        lf_service = LongformService(db_manager=self.db, tts_engine=self.mock_engine)
        # Prepare 3-chunk job
        job, err = lf_service.prepare_job(
            title="Pause Resume Test",
            text="First sentence here. Second sentence follows. Third sentence concludes.",
            target_chars=20,
            max_chars=35
        )
        self.assertIsNotNone(job)
        self.assertGreaterEqual(job.total_chunks, 2)

        # Simulate pause event requested right after chunk 0
        pause_evt = threading.Event()
        def on_prog(info):
            if info["chunk_index"] == 0:
                pause_evt.set()

        res = lf_service.execute_job(
            job_id=job.id,
            pause_event=pause_evt,
            on_progress=on_prog
        )
        self.assertEqual(res["status"], "paused")
        updated_job = self.db.get_longform_job(job.id)
        self.assertEqual(updated_job.status, "paused")
        self.assertGreaterEqual(updated_job.completed_chunks, 1)

        # Now resume the job without pause event
        res_resumed = lf_service.resume_job(job_id=job.id)
        self.assertEqual(res_resumed["status"], "completed")
        self.assertEqual(res_resumed["completed_chunks"], job.total_chunks)
        self.assertTrue(Path(res_resumed["output_wav_path"]).exists())

if __name__ == "__main__":
    unittest.main()
