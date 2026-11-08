"""Text processing and Khmer Unicode utilities."""
import re
import unicodedata

class TextProcessor:
    """Preprocesses text for multilingual TTS (Khmer, English, and Mixed)."""

    KHMER_CHAR_REGEX = re.compile(r"[\u1780-\u17FF]")

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalizes Unicode into canonical NFC form and cleans control characters."""
        if not text:
            return ""
        # NFC canonical composition
        normalized = unicodedata.normalize("NFC", text)
        # Replace newlines and multiple spaces with a single space
        cleaned = re.sub(r"[\r\n\t]+", " ", normalized)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @classmethod
    def contains_khmer(cls, text: str) -> bool:
        """Detects whether text contains Khmer Unicode characters."""
        return bool(cls.KHMER_CHAR_REGEX.search(text))

    @classmethod
    def detect_language(cls, text: str) -> str:
        """Heuristic language detection: 'khmer', 'english', or 'mixed'."""
        has_khmer = cls.contains_khmer(text)
        has_latin = bool(re.search(r"[a-zA-Z]", text))

        if has_khmer and has_latin:
            return "mixed"
        elif has_khmer:
            return "khmer"
        elif has_latin:
            return "english"
        return "multilingual"
