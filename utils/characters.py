"""The recurring cast.

Children recognise a channel by its characters long before they recognise its
topics, so the cast is fixed data rather than something the model invents per
video: the same names, personalities, catchphrases and visual descriptions are
fed to the script writer and to the illustrator on every run. That gives both a
consistent voice across videos and a consistent *look*, which matters because
each sentence's artwork is generated independently and would otherwise drift.

Casting is deterministic in the topic, so the same topic always brings back the
same duo, and a child watching several videos sees familiar faces.
"""

import hashlib
from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class Character:
    """One member of the recurring cast.

    Attributes:
        name: Telugu name, used verbatim in scripts and on screen.
        role: One-line function in a sketch - who they are to the audience.
        personality: Traits the script writer should play for comedy.
        catchphrase: A short Telugu line this character is known for. Repetition
            across videos is the point; kids repeat it back.
        voice: Gemini prebuilt voice used when this character speaks.
        appearance: Visual description handed to the illustrator verbatim, so
            the character looks the same in every generated frame.
    """

    name: str
    role: str
    personality: str
    catchphrase: str
    voice: str
    appearance: str


# The teacher/explainer characters. One of these anchors every video: they hold
# the actual lesson, so the comedy never comes at the cost of the teaching.
GUIDES: Tuple[Character, ...] = (
    Character(
        name="బుజ్జి టీచర్",
        role="Warm, patient teacher who explains the concept",
        personality=(
            "Cheerful and encouraging, never scolds, turns mistakes into jokes, "
            "explains with everyday household examples a child already knows"
        ),
        catchphrase="చాలా బాగా చెప్పావు!",
        voice="Kore",
        appearance=(
            "a friendly young Telugu woman teacher with a round smiling face, "
            "big kind eyes, hair in a neat bun with a small jasmine flower, "
            "wearing a bright yellow and green cotton saree, holding a chalk"
        ),
    ),
    Character(
        name="తాతయ్య జ్ఞాని",
        role="Storytelling grandfather who explains through little tales",
        personality=(
            "Twinkly-eyed and playful, pretends to forget things for laughs, "
            "wraps every lesson in a tiny story with a moral"
        ),
        catchphrase="ఇది ఒక చిన్న కథ!",
        voice="Charon",
        appearance=(
            "a jolly elderly Telugu grandfather with round spectacles, a big "
            "white moustache, a shiny bald head, wearing a white dhoti and a "
            "sky-blue kurta, leaning on a wooden walking stick"
        ),
    ),
)

# The comic characters. One of these is the child's stand-in: they ask the silly
# questions, get things wrong first, and make the lesson land through the laugh.
SIDEKICKS: Tuple[Character, ...] = (
    Character(
        name="చిట్టి",
        role="Curious little girl who asks the funny questions",
        personality=(
            "Bubbly and fearless, asks the exact question a 6-year-old would, "
            "guesses hilariously wrong answers with total confidence"
        ),
        catchphrase="అయ్యో! నిజమా?",
        voice="Leda",
        appearance=(
            "a lively 7-year-old Telugu girl with two high pigtails tied with "
            "red ribbons, huge curious eyes, a gap-toothed grin, wearing a "
            "bright pink frock with white polka dots"
        ),
    ),
    Character(
        name="గోపి",
        role="Goofy boy who learns by doing everything wrong first",
        personality=(
            "Over-confident and clumsy, tries the experiment before listening, "
            "ends up covered in whatever he was holding, laughs at himself"
        ),
        catchphrase="నాకు తెలుసు... తెలియదు!",
        voice="Puck",
        appearance=(
            "a cheeky 8-year-old Telugu boy with spiky black hair, a round face "
            "with a small mischievous smile, wearing an oversized orange "
            "t-shirt and blue shorts, always slightly untidy"
        ),
    ),
    Character(
        name="పిల్లి బామ్మ",
        role="Talking cat who supplies the punchlines",
        personality=(
            "Deadpan and lazy, comments on the humans like an unimpressed elder, "
            "delivers the final joke, secretly knows the answer all along"
        ),
        catchphrase="మ్యావ్... నేను ముందే చెప్పాను!",
        voice="Zephyr",
        appearance=(
            "a plump cartoon cat with soft grey fur, enormous sleepy green eyes, "
            "tiny round spectacles perched on her nose, wearing a small maroon "
            "shawl, usually curled up somewhere in the scene"
        ),
    ),
)

# A single house style, applied to every generated frame. Kept here rather than
# in the image module because it is part of the show's identity, alongside the
# cast.
ART_STYLE = (
    "bright colorful 2D cartoon illustration for young children, thick clean "
    "outlines, flat cheerful saturated colors, soft rounded friendly shapes, "
    "simple uncluttered background, warm sunny lighting, Indian Telugu village "
    "and town setting, children's picture-book style, no text, no words, "
    "no letters, no watermark"
)


def _stable_index(seed: str, salt: str, length: int) -> int:
    """Index derived from a stable hash of `seed`.

    Deliberately not random.choice: Python's hash() is salted per process and
    random would re-cast the same topic differently on every run. A child should
    meet the same characters when the same subject comes back around.
    """
    digest = hashlib.sha256(f"{salt}:{seed}".encode("utf-8")).hexdigest()
    return int(digest, 16) % length


def cast_for_topic(topic: str) -> List[Character]:
    """Pick the guide + sidekick pair for a topic, deterministically.

    Returns exactly two characters: the guide who teaches and the sidekick who
    supplies the comedy. Two is a deliberate cap - more speakers than that in a
    30-second Short stops being funny and starts being hard for a small child to
    follow.
    """
    guide = GUIDES[_stable_index(topic, "guide", len(GUIDES))]
    sidekick = SIDEKICKS[_stable_index(topic, "sidekick", len(SIDEKICKS))]
    return [guide, sidekick]


def describe_cast(characters: List[Character]) -> str:
    """Render the cast as prompt text for the script writer."""
    return "\n".join(
        f"- {c.name} ({c.role}). Personality: {c.personality}. "
        f'Catchphrase: "{c.catchphrase}"'
        for c in characters
    )


def describe_appearance(characters: List[Character]) -> str:
    """Render the cast's looks as prompt text for the illustrator."""
    return "; ".join(f"{c.name} is {c.appearance}" for c in characters)


def voice_for_speaker(name: str, characters: List[Character], default: str) -> str:
    """Map a script's speaker label to that character's voice.

    Falls back to `default` for narration or an unrecognised label, so a model
    that invents a speaker never breaks the render.
    """
    cleaned = name.strip().rstrip(":").strip()
    for character in characters:
        if character.name == cleaned:
            return character.voice
    return default
