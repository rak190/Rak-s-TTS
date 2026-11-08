"""Comprehensive linguistic test suite for Khmer, English, and Mixed code-switching.
Validates Pali/Sanskrit consonant clusters (Coeng), Khmer punctuation (Khan, Bariyoosan),
Zero-Width Space (ZWSP), English pangrams, and code-switching synthesis.
"""
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import unittest
import numpy as np
import soundfile as sf
from pathlib import Path

from app.utils.text_processor import TextProcessor
from app.engines.model_manager import ModelManager
from app.engines.voxcpm_adapter import VoxCPM2Adapter
from app.config import NATIVE_SAMPLE_RATE

class TestLinguisticValidation(unittest.TestCase):
    """Linguistic and tokenization validation across Khmer, English, and mixed scripts."""

    def test_01_khmer_unicode_normalization_and_detection(self):
        # Pali/Sanskrit cluster text with Coeng (ជើង)
        khmer_clusters = "សេចក្ដីព្យាយាមគង់បានសម្រេច ព្រះរាជាណាចក្រកម្ពុជា"
        norm = TextProcessor.normalize_text(khmer_clusters)
        self.assertEqual(norm, khmer_clusters) # NFC normalized
        self.assertEqual(TextProcessor.detect_language(norm), "khmer")
        self.assertTrue(TextProcessor.is_khmer(norm))

    def test_02_khmer_punctuation_handling(self):
        # Khan (។) and Bariyoosan (៕)
        khmer_punct = "សួស្តីពិភពលោក។ នេះជាប្រយោគទីមួយ។ ចប់ដោយបរិយោសាន៕"
        norm = TextProcessor.normalize_text(khmer_punct)
        self.assertIn("។", norm)
        self.assertIn("៕", norm)
        self.assertEqual(TextProcessor.detect_language(norm), "khmer")

    def test_03_khmer_zero_width_space_handling(self):
        # ZWSP \u200B between words
        khmer_zwsp = "ខ្ញុំ\u200Bស្រឡាញ់\u200Bប្រទេស\u200Bកម្ពុជា"
        norm = TextProcessor.normalize_text(khmer_zwsp)
        # Verify ZWSP is preserved or cleanly handled without breaking detection
        self.assertEqual(TextProcessor.detect_language(norm), "khmer")

    def test_04_english_phonetic_pangram_and_technical(self):
        pangram = "The quick brown fox jumps over the lazy dog."
        technical = "VoiceStudio AI synthesizes multilingual speech with high fidelity using local CPU flow matching."
        norm_pan = TextProcessor.normalize_text(pangram)
        norm_tech = TextProcessor.normalize_text(technical)
        self.assertEqual(TextProcessor.detect_language(norm_pan), "english")
        self.assertEqual(TextProcessor.detect_language(norm_tech), "english")

    def test_05_mixed_code_switching_detection(self):
        mixed = "កម្មវិធី VoiceStudio AI ដំណើរការលើ Windows 11 យ៉ាងរលូន។"
        norm_mixed = TextProcessor.normalize_text(mixed)
        self.assertEqual(TextProcessor.detect_language(norm_mixed), "mixed")
        self.assertTrue(TextProcessor.is_khmer(norm_mixed))

    def test_06_tokenizer_vocabulary_verification(self):
        """Verifies that the VoxCPM2 tokenizer encodes Khmer, English, and punctuation without [UNK] crashes."""
        model_mgr = ModelManager.get_instance()
        model = model_mgr.load_model()
        tokenizer = model.tts_model.text_tokenizer

        test_sentences = [
            "សួស្តីកម្ពុជា",
            "សេចក្ដីព្យាយាមគង់បានសម្រេច។",
            "បញ្ចប់ដោយបរិយោសាន៕",
            "ខ្ញុំ\u200Bស្រឡាញ់\u200Bភាសាខ្មែរ",
            "The quick brown fox jumps over the lazy dog.",
            "VoiceStudio AI ដំណើរការលើ Windows 11"
        ]

        for s in test_sentences:
            norm_s = TextProcessor.normalize_text(s)
            tokens = tokenizer.tokenize(norm_s)
            self.assertGreater(len(tokens), 0, f"Tokenization returned empty tokens for: {s}")

if __name__ == "__main__":
    unittest.main()
