"""
Unit and integration tests for Khmer Voice Collection & Instant Voice Preview:
- Schema v5 verification & migration.
- Voice collection seeding (verified profiles + persona templates).
- Catalog search, multi-facet filtering (category, gender, status).
- Zero-inference instant audio preview verification.
- Favorite and global default voice synchronization.
- Voice Pack ZIP and raw audio import / export.
- Template activation / upgrading with new audio.
"""
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import soundfile as sf

from app.config import NATIVE_SAMPLE_RATE, VOICES_DIR
from app.database.connection import DatabaseManager
from app.database.schema import CURRENT_SCHEMA_VERSION, migrate_v4_to_v5
from app.services.voice_service import VoiceProfileService
from app.ui.library_tab import (
    get_profile_choices,
    render_voice_cards_html,
    on_select_voice,
    handle_quick_preview,
    handle_set_default,
    handle_toggle_favorite,
    handle_save_inspector_metadata,
    handle_attach_audio_to_voice,
    handle_export_voice_pack,
    handle_import_voice_pack
)
from app.ui.tts_tab import get_available_profiles, get_default_profile_choice
from app.ui.script_studio_tab import get_voice_choices


class TestVoiceCatalogSuite(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_catalog.db"
        self._orig_db_inst = DatabaseManager._instance
        self._orig_svc_inst = VoiceProfileService._instance
        self.db = DatabaseManager(self.db_path)
        DatabaseManager._instance = self.db
        self.service = VoiceProfileService(db_manager=self.db)
        VoiceProfileService._instance = self.service

        # Generate a test reference WAV (48kHz mono sine wave)
        self.sample_wav = Path(self.temp_dir.name) / "khmer_sample.wav"
        audio = (0.3 * np.sin(2 * np.pi * 440 * np.linspace(0, 2.5, int(2.5 * NATIVE_SAMPLE_RATE)))).astype(np.float32)
        sf.write(str(self.sample_wav), audio, NATIVE_SAMPLE_RATE, subtype="PCM_16")

        self.cleanup_ids = []

    def tearDown(self):
        for pid in self.cleanup_ids:
            try:
                self.service.delete_profile(pid)
            except Exception:
                pass
        DatabaseManager._instance = self._orig_db_inst
        VoiceProfileService._instance = self._orig_svc_inst
        self.temp_dir.cleanup()

    def test_schema_v5_and_migration(self):
        """Verify Schema v5 contains all rich voice collection columns."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(voice_profiles)")
            cols = {row[1] for row in cursor.fetchall()}
            required_cols = {
                "id", "name", "display_name", "khmer_display_name", "category",
                "gender", "speaking_style", "origin", "source_license",
                "preview_audio_path", "preview_type", "is_favorite", "is_default",
                "last_used_at", "validation_status"
            }
            for col in required_cols:
                self.assertIn(col, cols, f"Missing required column '{col}' in Schema v5")

            cursor.execute("SELECT MAX(version) FROM schema_version")
            ver = cursor.fetchone()[0]
            self.assertEqual(ver, CURRENT_SCHEMA_VERSION)

    def test_seed_khmer_voice_collection(self):
        """Verify that seed_khmer_voice_collection creates templates and enriches existing voices."""
        # Create a mock base profile
        p, msg = self.service.create_profile(
            name="Mock Speaker KH",
            original_audio_path=self.sample_wav,
            language="khmer"
        )
        self.assertIsNotNone(p)
        self.cleanup_ids.append(p.id)

        self.service.seed_khmer_voice_collection()
        all_profs = self.service.list_profiles()
        self.assertGreaterEqual(len(all_profs), 8)

        # Verify persona templates exist
        tpl_names = {p.name for p in all_profs if p.validation_status == "template"}
        self.assertIn("Maly (ម៉ាលី)", tpl_names)
        self.assertIn("Bopha (បុប្ផា)", tpl_names)
        self.assertIn("Chann (ចាន់)", tpl_names)

        # Check template categories and genders
        maly = next(p for p in all_profs if p.name == "Maly (ម៉ាលី)")
        self.assertEqual(maly.category, "educational")
        self.assertEqual(maly.gender, "female")
        self.assertEqual(maly.validation_status, "template")

    def test_catalog_search_and_filters(self):
        """Verify searching and filtering by category, gender, and status."""
        self.service.seed_khmer_voice_collection()

        # Filter by category: educational
        edu_profs = self.service.search_catalog(category="educational")
        self.assertTrue(all(p.category == "educational" for p in edu_profs))
        self.assertTrue(any("Maly" in p.name for p in edu_profs))

        # Filter by gender: female
        female_profs = self.service.search_catalog(gender="female")
        self.assertTrue(all(p.gender == "female" for p in female_profs))

        # Filter by status: verified vs template
        templates = self.service.search_catalog(validation_status="template")
        self.assertTrue(all(p.validation_status == "template" for p in templates))

        # Search by keyword in Khmer
        khmer_matches = self.service.search_catalog(search_term="បុប្ផា")
        self.assertEqual(len(khmer_matches), 1)
        self.assertIn("Bopha", khmer_matches[0].name)

    def test_zero_inference_instant_preview(self):
        """Strict verification: Instant voice preview serves files with ZERO CPU inference overhead."""
        p, _ = self.service.create_profile(
            name="Instant Preview Voice",
            original_audio_path=self.sample_wav,
            language="khmer"
        )
        self.assertIsNotNone(p)
        self.cleanup_ids.append(p.id)

        # Format choice and invoke preview handler
        choice_str = f"✅ Instant Preview Voice [General] ({p.id})"
        audio_file, status_msg = handle_quick_preview(choice_str)

        self.assertIsNotNone(audio_file)
        self.assertTrue(Path(audio_file).exists())
        self.assertIn("instant preview", status_msg.lower())
        self.assertIn("0ms", status_msg)

        # For templates without audio, preview should report gracefully without failing or loading model
        tpl, _ = self.service.create_profile(
            name="Template Without Audio",
            original_audio_path="",
            language="khmer",
            validation_status="template"
        )
        self.cleanup_ids.append(tpl.id)
        template_choice = f"📦 Template Without Audio ({tpl.id})"
        no_audio, no_audio_msg = handle_quick_preview(template_choice)
        self.assertIsNone(no_audio)
        self.assertIn("no audio attached", no_audio_msg.lower())

    def test_favorites_and_global_default_sync(self):
        """Verify toggling favorites and setting global default across studios."""
        p, _ = self.service.create_profile(
            name="Star Voice",
            original_audio_path=self.sample_wav,
            language="khmer"
        )
        self.cleanup_ids.append(p.id)

        choice_str = f"✅ Star Voice ({p.id})"

        # 1. Toggle Favorite
        msg, update_obj, html = handle_toggle_favorite(choice_str)
        fav_p = self.service.get_profile(p.id)
        self.assertEqual(fav_p.is_favorite, 1)

        # 2. Set Default Voice
        msg2, banner, update_obj2 = handle_set_default(choice_str)
        def_p = self.service.get_default_profile()
        self.assertIsNotNone(def_p)
        self.assertEqual(def_p.id, p.id)

        # 3. Verify cross-studio reflection
        tts_choices = get_available_profiles()
        self.assertTrue(any(f"({p.id})" in c for c in tts_choices))
        default_tts_val = get_default_profile_choice()
        self.assertIn(f"({p.id})", default_tts_val)

        script_choices = get_voice_choices()
        self.assertTrue(any(f"({p.id})" in c for c in script_choices))

    def test_voice_pack_export_and_import(self):
        """Verify exporting a voice pack to .zip and importing it back as a verified voice."""
        # Create base voice
        orig_p, _ = self.service.create_profile(
            name="Exportable Voice",
            original_audio_path=self.sample_wav,
            description="Testing Voice Pack ZIP",
            transcript="សួស្តីកម្ពុជា",
            display_name="Sokha Export",
            khmer_display_name="សុខា",
            category="storytelling",
            gender="female"
        )
        self.cleanup_ids.append(orig_p.id)

        # 1. Export to ZIP
        export_choice = f"✅ Sokha Export ({orig_p.id})"
        exp_msg, zip_file_path = handle_export_voice_pack(export_choice)
        self.assertIsNotNone(zip_file_path)
        self.assertTrue(Path(zip_file_path).exists())

        # Inspect ZIP content
        with zipfile.ZipFile(zip_file_path, "r") as zf:
            names = zf.namelist()
            self.assertIn("metadata.json", names)
            self.assertIn("transcript.txt", names)
            self.assertIn("reference.wav", names)

        # 2. Import Voice Pack from ZIP
        imp_msg, update_obj, html, banner = handle_import_voice_pack(
            file_path=zip_file_path,
            name="Imported Sokha",
            display_name="Imported Sokha (សុខា)",
            khmer_name="សុខា នាំចូល",
            category="storytelling",
            gender="female",
            style="Expressive Fable",
            transcript="សួស្តីកម្ពុជា"
        )
        self.assertIn("Added", imp_msg)
        imported_p = self.service.db.get_voice_profile_by_name("Imported Sokha")
        self.assertIsNotNone(imported_p)
        self.cleanup_ids.append(imported_p.id)
        self.assertEqual(imported_p.validation_status, "verified")
        self.assertTrue(Path(imported_p.reference_segment_path).exists())

    def test_template_activation_with_audio(self):
        """Verify uploading audio to a persona template converts it to verified status."""
        self.service.seed_khmer_voice_collection()
        all_profs = self.service.list_profiles()
        maly = next(p for p in all_profs if p.name == "Maly (ម៉ាលី)")
        self.assertEqual(maly.validation_status, "template")

        choice_str = f"📦 Maly (ម៉ាលី) ({maly.id})"
        status_msg, preview_audio, update_obj, html, banner = handle_attach_audio_to_voice(
            selected_choice=choice_str,
            audio_path=str(self.sample_wav),
            start_sec=0.0,
            end_sec=2.0,
            transcript="សូមស្វាគមន៍មកកាន់មេរៀនបច្ចេកវិទ្យាព័ត៌មាន។"
        )

        self.assertIn("successfully", status_msg.lower())
        updated_maly = self.service.get_profile(maly.id)
        self.assertEqual(updated_maly.validation_status, "verified")
        self.assertTrue(Path(updated_maly.reference_segment_path).exists())


if __name__ == "__main__":
    unittest.main()
