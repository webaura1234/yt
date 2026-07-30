import re
from typing import List, Tuple

_SENTENCE_BOUNDARY_RE = re.compile(
    r'(?<=[.!?])\s+(?=[A-Z0-9"‘’“”])'
)


def split_sentences(script: str) -> List[str]:
    """Regex sentence split (no NLP dependency): splits on '.'/'!'/'?' followed by
    whitespace and a capital letter, digit, or opening/closing quote mark - which
    also means it naturally doesn't split mid-number ("3.5" has no whitespace
    after the '.', so the lookahead never matches there).

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
