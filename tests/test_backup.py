"""
Unit tests for DatabaseBackupService (Stage 5A).
"""
import sys
import unittest
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.backup import DatabaseBackupService, BACKUP_DIR
from app.config import DB_PATH

class TestDatabaseBackupService(unittest.TestCase):

    def test_01_create_backup(self):
        """Verifies creating an atomic verified backup snapshot."""
        ok, msg, path = DatabaseBackupService.create_backup("test_audit_backup")
        self.assertTrue(ok, f"Backup creation failed: {msg}")
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1024)

    def test_02_list_backups(self):
        """Verifies listing backups."""
        backups = DatabaseBackupService.list_backups()
        self.assertIsInstance(backups, list)
        self.assertGreaterEqual(len(backups), 1)
        names = [b["filename"] for b in backups]
        self.assertIn("test_audit_backup.db", names)

    def test_03_restore_backup(self):
        """Verifies safe database restoration."""
        backup_path = BACKUP_DIR / "test_audit_backup.db"
        ok, msg = DatabaseBackupService.restore_backup(backup_path)
        self.assertTrue(ok, f"Restore failed: {msg}")
        self.assertTrue(DB_PATH.exists())

        # Cleanup test backup
        if backup_path.exists():
            backup_path.unlink()

if __name__ == "__main__":
    unittest.main()
