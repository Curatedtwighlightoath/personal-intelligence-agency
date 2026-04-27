"""
Structure-aware text chunker.

Design choice (vs fixed-length char/token batching): chunks track natural
document units — paragraphs and sentences — because vectors over coherent
units yield better cosine-similarity ranking than vectors over arbitrary
1000-char windows that straddle sentence boundaries.

Single entry point: chunk_text(text). Returns the chunks in document order.
A chunk is never empty and never exceeds max_chars.
"""

import re
from typing import Iterable

# Cap is generous — text-embedding-3-small accepts up to ~8K tokens, so
# 4000 chars (~1000 tokens) leaves plenty of headroom while preventing
# pathological single-paragraph inputs from blowing past the limit.
DEFAULT_MAX_CHARS = 4000

# Split on blank lines (one-or-more) so single newlines inside a paragraph
# are preserved. Trailing/leading whitespace per paragraph is stripped.
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")

# Sentence boundary heuristic: end-of-sentence punctuation followed by
# whitespace. Not perfect (won't catch "Dr. Smith"), but good enough as a
# last-resort splitter for the rare paragraph that exceeds max_chars.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """
    Split `text` into chunks aligned with paragraphs.

    Algorithm:
      1. Split on blank lines → paragraphs.
      2. Each paragraph that fits in max_chars is its own chunk.
      3. Oversize paragraphs split on sentence boundaries; sentences are
         packed greedily up to max_chars.
      4. Any single sentence longer than max_chars is hard-broken at
         max_chars (truly pathological input — single 50KB run-on).
    """
    if not text or not text.strip():
        return []

    out: list[str] = []
    for paragraph in _split_paragraphs(text):
        if len(paragraph) <= max_chars:
            out.append(paragraph)
        else:
            out.extend(_split_oversize(paragraph, max_chars))
    return out


def _split_paragraphs(text: str) -> Iterable[str]:
    for raw in _PARAGRAPH_SPLIT.split(text):
        stripped = raw.strip()
        if stripped:
            yield stripped


def _split_oversize(paragraph: str, max_chars: int) -> list[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(paragraph) if s.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if buf:
            chunks.append(" ".join(buf))
            buf = []
            buf_len = 0

    for sent in sentences:
        if len(sent) > max_chars:
            # Single sentence exceeds the cap: flush, then hard-break.
            flush()
            for i in range(0, len(sent), max_chars):
                chunks.append(sent[i : i + max_chars])
            continue

        # +1 accounts for the space between sentences when joined.
        prospective = buf_len + len(sent) + (1 if buf else 0)
        if prospective > max_chars:
            flush()
            buf = [sent]
            buf_len = len(sent)
        else:
            buf.append(sent)
            buf_len = prospective

    flush()
    return chunks
