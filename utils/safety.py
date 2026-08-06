"""Kid-safety gate for every piece of generated text.

The prompts ask for child-appropriate content, but a prompt is a request, not a
guarantee: models drift, and "Indian History" is one bad completion away from a
battle death toll. This module is the guarantee. Every topic, title, script and
description passes through `assert_safe` before it can become a video, and a
rejection forces regeneration rather than being patched up - a script that had
to have the violence edited out of it is not a script worth keeping.

The check is deliberately a blocklist of surface terms rather than a model call:
it is free, instant, deterministic, and cannot itself hallucinate. It will not
catch everything a clever adult could smuggle past it, and it is not meant to
replace human review before publishing - it is a floor, not a ceiling.
"""

import logging
import re
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)


class UnsafeContentError(Exception):
    """Raised when generated text is not suitable for young children."""

    def __init__(self, matches: List[str], where: str, text: str):
        self.matches = matches
        self.where = where
        self.text = text
        super().__init__(
            f"{where} rejected as unsuitable for children "
            f"(matched: {', '.join(sorted(set(matches)))})"
        )


# English terms. Matched on word boundaries so "grape" doesn't trip "rape" and
# "classic" doesn't trip "ass" - substring matching on a list like this produces
# constant false positives and trains you to ignore the gate.
_BLOCKED_EN = (
    # violence / death
    "kill", "killed", "killing", "murder", "murdered", "death", "dead", "die",
    "died", "dying", "blood", "bloody", "gore", "war", "weapon", "gun", "guns",
    "shot", "shoot", "shooting", "bomb", "bombing", "attack", "attacked",
    "torture", "suicide", "massacre", "slaughter", "corpse", "assassinate",
    "assassinated", "stabbed", "violence", "violent", "brutal", "execution",
    # horror / fear
    "horror", "scary", "terrifying", "nightmare", "ghost", "haunted", "demon",
    "devil", "satan", "zombie", "monster", "creepy", "curse", "cursed", "evil",
    "possessed", "exorcism", "paranormal", "occult",
    # adult / romance
    "sex", "sexy", "sexual", "nude", "naked", "porn", "erotic", "kiss",
    "kissing", "romance", "romantic", "dating", "affair", "pregnant",
    "pregnancy", "seduce", "lust", "intimate",
    # substances
    "alcohol", "beer", "wine", "whisky", "drunk", "drug", "drugs", "cocaine",
    "smoking", "cigarette", "tobacco", "vape", "addiction", "overdose",
    # politics / religion-as-conflict
    "politics", "political", "politician", "election", "vote", "voting",
    "party", "minister", "government", "protest", "riot", "communal",
    "caste", "religion", "religious", "conversion", "propaganda",
    # controversy / crime
    "controversy", "controversial", "scandal", "banned", "arrested", "jail",
    "prison", "crime", "criminal", "thief", "steal", "stolen", "fraud",
    "corruption", "lawsuit", "abuse", "abusive", "harassment", "bully",
    "bullying", "racist", "racism", "hate",
    # money bait unsuitable for kids
    "gambling", "betting", "casino", "lottery", "crypto", "bitcoin",
    # body / medical distress
    "disease", "cancer", "tumor", "surgery", "wound", "injury", "injured",
    "bleeding", "vomit", "poison", "poisonous", "venom",
)

# Telugu terms. Matched as plain substrings: Telugu is agglutinative, so a stem
# routinely appears with case and postposition suffixes glued on, and a word
# boundary regex would miss most real occurrences. Every entry is therefore
# chosen to be long and specific enough that an incidental substring hit is
# implausible.
_BLOCKED_TE = (
    # violence / death
    "చంపు", "చంపి", "చంపే", "హత్య", "మరణ", "చనిపో", "చావు", "రక్తం", "యుద్ధ",
    "ఆయుధ", "తుపాకి", "బాంబు", "దాడి", "హింస", "క్రూర", "ఆత్మహత్య", "కత్తి",
    # horror / fear
    "భయంకర", "దెయ్యం", "భూతం", "పిశాచ", "రాక్షస", "శాపం", "మంత్రగా", "క్షుద్ర",
    # adult / romance
    "శృంగార", "ప్రేమికు", "ముద్దు", "నగ్న", "లైంగిక", "గర్భవతి", "వ్యభిచార",
    # substances
    "మద్యం", "సారా", "తాగుబోతు", "మత్తు", "సిగరెట్", "పొగాకు", "డ్రగ్",
    # politics / conflict
    "రాజకీయ", "ఎన్నిక", "ఓటు", "మంత్రి", "ప్రభుత్వ", "నిరసన", "అల్లర్ల",
    "కులం", "మతం", "మతపర",
    # controversy / crime
    "వివాద", "కుంభకోణ", "అరెస్ట్", "జైలు", "నేరం", "దొంగ", "మోసం", "అవినీతి",
    "వేధింపు", "ద్వేష",
    # medical distress
    "వ్యాధి", "క్యాన్సర్", "గాయం", "విషం", "ఆపరేష",
)

_EN_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _BLOCKED_EN) + r")\b",
    re.IGNORECASE,
)


def find_unsafe(text: str) -> List[str]:
    """Return every blocked term found in `text` (empty list means clean)."""
    if not text:
        return []

    matches = [m.group(0).lower() for m in _EN_PATTERN.finditer(text)]
    matches.extend(term for term in _BLOCKED_TE if term in text)
    return matches


def is_safe(text: str) -> bool:
    """True when `text` contains no blocked terms."""
    return not find_unsafe(text)


def assert_safe(text: str, where: str = "content") -> str:
    """Return `text` unchanged, or raise UnsafeContentError describing the hit."""
    matches = find_unsafe(text)
    if matches:
        raise UnsafeContentError(matches, where, text)
    return text


def safe_or_none(text: str, where: str = "content") -> Optional[str]:
    """`text` if it is safe, otherwise None with a warning logged.

    For places that have a usable fallback and shouldn't abort the whole run.
    """
    matches = find_unsafe(text)
    if matches:
        logger.warning(
            "%s rejected as unsuitable for children (matched: %s)",
            where,
            ", ".join(sorted(set(matches))),
        )
        return None
    return text


def filter_safe(items: Iterable[str], where: str = "item") -> List[str]:
    """Keep only the safe entries of `items`, logging each rejection."""
    kept = []
    for item in items:
        if safe_or_none(item, where) is not None:
            kept.append(item)
    return kept
