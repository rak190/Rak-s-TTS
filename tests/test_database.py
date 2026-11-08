"""Automated unit tests for SQLite database layer."""
import os
import tempfile
import unittest
from pathlib import Path

from app.database.connection import DatabaseManager
from app.database.models import VoiceProfile, GenerationRecord, QueueJob

class TestDatabaseLayer(unittest.TestCase):
    def setUp(self):
        # Create isolated temporary database
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = DatabaseManager.get_instance(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_initialization(self):
        """Verifies schema tables and versioning are properly initialized."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            expected = {"schema_version", "voice_profiles", "generations", "jobs", "settings"}
            self.assertTrue(expected.issubset(tables), f"Missing tables: {expected - tables}")

    def test_voice_profile_crud(self):
        """Verifies creating, retrieving, updating, and deleting voice profiles."""
        prof = VoiceProfile(
            id="prof_test_01",
            name="Sokha Narrator",
            description="Test Khmer voice profile",
            language="khmer",
            original_audio_path="/fake/orig.wav",
            reference_segment_path="/fake/ref.wav",
            transcript="សួស្តីពិភពលោក",
            duration_sec=15.5,
            sample_rate=48000
        )
        # Create
        created = self.db.create_voice_profile(prof)
        self.assertEqual(created.id, "prof_test_01")

        # Retrieve by ID
        fetched = self.db.get_voice_profile("prof_test_01")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Sokha Narrator")
        self.assertEqual(fetched.transcript, "សួស្តីពិភពលោក")

        # Retrieve by Name
        fetched_name = self.db.get_voice_profile_by_name("Sokha Narrator")
        self.assertIsNotNone(fetched_name)
        self.assertEqual(fetched_name.id, "prof_test_01")

        # Update
        fetched.description = "Updated description"
        ok = self.db.update_voice_profile(fetched)
        self.assertTrue(ok)
        updated = self.db.get_voice_profile("prof_test_01")
        self.assertEqual(updated.description, "Updated description")

        # Delete
        del_ok = self.db.delete_voice_profile("prof_test_01")
        self.assertTrue(del_ok)
        self.assertIsNone(self.db.get_voice_profile("prof_test_01"))

    def test_generation_records(self):
        """Verifies recording and listing speech generations."""
        record = GenerationRecord(
            id="gen_test_01",
            voice_profile_id=None,
            voice_name="Default Voice",
            target_text="Hello world test",
            mode="tts",
            language="english",
            output_audio_path="/fake/out.wav",
            duration_sec=3.5,
            generation_time_sec=75.0,
            rtf=21.4,
            sample_rate=48000,
            status="completed"
        )
        self.db.create_generation(record)
        gens = self.db.list_generations()
        self.assertEqual(len(gens), 1)
        self.assertEqual(gens[0].id, "gen_test_01")
        self.assertEqual(gens[0].rtf, 21.4)

    def test_job_queue_tracking(self):
        """Verifies job status tracking and transitions in database."""
        job = QueueJob(
            id="job_test_01",
            job_type="tts",
            status="pending",
            progress=0.0
        )
        self.db.create_job(job)

        fetched = self.db.get_job("job_test_01")
        self.assertEqual(fetched.status, "pending")

        fetched.status = "processing"
        fetched.progress = 0.5
        self.db.update_job(fetched)

        updated = self.db.get_job("job_test_01")
        self.assertEqual(updated.status, "processing")
        self.assertEqual(updated.progress, 0.5)

if __name__ == "__main__":
    unittest.main()
