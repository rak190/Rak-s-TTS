"""Unit and integration tests for DatabaseBackupService (Database Snapshot and Full Studio Archive)."""
import os
import sqlite3
import unittest
import zipfile
from pathlib import Path

from app.database.backup import DatabaseBackupService, BACKUP_DIR
from app.config import DB_PATH, STORAGE_DIR


class TestBackupExtended(unittest.TestCase):
    """Verifies atomic database snapshots, full studio archives, and safe restorations."""

    def test_01_create_database_snapshot(self):
        ok, msg, p = DatabaseBackupService.create_database_backup(custom_name="test_snapshot")
        self.assertTrue(ok)
        self.assertIsNotNone(p)
        self.assertTrue(p.exists())
        self.assertTrue(p.name.endswith(".db"))

        # Verify SQLite integrity
        conn = sqlite3.connect(str(p))
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()[0]
        conn.close()
        self.assertEqual(res, "ok")

    def test_02_create_full_studio_archive(self):
        ok, msg, p = DatabaseBackupService.create_full_studio_backup(custom_name="test_full_archive")
        self.assertTrue(ok)
        self.assertIsNotNone(p)
        self.assertTrue(p.exists())
        self.assertTrue(p.name.endswith(".zip"))

        # Inspect ZIP structure
        with zipfile.ZipFile(p, "r") as zf:
            names = zf.namelist()
            self.assertIn("database/voicestudio.db", names)
            self.assertIn("manifest.json", names)

            # Check that model weights are NOT in archive
            for n in names:
                self.assertFalse(n.startswith("models/"), f"Model weights must NOT be archived: {n}")
                self.assertFalse(n.endswith(".safetensors"))
                self.assertFalse(n.endswith(".pth"))

    def test_03_list_backups_metadata(self):
        backups = DatabaseBackupService.list_backups()
        self.assertIsInstance(backups, list)
        self.assertGreaterEqual(len(backups), 2)

        types = [b["type"] for b in backups]
        self.assertTrue(any("Database Snapshot" in t for t in types))
        self.assertTrue(any("Full Studio Archive" in t for t in types))

    def test_04_restore_database_snapshot_safety(self):
        # Locate the test snapshot
        target = BACKUP_DIR / "test_snapshot.db"
        self.assertTrue(target.exists())

        ok, msg = DatabaseBackupService.restore_backup(target)
        self.assertTrue(ok)
        self.assertIn("successfully restored", msg)

    def test_05_restore_full_archive_safety(self):
        target = BACKUP_DIR / "test_full_archive.zip"
        self.assertTrue(target.exists())

        ok, msg = DatabaseBackupService.restore_backup(target)
        self.assertTrue(ok)
        self.assertIn("successfully restored", msg)

    def test_06_corrupt_restore_rejected_safely(self):
        corrupt_file = BACKUP_DIR / "corrupt_test.db"
        corrupt_file.write_text("NOT A REAL SQLITE DATABASE FILE", encoding="utf-8")

        ok, msg = DatabaseBackupService.restore_backup(corrupt_file)
        self.assertFalse(ok)
        self.assertTrue("corrupt" in msg.lower() or "not a database" in msg.lower() or "failed to verify" in msg.lower())

        if corrupt_file.exists():
            corrupt_file.unlink()

    @classmethod
    def tearDownClass(cls):
        # Clean up test backups
        for name in ["test_snapshot.db", "test_full_archive.zip"]:
            p = BACKUP_DIR / name
            if p.exists():
                p.unlink()


if __name__ == "__main__":
    unittest.main()
