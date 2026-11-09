"""Service managing Voice Profile creation, storage, and lifecycle."""
import json
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from app.config import VOICES_DIR, NATIVE_SAMPLE_RATE
from app.audio.processor import AudioProcessor
from app.database.connection import DatabaseManager
from app.database.models import VoiceProfile

def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class VoiceProfileService:
    """Manages voice profiles, safe file storage, and segment references."""
    _instance: Optional["VoiceProfileService"] = None

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    @classmethod
    def get_instance(cls) -> "VoiceProfileService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_profile(
        self,
        name: str,
        original_audio_path: str | Path = "",
        description: str = "",
        language: str = "multilingual",
        transcript: str = "",
        trim_start_sec: Optional[float] = None,
        trim_end_sec: Optional[float] = None,
        display_name: str = "",
        khmer_display_name: str = "",
        category: str = "general",
        gender: str = "unspecified",
        speaking_style: str = "Natural",
        origin: str = "user_created",
        source_license: str = "Local User Audio",
        preview_audio_path: Optional[str] = None,
        preview_type: str = "reference",
        is_favorite: int = 0,
        is_default: int = 0,
        validation_status: str = "verified"
    ) -> Tuple[Optional[VoiceProfile], str]:
        """
        Creates a new voice profile, saving both the original audio and the processed
        reference segment in dedicated storage on Drive D:.
        Supports both verified audio profiles and catalog persona templates.
        """
        clean_name = name.strip()
        if not clean_name:
            return None, "Voice profile name cannot be empty."

        existing = self.db.get_voice_profile_by_name(clean_name)
        # If an existing profile is a template and we are providing audio, upgrade it
        if existing:
            if existing.validation_status == "template" and original_audio_path:
                ok, msg = self.replace_reference_audio(
                    profile_id=existing.id,
                    new_audio_path=original_audio_path,
                    trim_start_sec=trim_start_sec,
                    trim_end_sec=trim_end_sec,
                    new_transcript=transcript or existing.transcript
                )
                if ok:
                    upgraded = self.db.get_voice_profile(existing.id)
                    if upgraded:
                        upgraded.validation_status = "verified"
                        if display_name:
                            upgraded.display_name = display_name
                        if category:
                            upgraded.category = category
                        if gender:
                            upgraded.gender = gender
                        self.db.update_voice_profile(upgraded)
                        return upgraded, f"Template '{clean_name}' successfully activated with audio!"
                return None, f"Failed to activate template: {msg}"
            return None, f"A voice profile named '{clean_name}' already exists."

        # Template-only profile creation (no audio yet)
        if validation_status == "template" and not original_audio_path:
            profile_id = f"prof_tpl_{uuid.uuid4().hex[:10]}"
            now = utc_iso_now()
            profile = VoiceProfile(
                id=profile_id,
                name=clean_name,
                description=description.strip(),
                language=language,
                original_audio_path="",
                reference_segment_path="",
                transcript=transcript.strip(),
                duration_sec=0.0,
                sample_rate=NATIVE_SAMPLE_RATE,
                created_at=now,
                updated_at=now,
                display_name=display_name.strip() or clean_name,
                khmer_display_name=khmer_display_name.strip(),
                category=category.lower(),
                gender=gender.lower(),
                speaking_style=speaking_style.strip(),
                origin=origin,
                source_license=source_license,
                preview_audio_path="",
                preview_type="none",
                is_favorite=is_favorite,
                is_default=is_default,
                validation_status="template"
            )
            self.db.create_voice_profile(profile)
            return profile, f"Voice persona template '{clean_name}' created."

        # Audio-backed profile creation
        in_p = Path(original_audio_path)
        valid, msg = AudioProcessor.validate_audio(in_p, min_duration=1.0, max_duration=360.0)
        if not valid:
            return None, f"Audio validation failed: {msg}"

        profile_id = f"prof_{uuid.uuid4().hex[:12]}"
        prof_dir = VOICES_DIR / profile_id
        prof_dir.mkdir(parents=True, exist_ok=True)

        # 1. Safely store original audio (preserve pristine uploaded recording)
        orig_dest = prof_dir / f"original{in_p.suffix.lower()}"
        shutil.copy2(str(in_p), str(orig_dest))

        # 2. Extract or convert reference segment
        ref_dest = prof_dir / "reference.wav"
        if trim_start_sec is not None and trim_end_sec is not None and trim_end_sec > trim_start_sec:
            ref_meta = AudioProcessor.trim_audio_segment(
                input_path=orig_dest,
                output_path=ref_dest,
                start_sec=trim_start_sec,
                end_sec=trim_end_sec,
                target_sr=NATIVE_SAMPLE_RATE
            )
        else:
            ref_meta = AudioProcessor.convert_to_pcm16_mono(
                input_path=orig_dest,
                output_path=ref_dest,
                target_sr=NATIVE_SAMPLE_RATE
            )

        now = utc_iso_now()
        resolved_preview_path = preview_audio_path if (preview_audio_path and Path(preview_audio_path).exists()) else str(ref_dest)
        resolved_preview_type = preview_type if preview_audio_path else "reference"

        profile = VoiceProfile(
            id=profile_id,
            name=clean_name,
            description=description.strip(),
            language=language,
            original_audio_path=str(orig_dest),
            reference_segment_path=str(ref_dest),
            transcript=transcript.strip(),
            duration_sec=ref_meta.duration_sec,
            sample_rate=ref_meta.sample_rate,
            created_at=now,
            updated_at=now,
            display_name=display_name.strip() or clean_name,
            khmer_display_name=khmer_display_name.strip(),
            category=category.lower(),
            gender=gender.lower(),
            speaking_style=speaking_style.strip(),
            origin=origin,
            source_license=source_license,
            preview_audio_path=resolved_preview_path,
            preview_type=resolved_preview_type,
            is_favorite=is_favorite,
            is_default=is_default,
            validation_status="verified"
        )

        self.db.create_voice_profile(profile)
        self._save_profile_artifacts(profile, prof_dir)
        return profile, "Voice profile created successfully."

    def _save_profile_artifacts(self, profile: VoiceProfile, prof_dir: Path):
        """Saves transcript.txt and metadata.json in the profile storage directory."""
        try:
            prof_dir.mkdir(parents=True, exist_ok=True)
            trans_file = prof_dir / "transcript.txt"
            trans_file.write_text(profile.transcript or "", encoding="utf-8")

            meta_file = prof_dir / "metadata.json"
            meta_dict = {
                "id": profile.id,
                "name": profile.name,
                "display_name": profile.display_name,
                "khmer_display_name": profile.khmer_display_name,
                "category": profile.category,
                "gender": profile.gender,
                "speaking_style": profile.speaking_style,
                "origin": profile.origin,
                "source_license": profile.source_license,
                "description": profile.description,
                "language": profile.language,
                "original_audio_path": profile.original_audio_path,
                "reference_segment_path": profile.reference_segment_path,
                "preview_audio_path": profile.preview_audio_path,
                "preview_type": profile.preview_type,
                "is_favorite": profile.is_favorite,
                "is_default": profile.is_default,
                "validation_status": profile.validation_status,
                "transcript": profile.transcript,
                "duration_sec": profile.duration_sec,
                "sample_rate": profile.sample_rate,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at
            }
            meta_file.write_text(json.dumps(meta_dict, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def list_profiles(self) -> List[VoiceProfile]:
        return self.db.list_voice_profiles()

    def get_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        return self.db.get_voice_profile(profile_id)

    def get_default_profile(self) -> Optional[VoiceProfile]:
        return self.db.get_default_voice_profile()

    def set_favorite(self, profile_id: str, is_favorite: bool) -> Tuple[bool, str]:
        ok = self.db.set_voice_favorite(profile_id, is_favorite)
        if ok:
            return True, f"Voice {'added to' if is_favorite else 'removed from'} favorites."
        return False, "Failed to update favorite status."

    def set_default(self, profile_id: str) -> Tuple[bool, str]:
        ok = self.db.set_voice_default(profile_id)
        if ok:
            return True, "Default voice updated across Speech & Smart Script Studio."
        return False, "Failed to set default voice."

    def record_used(self, profile_id: str) -> bool:
        return self.db.record_voice_used(profile_id)

    def search_catalog(
        self,
        search_term: str = "",
        category: Optional[str] = None,
        gender: Optional[str] = None,
        origin: Optional[str] = None,
        favorites_only: bool = False,
        validation_status: Optional[str] = None
    ) -> List[VoiceProfile]:
        return self.db.search_voice_catalog(
            search_term=search_term,
            category=category,
            gender=gender,
            origin=origin,
            favorites_only=favorites_only,
            validation_status=validation_status
        )

    def update_profile(
        self,
        profile_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        language: Optional[str] = None,
        transcript: Optional[str] = None,
        new_trim_start: Optional[float] = None,
        new_trim_end: Optional[float] = None,
        display_name: Optional[str] = None,
        khmer_display_name: Optional[str] = None,
        category: Optional[str] = None,
        gender: Optional[str] = None,
        speaking_style: Optional[str] = None,
        source_license: Optional[str] = None,
        is_favorite: Optional[int] = None,
        is_default: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Updates profile metadata or re-trims reference slice without losing original audio."""
        prof = self.db.get_voice_profile(profile_id)
        if not prof:
            return False, "Profile not found."

        if name and name.strip() != prof.name:
            existing = self.db.get_voice_profile_by_name(name.strip())
            if existing and existing.id != profile_id:
                return False, f"Name '{name}' is already used by another profile."
            prof.name = name.strip()

        if description is not None:
            prof.description = description.strip()
        if language is not None:
            prof.language = language
        if transcript is not None:
            prof.transcript = transcript.strip()
        if display_name is not None:
            prof.display_name = display_name.strip()
        if khmer_display_name is not None:
            prof.khmer_display_name = khmer_display_name.strip()
        if category is not None:
            prof.category = category.lower()
        if gender is not None:
            prof.gender = gender.lower()
        if speaking_style is not None:
            prof.speaking_style = speaking_style.strip()
        if source_license is not None:
            prof.source_license = source_license.strip()
        if is_favorite is not None:
            prof.is_favorite = is_favorite
        if is_default is not None:
            prof.is_default = is_default

        # Re-trim reference slice from preserved original audio if requested and audio exists
        if (new_trim_start is not None and new_trim_end is not None and new_trim_end > new_trim_start
                and prof.original_audio_path and Path(prof.original_audio_path).exists()):
            ref_dest = Path(prof.reference_segment_path)
            meta = AudioProcessor.trim_audio_segment(
                input_path=prof.original_audio_path,
                output_path=ref_dest,
                start_sec=new_trim_start,
                end_sec=new_trim_end,
                target_sr=NATIVE_SAMPLE_RATE
            )
            prof.duration_sec = meta.duration_sec
            prof.sample_rate = meta.sample_rate
            prof.preview_audio_path = str(ref_dest)
            prof.preview_type = "reference"

        prof.updated_at = utc_iso_now()
        self.db.update_voice_profile(prof)
        self._save_profile_artifacts(prof, VOICES_DIR / profile_id)
        return True, "Profile updated successfully."

    def replace_reference_audio(
        self,
        profile_id: str,
        new_audio_path: str | Path,
        trim_start_sec: Optional[float] = None,
        trim_end_sec: Optional[float] = None,
        new_transcript: Optional[str] = None,
        transcript: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Replaces original recording and reference segment for an existing profile."""
        prof = self.db.get_voice_profile(profile_id)
        if not prof:
            return False, "Profile not found."

        in_p = Path(new_audio_path)
        valid, msg = AudioProcessor.validate_audio(in_p, min_duration=1.0, max_duration=360.0)
        if not valid:
            return False, f"Audio validation failed: {msg}"

        prof_dir = VOICES_DIR / profile_id
        prof_dir.mkdir(parents=True, exist_ok=True)

        orig_dest = prof_dir / f"original{in_p.suffix.lower()}"
        shutil.copy2(str(in_p), str(orig_dest))
        ref_dest = prof_dir / "reference.wav"

        if trim_start_sec is not None and trim_end_sec is not None and trim_end_sec > trim_start_sec:
            ref_meta = AudioProcessor.trim_audio_segment(
                input_path=orig_dest,
                output_path=ref_dest,
                start_sec=trim_start_sec,
                end_sec=trim_end_sec,
                target_sr=NATIVE_SAMPLE_RATE
            )
        else:
            ref_meta = AudioProcessor.convert_to_pcm16_mono(
                input_path=orig_dest,
                output_path=ref_dest,
                target_sr=NATIVE_SAMPLE_RATE
            )

        prof.original_audio_path = str(orig_dest)
        prof.reference_segment_path = str(ref_dest)
        prof.preview_audio_path = str(ref_dest)
        prof.preview_type = "reference"
        prof.duration_sec = ref_meta.duration_sec
        prof.sample_rate = ref_meta.sample_rate
        prof.validation_status = "verified"
        
        final_trans = transcript if transcript is not None else new_transcript
        if final_trans is not None:
            prof.transcript = final_trans.strip()
        prof.updated_at = utc_iso_now()

        self.db.update_voice_profile(prof)
        self._save_profile_artifacts(prof, prof_dir)
        return True, "Reference audio replaced successfully."

    def delete_profile(self, profile_id: str) -> Tuple[bool, str]:
        """Deletes voice profile record and cleans associated disk files safely."""
        prof = self.db.get_voice_profile(profile_id)
        if not prof:
            return False, "Profile not found."

        prof_dir = VOICES_DIR / profile_id
        if prof_dir.exists():
            try:
                shutil.rmtree(prof_dir)
            except Exception:
                pass

        self.db.delete_voice_profile(profile_id)
        return True, f"Voice profile '{prof.name}' deleted successfully."

    def import_voice_pack(
        self,
        file_or_dir_path: str | Path,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[VoiceProfile], str]:
        """
        Imports an authorized voice pack (.zip or audio file with optional metadata).
        Extracts reference audio, validates acoustics, and creates a verified VoiceProfile.
        """
        p = Path(file_or_dir_path)
        if not p.exists():
            return None, f"Voice pack path does not exist: {p}"

        meta = metadata.copy() if metadata else {}
        extracted_audio_path: Optional[Path] = None
        temp_dir: Optional[tempfile.TemporaryDirectory] = None

        try:
            if p.is_file() and p.suffix.lower() == ".zip":
                temp_dir = tempfile.TemporaryDirectory()
                extract_path = Path(temp_dir.name)
                with zipfile.ZipFile(p, "r") as zf:
                    zf.extractall(extract_path)

                # Look for manifest or metadata
                for meta_name in ("manifest.json", "metadata.json", "profile.json"):
                    cand = extract_path / meta_name
                    if cand.exists():
                        try:
                            file_meta = json.loads(cand.read_text(encoding="utf-8"))
                            for k, v in file_meta.items():
                                if k not in meta or not meta[k]:
                                    meta[k] = v
                        except Exception:
                            pass
                        break

                # Look for transcript file
                trans_cand = extract_path / "transcript.txt"
                if trans_cand.exists() and "transcript" not in meta:
                    meta["transcript"] = trans_cand.read_text(encoding="utf-8").strip()

                # Find primary audio file (prefer reference.wav or original.wav)
                audio_cands = []
                for ext in AudioProcessor.SUPPORTED_EXTENSIONS:
                    audio_cands.extend(list(extract_path.glob(f"*{ext}")))
                
                if not audio_cands:
                    return None, "No valid audio files (.wav, .mp3, etc.) found inside zip pack."

                # Prioritize reference or original
                pref = next((a for a in audio_cands if a.stem.lower() in ("reference", "voice", "original")), audio_cands[0])
                extracted_audio_path = pref

            elif p.is_file() and p.suffix.lower() in AudioProcessor.SUPPORTED_EXTENSIONS:
                extracted_audio_path = p
            else:
                return None, f"Unsupported voice pack format: {p.suffix}. Please upload .zip or .wav/.mp3 file."

            # Determine profile metadata
            name = meta.get("name") or p.stem.replace("_", " ").title()
            display_name = meta.get("display_name") or name
            khmer_display_name = meta.get("khmer_display_name") or ""
            desc = meta.get("description") or f"Imported voice pack: {p.name}"
            lang = meta.get("language") or "khmer"
            trans = meta.get("transcript") or ""
            cat = meta.get("category") or "general"
            gen = meta.get("gender") or "unspecified"
            style = meta.get("speaking_style") or "Natural"
            lic = meta.get("source_license") or "Imported Voice Pack (Authorized)"

            profile, msg = self.create_profile(
                name=name,
                original_audio_path=extracted_audio_path,
                description=desc,
                language=lang,
                transcript=trans,
                display_name=display_name,
                khmer_display_name=khmer_display_name,
                category=cat,
                gender=gen,
                speaking_style=style,
                origin="imported",
                source_license=lic,
                validation_status="verified"
            )
            return profile, msg

        except Exception as e:
            return None, f"Error importing voice pack: {str(e)}"
        finally:
            if temp_dir:
                try:
                    temp_dir.cleanup()
                except Exception:
                    pass

    def export_voice_pack(self, profile_id: str, export_dir: Optional[Path] = None) -> Tuple[Optional[Path], str]:
        """Creates a portable .zip voice pack for distribution and backup."""
        prof = self.db.get_voice_profile(profile_id)
        if not prof:
            return None, "Voice profile not found."

        prof_dir = VOICES_DIR / profile_id
        if not prof_dir.exists():
            return None, "Voice profile storage directory not found."

        out_dir = export_dir or prof_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in prof.name)
        zip_path = out_dir / f"VoicePack_{safe_name}_{prof.id}.zip"

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Include metadata.json
                meta_path = prof_dir / "metadata.json"
                if meta_path.exists():
                    zf.write(meta_path, arcname="metadata.json")
                # Include transcript
                trans_path = prof_dir / "transcript.txt"
                if trans_path.exists():
                    zf.write(trans_path, arcname="transcript.txt")
                # Include reference audio
                ref_path = Path(prof.reference_segment_path)
                if ref_path.exists():
                    zf.write(ref_path, arcname="reference.wav")
                # Include original audio if available
                orig_path = Path(prof.original_audio_path)
                if orig_path.exists() and orig_path != ref_path:
                    zf.write(orig_path, arcname=f"original{orig_path.suffix}")

            return zip_path, "Voice pack exported successfully."
        except Exception as e:
            return None, f"Failed to export voice pack: {str(e)}"

    def seed_khmer_voice_collection(self):
        """
        Seeds/upgrades the voice collection with rich metadata:
        1. Updates verified profiles (Narak / នរក្ស, Kosal / Stage 3 KH, David EN, Emma EN).
        2. Adds initial distinct Khmer voice persona templates (marked template) for easy import.
        """
        all_profs = self.db.list_voice_profiles()
        by_id = {p.id: p for p in all_profs}
        by_name = {p.name: p for p in all_profs}

        # 1. Enrich existing verified profiles
        if "prof_97f502d364b3" in by_id:
            p = by_id["prof_97f502d364b3"]
            p.display_name = "Narak (នរក្ស)"
            p.khmer_display_name = "នរក្ស"
            p.category = "educational"
            p.gender = "male"
            p.speaking_style = "Teaching / Clear Academic"
            p.origin = "user_created"
            p.source_license = "Authorised Local Recording"
            p.validation_status = "verified"
            p.preview_audio_path = p.reference_segment_path
            p.preview_type = "reference"
            p.is_favorite = 1
            p.is_default = 1
            self.db.update_voice_profile(p)
            self._save_profile_artifacts(p, VOICES_DIR / p.id)

        if "prof_d0fd33d8bdc7" in by_id:
            p = by_id["prof_d0fd33d8bdc7"]
            p.display_name = "Kosal (កុសល)"
            p.khmer_display_name = "កុសល"
            p.category = "conversational"
            p.gender = "male"
            p.speaking_style = "Friendly / Conversational"
            p.origin = "bundled"
            p.source_license = "Stage 3 Reference Voice"
            p.validation_status = "verified"
            p.preview_audio_path = p.reference_segment_path
            p.preview_type = "reference"
            self.db.update_voice_profile(p)
            self._save_profile_artifacts(p, VOICES_DIR / p.id)

        if "prof_1b30778f90fa" in by_id:
            p = by_id["prof_1b30778f90fa"]
            p.display_name = "David (Standard English)"
            p.category = "professional"
            p.gender = "male"
            p.speaking_style = "Articulate / Broadcast"
            p.origin = "bundled"
            p.preview_audio_path = p.reference_segment_path
            p.preview_type = "reference"
            self.db.update_voice_profile(p)

        if "prof_2d14c9894032" in by_id:
            p = by_id["prof_2d14c9894032"]
            p.display_name = "Emma (Casual English)"
            p.category = "conversational"
            p.gender = "female"
            p.speaking_style = "Warm / Conversational"
            p.origin = "bundled"
            p.preview_audio_path = p.reference_segment_path
            p.preview_type = "reference"
            self.db.update_voice_profile(p)

        # 2. Seed curated persona templates if they don't already exist
        persona_templates = [
            {
                "name": "Maly (ម៉ាលី)",
                "display_name": "Maly (ម៉ាលី)",
                "khmer_display_name": "ម៉ាលី",
                "category": "educational",
                "gender": "female",
                "speaking_style": "Warm Educational / Gentle Instructor",
                "description": "Ideal for online tutorials, student lectures, and educational e-learning modules.",
                "transcript": "សូមស្វាគមន៍មកកាន់មេរៀនបច្ចេកវិទ្យាព័ត៌មានថ្ងៃនេះ។ យើងនឹងសិក្សាអំពីបញ្ញាសិប្បនិម្មិត។"
            },
            {
                "name": "Bopha (បុប្ផា)",
                "display_name": "Bopha (បុប្ផា)",
                "khmer_display_name": "បុប្ផា",
                "category": "storytelling",
                "gender": "female",
                "speaking_style": "Expressive Narrative / Children's Fable",
                "description": "Engaging, melodious voice for audiobooks, folktales, and creative storytelling.",
                "transcript": "កាលពីព្រេងនាយ នៅជើងភ្នំដ៏ស្រស់បំព្រងមួយ មានភូមិតូចមួយរស់នៅយ៉ាងសុខសាន្ត។"
            },
            {
                "name": "Sophea (សុភា)",
                "display_name": "Sophea (សុភា)",
                "khmer_display_name": "សុភា",
                "category": "professional",
                "gender": "female",
                "speaking_style": "Corporate / Official Presentation",
                "description": "Clear, polished, and confident delivery for formal institutional announcements.",
                "transcript": "សូមគោរពជម្រាបសួរលោកលោកស្រី និងភ្ញៀវកិត្តិយសទាំងអស់ ដែលបានចូលរួមកម្មវិធីនៅថ្ងៃនេះ។"
            },
            {
                "name": "Chann (ចាន់)",
                "display_name": "Chann (ចាន់)",
                "khmer_display_name": "ចាន់",
                "category": "professional",
                "gender": "male",
                "speaking_style": "Authoritative News / Documentary",
                "description": "Deep, balanced, and articulate tone for documentary narration and daily news broadcasts.",
                "transcript": "ព្រឹត្តិការណ៍ព័ត៌មានវិទ្យាសាស្ត្រនិងបច្ចេកវិទ្យាប្រចាំសប្តាហ៍ ពីស្ទូឌីយោសំឡេង។"
            },
            {
                "name": "Rithy (រិទ្ធី)",
                "display_name": "Rithy (រិទ្ធី)",
                "khmer_display_name": "រិទ្ធី",
                "category": "conversational",
                "gender": "male",
                "speaking_style": "Energetic Youth / Modern Dynamic",
                "description": "Upbeat, casual voice designed for mobile apps, gaming dialogue, and social media clips.",
                "transcript": "សួស្តីអ្នកទាំងអស់គ្នា! តោះយើងមកសាកល្បងមុខងារថ្មីដ៏អស្ចារ្យជាមួយគ្នានៅថ្ងៃនេះ!"
            },
            {
                "name": "Kanya (កញ្ញា)",
                "display_name": "Kanya (កញ្ញា)",
                "khmer_display_name": "កញ្ញា",
                "category": "conversational",
                "gender": "female",
                "speaking_style": "Friendly Digital Assistant / Concierge",
                "description": "Polite, helpful customer service and intelligent voice assistant persona.",
                "transcript": "តើខ្ញុំអាចជួយលោកអ្នកស្វែងរកព័ត៌មានអ្វីខ្លះនៅពេលនេះ? ខ្ញុំត្រៀមខ្លួនជានិច្ច។"
            },
            {
                "name": "Piseth (ពិសិដ្ឋ)",
                "display_name": "Piseth (ពិសិដ្ឋ)",
                "khmer_display_name": "ពិសិដ្ឋ",
                "category": "presentation",
                "gender": "male",
                "speaking_style": "Reflective / Historical Narration",
                "description": "Resonant, slow-paced narration for historical accounts and intellectual lectures.",
                "transcript": "ប្រវត្តិសាស្ត្រជាតិយើង បានបន្សល់ទុកនូវកេរដំណែលវប្បធម៌ដ៏វិសេសវិសាល។"
            },
            {
                "name": "Vireak (វិរៈ)",
                "display_name": "Vireak (វិរៈ)",
                "khmer_display_name": "វិរៈ",
                "category": "storytelling",
                "gender": "male",
                "speaking_style": "Dramatic Character / Adventure",
                "description": "Bold character tone for cinematic dialogues and action-packed narrations.",
                "transcript": "ប្រយ័ត្ន! ដំណើរផ្សងព្រេងក្នុងព្រៃជ្រៅទើបតែចាប់ផ្តើមប៉ុណ្ណោះ ត្រូវប្រុងប្រយ័ត្នខ្ពស់!"
            }
        ]

        # Re-check current names
        current_names = {p.name for p in self.db.list_voice_profiles()}
        for tpl in persona_templates:
            if tpl["name"] not in current_names:
                self.create_profile(
                    name=tpl["name"],
                    original_audio_path="",
                    description=tpl["description"],
                    language="khmer",
                    transcript=tpl["transcript"],
                    display_name=tpl["display_name"],
                    khmer_display_name=tpl["khmer_display_name"],
                    category=tpl["category"],
                    gender=tpl["gender"],
                    speaking_style=tpl["speaking_style"],
                    origin="template",
                    source_license="Ready to Import Audio",
                    validation_status="template"
                )
