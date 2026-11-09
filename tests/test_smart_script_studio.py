"""
Smart Script-to-Speech Studio Acceptance & Regression Test Suite.
Tests structured DOCX storyboard parsing (ICT_Grade8_AI_Animation_Video_Storyboard_KM.docx),
spoken vs. non-spoken separation, multi-speaker dialogue extraction, voice direction guardrails,
scene-based synthesis, checkpoint recovery, timeline duration comparison, and 7-format export
using deterministic MockVoxCPM2Adapter (zero heavy CPU inference).
"""
import csv
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from app.config import BASE_DIR
from app.database.connection import DatabaseManager
from app.database.models import VoiceProfile
from app.queue.generation_queue import GenerationQueue
from app.services.script_parser import (
    StoryboardParser,
    VoiceDirectionValidator,
)
from app.services.script_project_service import ScriptProjectService
from app.ui.script_studio_tab import (
    build_scene_ui_state,
    format_dialogue_blocks_md,
    format_production_metadata_md,
    format_timeline_comparison_table,
)
from tests.mock_voxcpm_adapter import MockVoxCPM2Adapter

FIXTURE_DOCX = BASE_DIR / "tests" / "fixtures" / "ICT_Grade8_AI_Animation_Video_Storyboard_KM.docx"


class TestSmartScriptStudio(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.db_path = self.temp_path / "test_smart_script.db"
        self.projects_dir = self.temp_path / "projects"
        self.imports_dir = self.temp_path / "imports"

        DatabaseManager.reset_instance()
        ScriptProjectService.reset_instance()
        GenerationQueue.reset_instance()

        self.db = DatabaseManager.get_instance(db_path=self.db_path)
        self.mock_engine = MockVoxCPM2Adapter(delay_sec=0.005, tone_duration_sec=0.20)
        self.service = ScriptProjectService(
            db_manager=self.db,
            tts_engine=self.mock_engine,
            projects_dir=self.projects_dir,
            imports_dir=self.imports_dir,
        )
        ScriptProjectService._instance = self.service

        # Create dummy reference WAV for voice profile tests
        self.dummy_ref_wav = self.temp_path / "ref_voice.wav"
        sr = 48000
        tone = 0.2 * np.sin(2 * np.pi * 300.0 * np.linspace(0, 0.5, sr // 2, dtype=np.float32))
        sf.write(str(self.dummy_ref_wav), tone, sr, subtype="PCM_16")

    def tearDown(self):
        try:
            q = GenerationQueue._instance
            if q is not None:
                q.shutdown()
        except Exception:
            pass
        GenerationQueue.reset_instance()
        ScriptProjectService.reset_instance()
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def test_01_grade8_docx_import_and_9_scenes_structure(self):
        """Verifies ICT_Grade8_AI_Animation_Video_Storyboard_KM.docx parses all 9 scenes and metadata."""
        self.assertTrue(FIXTURE_DOCX.exists(), f"Missing primary acceptance fixture: {FIXTURE_DOCX}")
        orig_bytes = FIXTURE_DOCX.read_bytes()

        project = self.service.import_document(FIXTURE_DOCX)

        # Ensure original source DOCX was never modified and safe copy exists
        self.assertEqual(FIXTURE_DOCX.read_bytes(), orig_bytes)
        self.assertTrue(Path(project.source_copy_path).exists())

        # Header & table metadata
        self.assertIn("ICT Grade 8", project.title)
        self.assertIn("បញ្ញាសិប្បនិម្មិត", project.topic)
        self.assertEqual(project.audience, "សិស្សថ្នាក់ទី៨")
        self.assertEqual(project.planned_duration_sec, 295.0)
        self.assertIn("16:9", project.aspect_ratio)

        # All 9 scenes recognized with exact timing windows
        self.assertEqual(len(project.scenes), 9)
        expected_windows = [
            ("00:00", "00:22", 22.0),
            ("00:22", "00:55", 33.0),
            ("00:55", "01:23", 28.0),
            ("01:23", "01:55", 32.0),
            ("01:55", "02:35", 40.0),
            ("02:35", "03:10", 35.0),
            ("03:10", "03:55", 45.0),
            ("03:55", "04:22", 27.0),
            ("04:22", "04:55", 33.0),
        ]
        for sc, (exp_start, exp_end, exp_dur) in zip(project.scenes, expected_windows):
            self.assertEqual(sc.target_start_time, exp_start)
            self.assertEqual(sc.target_end_time, exp_end)
            self.assertEqual(sc.target_duration_sec, exp_dur)

        # Pre-export checklist items parsed separately (6 items)
        self.assertEqual(len(project.checklist_items), 6)
        self.assertIn("VideoZero", project.production_footer_note)

    def test_02_strict_spoken_vs_production_direction_separation(self):
        """Ensures visual directions, keywords, music/SFX notes, timestamps, and checklists are excluded from speech."""
        project = self.service.import_document(FIXTURE_DOCX)

        forbidden_non_spoken_phrases = [
            "រូបភាព និងចលនា៖",
            "ពាក្យគន្លឹះ៖",
            "សំឡេង SFX បែប pop ស្រាល",
            "បើកជាមួយសំណួរធំលើអេក្រង់",
            "បង្ហាញកាតបីជួរ",
            "បញ្ចូល gag សិស្សលាក់សៀវភៅ",
            "Timeline មានរូប Alan Turing",
            "បែងចែកអេក្រង់ជាពីរ",
            "បង្ហាញជញ្ជីង",
            "Classical instrumental",
            "ការត្រួតពិនិត្យមុន Export",
            "វីដេអូមានរយៈពេលមិនលើស ៥ នាទី",
            "VideoZero",
            "[00:00–00:22]",
            "[04:22–04:55]",
        ]

        all_spoken_text = " ".join(
            seg.text for sc in project.scenes for seg in sc.dialogue_segments
        )

        for phrase in forbidden_non_spoken_phrases:
            self.assertNotIn(
                phrase,
                all_spoken_text,
                f"Non-spoken production direction '{phrase}' leaked into spoken narration!",
            )

        # Verify visual notes, keywords, and SFX notes WERE preserved in scene metadata
        self.assertIn("បើកជាមួយសំណួរធំលើអេក្រង់", project.scenes[0].visual_notes)
        self.assertIn("AI?", project.scenes[0].keywords)
        self.assertIn("SFX", project.scenes[0].sfx_notes)
        self.assertIn("Computer Vision (CV)", project.scenes[7].keywords)
        self.assertIn("Natural Language Processing (NLP)", project.scenes[7].keywords)

    def test_03_scene_1_multi_speaker_dialogue_detection(self):
        """Verifies Student and Robot dialogue in Scene 1 are identified and quotation marks stripped."""
        project = self.service.import_document(FIXTURE_DOCX)
        sc1 = project.scenes[0]

        self.assertEqual(len(sc1.dialogue_segments), 5)
        roles = [seg.speaker_role for seg in sc1.dialogue_segments]
        self.assertEqual(roles, ["Narrator", "Student", "Narrator", "Robot", "Teacher"])

        student_seg = sc1.dialogue_segments[1]
        self.assertEqual(
            student_seg.text,
            "ហេ៎! ហេតុអ្វីបានជាទូរស័ព្ទខ្ញុំអាចស្គាល់មុខខ្ញុំ ហើយក៏អាចឆ្លើយសំណួរបានទៀត?",
        )
        self.assertNotIn("«", student_seg.text)
        self.assertNotIn("»", student_seg.text)

        robot_seg = sc1.dialogue_segments[3]
        self.assertEqual(
            robot_seg.text,
            "សួស្តី! នេះហើយជាឧទាហរណ៍នៃបញ្ញាសិប្បនិម្មិត ឬ AI!",
        )
        self.assertNotIn("«", robot_seg.text)
        self.assertNotIn("»", robot_seg.text)

    def test_04_khmer_and_english_technical_terms_preserved(self):
        """Verifies bilingual Khmer and English technical terms in Scenes 1-9 are preserved intact."""
        project = self.service.import_document(FIXTURE_DOCX)
        all_spoken = " ".join(
            seg.text for sc in project.scenes for seg in sc.dialogue_segments
        )

        expected_terms = [
            "AI",
            "Artificial Intelligence",
            "បញ្ញាសិប្បនិម្មិត",
            "Narrow AI",
            "Siri",
            "Alexa",
            "Bixby",
            "Cortana",
            "Chatbots",
            "Voice Assistant",
            "Alan Mathison Turing",
            "Turing Test",
            "Monte Carlo",
            "Machine Learning",
            "Data Mining",
            "Perceptron",
            "AND",
            "OR",
            "XOR",
            "AI Winter",
            "Hinton",
            "Computer Vision",
            "CV",
            "Natural Language Processing",
            "NLP",
        ]
        for term in expected_terms:
            self.assertIn(term, all_spoken, f"Expected term '{term}' missing from spoken text!")

    def test_05_maly_preset_fallback_and_multi_speaker_role_assignment(self):
        """Verifies Maly preset warning when missing, and role-to-voice assignment persistence."""
        # 1. Without 'Maly' profile in DB, verify warning is generated
        project = self.service.import_document(FIXTURE_DOCX)
        self.assertEqual(project.requested_voice_preset, "Maly")
        self.assertTrue(
            any("Maly" in w for w in project.validation_warnings),
            "Should warn when requested voice preset 'Maly' is not in Voice Library.",
        )

        # 2. Create authorized voice profiles for Teacher, Student, and Robot
        prof_teacher = VoiceProfile(
            id="vp_maly",
            name="Maly (Khmer Teacher)",
            original_audio_path=str(self.dummy_ref_wav),
            reference_segment_path=str(self.dummy_ref_wav),
            language="khmer",
            transcript="សួស្តីសិស្សានុសិស្សទាំងអស់គ្នា ថ្ងៃនេះយើងរៀនអំពីបញ្ញាសិប្បនិម្មិត។",
        )
        prof_student = VoiceProfile(
            id="vp_student",
            name="Dara (Grade 8 Student)",
            original_audio_path=str(self.dummy_ref_wav),
            reference_segment_path=str(self.dummy_ref_wav),
            language="khmer",
        )
        prof_robot = VoiceProfile(
            id="vp_robot",
            name="Nano Robot",
            original_audio_path=str(self.dummy_ref_wav),
            reference_segment_path=str(self.dummy_ref_wav),
            language="khmer",
            transcript="សួស្តី ខ្ញុំជាជំនួយការឆ្លាតវៃ។",
        )
        self.db.create_voice_profile(prof_teacher)
        self.db.create_voice_profile(prof_student)
        self.db.create_voice_profile(prof_robot)

        # Assign roles across project
        project = self.service.assign_role_voice(
            project, "Teacher", "vp_maly", mode="ultimate_cloning", delivery_style="Educational"
        )
        project = self.service.assign_role_voice(
            project, "Student", "vp_student", mode="cloning", delivery_style="Curious"
        )
        project = self.service.assign_role_voice(
            project, "Robot", "vp_robot", mode="ultimate_cloning", delivery_style="Cheerful"
        )

        # Reload from disk/SQLite and verify persistence
        reloaded = self.service.load_project(project.project_id)
        self.assertIsNotNone(reloaded)
        sc1_segs = reloaded.scenes[0].dialogue_segments
        self.assertEqual(sc1_segs[1].voice_profile_id, "vp_student")
        self.assertEqual(sc1_segs[1].mode, "cloning")
        self.assertEqual(sc1_segs[3].voice_profile_id, "vp_robot")
        self.assertEqual(sc1_segs[3].mode, "ultimate_cloning")
        self.assertEqual(sc1_segs[4].voice_profile_id, "vp_maly")
        self.assertEqual(sc1_segs[4].mode, "ultimate_cloning")

    def test_06_voice_direction_and_hifi_mode_guardrails(self):
        """Verifies Hi-Fi mode blocks style prompts and Khmer mode prevents speaking English directions."""
        khmer_line = "តោះ! ថ្ងៃនេះយើងមកស្គាល់ AI ឱ្យច្បាស់។"

        # 1. Hi-Fi / Ultimate Cloning must never inject parenthesized style prompts
        prompt_hifi, msg_hifi = VoiceDirectionValidator.build_synthesis_prompt(
            spoken_text=khmer_line,
            delivery_style="Cheerful",
            pace="Fast",
            mode="ultimate_cloning",
            enable_style_prefix=True,
        )
        self.assertEqual(prompt_hifi, khmer_line)
        self.assertIn("Hi-Fi", msg_hifi)

        # 2. Khmer text with default enable_style_prefix=False must keep pure Khmer text
        prompt_km_safe, msg_km_safe = VoiceDirectionValidator.build_synthesis_prompt(
            spoken_text="(friendly tone) " + khmer_line,
            delivery_style="Friendly",
            pace="Medium",
            mode="tts",
            enable_style_prefix=False,
        )
        self.assertEqual(prompt_km_safe, khmer_line)
        self.assertNotIn("(friendly", prompt_km_safe)
        self.assertIn("Safe Khmer", msg_km_safe)

        # 3. Controllable mode with explicit enable_style_prefix=True formats VoxCPM2 descriptor
        prompt_ctrl, msg_ctrl = VoiceDirectionValidator.build_synthesis_prompt(
            spoken_text="Hello students, welcome to AI class!",
            delivery_style="Cheerful",
            pace="Fast",
            mode="cloning",
            enable_style_prefix=True,
        )
        self.assertTrue(prompt_ctrl.startswith("(cheerful and bright tone, slightly faster speaking pace)"))
        self.assertIn("Controllable Style Active", msg_ctrl)

    def test_07_segment_edit_split_merge_and_scene_reorder(self):
        """Verifies editing text, splitting dialogue blocks, merging blocks, and reordering scenes."""
        project = self.service.import_document(FIXTURE_DOCX)
        sc2_id = project.scenes[1].scene_id
        orig_seg_id = project.scenes[1].dialogue_segments[0].segment_id

        # Split Scene 2's single narration block into 2 blocks
        project = self.service.split_segment(project, sc2_id, orig_seg_id)
        self.assertEqual(len(project.scenes[1].dialogue_segments), 2)

        # Edit first split block
        seg1_id = project.scenes[1].dialogue_segments[0].segment_id
        project = self.service.update_segment(
            project, sc2_id, seg1_id, text="AI មកពីពាក្យ Artificial Intelligence។", speaker_role="Narrator"
        )
        self.assertEqual(project.scenes[1].dialogue_segments[0].speaker_role, "Narrator")

        # Merge the two blocks back into 1
        project = self.service.merge_segments(project, sc2_id, seg1_id)
        self.assertEqual(len(project.scenes[1].dialogue_segments), 1)
        self.assertIn("Artificial Intelligence", project.scenes[1].dialogue_segments[0].text)

        # Reorder Scene 2 up to position 1
        project = self.service.reorder_scene(project, sc2_id, direction="up")
        self.assertEqual(project.scenes[0].scene_id, sc2_id)
        self.assertEqual(project.scenes[0].scene_number, 1)

    def test_08_scene_generation_multi_speaker_routing_and_checkpoint_recovery(self):
        """Verifies multi-speaker synthesis routing and retry-failed-only checkpoint recovery."""
        project = self.service.import_document(FIXTURE_DOCX)

        # Register profiles for Student (cloning) and Robot (ultimate_cloning)
        self.db.create_voice_profile(
            VoiceProfile(
                id="vp_stu",
                name="Student Voice",
                original_audio_path=str(self.dummy_ref_wav),
                reference_segment_path=str(self.dummy_ref_wav),
            )
        )
        self.db.create_voice_profile(
            VoiceProfile(
                id="vp_rob",
                name="Robot Voice",
                original_audio_path=str(self.dummy_ref_wav),
                reference_segment_path=str(self.dummy_ref_wav),
                transcript="សួស្តី ខ្ញុំជារ៉ូបូត។",
            )
        )
        project = self.service.assign_role_voice(project, "Student", "vp_stu", mode="cloning")
        project = self.service.assign_role_voice(project, "Robot", "vp_rob", mode="ultimate_cloning")

        # Configure Mock engine to fail on segment #3 of Scene 1
        self.mock_engine.fail_on_chunk = 3
        with self.assertRaises(RuntimeError):
            self.service.generate_scene(project.project_id, "scene_01")

        # Verify segments 1 and 2 succeeded and were persisted, while segment 3 failed
        failed_proj = self.service.load_project(project.project_id)
        sc1 = failed_proj.scenes[0]
        self.assertEqual(sc1.dialogue_segments[0].status, "completed")
        self.assertEqual(sc1.dialogue_segments[1].status, "completed")
        self.assertEqual(sc1.dialogue_segments[2].status, "failed")
        self.assertEqual(sc1.dialogue_segments[3].status, "pending")

        # Clear failure and retry Scene 1 with retry_failed_only=True
        self.mock_engine.fail_on_chunk = None
        self.mock_engine.calls_log.clear()

        res = self.service.generate_scene(project.project_id, "scene_01", retry_failed_only=True)
        self.assertEqual(res["status"], "completed")
        self.assertTrue(Path(res["scene_wav_path"]).exists())

        # Only segments 3, 4, and 5 should have been synthesized on retry (3 calls, not 5!)
        self.assertEqual(len(self.mock_engine.calls_log), 3)
        # Segment 4 is Robot -> must have been routed to 'ultimate_cloning'
        self.assertEqual(self.mock_engine.calls_log[1]["method"], "ultimate_cloning")

    def test_09_full_storyboard_synthesis_timeline_comparison_and_7_exports(self):
        """Verifies full 9-scene synthesis, timeline comparison, time-stretching, and 7 export formats."""
        project = self.service.import_document(FIXTURE_DOCX)
        # Configure modest time-stretch (1.05x) on Scene 1
        self.service.update_scene_metadata(project, "scene_01", stretch_ratio=1.05)

        res = self.service.generate_all_scenes(project.project_id)
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["total_scenes"], 9)
        self.assertTrue(Path(res["combined_wav_path"]).exists())
        self.assertTrue(Path(res["combined_mp3_path"]).exists())

        # Check timeline comparison table
        updated_proj = self.service.load_project(project.project_id)
        timeline = self.service.get_timeline_comparison(updated_proj)
        self.assertEqual(len(timeline), 9)
        self.assertTrue(all(r["actual_sec"] > 0 for r in timeline))

        # Export all 7 formats (A-G)
        bundle = self.service.export_project_bundle(project.project_id)
        self.assertEqual(len(bundle["scene_wav_files"]), 9)
        self.assertEqual(len(bundle["scene_mp3_files"]), 9)
        self.assertTrue(Path(bundle["scenes_wav_zip"]).exists())
        self.assertTrue(Path(bundle["scenes_mp3_zip"]).exists())
        self.assertTrue(Path(bundle["combined_wav_path"]).exists())
        self.assertTrue(Path(bundle["combined_mp3_path"]).exists())
        self.assertTrue(Path(bundle["project_json_path"]).exists())
        self.assertTrue(Path(bundle["cue_sheet_csv_path"]).exists())
        self.assertTrue(Path(bundle["approximate_srt_path"]).exists())

        # Inspect CSV Cue Sheet (verify UTF-8 BOM and 13 rows = 5 segs in Scene 1 + 8 segs in Scenes 2-9)
        csv_path = Path(bundle["cue_sheet_csv_path"])
        raw_csv_bytes = csv_path.read_bytes()
        self.assertTrue(raw_csv_bytes.startswith(b"\xef\xbb\xbf"), "CSV must start with UTF-8 BOM for Khmer Excel support.")
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(len(rows), 1 + 13)  # Header + 13 dialogue segments across 9 scenes

        # Inspect Approximate SRT Draft
        srt_text = Path(bundle["approximate_srt_path"]).read_text(encoding="utf-8")
        self.assertIn("APPROXIMATE SUBTITLE DRAFT", srt_text)
        self.assertIn("[Student]", srt_text)
        self.assertIn("[Robot]", srt_text)
        self.assertIn("-->", srt_text)

    def test_10_ui_state_helpers_and_batch_queue_submission(self):
        """Verifies Smart Script Studio UI formatters and single-worker GenerationQueue integration."""
        project = self.service.import_document(FIXTURE_DOCX)

        ui_state = build_scene_ui_state(project, selected_scene_id="scene_01")
        self.assertEqual(ui_state[0], project.project_id)
        self.assertIn("ICT Grade 8", ui_state[1])
        self.assertEqual(len(ui_state[3]), 9)  # 9 rows in scene_nav_table

        blocks_md = format_dialogue_blocks_md(project.scenes[0])
        self.assertIn("Student", blocks_md)
        self.assertIn("Robot", blocks_md)

        prod_md = format_production_metadata_md(project, project.scenes[0])
        self.assertIn("Strictly Excluded from Speech Synthesis", prod_md)
        self.assertIn("បើកជាមួយសំណួរធំលើអេក្រង់", prod_md)

        tl_table = format_timeline_comparison_table(project)
        self.assertEqual(len(tl_table), 9)

        # Submit Scene 2 to Batch Queue and wait for completion
        job_id, msg = self.service.submit_to_batch_queue(project.project_id, scene_id="scene_02")
        self.assertIsNotNone(job_id)

        q = GenerationQueue.get_instance()
        deadline = time.time() + 5.0
        while time.time() < deadline:
            st = q.get_job_display_status(job_id)["status"]
            if st == "completed":
                break
            time.sleep(0.05)

        self.assertEqual(q.get_job_display_status(job_id)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
