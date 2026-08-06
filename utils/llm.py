import json
import logging
import random
import re
import time
from typing import List, Optional

import requests
from openai import OpenAI

from config import (
    AUDIENCE_MAX_AGE,
    AUDIENCE_MIN_AGE,
    GEMINI_API_KEY,
    GEMINI_TEXT_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    POSSIBLE_TOPICS,
)
from utils.characters import ART_STYLE, cast_for_topic, describe_appearance, describe_cast
from utils.safety import UnsafeContentError, find_unsafe, is_safe
from utils.text import split_sentences

logger = logging.getLogger(__name__)

# OpenAI is optional: only initialized (and only ever called) as a fallback when
# Gemini - the default provider - fails or isn't configured.
_openai_client: Optional[OpenAI] = None
if OPENAI_API_KEY:
    client_kwargs = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        logger.info(f"Using OpenAI base URL: {OPENAI_BASE_URL}")
        client_kwargs["base_url"] = OPENAI_BASE_URL
    _openai_client = OpenAI(**client_kwargs)

_base_prompt = f"""
You are the head writer at a professional Telugu children's educational comedy
studio. You make short cartoon videos for Telugu-speaking children aged
{AUDIENCE_MIN_AGE}-{AUDIENCE_MAX_AGE}. Every video teaches ONE real concept and makes children laugh
while learning it.

Your absolute rules, which override every other instruction:
- Write in natural, conversational Telugu - the Telugu a loving family actually
  speaks at home, not textbook or news Telugu. Use simple everyday words a
  {AUDIENCE_MIN_AGE}-year-old already knows. Never use difficult Sanskrit-heavy vocabulary.
- The content must be 100% original, safe, gentle and joyful.
- ABSOLUTELY FORBIDDEN: violence, death, injury, weapons, war, blood, horror,
  ghosts, monsters, anything frightening, romance, adult themes, alcohol,
  smoking, drugs, politics, elections, government, caste, religious conflict,
  crime, controversy, scandal, gambling, disease or medical distress.
  Not even as a joke, a passing mention, or a "bad example" to avoid.
- Comedy comes from silliness, surprise, funny sounds, harmless mistakes and
  playful teasing between friends. Never from insults, cruelty, fear, or anyone
  being hurt or humiliated.
- The teaching must be factually correct. A joke is never worth teaching a
  child something false.
"""


def _call_gemini(prompt: str, user_content: Optional[str], json_mode: bool, retries: int = 2) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_TEXT_MODEL}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}

    generation_config = {"temperature": 0.8}
    if json_mode:
        generation_config["responseMimeType"] = "application/json"

    payload = {"generationConfig": generation_config}
    if user_content is not None:
        payload["systemInstruction"] = {"parts": [{"text": prompt}]}
        payload["contents"] = [{"role": "user", "parts": [{"text": user_content}]}]
    else:
        payload["contents"] = [{"role": "user", "parts": [{"text": prompt}]}]

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            last_error = e
            logger.warning(f"Gemini text generation attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(1.5 * attempt)

    raise Exception(f"Gemini text generation failed after {retries} attempts: {last_error}")


def _call_openai(prompt: str, user_content: Optional[str], json_mode: bool) -> str:
    if _openai_client is None:
        raise Exception("OpenAI fallback unavailable: OPENAI_API_KEY_AUTO_YT_SHORTS not set")

    if user_content is not None:
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ]
    else:
        messages = [{"role": "user", "content": prompt}]

    kwargs = {"response_format": {"type": "json_object" if json_mode else "text"}}

    response = (
        _openai_client.chat.completions.create(
            messages=messages,
            model=OPENAI_MODEL,
            **kwargs,
        )
        .choices[0]
        .message.content
    )
    return response


def _generate(prompt: str, user_content: Optional[str] = None, json_mode: bool = False) -> str:
    """Gemini is the default text-generation provider. OpenAI is used only as a
    fallback, and only when it's configured (OPENAI_API_KEY_AUTO_YT_SHORTS set)."""
    if GEMINI_API_KEY:
        try:
            return _call_gemini(prompt, user_content, json_mode)
        except Exception as e:
            if _openai_client is None:
                raise
            logger.warning(f"Gemini generation failed, falling back to OpenAI: {e}")
            return _call_openai(prompt, user_content, json_mode)

    if _openai_client is not None:
        return _call_openai(prompt, user_content, json_mode)

    raise Exception("No LLM provider configured: set GEMINI_API_KEY or OPENAI_API_KEY_AUTO_YT_SHORTS")


def _generate_safe(
    prompt: str,
    user_content: Optional[str] = None,
    json_mode: bool = False,
    where: str = "content",
    attempts: int = 3,
) -> str:
    """`_generate`, but the result must clear the kid-safety gate.

    A rejected generation is regenerated from scratch rather than sanitized:
    stripping the unsafe phrase out of a script leaves a script that was heading
    somewhere unsuitable, and the surrounding sentences usually still lean that
    way. Raises UnsafeContentError if every attempt is rejected, which fails the
    video rather than shipping something borderline to a child.
    """
    last_matches: List[str] = []

    for attempt in range(1, attempts + 1):
        response = _generate(prompt, user_content, json_mode)
        matches = find_unsafe(response)
        if not matches:
            return response

        last_matches = matches
        logger.warning(
            "%s attempt %d/%d rejected by the kid-safety gate (matched: %s); regenerating",
            where,
            attempt,
            attempts,
            ", ".join(sorted(set(matches))),
        )

    raise UnsafeContentError(last_matches, where, "")


def get_topic() -> str:
    """Picks a learning area from POSSIBLE_TOPICS, then makes one LLM call
    turning it into a concrete lesson a Telugu child would actually want to
    watch. Falls back to the raw category if the call fails, so a flaky LLM
    never breaks a run."""
    category = random.choice(POSSIBLE_TOPICS)

    _prompt = (
        _base_prompt
        + f"""
You've been given a learning area: "{category}".

Turn it into ONE specific, concrete lesson for a single short cartoon video -
not the whole area, but one small idea a child can fully understand in 30
seconds. Use these criteria:

- ONE CONCEPT ONLY: "why the sky is blue" is a lesson; "the science of light"
  is a syllabus. A child must be able to repeat what they learned in one
  sentence afterwards.
- CHILD'S CURIOSITY: pick the question children actually ask out loud - "why do
  we hiccup", "where does rain go", "why do cats always land on their feet".
- EVERYDAY ANCHOR: it should connect to something in a Telugu child's daily
  life - the kitchen, the school, the street, festivals, animals they see.
- COMIC POTENTIAL: the idea should have an obvious funny angle - something
  silly to imagine, or a wrong guess that would be hilarious.
- HAPPY AND SAFE: nothing frightening, sad, or upsetting. No danger, no harm.

Write the topic in English (it is used internally for search and filing), but
choose something that will work beautifully in Telugu.

Respond with JSON in the following format:
{{
    "topic": "..."
}}
"""
    )

    try:
        response = _generate(_prompt, json_mode=True)
        topic = json.loads(response)["topic"].strip()
        if not topic:
            return category
        # A topic that fails the gate is discarded rather than retried: the
        # category it came from is always safe, so falling back costs nothing.
        if not is_safe(topic):
            logger.warning(
                "get_topic produced an unsafe topic (%r); using the category instead", topic
            )
            return category
        return topic
    except Exception as e:
        logger.warning(f"get_topic LLM specialization failed, using raw category: {e}")
        return category


def get_titles(topic: str) -> List[str]:
    _prompt = (
        _base_prompt
        + """
The next message contains the lesson for your next video.

Write 6 candidate titles IN TELUGU SCRIPT. These are YouTube Kids titles, so
they must appeal to a curious child AND to the parent who taps play.

WHAT MAKES A GOOD TITLE HERE:
- Ask the child's own question: "సూర్యుడు ఎందుకు వేడిగా ఉంటాడు?" - a question a
  child has actually wondered about beats any clever wordplay.
- Promise a real answer the video delivers. Never tease something the video
  doesn't explain.
- Say the concept plainly, so a parent searching for it can find it.
- Keep it SHORT - under 60 characters. It must be readable at a glance.
- Warm and playful, never shouty. No ALL CAPS, no "SHOCKING", no fake urgency,
  no clickbait that the video doesn't pay off. Children's content that
  over-promises is a broken promise to a child.
- You may include ONE cheerful emoji if it fits naturally.

Write every title in Telugu script. Do not transliterate Telugu into English
letters.

Respond with JSON in the following format:
{
    "titles": [
        "Title 1",
        ...
        "Title n"
    ]
}
    """
    )

    response = _generate_safe(_prompt, topic, json_mode=True, where="titles")
    titles = json.loads(response)["titles"]

    return [t for t in titles if isinstance(t, str) and t.strip()]


def get_most_engaging_titles(titles: List[str], n: int = 1) -> List[str]:
    _prompt = (
        _base_prompt
        + """
You will be presented with a list of possible title for your video and a corresponding number.
Sort the titles by the best one first and respond with a list of indices.
The best title is the one a curious Telugu child would most want to tap, that a
parent would be happy to see them watch, and that most clearly names the thing
being taught. Prefer clarity and warmth over cleverness.

Respond with JSON in the following format:
{
    "most_engaging_titles": [n, m, ...]
}
"""
    )

    response = _generate(
        _prompt,
        "\n".join([f"{i+1}. {title}" for i, title in enumerate(titles)]),
        json_mode=True,
    )

    most_engaging_titles = json.loads(response)["most_engaging_titles"]

    # The prompt numbers titles 1-based ("1. title"); convert to 0-based here
    # rather than indexing the raw numbers directly. The old code did
    # `titles[i] for i in most_engaging_titles`, which silently returned the
    # WRONG title whenever the model (correctly, per the prompt) returned 1 for
    # its top pick - `titles[1]` is the SECOND title, not the first.
    sorted_titles = [
        titles[i - 1]
        for i in most_engaging_titles
        if isinstance(i, int) and 1 <= i <= len(titles)
    ]

    if not sorted_titles:
        sorted_titles = titles[:n]

    return sorted_titles[:n]


def get_description(title: str, script: str) -> str:
    _prompt = (
        _base_prompt
        + f"""
You have decided that your video is about {title}.
The Script for your video is:
{script}

Write the YouTube description. It is read by parents and teachers deciding
whether to let a child watch, and by YouTube Kids' search - so it must be
genuinely informative, never bait.

STRUCTURE:
1. One or two warm Telugu sentences saying exactly what the child will learn.
2. A line naming the characters in this video, so families recognise the show.
3. A gentle line for parents: that this is original, safe, ad-friendly
   educational content made for children.
4. One friendly question inviting a comment - about the lesson, never a
   demand to like/subscribe/share.
5. Hashtags on the final line.

HASHTAGS: 8-12 of them, mixing Telugu and English, all describing the real
subject and audience - for example #తెలుగు #పిల్లలు #విద్య #సైన్స్
#TeluguKids #KidsLearning #EducationalCartoon. No unrelated trending tags.

RULES:
- Telugu script for the prose. Hashtags may be Telugu or English.
- No fake urgency, no "you won't believe", no engagement bait.
- Nothing that isn't actually in the video.

Do not under any circumstance reference this prompt in your response.

ONLY RETURN THE RAW DESCRIPTION. DO NOT RETURN ANYTHING ELSE.
"""
    )

    return _generate_safe(_prompt, where="description").strip()


def get_script(title: str, topic: str = "") -> str:
    """Write the Telugu narration for one video.

    Returns plain narration text - one sentence per beat, no speaker labels and
    no stage directions - because everything downstream (sentence splitting,
    per-sentence artwork, word-timed subtitles) consumes exactly the words that
    get spoken. The cast still shapes the writing: characters are named inside
    the narration, so the story has recognisable people in it without the
    script needing a screenplay format the renderer can't use.
    """
    cast = cast_for_topic(topic or title)
    guide, sidekick = cast[0], cast[1]

    _prompt = (
        _base_prompt
        + f"""
Write the narration for a short Telugu cartoon video titled: "{title}".

YOUR RECURRING CHARACTERS (the children already know them - use these two, by
name, and keep them exactly in character):
{describe_cast(cast)}

THE SHAPE OF THE STORY (about 30-40 seconds spoken):
1. HOOK - the very first sentence must make a child curious. Best openers are a
   funny question, a silly wrong guess by {sidekick.name}, or a strange sound.
   No greetings. No "ఈ రోజు మనం నేర్చుకుందాం". Start inside the moment.
2. THE SILLY MISTAKE - {sidekick.name} guesses wrong in a way that makes
   children giggle. This is the comedy engine of the video.
3. THE REAL ANSWER - {guide.name} explains the true concept, simply and
   correctly, using something from a child's everyday life as the comparison.
4. THE "AHA" - one sentence where the child feels they understood it.
5. MEMORABLE ENDING - a warm, funny last line. Use a catchphrase where it fits,
   and end on a small happy beat children will remember and repeat.

HOW TO WRITE THE TELUGU:
- Natural spoken Telugu, the way an affectionate family talks at home.
- Simple words only. If a {AUDIENCE_MIN_AGE}-year-old wouldn't know a word, choose another one.
- Name the characters inside the narration so children follow who is doing what:
  e.g. "{sidekick.name} నవ్వుతూ అడిగింది..." then what they said.
- Add playful sound words - "ధడేల్!", "టప్!", "హిహిహి" - children love them.
- Warm, energetic, smiling. Like a favourite aunt telling a joke.

HARD FORMATTING RULES:
- Write ONLY the words that are spoken aloud, in Telugu script.
- NO speaker labels ("చిట్టి:"), NO stage directions, NO scene headings, NO
  narrator notes, NO markdown, NO numbering, NO emoji.
- Short, single-idea sentences. Each sentence becomes its own illustration, so
  each must describe exactly ONE thing a picture can show. Split ideas with a
  full stop rather than joining them with "మరియు" or a comma.
- Between 8 and 14 sentences total.
- The concept taught must be factually TRUE.

ONLY RETURN THE RAW TELUGU NARRATION. NOTHING ELSE.
"""
    )

    return _generate_safe(_prompt, where="script").strip()


def get_visual_prompts(title: str, script: str, topic: str = "") -> list:
    """One cartoon-illustration prompt per sentence, in narration order.

    This replaces the old stock-footage search terms. Stock video cannot show a
    recurring cartoon character tipping a bucket of water over their own head,
    and a channel illustrated with unrelated clips of strangers does not look
    like a children's studio - so every sentence gets a purpose-drawn frame
    instead of a search query.

    `len(result) == len(split_sentences(script))` is guaranteed regardless of
    what the model returns, so callers never have to defend against a mismatch.
    """
    sentences = split_sentences(script)

    if not sentences:
        return []

    cast = cast_for_topic(topic or title)
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))

    _prompt = (
        _base_prompt
        + f"""
You are art-directing the cartoon for a video titled: "{title}".

The narration has been split into {len(sentences)} sentences, in order:
{numbered}

THE CAST AND HOW THEY MUST LOOK (identical in every frame):
{describe_appearance(cast)}

Write EXACTLY {len(sentences)} image-generation prompts, one per sentence, IN
THE SAME ORDER. Each prompt describes the single cartoon frame illustrating
THAT sentence.

RULES FOR EACH PROMPT:
- Write the prompt IN ENGLISH (the image model reads English), even though the
  narration is Telugu.
- Describe one clear, concrete moment a picture can show - the actual thing
  happening in that sentence, not the video's abstract subject.
- If a character appears, name them AND restate their appearance from the list
  above, so the drawing matches the surrounding frames.
- Vary the framing between consecutive prompts - wide shot, close-up on a face,
  overhead - so the video doesn't feel static.
- Keep every frame bright, happy and safe. No frightening imagery, no darkness,
  nobody hurt or sad.
- Never ask for text, letters, numbers or speech bubbles in the image. Words are
  added later by the renderer, and generated lettering comes out garbled.

Respond with JSON in the following format:
{{
    "visual_prompts": [<exactly {len(sentences)} strings, one per sentence above>]
}}
"""
    )

    try:
        response = _generate(_prompt, json_mode=True)
        prompts = json.loads(response)["visual_prompts"]
    except Exception as e:
        logger.warning(
            f"get_visual_prompts LLM call failed, deriving prompts from sentences: {e}"
        )
        prompts = []

    prompts = _align_terms_to_sentence_count(prompts, sentences)

    # The house style is appended here rather than requested inside the prompt:
    # it must appear on every frame verbatim, and a model asked to repeat a long
    # style string a dozen times paraphrases it and lets the look drift.
    return [f"{p}. {ART_STYLE}" for p in prompts]


def _align_terms_to_sentence_count(terms: list, sentences: List[str]) -> list:
    """Defensively pads/truncates so callers can always assume
    len(result) == len(sentences), regardless of what the LLM returned (wrong
    count, non-string entries, or the call failing entirely)."""
    terms = [t for t in terms if isinstance(t, str) and t.strip()]

    if len(terms) > len(sentences):
        return terms[: len(sentences)]

    if not terms:
        # Zero usable terms: derive one query per sentence from its own text
        # rather than a generic placeholder.
        return [_derive_query_from_sentence(s) for s in sentences]

    aligned = list(terms)
    while len(aligned) < len(sentences):
        aligned.append(aligned[-1])

    return aligned


def _derive_query_from_sentence(sentence: str) -> str:
    """Cheap, non-LLM fallback prompt, used only when the model returned zero
    usable prompts at all.

    The narration is Telugu, so this cannot just scrape Latin words out of the
    sentence the way it used to - on Telugu input that regex matches nothing and
    every frame silently collapses to the same placeholder. It also cannot feed
    Telugu text to an English image model and expect a sensible drawing. So the
    fallback is an honest generic children's scene: bland, but on-style, safe,
    and different from a broken render.
    """
    words = re.findall(r"[A-Za-z0-9']+", sentence)
    if words:
        return " ".join(words[:6])
    return (
        "a cheerful Telugu boy and girl sitting together outdoors on a sunny "
        "day, looking curious and happy, simple friendly scene"
    )
