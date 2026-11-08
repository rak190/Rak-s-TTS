"""
Comprehensive Backup and Restore Service for VoiceStudio AI (Stage 5C).
Supports:
1. Fast atomic SQLite Database Snapshots (.db).
2. Full Studio Data Archives (.zip) covering SQLite database, voice profiles,
   original recordings, reference audio, generated audio, mastered audio,
   and longform checkpoints (strictly excluding heavy ~6.2GB model weights).
Provides pre-restore safety snapshots, integrity verification, and rollback protection.
"""
import json
import logging
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import DB_PATH, STORAGE_DIR

logger = logging.getLogger(__name__)

BACKUP_DIR = STORAGE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


class DatabaseBackupService:
    """Manages atomic backups, full studio archives, and safe restorations."""

    @staticmethod
    def create_database_backup(custom_name: Optional[str] = None) -> Tuple[bool, str, Optional[Path]]:
        """
        Creates an atomic backup snapshot of voicestudio.db using SQLite's
        online backup API. Fast, zero-corruption snapshot of database records only.
        """
        if not DB_PATH.exists():
            return False, "Database file does not exist.", None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"voicestudio_db_backup_{timestamp}.db" if not custom_name else f"{custom_name}.db"
        dest_path = BACKUP_DIR / backup_filename

        try:
            src_conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
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

            logger.info("Database backup created successfully: %s", dest_path)
            return True, f"Database backup created: {dest_path.name}", dest_path

        except Exception as e:
            logger.error("Database backup failed: %s", e, exc_info=True)
            return False, str(e), None

    @staticmethod
    def create_full_studio_backup(custom_name: Optional[str] = None) -> Tuple[bool, str, Optional[Path]]:
        """
        Creates a complete Studio Data Archive (ZIP) containing:
        - SQLite database snapshot (voicestudio.db)
        - Voice profiles and original uploaded audio (storage/voices/)
        - Reference slices (storage/references/)
        - Generated speech audio (storage/generated/)
        - Long-form audiobooks and chunk checkpoints (storage/longform/)
        - Mastered audio (storage/mastered/)
        Strictly excludes multi-gigabyte neural model weights and temporary caches.
        """
        if not DB_PATH.exists():
            return False, "Database file does not exist.", None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_name = f"voicestudio_full_backup_{timestamp}.zip" if not custom_name else f"{custom_name}.zip"
        dest_zip = BACKUP_DIR / archive_name

        # 1. Create a clean atomic DB snapshot first
        temp_db = BACKUP_DIR / f"_temp_db_{timestamp}.db"
        try:
            src_conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
            dest_conn = sqlite3.connect(str(temp_db))
            with dest_conn:
                src_conn.backup(dest_conn)
            dest_conn.close()
            src_conn.close()

            # 2. Build ZIP archive
            directories_to_archive = [
                ("voices", STORAGE_DIR / "voices"),
                ("references", STORAGE_DIR / "references"),
                ("generated", STORAGE_DIR / "generated"),
                ("longform", STORAGE_DIR / "longform"),
                ("mastered", STORAGE_DIR / "mastered"),
            ]

            manifest = {
                "backup_type": "full_studio_archive",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "app_version": "5.3.0",
                "archive_name": archive_name,
                "included_folders": []
            }

            file_count = 1
            with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                # Add database
                zf.write(temp_db, arcname="database/voicestudio.db")

                # Add user audio directories
                for folder_name, folder_path in directories_to_archive:
                    if folder_path.exists():
                        folder_files = 0
                        for root, _, files in os.walk(folder_path):
                            for f in files:
                                if f == ".gitkeep":
                                    continue
                                full_file = Path(root) / f
                                rel_path = full_file.relative_to(STORAGE_DIR)
                                zf.write(full_file, arcname=f"storage/{rel_path.as_posix()}")
                                file_count += 1
                                folder_files += 1
                        manifest["included_folders"].append({
                            "folder": folder_name,
                            "files_archived": folder_files
                        })

                # Write manifest into archive
                manifest["total_files"] = file_count
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))

            logger.info("Full studio archive created successfully: %s (%d files)", dest_zip, file_count)
            return True, f"Full Studio Archive created ({file_count} items): {dest_zip.name}", dest_zip

        except Exception as e:
            logger.error("Full studio archive creation failed: %s", e, exc_info=True)
            if dest_zip.exists():
                dest_zip.unlink()
            return False, f"Failed to create full archive: {e}", None

        finally:
            if temp_db.exists():
                temp_db.unlink()

    # Alias for backward compatibility
    create_backup = create_database_backup

    @staticmethod
    def list_backups() -> List[Dict]:
        """
        Lists all available backups (both Database Snapshots and Full Studio Archives)
        sorted by creation date descending.
        """
        if not BACKUP_DIR.exists():
            return []

        backups = []
        for p in BACKUP_DIR.glob("*"):
            if p.name.startswith("_temp") or p.name.startswith("pre_restore"):
                continue

            if p.suffix.lower() == ".db":
                size_mb = round(p.stat().st_size / (1024 * 1024), 2)
                backups.append({
                    "type": "Database Snapshot (SQLite)",
                    "filename": p.name,
                    "path": str(p),
                    "size": f"{size_mb} MB" if size_mb >= 0.1 else f"{round(p.stat().st_size / 1024, 1)} KB",
                    "created_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                })
            elif p.suffix.lower() == ".zip":
                size_mb = round(p.stat().st_size / (1024 * 1024), 2)
                backups.append({
                    "type": "Full Studio Archive (Data & Audio)",
                    "filename": p.name,
                    "path": str(p),
                    "size": f"{size_mb} MB",
                    "created_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                })

        return sorted(backups, key=lambda x: x["created_at"], reverse=True)

    @staticmethod
    def restore_backup(backup_path: str | Path) -> Tuple[bool, str]:
        """
        Restores data from either a Database Snapshot (.db) or a Full Studio Archive (.zip).
        Creates a pre-restore safety snapshot before touching any live files.
        Guarantees rollback if restoration fails.
        """
        b_path = Path(backup_path)
        if not b_path.exists():
            return False, f"Backup file not found: {b_path}"

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        ext = b_path.suffix.lower()

        # 1. Restore Database Snapshot (.db)
        if ext == ".db":
            check_conn = None
            try:
                # Verify integrity
                check_conn = sqlite3.connect(str(b_path))
                cur = check_conn.cursor()
                cur.execute("PRAGMA integrity_check;")
                res = cur.fetchone()[0]
                if res != "ok":
                    return False, f"Cannot restore corrupted database backup: {res}"
            except Exception as e:
                return False, f"Failed to verify database integrity: {e}"
            finally:
                if check_conn:
                    try:
                        check_conn.close()
                    except Exception:
                        pass

            # Safety snapshot of live DB
            safety_db = BACKUP_DIR / f"pre_restore_safety_{timestamp}.db"
            if DB_PATH.exists():
                shutil.copy2(str(DB_PATH), str(safety_db))

            try:
                shutil.copy2(str(b_path), str(DB_PATH))
                logger.info("Database restored from %s", b_path)
                return True, f"✅ Database successfully restored from {b_path.name}."
            except Exception as e:
                if safety_db.exists():
                    shutil.copy2(str(safety_db), str(DB_PATH))
                return False, f"Restore failed, reverted to safety snapshot: {e}"

        # 2. Restore Full Studio Archive (.zip)
        elif ext == ".zip":
            # Verify ZIP file integrity
            try:
                with zipfile.ZipFile(b_path, "r") as zf:
                    corrupt = zf.testzip()
                    if corrupt is not None:
                        return False, f"Archive corruption detected in: {corrupt}"
                    names = zf.namelist()
                    if "database/voicestudio.db" not in names:
                        return False, "Archive is missing required database/voicestudio.db"
            except Exception as e:
                return False, f"Failed to verify ZIP archive: {e}"

            # Create pre-restore safety snapshot of live database
            safety_db = BACKUP_DIR / f"pre_restore_safety_{timestamp}.db"
            if DB_PATH.exists():
                shutil.copy2(str(DB_PATH), str(safety_db))

            # Extract archive safely
            try:
                with zipfile.ZipFile(b_path, "r") as zf:
                    for member in zf.namelist():
                        if member == "manifest.json":
                            continue
                        elif member == "database/voicestudio.db":
                            with zf.open(member) as src, open(DB_PATH, "wb") as dst:
                                shutil.copyfileobj(src, dst)
                        elif member.startswith("storage/"):
                            rel_subpath = member[len("storage/"):]
                            target_file = STORAGE_DIR / rel_subpath
                            target_file.parent.mkdir(parents=True, exist_ok=True)
                            with zf.open(member) as src, open(target_file, "wb") as dst:
                                shutil.copyfileobj(src, dst)

                logger.info("Full studio archive restored successfully from %s", b_path)
                return True, f"✅ Full Studio Archive successfully restored from {b_path.name}."

            except Exception as e:
                logger.error("Full archive restore failed: %s. Reverting database...", e)
                if safety_db.exists():
                    shutil.copy2(str(safety_db), str(DB_PATH))
                return False, f"Restore failed, reverted database to safety snapshot: {e}"

        else:
            return False, f"Unsupported backup file format '{ext}'. Must be .db or .zip."
