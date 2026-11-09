"""
Smart Script Project Service for VoiceStudio Pro.
Manages storyboard project persistence, multi-speaker role mapping,
segment editing/splitting/merging, scene-based audio synthesis with checkpointing,
timeline duration comparison, modest time-stretching, and multi-format export
(Scene WAV/MP3, Complete WAV/MP3, JSON, CSV Cue Sheet, and Approximate SRT Draft).
"""
import csv
import json
import logging
import re
import shutil
import subprocess
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

from app.audio.stitcher import AudioStitcher
from app.config import (
    DEFAULT_CFG_VALUE,
    DEFAULT_INFERENCE_TIMESTEPS,
    IMPORTS_DIR,
    NATIVE_SAMPLE_RATE,
    PROJECTS_DIR,
)
from app.database.connection import DatabaseManager
from app.database.models import QueueJob, ScriptProjectRecord
from app.engines.voxcpm_adapter import VoxCPM2Adapter
from app.queue.generation_queue import GenerationQueue, GenerationTask
from app.services.script_parser import (
     SUPPORTED_DELIVERY_STYLES,
    SUPPORTED_PACES,
    SUPPORTED_SPEAKER_ROLES,
    DialogueSegment,
    ScriptProject,
    StoryboardParser,
    StoryboardScene,
    VoiceDirectionValidator,
    format_sec_to_srt_timestamp,
    format_sec_to_timecode,
    parse_timecode_to_sec,
    utc_iso_now,
)
from app.utils.text_processor import TextProcessor

logger = logging.getLogger(__name__)


class ScriptProjectService:
    """
    Orchestrates Smart Script Studio projects, persistence, multi-speaker synthesis,
    timeline analysis, and exports.
    """

    _instance: Optional["ScriptProjectService"] = None

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        tts_engine: Optional[VoxCPM2Adapter] = None,
        projects_dir: Path = PROJECTS_DIR,
        imports_dir: Path = IMPORTS_DIR,
    ):
        self.db = db_manager or DatabaseManager.get_instance()
        self.engine = tts_engine or VoxCPM2Adapter()
        self.projects_dir = Path(projects_dir)
        self.imports_dir = Path(imports_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.imports_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls) -> "ScriptProjectService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    def _project_dir(self, project_id: str) -> Path:
        d = self.projects_dir / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _project_json_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    # ------------------------------------------------------------------
    # Import, Save & Load
    # ------------------------------------------------------------------
    def import_document(self, file_path: str | Path) -> ScriptProject:
        """
        Imports a .docx, .txt, or .md storyboard file without modifying the original source file.
        Saves a safe copy in storage/imports/<project_id>/ and persists structured project JSON + SQLite record.
        """
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"Source document not found: {file_path}")

        profiles = self.db.list_voice_profiles()
        project = StoryboardParser.parse_file(src, available_voice_profiles=profiles)

        # Copy source document into storage/imports/<project_id>/ (never overwrite user's original DOCX)
        imp_dir = self.imports_dir / project.project_id
        imp_dir.mkdir(parents=True, exist_ok=True)
        copied_source = imp_dir / src.name
        if src.resolve() != copied_source.resolve():
            shutil.copy2(str(src), str(copied_source))
        project.source_copy_path = str(copied_source)
        project.source_filename = src.name

        return self.save_project(project, is_new=True)

    def import_pasted_text(self, raw_text: str, title: str = "Pasted Storyboard") -> ScriptProject:
        """
        Imports pasted storyboard or narration text into a structured ScriptProject.
        """
        profiles = self.db.list_voice_profiles()
        safe_name = f"{title.strip() or 'pasted_script'}.txt"
        project = StoryboardParser.parse_text(
            raw_text=raw_text,
            source_filename=safe_name,
            available_voice_profiles=profiles,
        )
        if title and title.strip() and project.title == "Untitled Storyboard Project":
            project.title = title.strip()

        imp_dir = self.imports_dir / project.project_id
        imp_dir.mkdir(parents=True, exist_ok=True)
        copied_source = imp_dir / "pasted_source.txt"
        copied_source.write_text(raw_text, encoding="utf-8")
        project.source_copy_path = str(copied_source)

        return self.save_project(project, is_new=True)

    def save_project(self, project: ScriptProject, is_new: bool = False) -> ScriptProject:
        """
        Persists project structure to storage/projects/<project_id>/project.json
        and synchronizes summary metadata in SQLite script_projects table.
        """
        project.updated_at = utc_iso_now()

        # Recalculate scene summaries & totals
        completed_count = 0
        total_actual = 0.0
        for idx, sc in enumerate(project.scenes):
            sc.scene_number = idx + 1
            if sc.dialogue_segments:
                # Re-index segments and sync scene narration preview
                for s_idx, seg in enumerate(sc.dialogue_segments):
                    seg.index = s_idx
                sc.narration_text = " ".join(
                    seg.text.strip() for seg in sc.dialogue_segments if seg.text.strip()
                )
                unique_roles = []
                for seg in sc.dialogue_segments:
                    if seg.speaker_role not in unique_roles:
                        unique_roles.append(seg.speaker_role)
                sc.speaker_role = " + ".join(unique_roles) if unique_roles else sc.speaker_role

            if sc.status == "completed":
                completed_count += 1
            total_actual += sc.actual_duration_sec

        project.actual_total_duration_sec = round(total_actual, 2)
        if completed_count == len(project.scenes) and len(project.scenes) > 0:
            project.status = "completed"
        elif completed_count > 0:
            project.status = "partial"

        json_path = self._project_json_path(project.project_id)
        json_path.write_text(
            json.dumps(project.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        rec = ScriptProjectRecord(
            id=project.project_id,
            title=project.title,
            topic=project.topic,
            source_filename=project.source_filename,
            source_copy_path=project.source_copy_path,
            project_json_path=str(json_path),
            scene_count=len(project.scenes),
            completed_scenes=completed_count,
            planned_duration_sec=project.planned_duration_sec,
            actual_duration_sec=project.actual_total_duration_sec,
            status=project.status,
            combined_wav_path=project.combined_wav_path,
            combined_mp3_path=project.combined_mp3_path,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

        existing = self.db.get_script_project(project.project_id)
        if existing is None or is_new:
            if existing is None:
                self.db.create_script_project(rec)
            else:
                self.db.update_script_project(rec)
        else:
            self.db.update_script_project(rec)

        return project

    def load_project(self, project_id: str) -> Optional[ScriptProject]:
        """Loads a ScriptProject from disk or SQLite record."""
        json_path = self._project_json_path(project_id)
        if not json_path.exists():
            rec = self.db.get_script_project(project_id)
            if rec and rec.project_json_path and Path(rec.project_json_path).exists():
                json_path = Path(rec.project_json_path)
            else:
                return None

        data = json.loads(json_path.read_text(encoding="utf-8"))
        return ScriptProject.from_dict(data)

    def list_projects(self, limit: int = 50) -> List[ScriptProjectRecord]:
        return self.db.list_script_projects(limit=limit)

    # ------------------------------------------------------------------
    # Scene, Dialogue & Speaker Editing Operations (Step C)
    # ------------------------------------------------------------------
    def assign_role_voice(
        self,
        project: ScriptProject,
        speaker_role: str,
        voice_profile_id: Optional[str],
        mode: str = "tts",
        delivery_style: Optional[str] = None,
        pace: Optional[str] = None,
        apply_to_existing_segments: bool = True,
    ) -> ScriptProject:
        """
        Assigns an existing Voice Profile (or Default Voice) and generation mode
        to a speaker role (Narrator, Teacher, Student, Robot, Custom Character).
        """
        voice_name = "Default Voice"
        clean_prof_id = None
        if voice_profile_id and voice_profile_id not in ("Default Voice", "Default Voice (No Profile)", ""):
            # Handle dropdown format "Name (id)" or raw id
            if "(" in voice_profile_id and voice_profile_id.endswith(")"):
                clean_prof_id = voice_profile_id.split("(")[-1].rstrip(")").strip()
            else:
                clean_prof_id = voice_profile_id.strip()
            prof = self.db.get_voice_profile(clean_prof_id)
            if prof:
                voice_name = prof.name
            else:
                raise ValueError(f"Voice profile '{clean_prof_id}' does not exist in Voice Library.")

        norm_mode = self._normalize_mode(mode)
        role_cfg = project.role_voice_map.get(speaker_role, {})
        role_cfg["voice_profile_id"] = clean_prof_id
        role_cfg["voice_name"] = voice_name
        role_cfg["mode"] = norm_mode
        if delivery_style in SUPPORTED_DELIVERY_STYLES:
            role_cfg["delivery_style"] = delivery_style
        if pace in SUPPORTED_PACES:
            role_cfg["pace"] = pace
        project.role_voice_map[speaker_role] = role_cfg

        if apply_to_existing_segments:
            for sc in project.scenes:
                changed = False
                for seg in sc.dialogue_segments:
                    if seg.speaker_role == speaker_role:
                        if (
                            seg.voice_profile_id != clean_prof_id
                            or seg.mode != norm_mode
                            or (delivery_style and seg.delivery_style != delivery_style)
                            or (pace and seg.pace != pace)
                        ):
                            seg.voice_profile_id = clean_prof_id
                            seg.voice_name = voice_name
                            seg.mode = norm_mode
                            if delivery_style in SUPPORTED_DELIVERY_STYLES:
                                seg.delivery_style = delivery_style
                            if pace in SUPPORTED_PACES:
                                seg.pace = pace
                            seg.status = "pending"
                            changed = True
                if changed and sc.status == "completed":
                    sc.status = "partial"

        return self.save_project(project)

    def update_segment(
        self,
        project: ScriptProject,
        scene_id: str,
        segment_id: str,
        text: Optional[str] = None,
        speaker_role: Optional[str] = None,
        voice_profile_id: Optional[str] = "__unchanged__",
        mode: Optional[str] = None,
        delivery_style: Optional[str] = None,
        pace: Optional[str] = None,
        pause_after_ms: Optional[int] = None,
        enable_style_prefix: Optional[bool] = None,
    ) -> ScriptProject:
        """
        Updates an individual dialogue segment inside a scene.
        Marks only the modified segment as pending so unchanged segments stay cached.
        """
        scene = self._find_scene(project, scene_id)
        seg = self._find_segment(scene, segment_id)

        modified = False
        if text is not None and text.strip() != seg.text:
            seg.text = VoiceDirectionValidator.strip_accidental_directions(text)
            modified = True

        if speaker_role is not None and speaker_role in SUPPORTED_SPEAKER_ROLES:
            if speaker_role != seg.speaker_role:
                seg.speaker_role = speaker_role
                # Inherit role's voice assignment unless explicitly overridden in same call
                if voice_profile_id == "__unchanged__":
                    rcfg = project.role_voice_map.get(speaker_role, {})
                    seg.voice_profile_id = rcfg.get("voice_profile_id")
                    seg.voice_name = rcfg.get("voice_name", "Default Voice")
                    seg.mode = rcfg.get("mode", seg.mode)
                modified = True

        if voice_profile_id != "__unchanged__":
            clean_id, v_name = self._resolve_profile_input(voice_profile_id)
            if clean_id != seg.voice_profile_id:
                seg.voice_profile_id = clean_id
                seg.voice_name = v_name
                modified = True

        if mode is not None:
            norm_m = self._normalize_mode(mode)
            if norm_m != seg.mode:
                seg.mode = norm_m
                modified = True

        if delivery_style is not None and delivery_style in SUPPORTED_DELIVERY_STYLES:
            if delivery_style != seg.delivery_style:
                seg.delivery_style = delivery_style
                modified = True

        if pace is not None and pace in SUPPORTED_PACES:
            if pace != seg.pace:
                seg.pace = pace
                modified = True

        if pause_after_ms is not None:
            seg.pause_after_ms = max(0, int(pause_after_ms))

        if enable_style_prefix is not None:
            if bool(enable_style_prefix) != seg.enable_style_prefix:
                seg.enable_style_prefix = bool(enable_style_prefix)
                modified = True

        if modified:
            seg.status = "pending"
            if scene.status == "completed":
                scene.status = "partial"

        return self.save_project(project)

    def split_segment(
        self,
        project: ScriptProject,
        scene_id: str,
        segment_id: str,
        split_at_text: Optional[str] = None,
    ) -> ScriptProject:
        """
        Splits a dialogue segment into two segments at a sentence boundary (។, ?, !, .)
        or at the specified substring/midpoint.
        """
        scene = self._find_scene(project, scene_id)
        seg_idx = next(
            (i for i, s in enumerate(scene.dialogue_segments) if s.segment_id == segment_id),
            None,
        )
        if seg_idx is None:
            raise ValueError(f"Segment '{segment_id}' not found in scene '{scene_id}'.")

        seg = scene.dialogue_segments[seg_idx]
        txt = seg.text.strip()
        if len(txt) < 4:
            raise ValueError("Segment text is too short to split.")

        part1 = ""
        part2 = ""
        if split_at_text and split_at_text in txt:
            pos = txt.index(split_at_text)
            if pos > 0:
                part1 = txt[:pos].strip()
                part2 = txt[pos:].strip()

        if not part1 or not part2:
            # Find sentence boundary closest to midpoint
            mid = len(txt) // 2
            boundaries = [
                m.end()
                for m in re.finditer(r"[។\?\!\.;]+", txt)
                if 2 <= m.end() <= len(txt) - 2
            ]
            if boundaries:
                best_b = min(boundaries, key=lambda b: abs(b - mid))
                part1 = txt[:best_b].strip()
                part2 = txt[best_b:].strip()
            else:
                # Split at space closest to midpoint
                spaces = [m.start() for m in re.finditer(r"\s+", txt) if 2 <= m.start() <= len(txt) - 2]
                if spaces:
                    best_s = min(spaces, key=lambda s: abs(s - mid))
                    part1 = txt[:best_s].strip()
                    part2 = txt[best_s:].strip()
                else:
                    part1 = txt[:mid].strip()
                    part2 = txt[mid:].strip()

        seg.text = part1
        seg.status = "pending"
        new_seg = DialogueSegment(
            segment_id=f"{scene.scene_id}_seg_{uuid.uuid4().hex[:4]}",
            index=seg_idx + 1,
            speaker_role=seg.speaker_role,
            custom_speaker_name=seg.custom_speaker_name,
            text=part2,
            voice_profile_id=seg.voice_profile_id,
            voice_name=seg.voice_name,
            mode=seg.mode,
            delivery_style=seg.delivery_style,
            pace=seg.pace,
            pause_after_ms=seg.pause_after_ms,
            enable_style_prefix=seg.enable_style_prefix,
            status="pending",
        )
        scene.dialogue_segments.insert(seg_idx + 1, new_seg)
        for i, s in enumerate(scene.dialogue_segments):
            s.index = i
            s.segment_id = f"{scene.scene_id}_seg_{i + 1:02d}"

        if scene.status == "completed":
            scene.status = "partial"
        return self.save_project(project)

    def merge_segments(
        self,
        project: ScriptProject,
        scene_id: str,
        first_segment_id: str,
        second_segment_id: Optional[str] = None,
    ) -> ScriptProject:
        """
        Merges two adjacent dialogue segments in a scene into a single segment.
        If second_segment_id is omitted, merges first_segment_id with the next segment.
        """
        scene = self._find_scene(project, scene_id)
        if len(scene.dialogue_segments) < 2:
            raise ValueError("Scene must have at least 2 segments to merge.")

        idx1 = next(
            (i for i, s in enumerate(scene.dialogue_segments) if s.segment_id == first_segment_id),
            None,
        )
        if idx1 is None:
            raise ValueError(f"Segment '{first_segment_id}' not found.")

        if second_segment_id:
            idx2 = next(
                (i for i, s in enumerate(scene.dialogue_segments) if s.segment_id == second_segment_id),
                None,
            )
            if idx2 is None:
                raise ValueError(f"Segment '{second_segment_id}' not found.")
        else:
            idx2 = idx1 + 1 if idx1 + 1 < len(scene.dialogue_segments) else idx1 - 1

        if abs(idx1 - idx2) != 1:
            raise ValueError("Only adjacent segments can be merged.")

        low_idx = min(idx1, idx2)
        high_idx = max(idx1, idx2)
        seg_a = scene.dialogue_segments[low_idx]
        seg_b = scene.dialogue_segments[high_idx]

        seg_a.text = f"{seg_a.text.strip()} {seg_b.text.strip()}".strip()
        seg_a.status = "pending"
        scene.dialogue_segments.pop(high_idx)

        for i, s in enumerate(scene.dialogue_segments):
            s.index = i
            s.segment_id = f"{scene.scene_id}_seg_{i + 1:02d}"

        if scene.status == "completed":
            scene.status = "partial"
        return self.save_project(project)

    def reorder_scene(
        self,
        project: ScriptProject,
        scene_id: str,
        direction: str = "down",
    ) -> ScriptProject:
        """Moves a scene 'up' or 'down' in the storyboard sequence."""
        idx = next(
            (i for i, s in enumerate(project.scenes) if s.scene_id == scene_id),
            None,
        )
        if idx is None:
            raise ValueError(f"Scene '{scene_id}' not found.")

        target_idx = idx - 1 if direction.lower() == "up" else idx + 1
        if target_idx < 0 or target_idx >= len(project.scenes):
            return project

        project.scenes[idx], project.scenes[target_idx] = (
            project.scenes[target_idx],
            project.scenes[idx],
        )
        for i, sc in enumerate(project.scenes):
            sc.scene_number = i + 1
        return self.save_project(project)

    def update_scene_metadata(
        self,
        project: ScriptProject,
        scene_id: str,
        title: Optional[str] = None,
        target_start_time: Optional[str] = None,
        target_end_time: Optional[str] = None,
        visual_notes: Optional[str] = None,
        music_notes: Optional[str] = None,
        sfx_notes: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        pause_after_scene_ms: Optional[int] = None,
        stretch_ratio: Optional[float] = None,
    ) -> ScriptProject:
        """Updates scene timing targets, production notes, pause padding, or modest time-stretch ratio."""
        scene = self._find_scene(project, scene_id)
        if title is not None:
            scene.title = title.strip()
        if target_start_time is not None:
            scene.target_start_time = target_start_time.strip()
            scene.target_start_sec = parse_timecode_to_sec(scene.target_start_time)
        if target_end_time is not None:
            scene.target_end_time = target_end_time.strip()
            scene.target_end_sec = parse_timecode_to_sec(scene.target_end_time)
        if target_start_time is not None or target_end_time is not None:
            scene.target_duration_sec = round(max(0.0, scene.target_end_sec - scene.target_start_sec), 2)
            if scene.actual_duration_sec > 0:
                scene.duration_diff_sec = round(scene.actual_duration_sec - scene.target_duration_sec, 2)
        if visual_notes is not None:
            scene.visual_notes = visual_notes.strip()
        if music_notes is not None:
            scene.music_notes = music_notes.strip()
        if sfx_notes is not None:
            scene.sfx_notes = sfx_notes.strip()
        if keywords is not None:
            scene.keywords = [k.strip() for k in keywords if k.strip()]
        if pause_after_scene_ms is not None:
            scene.pause_after_scene_ms = max(0, int(pause_after_scene_ms))
        if stretch_ratio is not None:
            r = round(float(stretch_ratio), 3)
            scene.stretch_ratio = max(0.80, min(1.25, r))
            if abs(scene.stretch_ratio - 1.0) > 0.10:
                warn = (
                    f"⚠️ Time-stretch ratio {scene.stretch_ratio:.2f}x exceeds ±10%; "
                    "consider adjusting pauses or editing script wording to preserve natural Khmer prosody."
                )
                if warn not in scene.validation_warnings:
                    scene.validation_warnings.append(warn)

        return self.save_project(project)

    # ------------------------------------------------------------------
    # Scene-Based Audio Generation & Checkpoint Recovery (Step E)
    # ------------------------------------------------------------------
    def generate_scene(
        self,
        project_id: str,
        scene_id: str,
        cfg_value: float = DEFAULT_CFG_VALUE,
        inference_timesteps: int = DEFAULT_INFERENCE_TIMESTEPS,
        retry_failed_only: bool = True,
        cancel_event=None,
        pause_event=None,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes all dialogue segments in a scene using their assigned speaker voices,
        delivery styles, and modes. Reuses completed segments on retry (checkpoint recovery).
        Saves individual segment WAVs, stitched scene WAV/MP3, and scene_metadata.json.
        """
        project = self.load_project(project_id)
        if not project:
            raise ValueError(f"Project '{project_id}' not found.")

        scene = self._find_scene(project, scene_id)
        if not scene.dialogue_segments:
            raise ValueError(f"Scene '{scene_id}' has no spoken dialogue segments.")

        scene.status = "processing"
        self.save_project(project)

        scene_dir = self._project_dir(project_id) / "scenes" / scene.scene_id
        segments_dir = scene_dir / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)

        segment_wavs: List[Path] = []
        segment_pauses: List[int] = []
        total_gen_time = 0.0

        for seg in scene.dialogue_segments:
            if cancel_event and cancel_event.is_set():
                scene.status = "partial"
                self.save_project(project)
                return {"status": "cancelled", "scene_id": scene.scene_id}

            if pause_event and pause_event.is_set():
                scene.status = "partial"
                self.save_project(project)
                return {"status": "paused", "scene_id": scene.scene_id}

            seg_wav_path = segments_dir / f"{seg.segment_id}.wav"

            # Checkpoint reuse: skip already completed segments if retry_failed_only is True
            if (
                retry_failed_only
                and seg.status == "completed"
                and seg.output_wav_path
                and Path(seg.output_wav_path).exists()
                and Path(seg.output_wav_path).stat().st_size > 100
            ):
                segment_wavs.append(Path(seg.output_wav_path))
                eff_pause = int(
                    seg.pause_after_ms
                    * VoiceDirectionValidator.PACE_PAUSE_MULTIPLIER.get(seg.pace, 1.0)
                )
                segment_pauses.append(eff_pause)
                continue

            seg.status = "processing"
            seg.error_message = ""
            self.save_project(project)

            # Resolve voice profile & conditioning files
            ref_wav, prompt_wav, prompt_txt, resolved_mode = self._resolve_segment_conditioning(
                project, scene, seg
            )

            # Build validated synthesis prompt (never leaks style instructions into Khmer or Hi-Fi mode)
            lang = TextProcessor.detect_language(seg.text)
            synth_prompt, style_note = VoiceDirectionValidator.build_synthesis_prompt(
                spoken_text=seg.text,
                delivery_style=seg.delivery_style,
                pace=seg.pace,
                mode=resolved_mode,
                language=lang,
                enable_style_prefix=seg.enable_style_prefix,
            )

            try:
                if resolved_mode == "cloning" and ref_wav:
                    wav_np, sr, elapsed = self.engine.generate_voice_cloning(
                        text=synth_prompt,
                        reference_wav_path=ref_wav,
                        cfg_value=cfg_value,
                        inference_timesteps=inference_timesteps,
                    )
                elif resolved_mode == "ultimate_cloning" and prompt_wav and prompt_txt:
                    wav_np, sr, elapsed = self.engine.generate_ultimate_cloning(
                        text=synth_prompt,
                        prompt_wav_path=prompt_wav,
                        prompt_text=prompt_txt,
                        reference_wav_path=ref_wav or prompt_wav,
                        cfg_value=cfg_value,
                        inference_timesteps=inference_timesteps,
                    )
                else:
                    wav_np, sr, elapsed = self.engine.generate_tts(
                        text=synth_prompt,
                        cfg_value=cfg_value,
                        inference_timesteps=inference_timesteps,
                    )

                sf.write(str(seg_wav_path), wav_np, sr, subtype="PCM_16")
                seg_dur = round(len(wav_np) / sr, 2)
                total_gen_time += elapsed

                seg.status = "completed"
                seg.output_wav_path = str(seg_wav_path)
                seg.duration_sec = seg_dur
                seg.generation_time_sec = elapsed
                segment_wavs.append(seg_wav_path)

                eff_pause = int(
                    seg.pause_after_ms
                    * VoiceDirectionValidator.PACE_PAUSE_MULTIPLIER.get(seg.pace, 1.0)
                )
                segment_pauses.append(eff_pause)
                self.save_project(project)

                if on_progress:
                    on_progress(
                        {
                            "scene_id": scene.scene_id,
                            "segment_id": seg.segment_id,
                            "speaker_role": seg.speaker_role,
                            "duration_sec": seg_dur,
                            "style_note": style_note,
                        }
                    )
            except Exception as e:
                seg.status = "failed"
                seg.error_message = str(e)
                scene.status = "failed"
                self.save_project(project)
                logger.error(f"Failed generating segment {seg.segment_id} in {scene.scene_id}: {e}")
                raise

        # Stitch all segments in the scene into scene WAV & MP3
        stitched_audio, raw_scene_dur = AudioStitcher.stitch_chunks(
            chunk_paths=segment_wavs,
            pauses_ms=segment_pauses,
            target_sr=NATIVE_SAMPLE_RATE,
        )

        scene_wav_path = scene_dir / f"{scene.scene_id}.wav"
        AudioStitcher.export_wav(stitched_audio, scene_wav_path, sample_rate=NATIVE_SAMPLE_RATE)

        # Apply optional modest time-stretching if configured by user (e.g. 0.90x - 1.15x)
        if abs(scene.stretch_ratio - 1.0) >= 0.01:
            stretched_wav = scene_dir / f"{scene.scene_id}_stretched.wav"
            final_wav, stretched_dur = self._apply_modest_time_stretch(
                input_wav=scene_wav_path,
                output_wav=stretched_wav,
                tempo_ratio=scene.stretch_ratio,
            )
            scene_wav_path = final_wav
            actual_dur = stretched_dur
        else:
            actual_dur = raw_scene_dur

        scene_mp3_path = scene_dir / f"{scene.scene_id}.mp3"
        AudioStitcher.export_mp3(scene_wav_path, scene_mp3_path)

        scene.scene_wav_path = str(scene_wav_path)
        scene.scene_mp3_path = str(scene_mp3_path)
        scene.actual_duration_sec = round(actual_dur, 2)
        scene.duration_diff_sec = round(scene.actual_duration_sec - scene.target_duration_sec, 2)
        scene.status = "completed"

        # Save scene_metadata.json alongside scene audio
        meta_path = scene_dir / "scene_metadata.json"
        meta_path.write_text(
            json.dumps(
                {
                    "project_id": project.project_id,
                    "scene_id": scene.scene_id,
                    "scene_number": scene.scene_number,
                    "title": scene.title,
                    "target_start_time": scene.target_start_time,
                    "target_end_time": scene.target_end_time,
                    "target_duration_sec": scene.target_duration_sec,
                    "actual_duration_sec": scene.actual_duration_sec,
                    "duration_diff_sec": scene.duration_diff_sec,
                    "cfg_value": cfg_value,
                    "inference_timesteps": inference_timesteps,
                    "scene_wav_path": scene.scene_wav_path,
                    "scene_mp3_path": scene.scene_mp3_path,
                    "segments": [
                        {
                            "segment_id": s.segment_id,
                            "speaker_role": s.speaker_role,
                            "voice_name": s.voice_name,
                            "mode": s.mode,
                            "delivery_style": s.delivery_style,
                            "pace": s.pace,
                            "text": s.text,
                            "duration_sec": s.duration_sec,
                            "output_wav_path": s.output_wav_path,
                        }
                        for s in scene.dialogue_segments
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self.save_project(project)
        return {
            "status": "completed",
            "scene_id": scene.scene_id,
            "scene_wav_path": scene.scene_wav_path,
            "scene_mp3_path": scene.scene_mp3_path,
            "target_duration_sec": scene.target_duration_sec,
            "actual_duration_sec": scene.actual_duration_sec,
            "duration_diff_sec": scene.duration_diff_sec,
            "generation_time_sec": round(total_gen_time, 2),
        }

    def generate_all_scenes(
        self,
        project_id: str,
        cfg_value: float = DEFAULT_CFG_VALUE,
        inference_timesteps: int = DEFAULT_INFERENCE_TIMESTEPS,
        retry_failed_only: bool = True,
        cancel_event=None,
        pause_event=None,
        on_scene_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes all scenes in the storyboard project sequentially,
        preserving completed segments/scenes on interruption, and stitches
        the complete narration WAV and MP3.
        """
        project = self.load_project(project_id)
        if not project:
            raise ValueError(f"Project '{project_id}' not found.")

        total_scenes = len(project.scenes)
        completed_scene_wavs: List[Path] = []
        inter_scene_pauses: List[int] = []

        for idx, sc in enumerate(project.scenes):
            if cancel_event and cancel_event.is_set():
                return {"status": "cancelled", "project_id": project_id}
            if pause_event and pause_event.is_set():
                return {"status": "paused", "project_id": project_id}

            # If scene is already completed and all its segment WAVs + scene WAV exist, reuse it
            if (
                retry_failed_only
                and sc.status == "completed"
                and sc.scene_wav_path
                and Path(sc.scene_wav_path).exists()
                and all(s.status == "completed" for s in sc.dialogue_segments)
            ):
                completed_scene_wavs.append(Path(sc.scene_wav_path))
                inter_scene_pauses.append(sc.pause_after_scene_ms)
                continue

            res = self.generate_scene(
                project_id=project_id,
                scene_id=sc.scene_id,
                cfg_value=cfg_value,
                inference_timesteps=inference_timesteps,
                retry_failed_only=retry_failed_only,
                cancel_event=cancel_event,
                pause_event=pause_event,
            )
            if res.get("status") != "completed":
                return res

            completed_scene_wavs.append(Path(res["scene_wav_path"]))
            inter_scene_pauses.append(sc.pause_after_scene_ms)

            if on_scene_progress:
                on_scene_progress(
                    {
                        "scene_index": idx + 1,
                        "total_scenes": total_scenes,
                        "scene_id": sc.scene_id,
                        "title": sc.title,
                        "actual_duration_sec": res["actual_duration_sec"],
                    }
                )

        # Reload updated project state and stitch complete narration
        project = self.load_project(project_id)
        export_res = self.stitch_complete_narration(project)
        return {
            "status": "completed",
            "project_id": project_id,
            "total_scenes": total_scenes,
            "combined_wav_path": export_res["combined_wav_path"],
            "combined_mp3_path": export_res["combined_mp3_path"],
            "actual_total_duration_sec": export_res["actual_total_duration_sec"],
            "planned_duration_sec": project.planned_duration_sec,
        }

    def stitch_complete_narration(self, project: ScriptProject) -> Dict[str, Any]:
        """
        Stitches all completed scene WAV files into complete_narration.wav and complete_narration.mp3.
        Preserves natural speech duration with each scene's configured pause_after_scene_ms.
        """
        scene_wavs: List[Path] = []
        pauses: List[int] = []
        for sc in project.scenes:
            if sc.scene_wav_path and Path(sc.scene_wav_path).exists():
                scene_wavs.append(Path(sc.scene_wav_path))
                pauses.append(sc.pause_after_scene_ms)

        if not scene_wavs:
            raise ValueError("No generated scene audio files available to stitch.")

        exports_dir = self._project_dir(project.project_id) / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)

        full_audio, full_dur = AudioStitcher.stitch_chunks(
            chunk_paths=scene_wavs,
            pauses_ms=pauses,
            target_sr=NATIVE_SAMPLE_RATE,
        )

        combined_wav = exports_dir / f"{project.project_id}_complete_narration.wav"
        combined_mp3 = exports_dir / f"{project.project_id}_complete_narration.mp3"
        AudioStitcher.export_wav(full_audio, combined_wav, sample_rate=NATIVE_SAMPLE_RATE)
        AudioStitcher.export_mp3(combined_wav, combined_mp3)

        project.combined_wav_path = str(combined_wav)
        project.combined_mp3_path = str(combined_mp3)
        project.actual_total_duration_sec = round(full_dur, 2)
        self.save_project(project)

        return {
            "combined_wav_path": str(combined_wav),
            "combined_mp3_path": str(combined_mp3),
            "actual_total_duration_sec": project.actual_total_duration_sec,
        }

    def submit_to_batch_queue(
        self,
        project_id: str,
        scene_id: Optional[str] = None,
        cfg_value: float = DEFAULT_CFG_VALUE,
        inference_timesteps: int = DEFAULT_INFERENCE_TIMESTEPS,
    ) -> Tuple[Optional[str], str]:
        """
        Submits a single scene or an entire storyboard project to the single-worker
        GenerationQueue with persistent SQLite job tracking.
        """
        project = self.load_project(project_id)
        if not project:
            return None, f"Project '{project_id}' not found."

        job_id = f"job_sc_{uuid.uuid4().hex[:8]}"
        if scene_id:
            scene = self._find_scene(project, scene_id)
            title = f"{project.title} — Scene {scene.scene_number}: {scene.title}"
            total_chunks = len(scene.dialogue_segments)
            target_text = scene.narration_text
        else:
            title = f"{project.title} (All {len(project.scenes)} Scenes)"
            total_chunks = sum(len(s.dialogue_segments) for s in project.scenes)
            target_text = " | ".join(s.narration_text[:60] for s in project.scenes)

        qjob = QueueJob(
            id=job_id,
            job_type="longform",
            status="queued",
            progress=0.0,
            status_message=f"Queued Smart Script ({total_chunks} segments)",
            title=title,
            target_text=target_text,
            voice_name="Multi-Speaker Storyboard",
            language="mixed",
            mode="tts",
            cfg_value=float(cfg_value),
            inference_timesteps=int(inference_timesteps),
            total_chunks=max(1, total_chunks),
            completed_chunks=0,
        )
        self.db.create_job(qjob)

        def _executor(task: GenerationTask):
            q_inst = GenerationQueue.get_instance()
            if scene_id:
                res = self.generate_scene(
                    project_id=project_id,
                    scene_id=scene_id,
                    cfg_value=cfg_value,
                    inference_timesteps=inference_timesteps,
                    cancel_event=task.cancel_event,
                    pause_event=q_inst._pause_requested,
                )
                return {
                    "status": res.get("status", "completed"),
                    "output_path": res.get("scene_wav_path"),
                    "output_mp3_path": res.get("scene_mp3_path"),
                    "duration_sec": res.get("actual_duration_sec", 0.0),
                }
            else:
                res = self.generate_all_scenes(
                    project_id=project_id,
                    cfg_value=cfg_value,
                    inference_timesteps=inference_timesteps,
                    cancel_event=task.cancel_event,
                    pause_event=q_inst._pause_requested,
                )
                return {
                    "status": res.get("status", "completed"),
                    "output_path": res.get("combined_wav_path"),
                    "output_mp3_path": res.get("combined_mp3_path"),
                    "duration_sec": res.get("actual_total_duration_sec", 0.0),
                }

        task = GenerationTask(
            job_id=job_id,
            job_type="longform",
            title=title,
            target_text=target_text,
            voice_name="Multi-Speaker Storyboard",
            cfg_value=float(cfg_value),
            inference_timesteps=int(inference_timesteps),
            total_chunks=max(1, total_chunks),
            executor=_executor,
        )
        GenerationQueue.get_instance().submit_task(task)
        return job_id, f"Submitted '{title}' to single-worker queue."

    # ------------------------------------------------------------------
    # Timeline Comparisons & Modest Time Stretching (Step F)
    # ------------------------------------------------------------------
    def get_timeline_comparison(self, project: ScriptProject) -> List[Dict[str, Any]]:
        """
        Compares each scene's planned storyboard duration against actual generated duration.
        Highlights short or overlong scenes and recommends safe adjustments.
        """
        rows: List[Dict[str, Any]] = []
        tolerance_sec = 2.5

        for sc in project.scenes:
            target = sc.target_duration_sec
            actual = sc.actual_duration_sec
            if sc.status != "completed" or actual <= 0:
                badge = "⏳ Pending"
                diff_str = "—"
                recommendation = "Generate scene audio to compare against storyboard target."
            else:
                diff = round(actual - target, 2)
                sc.duration_diff_sec = diff
                sign = "+" if diff > 0 else ""
                diff_str = f"{sign}{diff:.2f}s"
                if abs(diff) <= tolerance_sec:
                    badge = "✅ On Target"
                    recommendation = "Natural duration fits storyboard window."
                elif diff > tolerance_sec:
                    badge = "⚠️ Overlong"
                    needed_ratio = round(min(1.15, actual / max(1.0, target)), 2)
                    recommendation = (
                        f"Over target by {diff:.1f}s. Trim pause padding, shorten script wording, "
                        f"or apply modest time-stretch (~{needed_ratio:.2f}x)."
                    )
                else:
                    badge = "🔵 Short"
                    short_by_ms = int(round(abs(diff) * 1000))
                    recommendation = (
                        f"Under target by {abs(diff):.1f}s. Preserve natural duration or add "
                        f"+{min(3000, short_by_ms)}ms pause padding."
                    )

            rows.append(
                {
                    "scene_number": sc.scene_number,
                    "scene_id": sc.scene_id,
                    "title": sc.title,
                    "window": f"[{sc.target_start_time}–{sc.target_end_time}]",
                    "target_sec": target,
                    "actual_sec": actual,
                    "diff_str": diff_str,
                    "status_badge": badge,
                    "stretch_ratio": sc.stretch_ratio,
                    "pause_after_scene_ms": sc.pause_after_scene_ms,
                    "recommendation": recommendation,
                }
            )
        return rows

    def _apply_modest_time_stretch(
        self,
        input_wav: Path,
        output_wav: Path,
        tempo_ratio: float,
    ) -> Tuple[Path, float]:
        """
        Applies modest time-stretching (e.g. 0.85x to 1.20x) using FFmpeg atempo filter
        to preserve pitch, falling back to linear interpolation if FFmpeg is unavailable.
        """
        ratio = max(0.80, min(1.25, float(tempo_ratio)))
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i",
                str(input_wav),
                "-filter:a",
                f"atempo={ratio:.4f}",
                str(output_wav),
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and output_wav.exists():
                data, sr = sf.read(str(output_wav))
                return output_wav, round(len(data) / sr, 2)

        # Fallback: resample array and write at native sample rate
        data, sr = sf.read(str(input_wav))
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        new_len = max(1, int(round(len(data) / ratio)))
        stretched = np.interp(
            np.linspace(0, len(data), new_len, endpoint=False),
            np.arange(len(data)),
            data,
        ).astype(np.float32)
        sf.write(str(output_wav), stretched, sr, subtype="PCM_16")
        return output_wav, round(len(stretched) / sr, 2)

    # ------------------------------------------------------------------
    # Export Options (Section 10: A, B, C, D, E, F, G)
    # ------------------------------------------------------------------
    def export_project_bundle(self, project_id: str) -> Dict[str, Any]:
        """
        Generates all 7 export deliverables for the project:
        A. Individual scene WAV files (+ ZIP bundle)
        B. Individual scene MP3 files (+ ZIP bundle)
        C. Complete narration WAV
        D. Complete narration MP3
        E. Structured JSON project file
        F. CSV cue sheet (UTF-8 with BOM for Khmer Excel compatibility)
        G. Approximate SRT subtitle/caption draft (clearly labeled approximate)
        """
        project = self.load_project(project_id)
        if not project:
            raise ValueError(f"Project '{project_id}' not found.")

        exports_dir = self._project_dir(project_id) / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)

        # A & B: Individual scene WAV & MP3 files + ZIP bundles
        scene_wavs = [
            Path(s.scene_wav_path)
            for s in project.scenes
            if s.scene_wav_path and Path(s.scene_wav_path).exists()
        ]
        scene_mp3s = [
            Path(s.scene_mp3_path)
            for s in project.scenes
            if s.scene_mp3_path and Path(s.scene_mp3_path).exists()
        ]

        wav_zip_path = exports_dir / f"{project.project_id}_scenes_wav.zip"
        with zipfile.ZipFile(wav_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in scene_wavs:
                zf.write(p, arcname=p.name)

        mp3_zip_path = exports_dir / f"{project.project_id}_scenes_mp3.zip"
        with zipfile.ZipFile(mp3_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in scene_mp3s:
                zf.write(p, arcname=p.name)

        # C & D: Complete narration WAV & MP3 (stitch if scene WAVs exist)
        if scene_wavs:
            self.stitch_complete_narration(project)
            project = self.load_project(project_id)

        # E: Structured JSON project file
        json_export_path = exports_dir / f"{project.project_id}_structured_project.json"
        json_export_path.write_text(
            json.dumps(project.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # F: CSV cue sheet
        csv_export_path = self.export_csv_cue_sheet(project, exports_dir / f"{project.project_id}_cue_sheet.csv")

        # G: Optional approximate SRT subtitle/caption draft
        srt_export_path = self.export_approximate_srt(
            project, exports_dir / f"{project.project_id}_captions_APPROXIMATE_DRAFT.srt"
        )

        return {
            "scene_wav_files": [str(p) for p in scene_wavs],
            "scene_mp3_files": [str(p) for p in scene_mp3s],
            "scenes_wav_zip": str(wav_zip_path),
            "scenes_mp3_zip": str(mp3_zip_path),
            "combined_wav_path": project.combined_wav_path,
            "combined_mp3_path": project.combined_mp3_path,
            "project_json_path": str(json_export_path),
            "cue_sheet_csv_path": str(csv_export_path),
            "approximate_srt_path": str(srt_export_path),
        }

    def export_csv_cue_sheet(self, project: ScriptProject, out_path: Path) -> Path:
        """
        Exports a production CSV cue sheet containing:
        Scene, Scene Title, Segment, Speaker, Delivery Style, Pace, Text,
        Planned Start, Planned End, Planned Duration, Actual Duration, Output File Path.
        Writes UTF-8 with BOM (\ufeff) so Khmer script opens cleanly in Excel.
        """
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Scene",
                    "Scene Title",
                    "Segment",
                    "Speaker",
                    "Voice Profile",
                    "Delivery Style",
                    "Pace",
                    "Text",
                    "Planned Start",
                    "Planned End",
                    "Planned Scene Duration (s)",
                    "Actual Duration (s)",
                    "Output File Path",
                ]
            )
            for sc in project.scenes:
                if not sc.dialogue_segments:
                    writer.writerow(
                        [
                            sc.scene_number,
                            sc.title,
                            1,
                            sc.speaker_role,
                            sc.voice_name,
                            sc.delivery_style,
                            sc.pace,
                            sc.narration_text,
                            sc.target_start_time,
                            sc.target_end_time,
                            sc.target_duration_sec,
                            sc.actual_duration_sec,
                            sc.scene_wav_path or "",
                        ]
                    )
                else:
                    for seg in sc.dialogue_segments:
                        writer.writerow(
                            [
                                sc.scene_number,
                                sc.title,
                                seg.index + 1,
                                seg.speaker_role,
                                seg.voice_name,
                                seg.delivery_style,
                                seg.pace,
                                seg.text,
                                sc.target_start_time,
                                sc.target_end_time,
                                sc.target_duration_sec,
                                seg.duration_sec if seg.duration_sec > 0 else sc.actual_duration_sec,
                                seg.output_wav_path or sc.scene_wav_path or "",
                            ]
                        )
        return out_path

    def export_approximate_srt(self, project: ScriptProject, out_path: Path) -> Path:
        """
        Exports an approximate SRT subtitle/caption draft clearly labeled as approximate
        (computed from generated segment/scene audio durations or planned scene windows,
        never claiming word-level forced alignment).
        """
        out_path.parent.mkdir(parents=True, exist_ok=True)
        lines: List[str] = [
            "NOTE: APPROXIMATE SUBTITLE DRAFT — Timestamps are estimated from scene/segment audio durations, not word-level forced alignment.",
            "",
        ]
        cue_index = 1
        running_sec = 0.0

        for sc in project.scenes:
            segs = sc.dialogue_segments
            if not segs:
                continue

            # Determine if actual segment durations are available
            has_actual_segs = all(s.duration_sec > 0 for s in segs)
            total_chars = max(1, sum(len(s.text) for s in segs))

            if not has_actual_segs and sc.target_start_sec >= running_sec:
                running_sec = sc.target_start_sec

            for i, seg in enumerate(segs):
                if has_actual_segs:
                    seg_dur = seg.duration_sec
                    pause_s = (
                        (seg.pause_after_ms / 1000.0)
                        * VoiceDirectionValidator.PACE_PAUSE_MULTIPLIER.get(seg.pace, 1.0)
                        if i < len(segs) - 1
                        else (sc.pause_after_scene_ms / 1000.0)
                    )
                else:
                    # Proportional estimate across planned scene target duration
                    scene_budget = sc.target_duration_sec if sc.target_duration_sec > 0 else 15.0
                    seg_dur = round(scene_budget * (len(seg.text) / total_chars), 2)
                    pause_s = 0.0

                start_ts = format_sec_to_srt_timestamp(running_sec)
                end_ts = format_sec_to_srt_timestamp(running_sec + seg_dur)
                speaker_prefix = f"[{seg.speaker_role}] " if len(segs) > 1 else ""

                lines.append(str(cue_index))
                lines.append(f"{start_ts} --> {end_ts}")
                lines.append(f"{speaker_prefix}{seg.text}")
                lines.append("")

                cue_index += 1
                running_sec += seg_dur + pause_s

        out_path.write_text("\n".join(lines), encoding="utf-8")
        return out_path

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_mode(mode: str) -> str:
        m = (mode or "tts").strip().lower()
        if m in ("voice cloning", "cloning", "controllable cloning"):
            return "cloning"
        if m in ("ultimate cloning", "ultimate_cloning", "hi-fi", "hifi"):
            return "ultimate_cloning"
        return "tts"

    def _resolve_profile_input(self, voice_profile_id: Optional[str]) -> Tuple[Optional[str], str]:
        if not voice_profile_id or voice_profile_id in ("Default Voice", "Default Voice (No Profile)", ""):
            return None, "Default Voice"
        clean_id = voice_profile_id
        if "(" in voice_profile_id and voice_profile_id.endswith(")"):
            clean_id = voice_profile_id.split("(")[-1].rstrip(")").strip()
        prof = self.db.get_voice_profile(clean_id)
        if not prof:
            raise ValueError(f"Voice profile '{clean_id}' not found.")
        return prof.id, prof.name

    def _resolve_segment_conditioning(
        self,
        project: ScriptProject,
        scene: StoryboardScene,
        seg: DialogueSegment,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
        """
        Resolves (reference_wav_path, prompt_wav_path, prompt_text, mode) for a segment.
        """
        prof_id = seg.voice_profile_id
        mode = seg.mode
        if not prof_id:
            rcfg = project.role_voice_map.get(seg.speaker_role, {})
            prof_id = rcfg.get("voice_profile_id") or scene.voice_profile_id
            if not mode or mode == "tts":
                mode = rcfg.get("mode", mode)

        norm_mode = self._normalize_mode(mode)
        if not prof_id:
            return None, None, None, "tts"

        prof = self.db.get_voice_profile(prof_id)
        if not prof:
            return None, None, None, "tts"

        seg.voice_profile_id = prof.id
        seg.voice_name = prof.name
        ref_wav = prof.reference_segment_path
        prompt_wav = prof.reference_segment_path
        prompt_txt = prof.transcript

        if norm_mode == "ultimate_cloning":
            if not ref_wav or not Path(ref_wav).exists() or not prompt_txt or not prompt_txt.strip():
                # Fallback to controllable cloning if transcript is missing
                norm_mode = "cloning" if (ref_wav and Path(ref_wav).exists()) else "tts"
        elif norm_mode == "cloning":
            if not ref_wav or not Path(ref_wav).exists():
                norm_mode = "tts"

        return ref_wav, prompt_wav, prompt_txt, norm_mode

    @staticmethod
    def _find_scene(project: ScriptProject, scene_id: str) -> StoryboardScene:
        for sc in project.scenes:
            if sc.scene_id == scene_id or f"Scene {sc.scene_number}" == scene_id:
                return sc
        raise ValueError(f"Scene '{scene_id}' not found in project '{project.project_id}'.")

    @staticmethod
    def _find_segment(scene: StoryboardScene, segment_id: str) -> DialogueSegment:
        for seg in scene.dialogue_segments:
            if seg.segment_id == segment_id or f"Segment {seg.index + 1}" == segment_id:
                return seg
        raise ValueError(f"Segment '{segment_id}' not found in scene '{scene.scene_id}'.")
