"""Per-sentence storyboarding.

The old pipeline asked the model for one search string per sentence and handed
it straight to Pexels. That is why the footage looked like random B-roll: "the
moon changes shape" became the query "moon", Pexels returned whatever is most
downloaded for "moon", and the first result won.

This module replaces that with the two things a human editor actually does
before searching. First it *reads* the sentence - who is in it, what they are
doing, where, when, what mood, which objects, and what kind of shot would show
it. Then it writes several competing queries from that understanding, each
aimed at a different way the shot could exist in a library, so the search has a
pool to choose between instead of a single guess.

Nothing here talks to a footage provider. It produces the brief that the search
and scoring stages work from, and the storyboard table a human reads before
committing to a render.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from utils.text import split_sentences

logger = logging.getLogger(__name__)

# Shot vocabulary the brief may ask for. Kept as a closed set so the query
# builder can rely on the value, and so a model that invents "epic cinematic
# masterpiece shot" gets normalised to something a stock library indexes.
SHOT_STYLES = (
    "close up",
    "macro",
    "wide shot",
    "drone aerial",
    "slow motion",
    "time lapse",
    "scientific footage",
    "archival footage",
    "handheld documentary",
)

_DEFAULT_SHOT_STYLE = "close up"

# Modifiers appended to queries to bias a library toward real, well-shot
# material rather than the flat corporate stock that dominates generic terms.
_REALISM_MODIFIERS = ("real", "cinematic", "natural light", "documentary")


@dataclass
class SceneBrief:
    """What one narration line is actually about, and how to find it."""

    index: int
    sentence: str
    subject: str = ""
    action: str = ""
    location: str = ""
    time_of_day: str = ""
    emotion: str = ""
    objects: List[str] = field(default_factory=list)
    shot_style: str = _DEFAULT_SHOT_STYLE
    queries: List[str] = field(default_factory=list)
    # Set when the narration is genuinely about something the generic-B-roll
    # filter would otherwise reject (a sentence about laptops needs a laptop).
    allow_generic: List[str] = field(default_factory=list)

    def concept_terms(self) -> List[str]:
        """Every concrete concept in the brief, for lexical relevance scoring."""
        terms = [self.subject, self.action, self.location, *self.objects]
        return [t.strip().lower() for t in terms if t and t.strip()]

    def summary(self) -> str:
        """One-line description of the shot this scene needs."""
        parts = [p for p in (self.subject, self.action, self.location) if p]
        return ", ".join(parts) or self.sentence

    def to_dict(self) -> dict:
        """Plain-JSON form, for persisting a storyboard between pipeline stages.

        The dashboard analyses the script in one request and renders in another,
        so the brief has to survive a round trip through SQLite. Only the brief
        travels - the chosen clips are found and used inside the render stage,
        so nothing about a SceneSelection needs to be serialisable.
        """
        return {
            "index": self.index,
            "sentence": self.sentence,
            "subject": self.subject,
            "action": self.action,
            "location": self.location,
            "time_of_day": self.time_of_day,
            "emotion": self.emotion,
            "objects": list(self.objects),
            "shot_style": self.shot_style,
            "queries": list(self.queries),
            "allow_generic": list(self.allow_generic),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "SceneBrief":
        """Rebuild a brief from `to_dict` output, tolerating missing keys.

        Lenient on purpose: a job stored before a field existed should still
        render rather than raise, so every field falls back to its default.
        """
        brief = cls(
            index=int(payload.get("index", 0)),
            sentence=str(payload.get("sentence", "")),
            subject=str(payload.get("subject", "")),
            action=str(payload.get("action", "")),
            location=str(payload.get("location", "")),
            time_of_day=str(payload.get("time_of_day", "")),
            emotion=str(payload.get("emotion", "")),
            objects=[str(o) for o in payload.get("objects", []) or []],
            shot_style=_normalise_shot_style(str(payload.get("shot_style", ""))),
            allow_generic=[str(a) for a in payload.get("allow_generic", []) or []],
        )
        brief.queries = [str(q) for q in payload.get("queries", []) or [] if str(q).strip()]
        if not brief.queries:
            brief.queries = _decorate_queries(_fallback_queries(brief), brief)
        return brief


def _normalise_shot_style(value: str) -> str:
    """Map free text onto SHOT_STYLES, so downstream code can trust the value."""
    lowered = (value or "").strip().lower()
    for style in SHOT_STYLES:
        if style in lowered:
            return style
    # Common synonyms a model reaches for.
    if "aerial" in lowered or "drone" in lowered:
        return "drone aerial"
    if "timelapse" in lowered or "lapse" in lowered:
        return "time lapse"
    if "slowmo" in lowered or "slo-mo" in lowered:
        return "slow motion"
    if "microscope" in lowered or "micro" in lowered:
        return "macro"
    if "archive" in lowered or "historical" in lowered:
        return "archival footage"
    return _DEFAULT_SHOT_STYLE


def _fallback_queries(brief: SceneBrief) -> List[str]:
    """Queries derived from the brief without another model call.

    Used when the LLM gives us a brief but no usable queries, and when it fails
    entirely. Still concept-driven rather than a bag of sentence words, because
    the whole failure being fixed here is queries that are too thin.
    """
    subject = brief.subject or ""
    action = brief.action or ""
    location = brief.location or ""

    combos = [
        " ".join(p for p in (subject, action) if p),
        " ".join(p for p in (subject, location) if p),
        " ".join(p for p in (brief.shot_style, subject) if p),
        " ".join(p for p in (subject, brief.time_of_day) if p),
    ]
    for obj in brief.objects[:2]:
        combos.append(" ".join(p for p in (obj, action or location) if p))

    seen, queries = set(), []
    for combo in combos:
        cleaned = re.sub(r"\s+", " ", combo).strip()
        if len(cleaned) < 3 or cleaned in seen:
            continue
        seen.add(cleaned)
        queries.append(cleaned)

    return queries


def _decorate_queries(queries: List[str], brief: SceneBrief) -> List[str]:
    """Add realism/shot-style variants so the pool spans different phrasings.

    A stock library's results for "crescent moon" and "real crescent moon night
    sky" barely overlap, and the second is far more likely to be the shot an
    editor wanted. Searching both is cheap; guessing which one works is not.
    """
    decorated: List[str] = []
    seen = set()

    for query in queries:
        for variant in (query, f"{brief.shot_style} {query}", f"{_REALISM_MODIFIERS[0]} {query}"):
            cleaned = re.sub(r"\s+", " ", variant).strip().lower()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                decorated.append(cleaned)

    return decorated


def _brief_from_payload(index: int, sentence: str, payload: dict) -> SceneBrief:
    def _text(key: str) -> str:
        value = payload.get(key, "")
        return value.strip() if isinstance(value, str) else ""

    objects = payload.get("objects", [])
    if not isinstance(objects, list):
        objects = []

    allow_generic = payload.get("allow_generic", [])
    if not isinstance(allow_generic, list):
        allow_generic = []

    brief = SceneBrief(
        index=index,
        sentence=sentence,
        subject=_text("subject"),
        action=_text("action"),
        location=_text("location"),
        time_of_day=_text("time_of_day"),
        emotion=_text("emotion"),
        objects=[o.strip().lower() for o in objects if isinstance(o, str) and o.strip()],
        shot_style=_normalise_shot_style(_text("shot_style")),
        allow_generic=[a.strip().lower() for a in allow_generic if isinstance(a, str)],
    )

    queries = payload.get("queries", [])
    if isinstance(queries, list):
        brief.queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
    if not brief.queries:
        brief.queries = _fallback_queries(brief)

    brief.queries = _decorate_queries(brief.queries, brief)
    return brief


def build_storyboard(
    title: str,
    script: str,
    generate=None,
    min_queries: int = 4,
) -> List[SceneBrief]:
    """Analyse every narration line and return its brief.

    `generate` is injected so this module doesn't import utils.llm at module
    scope (which would make a circular import) and so tests can drive it without
    a provider. It is called as generate(prompt, json_mode=True).

    `len(result) == len(split_sentences(script))` always holds - a scene that
    cannot be analysed still gets a brief built from its own text, because a
    missing brief would silently drop that sentence's visual.
    """
    sentences = split_sentences(script)
    if not sentences:
        return []

    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))

    prompt = f"""
You are a video editor storyboarding a short video titled: "{title}".

Here are its {len(sentences)} narration lines, in order:
{numbered}

For EACH line, work out what should be on screen while it is spoken, then write
the searches you would run to find that shot in a stock footage library.

For each line return:
- subject: the main thing on screen (a concrete noun, in English)
- action: what it is doing
- location: where this happens
- time_of_day: e.g. day, night, sunrise - "" if it doesn't matter
- emotion: the feeling the shot should carry - "" if neutral
- objects: other concrete things that should be visible (0-3 items)
- shot_style: exactly one of {", ".join(SHOT_STYLES)}
- queries: {min_queries}-6 DIFFERENT search queries for this shot
- allow_generic: list any of ["people walking", "laptop", "office", "city
  traffic", "abstract background"] that this line is GENUINELY about. Almost
  always empty. Only fill it when the narration is literally about that thing.

RULES FOR THE QUERIES - this is the part that matters most:
- Never search the bare topic word. For "The moon changes shape", "moon" is a
  bad query; "real moon phases time lapse", "crescent moon night sky", "full
  moon close up" and "waxing moon astronomy" are good ones.
- Each query must describe a SHOT someone actually filmed: a subject doing
  something, framed a particular way.
- Make the queries genuinely different from each other - different framing,
  different moment, different angle - so there is a real choice between them,
  not four rewordings of one idea.
- Prefer real, filmed material: cinematic, macro, drone, slow motion, time
  lapse, scientific or archival, whichever suits the line.
- Write queries in English even when the narration is in another language.
- 2 to 6 words per query. Long sentences return nothing in a stock library.

Respond with JSON:
{{
  "scenes": [
    {{"subject": "...", "action": "...", "location": "...", "time_of_day": "...",
      "emotion": "...", "objects": ["..."], "shot_style": "...",
      "queries": ["...", "..."], "allow_generic": []}}
  ]
}}
Return exactly {len(sentences)} entries, in the same order as the lines above.
"""

    payloads: List[dict] = []
    if generate is not None:
        try:
            raw = generate(prompt, json_mode=True)
            parsed = json.loads(raw).get("scenes", [])
            if isinstance(parsed, list):
                payloads = [p for p in parsed if isinstance(p, dict)]
        except Exception as e:
            logger.warning(f"Storyboard analysis failed, falling back per sentence: {e}")

    briefs = []
    for index, sentence in enumerate(sentences):
        payload = payloads[index] if index < len(payloads) else {}
        if not payload:
            # No usable analysis for this line. Build the thinnest honest brief
            # from the sentence itself rather than dropping the scene.
            payload = {"subject": _guess_subject(sentence), "action": "", "location": ""}
        briefs.append(_brief_from_payload(index, sentence, payload))

    return briefs


def _guess_subject(sentence: str) -> str:
    """Last-resort subject guess from the sentence's own Latin words.

    Narration may be non-Latin (this pipeline's is Telugu), in which case there
    is nothing here to scrape and the caller gets an empty subject - which the
    scoring stage treats as "no lexical signal" rather than pretending to match.
    """
    words = re.findall(r"[A-Za-z][A-Za-z'-]+", sentence)
    meaningful = [w for w in words if len(w) > 3]
    return " ".join(meaningful[:3]).lower()


def storyboard_table(rows: List[dict]) -> str:
    """Render the pre-render storyboard as a readable fixed-width table.

    Printed before any rendering happens so the shot choices can be reviewed
    while they are still cheap to change, rather than after a full export.
    Each row is a dict with: sentence, queries, clip, reason, crop_mode, score.
    """
    if not rows:
        return "(empty storyboard)"

    headers = ["#", "SENTENCE", "QUERIES", "SELECTED CLIP", "WHY IT MATCHES", "CROP", "SCORE"]
    widths = [3, 34, 30, 22, 34, 14, 6]

    def cell(text: str, width: int) -> str:
        text = re.sub(r"\s+", " ", str(text)).strip()
        if len(text) > width:
            text = text[: width - 1] + "…"
        return text.ljust(width)

    line = "  ".join("-" * w for w in widths)
    out = ["  ".join(cell(h, w) for h, w in zip(headers, widths)), line]

    for i, row in enumerate(rows, start=1):
        queries = row.get("queries") or []
        out.append(
            "  ".join(
                [
                    cell(i, widths[0]),
                    cell(row.get("sentence", ""), widths[1]),
                    cell(" | ".join(queries), widths[2]),
                    cell(row.get("clip", ""), widths[3]),
                    cell(row.get("reason", ""), widths[4]),
                    cell(row.get("crop_mode", ""), widths[5]),
                    cell(row.get("score", ""), widths[6]),
                ]
            )
        )

    return "\n".join(out)


def brief_rows(briefs: List[SceneBrief], selections: Optional[List[dict]] = None) -> List[dict]:
    """Zip briefs with their chosen clips into storyboard_table rows."""
    rows = []
    for i, brief in enumerate(briefs):
        selection = selections[i] if selections and i < len(selections) else {}
        rows.append(
            {
                "sentence": brief.sentence,
                "queries": brief.queries[:3],
                "clip": selection.get("clip", "-"),
                "reason": selection.get("reason", brief.summary()),
                "crop_mode": selection.get("crop_mode", "-"),
                "score": selection.get("score", "-"),
            }
        )
    return rows
