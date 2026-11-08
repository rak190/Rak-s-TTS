"""
Intelligent Sentence-Aware Text Chunker for Long-Form Speech Synthesis.
Supports Khmer (handling '។', '៕', phrase spaces), English, and code-switching text.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from app.utils.text_processor import TextProcessor

@dataclass
class TextChunk:
    index: int
    text: str
    char_count: int
    language: str
    terminal_punct: Optional[str] = None
    pause_after_ms: int = 300

class SentenceAwareChunker:
    """
    Splits long-form text into syntactically natural, pronunciation-friendly chunks
    optimized for VoxCPM2 diffusion attention windows.
    """

    # Primary sentence delimiters:
    # Khmer Khan (\u17D4 = '។'), Bariyoosan (\u17D5 = '៕'), Peyyealam (\u17D8 = '៘')
    # Standard terminal punctuation: '.', '!', '?', '\n'
    SENTENCE_SPLIT_REGEX = re.compile(r"([។៕៘.!?\n]+)")

    # Secondary clause delimiters for breaking oversized sentences:
    # Commas, semicolons, colons, Khmer Camnuc-pi-kuuh (\u17D6 = '៖'), dashes
    CLAUSE_SPLIT_REGEX = re.compile(r"([,;:៖\u2014\u2013\-]+)")

    DEFAULT_TARGET_CHARS = 110
    DEFAULT_MAX_CHARS = 150
    DEFAULT_MIN_CHARS = 25

    @classmethod
    def split_into_raw_sentences(cls, text: str) -> List[str]:
        """
        Splits text on primary sentence terminators while preserving punctuation
        with the preceding sentence.
        """
        if not text or not text.strip():
            return []

        tokens = cls.SENTENCE_SPLIT_REGEX.split(text)
        sentences = []
        i = 0
        while i < len(tokens):
            chunk = tokens[i].strip()
            if not chunk:
                i += 1
                continue
            
            # If the next token is punctuation, attach it
            if i + 1 < len(tokens) and cls.SENTENCE_SPLIT_REGEX.fullmatch(tokens[i + 1]):
                punct = tokens[i + 1].strip()
                full_sent = f"{chunk}{punct}".strip()
                i += 2
            else:
                full_sent = chunk
                i += 1

            if full_sent:
                sentences.append(full_sent)

        return sentences

    @classmethod
    def split_oversized_sentence(
        cls,
        sentence: str,
        max_chars: int = DEFAULT_MAX_CHARS
    ) -> List[str]:
        """
        Sub-divides an overly long sentence using secondary clause boundaries
        or spaces (for Khmer, spaces are phrase boundaries).
        """
        if len(sentence) <= max_chars:
            return [sentence]

        is_khmer = TextProcessor.contains_khmer(sentence)

        # 1. Try splitting on secondary punctuation (commas, semicolons, etc.)
        tokens = cls.CLAUSE_SPLIT_REGEX.split(sentence)
        if len(tokens) > 1:
            clauses = []
            cur_clause = ""
            for tok in tokens:
                if len(cur_clause) + len(tok) <= max_chars:
                    cur_clause += tok
                else:
                    if cur_clause.strip():
                        clauses.append(cur_clause.strip())
                    cur_clause = tok
            if cur_clause.strip():
                clauses.append(cur_clause.strip())
            
            # If all sub-clauses are within budget, return them
            if all(len(c) <= max_chars for c in clauses):
                return clauses

        # 2. Try splitting on whitespace boundaries
        # In Khmer, spaces are clause/phrase separators, so space splitting is linguistically sound.
        words = sentence.split(" ")
        sub_chunks = []
        current = []
        current_len = 0

        for w in words:
            w_len = len(w) + 1  # include space
            if current_len + w_len > max_chars and current:
                sub_chunks.append(" ".join(current).strip())
                current = [w]
                current_len = len(w)
            else:
                current.append(w)
                current_len += w_len

        if current:
            sub_chunks.append(" ".join(current).strip())

        return sub_chunks if sub_chunks else [sentence]

    @classmethod
    def chunk_text(
        cls,
        text: str,
        target_chars: int = DEFAULT_TARGET_CHARS,
        max_chars: int = DEFAULT_MAX_CHARS,
        min_chars: int = DEFAULT_MIN_CHARS
    ) -> List[TextChunk]:
        """
        Chunks arbitrary-length text into balanced, natural speech segments.
        Merges short sentences up to target_chars and splits sentences exceeding max_chars.
        """
        normalized = TextProcessor.normalize_text(text)
        if not normalized:
            return []

        raw_sentences = cls.split_into_raw_sentences(normalized)
        expanded_sentences = []

        # Expand oversized sentences
        for s in raw_sentences:
            if len(s) > max_chars:
                expanded_sentences.extend(cls.split_oversized_sentence(s, max_chars=max_chars))
            else:
                expanded_sentences.append(s)

        # Group sentences into target-sized chunks
        grouped_texts: List[str] = []
        buffer = ""

        for sent in expanded_sentences:
            sent_clean = sent.strip()
            if not sent_clean:
                continue

            if not buffer:
                buffer = sent_clean
            elif len(buffer) + len(sent_clean) + 1 <= target_chars:
                buffer = f"{buffer} {sent_clean}"
            elif len(buffer) < min_chars and len(buffer) + len(sent_clean) + 1 <= max_chars:
                # Merge tiny buffer into current sentence if under max_chars
                buffer = f"{buffer} {sent_clean}"
            else:
                grouped_texts.append(buffer)
                buffer = sent_clean

        if buffer:
            # If trailing buffer is too small, merge with previous chunk if budget allows
            if grouped_texts and len(buffer) < min_chars and (len(grouped_texts[-1]) + len(buffer) + 1) <= max_chars:
                grouped_texts[-1] = f"{grouped_texts[-1]} {buffer}"
            else:
                grouped_texts.append(buffer)

        # Build structured TextChunk objects with pause annotations
        chunks: List[TextChunk] = []
        for idx, chunk_str in enumerate(grouped_texts):
            clean_str = chunk_str.strip()
            lang = TextProcessor.detect_language(clean_str)

            # Determine terminal punctuation and pause duration
            term_punct = None
            pause_ms = 300

            if clean_str.endswith("។") or clean_str.endswith("."):
                term_punct = "។" if clean_str.endswith("។") else "."
                pause_ms = 350
            elif clean_str.endswith("៕"):
                term_punct = "៕"
                pause_ms = 500
            elif clean_str.endswith("?") or clean_str.endswith("!"):
                term_punct = clean_str[-1]
                pause_ms = 400
            elif clean_str.endswith(",") or clean_str.endswith(";") or clean_str.endswith("៖"):
                term_punct = clean_str[-1]
                pause_ms = 200

            chunks.append(
                TextChunk(
                    index=idx,
                    text=clean_str,
                    char_count=len(clean_str),
                    language=lang,
                    terminal_punct=term_punct,
                    pause_after_ms=pause_ms
                )
            )

        return chunks
