"""
Unit tests for SentenceAwareChunker (Phase 4B).
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

from app.utils.chunker import SentenceAwareChunker, TextChunk

class TestSentenceAwareChunker(unittest.TestCase):

    def test_01_empty_and_trivial_text(self):
        """Verifies empty and whitespace-only text returns empty list."""
        self.assertEqual(SentenceAwareChunker.chunk_text(""), [])
        self.assertEqual(SentenceAwareChunker.chunk_text("   \n\t  "), [])

    def test_02_khmer_sentence_splitting(self):
        """Verifies splitting on Khmer Khan (។) and Bariyoosan (៕)."""
        kh_text = "សួស្តី! នេះគឺជាការសាកល្បងទីមួយ។ ឯនេះគឺជាការសាកល្បងទីពីរ។ សូមអរគុណច្រើន៕"
        chunks = SentenceAwareChunker.chunk_text(kh_text, target_chars=40, max_chars=60)
        
        self.assertGreaterEqual(len(chunks), 2)
        all_text = " ".join(c.text for c in chunks)
        self.assertIn("សួស្តី!", all_text)
        self.assertIn("សូមអរគុណច្រើន៕", all_text)

        for c in chunks:
            self.assertEqual(c.language, "khmer")
            self.assertLessEqual(c.char_count, 120)
            self.assertGreater(c.char_count, 0)

    def test_03_english_paragraph_splitting(self):
        """Verifies splitting English paragraphs on sentences and grouping within target length."""
        en_text = (
            "VoiceStudio AI is an offline speech synthesis workstation. "
            "It runs on mobile Intel CPUs without requiring dedicated cloud GPUs. "
            "Each sentence is analyzed and partitioned into natural acoustic chunks. "
            "Does it support long audio? Yes, it seamlessly handles chapters and articles."
        )
        chunks = SentenceAwareChunker.chunk_text(en_text, target_chars=100, max_chars=140)
        self.assertGreaterEqual(len(chunks), 2)
        for c in chunks:
            self.assertEqual(c.language, "english")
            self.assertLessEqual(c.char_count, 140)
            self.assertGreater(len(c.text), 15)

    def test_04_oversized_sentence_handling(self):
        """Verifies sentences exceeding max_chars are divided at clauses or spaces."""
        long_khmer_clause = (
            "ប្រទេសកម្ពុជាគឺជាប្រទេសមួយដែលមានប្រវត្តិសាស្ត្រយូរលង់ណាស់មកហើយ "
            "ហើយប្រជាជនកម្ពុជាមានភាពរួសរាយរាក់ទាក់និងចូលចិត្តជួយគ្នាក្នុងគ្រាលំបាក "
            "លើសពីនេះទៅទៀតប្រាសាទអង្គរវត្តគឺជាសម្បត្តិបេតិកភណ្ឌពិភពលោកដ៏ល្បីល្បាញបំផុត។"
        )
        chunks = SentenceAwareChunker.chunk_text(long_khmer_clause, target_chars=70, max_chars=90)
        self.assertGreaterEqual(len(chunks), 2)
        for c in chunks:
            self.assertLessEqual(c.char_count, 90)

    def test_05_mixed_text_detection(self):
        """Verifies mixed Khmer-English code-switching text."""
        mixed_text = "សូមស្វាគមន៍មកកាន់ VoiceStudio AI Studio! We support high fidelity voice cloning។"
        chunks = SentenceAwareChunker.chunk_text(mixed_text, target_chars=120)
        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual(chunks[0].language, "mixed")

    def test_06_pause_duration_heuristics(self):
        """Verifies appropriate pause durations based on terminal punctuation."""
        t1 = "នេះជាប្រយោគទីមួយ។"
        c1 = SentenceAwareChunker.chunk_text(t1)[0]
        self.assertEqual(c1.terminal_punct, "។")
        self.assertEqual(c1.pause_after_ms, 350)

        t2 = "This is a question?"
        c2 = SentenceAwareChunker.chunk_text(t2)[0]
        self.assertEqual(c2.terminal_punct, "?")
        self.assertEqual(c2.pause_after_ms, 400)

    def test_07_small_chunk_merging(self):
        """Verifies tiny sentences below min_chars are merged into previous chunk."""
        text = "This is the first primary sentence that is long enough. OK."
        chunks = SentenceAwareChunker.chunk_text(text, target_chars=80, max_chars=120, min_chars=10)
        # 'OK.' should be merged rather than left as a 3-char isolated chunk
        self.assertEqual(len(chunks), 1)
        self.assertIn("OK.", chunks[0].text)

if __name__ == "__main__":
    unittest.main()
