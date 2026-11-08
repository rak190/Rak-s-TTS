"""
Database backup and restore service for VoiceStudio AI (Stage 5A).
Provides atomic SQLite snapshots using native backup API and safe recovery.
"""
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import DB_PATH, STORAGE_DIR

logger = logging.getLogger(__name__)

BACKUP_DIR = STORAGE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

class DatabaseBackupService:
    """Manages atomic backups and verification of VoiceStudio AI SQLite databases."""

    @staticmethod
    def create_backup(custom_name: Optional[str] = None) -> Tuple[bool, str, Optional[Path]]:
        """
        Creates an atomic backup snapshot of voicestudio.db using SQLite's
        online backup API, guaranteeing zero corruption even if writes are active.
        """
        if not DB_PATH.exists():
            return False, "Database file does not exist.", None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"voicestudio_backup_{timestamp}.db" if not custom_name else f"{custom_name}.db"
        dest_path = BACKUP_DIR / backup_filename

        try:
            # Source connection
            src_conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
            # Destination connection
            dest_conn = sqlite3.connect(str(dest_path))
            
            with dest_conn:
                src_conn.backup(dest_conn)
            
            dest_conn.close()
            src_conn.close()

            # Verify backup integrity
            verify_conn = sqlite3.connect(str(dest_path))
            cur = verify_conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            status = cur.fetchone()[0]
            verify_conn.close()

            if status != "ok":
                if dest_path.exists():
                    dest_path.unlink()
                return False, f"Integrity check failed on backup: {status}", None

            logger.info(f"Database backup created successfully: {dest_path}")
            return True, "Backup created successfully.", dest_path

        except Exception as e:
            logger.error(f"Backup failed: {e}", exc_info=True)
            return False, str(e), None

    @staticmethod
    def list_backups() -> List[Dict]:
        """Lists available backup files sorted by creation date."""
        if not BACKUP_DIR.exists():
            return []
        
        backups = []
        for p in BACKUP_DIR.glob("*.db"):
            backups.append({
                "filename": p.name,
                "path": str(p),
                "size_kb": round(p.stat().st_size / 1024, 2),
                "created_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
            })
        return sorted(backups, key=lambda x: x["created_at"], reverse=True)

    @staticmethod
    def restore_backup(backup_path: str | Path) -> Tuple[bool, str]:
        """
        Restores database from a verified backup snapshot.
        Creates a safety snapshot of the existing database before restoration.
        """
        b_path = Path(backup_path)
        if not b_path.exists():
            return False, f"Backup file not found: {b_path}"

        # 1. Verify backup file integrity first
        try:
            check_conn = sqlite3.connect(str(b_path))
            cur = check_conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            res = cur.fetchone()[0]
            check_conn.close()
            if res != "ok":
                return False, f"Cannot restore corrupted backup: {res}"
        except Exception as e:
            return False, f"Failed to verify backup integrity: {e}"

        # 2. Safety snapshot of current database
        safety_path = BACKUP_DIR / f"pre_restore_safety_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
        if DB_PATH.exists():
            shutil.copy2(str(DB_PATH), str(safety_path))

        # 3. Perform restoration via atomic copy
        try:
            shutil.copy2(str(b_path), str(DB_PATH))
            logger.info(f"Database restored from {b_path}")
            return True, "Database restored successfully."
        except Exception as e:
            # Revert from safety snapshot
            if safety_path.exists():
                shutil.copy2(str(safety_path), str(DB_PATH))
            return False, f"Restore failed, reverted to safety snapshot: {e}"
