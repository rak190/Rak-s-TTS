"""
Smart Script & Educational Storyboard Parser for VoiceStudio Pro.
Supports importing .docx, .txt, .md, and pasted Khmer/English storyboard scripts.
Strictly separates spoken narration and multi-speaker dialogue from visual directions,
keywords, music/SFX metadata, timestamps, and pre-export checklists.
"""
import json
import re
import unicodedata
import uuid
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.utils.text_processor import TextProcessor

SUPPORTED_SPEAKER_ROLES = [
    "Narrator",
    "Teacher",
    "Student",
    "Robot",
    "Custom Character",
]

SUPPORTED_DELIVERY_STYLES = [
    "Natural",
    "Friendly",
    "Educational",
    "Curious",
    "Cheerful",
    "Excited",
    "Calm",
    "Serious",
    "Gentle",
    "Playful",
]

SUPPORTED_PACES = [
    "Slow",
    "Medium",
    "Fast",
]

KHMER_DIGIT_MAP = str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def khmer_digits_to_ascii(text: str) -> str:
    """Converts Khmer numerals (០-៩) to ASCII digits (0-9)."""
    if not text:
        return ""
    return text.translate(KHMER_DIGIT_MAP)


def parse_timecode_to_sec(tc: str) -> float:
    """
    Parses a MM:SS or HH:MM:SS string (with ASCII or Khmer digits) into seconds.
    """
    if not tc:
        return 0.0
    clean = khmer_digits_to_ascii(tc.strip())
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", clean)
    if not m:
        return 0.0
    if m.group(3) is not None:
        hours = int(m.group(1))
        minutes = int(m.group(2))
        seconds = int(m.group(3))
        return float(hours * 3600 + minutes * 60 + seconds)
    minutes = int(m.group(1))
    seconds = int(m.group(2))
    return float(minutes * 60 + seconds)


def format_sec_to_timecode(seconds: float) -> str:
    """Formats seconds into MM:SS (or HH:MM:SS if >= 3600)."""
    sec_int = max(0, int(round(seconds)))
    if sec_int >= 3600:
        h = sec_int // 3600
        m = (sec_int % 3600) // 60
        s = sec_int % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    m = sec_int // 60
    s = sec_int % 60
    return f"{m:02d}:{s:02d}"


def format_sec_to_srt_timestamp(seconds: float) -> str:
    """Formats seconds into SRT timestamp HH:MM:SS,mmm."""
    total_ms = max(0, int(round(seconds * 1000)))
    h = total_ms // 3600000
    rem = total_ms % 3600000
    m = rem // 60000
    rem = rem % 60000
    s = rem // 1000
    ms = rem % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


@dataclass
class DialogueSegment:
    segment_id: str
    index: int
    speaker_role: str = "Narrator"
    custom_speaker_name: str = ""
    text: str = ""
    voice_profile_id: Optional[str] = None
    voice_name: str = "Default Voice"
    mode: str = "tts"  # 'tts', 'cloning', 'ultimate_cloning'
    delivery_style: str = "Natural"
    pace: str = "Medium"
    pause_after_ms: int = 280
    enable_style_prefix: bool = False
    status: str = "pending"  # pending, processing, completed, failed
    output_wav_path: Optional[str] = None
    duration_sec: float = 0.0
    generation_time_sec: float = 0.0
    error_message: str = ""


@dataclass
class StoryboardScene:
    scene_id: str
    scene_number: int
    title: str
    target_start_time: str = "00:00"
    target_end_time: str = "00:00"
    target_start_sec: float = 0.0
    target_end_sec: float = 0.0
    target_duration_sec: float = 0.0
    narration_text: str = ""
    dialogue_segments: List[DialogueSegment] = field(default_factory=list)
    speaker_role: str = "Teacher"
    voice_profile_id: Optional[str] = None
    voice_name: str = "Default Voice"
    delivery_style: str = "Educational"
    pace: str = "Medium"
    visual_notes: str = ""
    music_notes: str = ""
    sfx_notes: str = ""
    keywords: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    pause_after_scene_ms: int = 400
    stretch_ratio: float = 1.0  # 1.0 = preserve natural duration
    status: str = "pending"  # pending, processing, partial, completed, failed
    scene_wav_path: Optional[str] = None
    scene_mp3_path: Optional[str] = None
    actual_duration_sec: float = 0.0
    duration_diff_sec: float = 0.0


@dataclass
class ScriptProject:
    project_id: str
    title: str
    subtitle: str = ""
    topic: str = ""
    source_filename: str = ""
    source_copy_path: str = ""
    audience: str = ""
    planned_duration_label: str = ""
    planned_duration_sec: float = 0.0
    aspect_ratio: str = ""
    visual_style: str = ""
    voice_production_notes: str = ""
    requested_voice_preset: str = ""
    music_production_notes: str = ""
    style_production_notes: str = ""
    text_production_notes: str = ""
    education_production_notes: str = ""
    checklist_items: List[str] = field(default_factory=list)
    production_footer_note: str = ""
    role_voice_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    scenes: List[StoryboardScene] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    status: str = "draft"
    combined_wav_path: Optional[str] = None
    combined_mp3_path: Optional[str] = None
    actual_total_duration_sec: float = 0.0
    created_at: str = field(default_factory=utc_iso_now)
    updated_at: str = field(default_factory=utc_iso_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScriptProject":
        scenes_raw = data.get("scenes", [])
        scenes: List[StoryboardScene] = []
        for s_dict in scenes_raw:
            segs_raw = s_dict.get("dialogue_segments", [])
            segs = [DialogueSegment(**seg) for seg in segs_raw]
            s_copy = dict(s_dict)
            s_copy["dialogue_segments"] = segs
            scenes.append(StoryboardScene(**s_copy))
        p_copy = dict(data)
        p_copy["scenes"] = scenes
        return cls(**p_copy)


class VoiceDirectionValidator:
    """
    Validates and formats voice delivery styles and speaking paces for VoxCPM2.
    Ensures Hi-Fi / Ultimate Cloning never exposes fake emotion prompts and
    Khmer narration never speaks raw English style directions aloud.
    """

    STYLE_DESCRIPTORS = {
        "Natural": "",
        "Friendly": "friendly and warm tone",
        "Educational": "clear, engaging educational teacher tone",
        "Curious": "curious and inquisitive tone",
        "Cheerful": "cheerful and bright tone",
        "Excited": "excited and energetic tone",
        "Calm": "calm and composed tone",
        "Serious": "serious and authoritative tone",
        "Gentle": "gentle and soft tone",
        "Playful": "playful and lively tone",
    }

    PACE_DESCRIPTORS = {
        "Slow": "slow speaking pace",
        "Medium": "",
        "Fast": "slightly faster speaking pace",
    }

    PACE_PAUSE_MULTIPLIER = {
        "Slow": 1.25,
        "Medium": 1.0,
        "Fast": 0.80,
    }

    @classmethod
    def strip_accidental_directions(cls, text: str) -> str:
        """
        Removes surrounding guillemets «...» and accidental leading parenthesized
        English style directions when style prefix injection is disabled.
        """
        if not text:
            return ""
        cleaned = unicodedata.normalize("NFC", text).strip()
        # Strip outer guillemets if the entire segment is wrapped in them
        if cleaned.startswith("«") and cleaned.endswith("»"):
            cleaned = cleaned[1:-1].strip()
        return cleaned

    @classmethod
    def check_mode_compatibility(
        cls,
        mode: str,
        delivery_style: str,
        pace: str,
        language: str,
        enable_style_prefix: bool = False,
    ) -> Tuple[bool, str]:
        """
        Returns (is_style_prefix_active, explanation_message).
        """
        norm_mode = mode.lower().strip()
        if norm_mode in ("ultimate_cloning", "ultimate cloning", "hi-fi"):
            return (
                False,
                "🔒 Hi-Fi / Ultimate Cloning uses verbatim audio continuation and ignores style/pace text instructions. "
                "Switch to Controllable Voice Cloning or Ordinary TTS if you want style prompt steering.",
            )

        has_non_default = (delivery_style != "Natural") or (pace != "Medium")
        if not has_non_default:
            return False, "ℹ️ Natural delivery & Medium pace active (no style prefix needed)."

        if language in ("khmer", "mixed") and not enable_style_prefix:
            return (
                False,
                f"🛡️ Safe Khmer Delivery Active: Style '{delivery_style}' & Pace '{pace}' are stored as scene metadata "
                "and pause timing without injecting English parenthesized tokens into Khmer speech.",
            )

        return (
            True,
            f"✅ Controllable Style Active: VoxCPM2 style descriptor for '{delivery_style}' ({pace}) enabled.",
        )

    @classmethod
    def build_synthesis_prompt(
        cls,
        spoken_text: str,
        delivery_style: str = "Natural",
        pace: str = "Medium",
        mode: str = "tts",
        language: Optional[str] = None,
        enable_style_prefix: bool = False,
    ) -> Tuple[str, str]:
        """
        Builds the exact text string sent to VoxCPM2Adapter while guaranteeing
        style instructions are never spoken aloud inappropriately.
        """
        clean_text = cls.strip_accidental_directions(spoken_text)
        # If someone pasted a leading English parenthesized instruction like "(friendly tone) សួស្តី"
        # and style prefix is disabled or Hi-Fi mode is used, strip that leading parenthesized instruction.
        if not enable_style_prefix or mode in ("ultimate_cloning", "Ultimate Cloning"):
            clean_text = re.sub(
                r"^\([a-zA-Z\s,;:\-]+\)\s*(?=[\u1780-\u17FF])",
                "",
                clean_text,
            ).strip()

        detected_lang = language or TextProcessor.detect_language(clean_text)
        is_active, explanation = cls.check_mode_compatibility(
            mode=mode,
            delivery_style=delivery_style,
            pace=pace,
            language=detected_lang,
            enable_style_prefix=enable_style_prefix,
        )

        if not is_active:
            return clean_text, explanation

        parts = []
        style_desc = cls.STYLE_DESCRIPTORS.get(delivery_style, "")
        pace_desc = cls.PACE_DESCRIPTORS.get(pace, "")
        if style_desc:
            parts.append(style_desc)
        if pace_desc:
            parts.append(pace_desc)

        if not parts:
            return clean_text, explanation

        prefix = f"({', '.join(parts)})"
        return f"{prefix}{clean_text}", explanation


class StoryboardParser:
    """
    Parses structured educational storyboards and narration scripts (.docx, .txt, .md, or raw text).
    Specifically engineered for Khmer & bilingual ICT/educational storyboards such as
    ICT_Grade8_AI_Animation_Video_Storyboard_KM.docx.
    """

    # Matches scene headers such as:
    # "1. HOOK: តើទូរស័ព្ទកំពុងគិតជំនួសយើងមែនទេ?  [00:00–00:22]"
    # "2. ១. តើ AI ជាអ្វី?  [00:22–00:55]"
    # "Scene 1: Introduction [00:00-00:30]"
    SCENE_HEADER_REGEX = re.compile(
        r"^(?:#+\s*)?(?:Scene\s*|ឈុតទី\s*)?(?:([0-9០-៩]+)[\.\)]\s*)?"
        r"(.+?)\s*\[\s*([0-9០-៩]{1,2}:[0-9០-៩]{2}(?::[0-9០-៩]{2})?)\s*[\-–—~ដល់to]+\s*"
        r"([0-9០-៩]{1,2}:[0-9០-៩]{2}(?::[0-9០-៩]{2})?)\s*\]\s*$",
        re.IGNORECASE,
    )

    # Spoken narration markers
    NARRATION_MARKER_REGEX = re.compile(
        r"^(?:[•\-\*]\s*)?(?:សំឡេងអាន|អត្ថបទអាន|សំឡេងនិយាយ|Narration|Voiceover|Spoken)\s*[៖:]\s*(.*)$",
        re.IGNORECASE,
    )

    # Visual / animation markers (strictly non-spoken)
    VISUAL_MARKER_REGEX = re.compile(
        r"^(?:[•\-\*]\s*)?(?:រូបភាព\s*និង\s*ចលនា|រូបភាពនិងចលនា|រូបភាព|ចលនា|Visuals?|Animation)\s*[៖:]\s*(.*)$",
        re.IGNORECASE,
    )

    # Production setting markers in Section 1
    PROD_VOICE_REGEX = re.compile(r"^(?:[•\-\*]\s*)?សំឡេង\s*[៖:]\s*(.*)$")
    PROD_MUSIC_REGEX = re.compile(r"^(?:[•\-\*]\s*)?តន្ត្រី\s*[៖:]\s*(.*)$")
    PROD_STYLE_REGEX = re.compile(r"^(?:[•\-\*]\s*)?រចនាបថ\s*[៖:]\s*(.*)$")
    PROD_TEXT_REGEX = re.compile(r"^(?:[•\-\*]\s*)?អត្ថបទ\s*[៖:]\s*(.*)$")
    PROD_EDU_REGEX = re.compile(r"^(?:[•\-\*]\s*)?ការអប់រំ\s*[៖:]\s*(.*)$")

    # Section headings
    SECTION_1_REGEX = re.compile(r"^[១1][\.\)]\s*ការកំណត់ផលិតកម្ម")
    SECTION_2_REGEX = re.compile(r"^[២2][\.\)]\s*Storyboard", re.IGNORECASE)
    SECTION_3_REGEX = re.compile(r"^[៣3][\.\)]\s*ការត្រួតពិនិត្យមុន\s*Export", re.IGNORECASE)

    # Checklist & footer markers (strictly non-spoken)
    CHECKLIST_LINE_REGEX = re.compile(r"^(?:[☐☑✓✔]|\-\s*\[\s*[xX ]?\s*\])\s*(.+)$")
    FOOTER_NOTE_REGEX = re.compile(r"^(?:ចំណាំ|សម្គាល់|Note)\s*[៖:]\s*(.*)$", re.IGNORECASE)

    @classmethod
    def extract_blocks_from_docx(cls, docx_path: str | Path) -> Tuple[List[str], List[List[List[str]]]]:
        """
        Extracts paragraphs and tables from a .docx file while preserving 100% of Khmer Unicode.
        Uses python-docx if installed, with a built-in zero-dependency OpenXML parser.
        Returns (paragraphs, tables) where each table is a list of rows (list of cell strings).
        """
        p = Path(docx_path)
        if not p.exists():
            raise FileNotFoundError(f"DOCX file not found: {docx_path}")

        paragraphs: List[str] = []
        tables: List[List[List[str]]] = []

        # Parse directly from OpenXML word/document.xml to preserve exact document order and Khmer Unicode
        with zipfile.ZipFile(p, "r") as zf:
            if "word/document.xml" not in zf.namelist():
                raise ValueError(f"Invalid .docx archive (missing word/document.xml): {docx_path}")
            xml_bytes = zf.read("word/document.xml")

        root = ET.fromstring(xml_bytes)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        body = root.find("w:body", ns)
        if body is None:
            return paragraphs, tables

        for child in list(body):
            tag = child.tag.split("}")[-1]
            if tag == "p":
                text = "".join(child.itertext())
                text = unicodedata.normalize("NFC", text).strip()
                if text:
                    paragraphs.append(text)
            elif tag == "tbl":
                table_rows: List[List[str]] = []
                for tr in child.findall(".//w:tr", ns):
                    row_cells: List[str] = []
                    for tc in tr.findall("./w:tc", ns):
                        cell_paras = [
                            unicodedata.normalize("NFC", "".join(wp.itertext())).strip()
                            for wp in tc.findall(".//w:p", ns)
                        ]
                        cell_text = " ".join([cp for cp in cell_paras if cp]).strip()
                        row_cells.append(cell_text)
                    if any(row_cells):
                        table_rows.append(row_cells)
                if table_rows:
                    tables.append(table_rows)

        return paragraphs, tables

    @classmethod
    def parse_file(
        cls,
        file_path: str | Path,
        available_voice_profiles: Optional[List[Any]] = None,
    ) -> ScriptProject:
        """
        Parses a .docx, .txt, or .md file into a structured ScriptProject.
        """
        p = Path(file_path)
        ext = p.suffix.lower()
        if ext == ".docx":
            paragraphs, tables = cls.extract_blocks_from_docx(p)
            return cls._parse_blocks(
                paragraphs=paragraphs,
                tables=tables,
                source_filename=p.name,
                available_voice_profiles=available_voice_profiles,
            )
        else:
            raw_text = p.read_text(encoding="utf-8")
            return cls.parse_text(
                raw_text=raw_text,
                source_filename=p.name,
                available_voice_profiles=available_voice_profiles,
            )

    @classmethod
    def parse_text(
        cls,
        raw_text: str,
        source_filename: str = "pasted_script.txt",
        available_voice_profiles: Optional[List[Any]] = None,
    ) -> ScriptProject:
        """
        Parses raw pasted text or .txt/.md content into a structured ScriptProject.
        """
        if not raw_text or not raw_text.strip():
            raise ValueError("Script content cannot be empty.")

        normalized = unicodedata.normalize("NFC", raw_text)
        lines = [ln.strip() for ln in normalized.splitlines() if ln.strip()]
        return cls._parse_blocks(
            paragraphs=lines,
            tables=[],
            source_filename=source_filename,
            available_voice_profiles=available_voice_profiles,
        )

    @classmethod
    def _parse_visual_line_details(cls, visual_line: str) -> Tuple[str, List[str], str, str]:
        """
        Splits a visual direction line into:
        (clean_visual_notes, keywords_list, sfx_notes, music_notes)
        """
        visual_text = visual_line.strip()
        keywords: List[str] = []
        sfx_notes_list: List[str] = []
        music_notes_list: List[str] = []

        # Extract Keywords ("ពាក្យគន្លឹះ៖ ...")
        kw_match = re.search(r"ពាក្យគន្លឹះ\s*[៖:]\s*([^។\.।]+(?:[។\.।]|$))", visual_text)
        if kw_match:
            kw_raw = kw_match.group(1).strip().rstrip("។.।")
            keywords = [k.strip().rstrip("។.।") for k in re.split(r"[/,;|]", kw_raw) if k.strip()]

        # Extract SFX notes ("សំឡេង SFX ..." or "SFX: ...")
        sfx_matches = re.findall(r"((?:សំឡេង\s*)?SFX[^។\.]*(?:[។\.]|$))", visual_text, flags=re.IGNORECASE)
        for sm in sfx_matches:
            sfx_clean = sm.strip().rstrip("។.")
            if sfx_clean and sfx_clean not in sfx_notes_list:
                sfx_notes_list.append(sfx_clean)

        return (
            visual_text,
            keywords,
            "; ".join(sfx_notes_list),
            "; ".join(music_notes_list),
        )

    @classmethod
    def _infer_role_and_style_from_intro(cls, intro_text: str) -> Tuple[str, str]:
        """
        Determines the character role and default delivery style for a quoted dialogue line
        based on the preceding narrator intro clause.
        """
        lower_intro = intro_text.lower()
        # Look at the clause closest to the speaking verb (rightmost mention)
        student_pos = max(intro_text.rfind("សិស្ស"), lower_intro.rfind("student"))
        robot_pos = max(lower_intro.rfind("robot"), intro_text.rfind("រ៉ូបូត"))
        teacher_pos = max(intro_text.rfind("គ្រូ"), lower_intro.rfind("teacher"))

        best_pos = max(student_pos, robot_pos, teacher_pos)
        if best_pos == -1:
            return "Custom Character", "Friendly"
        if best_pos == robot_pos:
            return "Robot", "Cheerful"
        if best_pos == student_pos:
            return "Student", "Curious"
        return "Teacher", "Educational"

    @classmethod
    def split_narration_into_dialogue_segments(
        cls,
        narration_text: str,
        scene_id: str,
        default_role: str = "Teacher",
        default_style: str = "Educational",
    ) -> Tuple[List[DialogueSegment], List[str]]:
        """
        Splits a scene's spoken narration (`សំឡេងអាន៖`) into multi-speaker DialogueSegments.
        Recognizes inline character quotes preceded by speaking cues (e.g. `សួរ៖ «...»`, `និយាយថា៖ «...»`).
        Strips quotation marks «...» from spoken segment text so punctuation is never read aloud.
        """
        text = unicodedata.normalize("NFC", narration_text).strip()
        warnings: List[str] = []
        if not text:
            return [], warnings

        # Detect inline spoken quotes introduced by speaking verbs or colons:
        # e.g., សួរ៖ «...» or និយាយថា៖ «...» or ឆ្លើយថា៖ «...»
        dialogue_quote_pattern = re.compile(
            r"(?:សួរថា|សួរ|និយាយថា|និយាយ|ឆ្លើយថា|ឆ្លើយ|ពោលថា|ប្រាប់ថា|ស្រែកថា|asks?|says?|replies?)\s*[៖:]?\s*([«\"“])(.+?)([»\"”])",
            re.IGNORECASE,
        )

        matches = list(dialogue_quote_pattern.finditer(text))
        if not matches:
            # Single-speaker narration block
            seg = DialogueSegment(
                segment_id=f"{scene_id}_seg_01",
                index=0,
                speaker_role=default_role,
                text=text,
                delivery_style=default_style,
                pace="Medium",
                pause_after_ms=300,
            )
            return [seg], warnings

        segments: List[DialogueSegment] = []
        cursor = 0
        seg_idx = 0

        for m in matches:
            quote_open_idx = m.start(1)
            quote_close_idx = m.end(3)
            quoted_speech = m.group(2).strip()

            # Preceding narrator setup / bridge (up to the opening quote mark)
            narrator_setup = text[cursor:quote_open_idx].strip()
            if narrator_setup:
                segments.append(
                    DialogueSegment(
                        segment_id=f"{scene_id}_seg_{seg_idx + 1:02d}",
                        index=seg_idx,
                        speaker_role="Narrator",
                        text=narrator_setup,
                        delivery_style="Friendly",
                        pace="Medium",
                        pause_after_ms=220,
                    )
                )
                seg_idx += 1

            # Infer character role from the setup clause
            role, style = cls._infer_role_and_style_from_intro(narrator_setup or text[:quote_open_idx])
            if role == "Custom Character":
                warnings.append(
                    f"Ambiguous speaker identity for quote «{quoted_speech[:30]}...»; assigned 'Custom Character' for review."
                )

            if quoted_speech:
                segments.append(
                    DialogueSegment(
                        segment_id=f"{scene_id}_seg_{seg_idx + 1:02d}",
                        index=seg_idx,
                        speaker_role=role,
                        text=quoted_speech,
                        delivery_style=style,
                        pace="Medium",
                        pause_after_ms=320,
                    )
                )
                seg_idx += 1

            cursor = quote_close_idx

        # Any trailing narration after the last quote
        trailing = text[cursor:].strip()
        if trailing:
            segments.append(
                DialogueSegment(
                    segment_id=f"{scene_id}_seg_{seg_idx + 1:02d}",
                    index=seg_idx,
                    speaker_role=default_role,
                    text=trailing,
                    delivery_style=default_style,
                    pace="Medium",
                    pause_after_ms=350,
                )
            )

        return segments, warnings

    @classmethod
    def _parse_blocks(
        cls,
        paragraphs: List[str],
        tables: List[List[List[str]]],
        source_filename: str,
        available_voice_profiles: Optional[List[Any]] = None,
    ) -> ScriptProject:
        project_id = f"proj_{uuid.uuid4().hex[:10]}"
        project = ScriptProject(
            project_id=project_id,
            title="Untitled Storyboard Project",
            source_filename=source_filename,
        )

        # 1. Inspect metadata tables (e.g., Audience, Duration, Aspect Ratio, Style)
        for tbl in tables:
            if len(tbl) >= 2 and len(tbl[0]) >= 2:
                headers = tbl[0]
                values = tbl[1]
                for h, v in zip(headers, values):
                    if "ទស្សនិកជន" in h or "audience" in h.lower():
                        project.audience = v
                    elif "រយៈពេល" in h or "duration" in h.lower():
                        project.planned_duration_label = v
                        project.planned_duration_sec = parse_timecode_to_sec(v)
                    elif "ទំហំ" in h or "aspect" in h.lower():
                        project.aspect_ratio = v
                    elif "រចនាបថ" in h or "style" in h.lower():
                        project.visual_style = v

        # 2. Walk paragraphs and classify into Header, Section 1 (Production), Section 2 (Scenes), Section 3 (Checklist)
        current_section = "header"
        current_scene: Optional[StoryboardScene] = None
        header_lines: List[str] = []

        for line in paragraphs:
            clean_line = unicodedata.normalize("NFC", line).strip()
            if not clean_line:
                continue

            # Check section transitions
            if cls.SECTION_1_REGEX.search(clean_line):
                current_section = "production_settings"
                continue
            if cls.SECTION_2_REGEX.search(clean_line):
                current_section = "storyboard"
                continue
            if cls.SECTION_3_REGEX.search(clean_line):
                if current_scene is not None:
                    project.scenes.append(current_scene)
                    current_scene = None
                current_section = "checklist"
                continue

            # Always check for checklist items or footer notes anywhere at end of document
            chk_m = cls.CHECKLIST_LINE_REGEX.match(clean_line)
            if chk_m:
                if current_scene is not None:
                    project.scenes.append(current_scene)
                    current_scene = None
                current_section = "checklist"
                project.checklist_items.append(chk_m.group(1).strip())
                continue

            footer_m = cls.FOOTER_NOTE_REGEX.match(clean_line)
            if footer_m and (current_section == "checklist" or len(project.scenes) > 0):
                if current_scene is not None:
                    project.scenes.append(current_scene)
                    current_scene = None
                project.production_footer_note = footer_m.group(1).strip()
                continue

            # Check if line is a Scene Header with [MM:SS–MM:SS]
            scene_m = cls.SCENE_HEADER_REGEX.match(clean_line)
            if scene_m:
                if current_scene is not None:
                    project.scenes.append(current_scene)
                current_section = "storyboard"
                seq_num = len(project.scenes) + 1
                if scene_m.group(1):
                    try:
                        seq_num = int(khmer_digits_to_ascii(scene_m.group(1)))
                    except ValueError:
                        pass
                raw_title = scene_m.group(2).strip()
                start_tc = khmer_digits_to_ascii(scene_m.group(3).strip())
                end_tc = khmer_digits_to_ascii(scene_m.group(4).strip())
                start_sec = parse_timecode_to_sec(start_tc)
                end_sec = parse_timecode_to_sec(end_tc)
                target_dur = round(max(0.0, end_sec - start_sec), 2)

                current_scene = StoryboardScene(
                    scene_id=f"scene_{seq_num:02d}",
                    scene_number=seq_num,
                    title=raw_title,
                    target_start_time=start_tc,
                    target_end_time=end_tc,
                    target_start_sec=start_sec,
                    target_end_sec=end_sec,
                    target_duration_sec=target_dur,
                )
                continue

            # Handle lines inside Section 1 (Production Settings)
            if current_section == "production_settings":
                if m := cls.PROD_VOICE_REGEX.match(clean_line):
                    project.voice_production_notes = m.group(1).strip()
                    # Detect requested voice preset name such as «Maly» or "Maly"
                    preset_m = re.search(r"voice\s*preset\s*[«\"“]([^»\"”]+)[»\"”]", project.voice_production_notes, re.IGNORECASE)
                    if preset_m:
                        project.requested_voice_preset = preset_m.group(1).strip()
                    continue
                if m := cls.PROD_MUSIC_REGEX.match(clean_line):
                    project.music_production_notes = m.group(1).strip()
                    continue
                if m := cls.PROD_STYLE_REGEX.match(clean_line):
                    project.style_production_notes = m.group(1).strip()
                    continue
                if m := cls.PROD_TEXT_REGEX.match(clean_line):
                    project.text_production_notes = m.group(1).strip()
                    continue
                if m := cls.PROD_EDU_REGEX.match(clean_line):
                    project.education_production_notes = m.group(1).strip()
                    continue

            # Handle lines inside Storyboard Scenes
            if current_scene is not None:
                narr_m = cls.NARRATION_MARKER_REGEX.match(clean_line)
                if narr_m:
                    spoken_body = narr_m.group(1).strip()
                    if current_scene.narration_text:
                        current_scene.narration_text += " " + spoken_body
                    else:
                        current_scene.narration_text = spoken_body
                    continue

                vis_m = cls.VISUAL_MARKER_REGEX.match(clean_line)
                if vis_m:
                    vis_body = vis_m.group(1).strip()
                    v_notes, kws, sfx, mus = cls._parse_visual_line_details(vis_body)
                    current_scene.visual_notes = (
                        f"{current_scene.visual_notes} {v_notes}".strip()
                        if current_scene.visual_notes
                        else v_notes
                    )
                    for k in kws:
                        if k not in current_scene.keywords:
                            current_scene.keywords.append(k)
                    if sfx:
                        current_scene.sfx_notes = (
                            f"{current_scene.sfx_notes}; {sfx}".strip("; ")
                            if current_scene.sfx_notes
                            else sfx
                        )
                    if mus:
                        current_scene.music_notes = (
                            f"{current_scene.music_notes}; {mus}".strip("; ")
                            if current_scene.music_notes
                            else mus
                        )
                    continue

                # Check standalone keyword / music / SFX lines inside a scene
                if clean_line.startswith("ពាក្យគន្លឹះ"):
                    _, kws, _, _ = cls._parse_visual_line_details(clean_line)
                    for k in kws:
                        if k not in current_scene.keywords:
                            current_scene.keywords.append(k)
                    continue
                if m := cls.PROD_MUSIC_REGEX.match(clean_line):
                    current_scene.music_notes = m.group(1).strip()
                    continue

                # Ambiguous line inside a scene without an explicit marker:
                # Never silently invent speech if a scene already has narration_text;
                # store in validation_warnings for user review.
                if current_scene.narration_text:
                    current_scene.validation_warnings.append(
                        f"Unlabeled line excluded from spoken audio (review if intended as speech): '{clean_line[:80]}'"
                    )
                else:
                    current_scene.narration_text = clean_line
                    current_scene.validation_warnings.append(
                        "Scene narration lacked explicit 'សំឡេងអាន៖' marker; please verify spoken text."
                    )
                continue

            # Header section before Section 1 / Storyboard
            if current_section == "header":
                if clean_line.startswith("ប្រធានបទ៖") or clean_line.startswith("ប្រធានបទ:"):
                    project.topic = re.sub(r"^ប្រធានបទ\s*[៖:]\s*", "", clean_line).strip()
                else:
                    header_lines.append(clean_line)

        # Flush last scene
        if current_scene is not None:
            project.scenes.append(current_scene)

        # Fallback: if plain text was pasted with no [MM:SS–MM:SS] scene headers
        if not project.scenes and header_lines:
            raw_spoken: List[str] = []
            for hl in header_lines:
                if nm := cls.NARRATION_MARKER_REGEX.match(hl):
                    raw_spoken.append(nm.group(1).strip())
                elif cls.VISUAL_MARKER_REGEX.match(hl) or cls.PROD_MUSIC_REGEX.match(hl) or cls.PROD_VOICE_REGEX.match(hl):
                    continue
                else:
                    raw_spoken.append(hl)
            if raw_spoken:
                fallback_text = " ".join(raw_spoken).strip()
                fallback_scene = StoryboardScene(
                    scene_id="scene_01",
                    scene_number=1,
                    title="Scene 1",
                    target_start_time="00:00",
                    target_end_time="00:30",
                    target_start_sec=0.0,
                    target_end_sec=30.0,
                    target_duration_sec=30.0,
                    narration_text=fallback_text,
                    validation_warnings=[
                        "Imported plain text without timestamped scene headers; created Scene 1 for review."
                    ],
                )
                project.scenes.append(fallback_scene)
                header_lines = [Path(source_filename).stem]

        if header_lines:
            project.title = header_lines[0]
            if len(header_lines) > 1:
                project.subtitle = " • ".join(header_lines[1:])

        # If planned_duration_sec wasn't in table, compute from scenes
        if project.planned_duration_sec <= 0 and project.scenes:
            max_end = max(s.target_end_sec for s in project.scenes)
            project.planned_duration_sec = max_end if max_end > 0 else sum(s.target_duration_sec for s in project.scenes)
            if not project.planned_duration_label:
                project.planned_duration_label = format_sec_to_timecode(project.planned_duration_sec)

        # 3. Resolve available voice profiles and requested preset ("Maly")
        profiles = available_voice_profiles or []
        matched_preset_profile = None
        if project.requested_voice_preset:
            req_lower = project.requested_voice_preset.lower()
            for prof in profiles:
                p_name = getattr(prof, "name", "") or (prof.get("name", "") if isinstance(prof, dict) else "")
                if req_lower in p_name.lower():
                    matched_preset_profile = prof
                    break
            if not matched_preset_profile:
                project.validation_warnings.append(
                    f"⚠️ Document requests voice preset «{project.requested_voice_preset}», which is not installed in your Voice Library. "
                    "Assigned fallback voice selection — please choose a compatible Khmer Voice Profile in the Role Inspector."
                )

        default_prof_id = getattr(matched_preset_profile, "id", None) if matched_preset_profile else None
        default_prof_name = getattr(matched_preset_profile, "name", "Default Voice") if matched_preset_profile else "Default Voice"

        # Initialize default role->voice mappings
        for role in SUPPORTED_SPEAKER_ROLES:
            default_style_for_role = {
                "Narrator": "Friendly",
                "Teacher": "Educational",
                "Student": "Curious",
                "Robot": "Cheerful",
                "Custom Character": "Natural",
            }.get(role, "Natural")
            project.role_voice_map[role] = {
                "voice_profile_id": default_prof_id,
                "voice_name": default_prof_name,
                "mode": "tts",
                "delivery_style": default_style_for_role,
                "pace": "Medium",
            }

        # 4. Segment each scene's spoken narration into multi-speaker DialogueSegments
        for sc in project.scenes:
            if not sc.narration_text.strip():
                sc.validation_warnings.append("⚠️ Scene has no spoken narration ('សំឡេងអាន៖' is empty).")
                continue

            segs, seg_warnings = cls.split_narration_into_dialogue_segments(
                narration_text=sc.narration_text,
                scene_id=sc.scene_id,
                default_role="Teacher",
                default_style="Educational",
            )
            for w in seg_warnings:
                if w not in sc.validation_warnings:
                    sc.validation_warnings.append(w)

            for seg in segs:
                role_cfg = project.role_voice_map.get(seg.speaker_role, {})
                seg.voice_profile_id = role_cfg.get("voice_profile_id")
                seg.voice_name = role_cfg.get("voice_name", "Default Voice")
                seg.mode = role_cfg.get("mode", "tts")

            sc.dialogue_segments = segs
            # Set primary scene speaker role summary
            unique_roles = []
            for seg in segs:
                if seg.speaker_role not in unique_roles:
                    unique_roles.append(seg.speaker_role)
            sc.speaker_role = " + ".join(unique_roles) if unique_roles else "Teacher"
            sc.voice_profile_id = default_prof_id
            sc.voice_name = default_prof_name

        return project
