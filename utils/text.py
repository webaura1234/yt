import re
from typing import List, Tuple

# Sentence-ending punctuation, including the Devanagari danda and double danda
# which Indic scripts also use.
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?।॥])\s+")


def split_sentences(script: str) -> List[str]:
    """Regex sentence split (no NLP dependency): splits on sentence-ending
    punctuation followed by whitespace.

    The boundary deliberately does NOT require the next sentence to start with a
    capital letter. It used to, and that quietly broke every non-Latin script:
    Telugu has no capitals, so the lookahead never matched and an entire Telugu
    script came back as ONE sentence. Everything downstream is per-sentence -
    the storyboard, the shot selection, the visual for each line - so a whole
    video collapsed to a single static image. Requiring a capital is an
    English-only assumption this pipeline cannot make.

    Decimals are still safe: "3.5" has no whitespace after the '.', so the
    boundary never matches inside a number.

    Known limitation: doesn't special-case abbreviations (e.g. "Mr. Smith" would
    split into two sentences) - acceptable given this project's short,
    conversational Shorts scripts, which rarely contain them.
    """
    if not script or not script.strip():
        return []

    fragments = _SENTENCE_BOUNDARY_RE.split(script.strip())
    return [f.strip() for f in fragments if f.strip()]


def align_sentences_to_word_times(
    sentences: List[str], words: List[dict], total_duration: float
) -> List[Tuple[float, float]]:
    """Returns one (start, end) tuple per sentence, in seconds.

    Primary path: sequentially consumes words from the flat AssemblyAI word list
    per sentence, positionally, by word count - a sentence's (start, end) is its
    first consumed word's 'start' and its last consumed word's 'end'. Only used
    when the sentences' combined word count matches len(words) EXACTLY; a partial/
    best-effort positional alignment on a mismatch would silently drift, so any
    mismatch instead takes the fallback path below rather than half-aligning.

    Fallback path (word list empty, or the counts don't match - e.g. TTS
    mispronunciation, filler words, or the transcriber merging/dropping a word):
    splits the known audio span proportionally by each sentence's character
    length. Never raises.
    """
    if not sentences:
        return []

    word_counts = [len(s.split()) for s in sentences]

    if words and sum(word_counts) == len(words):
        times = []
        idx = 0
        for count in word_counts:
            chunk = words[idx : idx + count]
            times.append((chunk[0]["start"], chunk[-1]["end"]))
            idx += count
        return times

    span_start = words[0]["start"] if words else 0.0
    span_end = words[-1]["end"] if words else total_duration
    span = max(span_end - span_start, 0.0)

    total_chars = sum(len(s) for s in sentences) or 1
    times = []
    cursor = span_start
    for s in sentences:
        duration = span * (len(s) / total_chars)
        times.append((cursor, cursor + duration))
        cursor += duration
    return times
