import json
import logging
import random
import re
import time
from typing import List, Optional

import requests
from openai import OpenAI

from config import (
    GEMINI_API_KEY,
    GEMINI_TEXT_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    POSSIBLE_TOPICS,
)
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

_base_prompt = """
You are a passionate Tiktok creator and you want to create more short form content. Your videos contain a voiceover, stock footage and subtitles.
The content of the video is one informative, interesting or mind-blowing fact about the topic which people will find interesting.
Your videos are not too complex, they should bring the message across in a simple and engaging way.
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


def get_topic() -> str:
    """Picks a random category from POSSIBLE_TOPICS as a genre anchor, then makes
    one Gemini call specializing it into a concrete, curiosity-driven, emotionally
    charged Shorts topic - not just a repeat of the category name. Falls back to
    the raw category string (the old behavior) if the call fails, so a flaky LLM
    call never breaks a run."""
    category = random.choice(POSSIBLE_TOPICS)

    _prompt = (
        _base_prompt
        + f"""
You've been given a broad content category: "{category}".

Specialize this into ONE specific, concrete Shorts topic - not the category
itself, but a single fact/angle/entity within it. Pick the angle most likely to
make someone stop scrolling and watch to the end. Use these criteria:

- CURIOSITY GAP: the topic must promise a specific payoff ("why X happened",
  "what X actually did") that a 20-30 second video can fully deliver - avoid
  vague, unresolvable hype with no real answer.
- EMOTIONAL CHARGE: pick an angle that provokes surprise, disbelief, injustice,
  or awe - not a flat, textbook fact.
- SPECIFICITY: name a real person, event, place, product, or number where
  possible. "A celebrity's controversial statement" is too vague; "why a famous
  chef was banned from his own restaurant" is specific.

Respond with JSON in the following format:
{{
    "topic": "..."
}}
"""
    )

    try:
        response = _generate(_prompt, json_mode=True)
        topic = json.loads(response)["topic"].strip()
        return topic or category
    except Exception as e:
        logger.warning(f"get_topic LLM specialization failed, using raw category: {e}")
        return category


def get_titles(topic: str) -> List[str]:
    _prompt = (
        _base_prompt
        + """
The next message will contain the name of the topic, that you want to make a Tiktok about.
The length of the video should be between 15 and 30 seconds.

Generate highly engaging titles that will stop users from scrolling. The FIRST 3 WORDS are CRITICAL - they must immediately grab attention.

A good hook creates a SPECIFIC, nameable gap between what the viewer knows and
what they want to know, and telegraphs that the answer is coming without giving
it away - a vague tease ("you won't believe this") is weaker than one with a
concrete referent ("this NASA photo got a scientist fired"). Reject a candidate
title if it's so vague it could describe five unrelated facts equally well -
a title must be specific enough that only one script could follow it.

Use these proven viral title formulas:
- Shock/Mystery: "You won't believe...", "This will shock you...", "Scientists discovered..."
- Numbers/Stats: "97% of people don't know...", "In just 3 seconds...", "Only 1 in 1000..."
- Direct Questions: "Did you know that...", "What if I told you...", "Have you ever wondered..."
- Urgency: "Before you scroll...", "Stop what you're doing...", "This changes everything..."
- Authority: "Experts revealed...", "[Celebrity name] uses this...", "Billionaires know this secret..."
- Contradiction: "Everyone thinks [X] but actually...", "This looks normal, but..."

REQUIREMENTS:
- Include a famous person, brand, or well-known entity when possible
- Focus on ONE specific shocking/interesting fact
- Create curiosity gaps that demand answers
- Use power words: secret, revealed, discovered, shocking, hidden, truth, exposed
- Make the first 3 words irresistible

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

    response = _generate(_prompt, topic, json_mode=True)

    return json.loads(response)["titles"]


def get_most_engaging_titles(titles: List[str], n: int = 1) -> List[str]:
    _prompt = (
        _base_prompt
        + """
You will be presented with a list of possible title for your video and a corresponding number.
Sort the titles by the most engaging one first and respond with a list of indices.
They should have a name of a famous person, event, product or company, choose the one that is most engaging.

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

Create a compelling caption that amplifies engagement and encourages interaction. The description should complement the video content and drive more views.

DESCRIPTION STRATEGY:
- Start with a hook that reinforces the video's intrigue
- Include a call-to-action that encourages comments
- Use relevant hashtags strategically
- Create FOMO (fear of missing out)
- Ask questions that spark debate or discussion

STRUCTURE:
1. Hook line (builds on video's shock value)
2. Engagement question or controversial statement
3. Call-to-action for comments/shares
4. Strategic hashtags

EXAMPLES OF ENGAGEMENT TACTICS:
- "Wait until you see what happens next..."
- "This blew my mind - did you know this?"
- "Comment 'MIND BLOWN' if this shocked you"
- "Tag someone who needs to see this"
- "Most people have no idea about this..."

Keep it concise but impactful. Focus on maximizing comments and shares.

Do not under any circumstance reference this prompt in your response.

ONLY RETURN THE RAW DESCRIPTION. DO NOT RETURN ANYTHING ELSE.
"""
    )

    return _generate(_prompt).strip()


def get_script(title: str) -> str:
    _prompt = (
        _base_prompt
        + f"""
You have decided on the title for your video: "{title}".

Create a script that hooks viewers IMMEDIATELY. The first 3-5 words are CRITICAL - they determine if someone keeps watching or scrolls away.

SCRIPT STRUCTURE:
1. HOOK (0-3 seconds): Start with an attention-grabbing opener that creates instant intrigue
2. REVELATION (3-15 seconds): Deliver the shocking/interesting fact with specific details
3. IMPACT (15-30 seconds): End with why this matters or a memorable conclusion

PROVEN OPENING HOOKS:
- Shock: "This will terrify you...", "You've been lied to...", "This changes everything..."
- Numbers: "In 3 seconds, you'll discover...", "97% of people don't know..."
- Questions: "What if I told you...", "Did you know that right now..."
- Contradiction: "Everyone believes [X], but actually...", "This looks innocent, but..."
- Urgency: "Before you scroll past this...", "Stop what you're doing..."

REQUIREMENTS:
- NO introductions, greetings, or "welcome" phrases
- Jump straight into the hook within the first 3 words
- Use conversational, natural speech patterns
- Include specific names, numbers, or details when possible
- Create curiosity that demands immediate answers
- End with impact that makes them want to share
- 15-30 seconds of speaking time
- Write in short, single-idea sentences (roughly 4-14 words each). Each
  sentence must express exactly ONE concrete, visualizable idea - avoid joining
  two ideas with "and"/commas into one long sentence, since each sentence will
  be paired with its own distinct visual in editing. Prefer a period over a
  comma between ideas.

TONE: Conversational but urgent, like you're sharing an incredible secret with a friend.

ONLY RETURN THE RAW SCRIPT. DO NOT RETURN ANYTHING ELSE.
"""
    )

    return _generate(_prompt).strip()


def get_search_terms(title: str, script: str) -> list:
    """Returns one Pexels search query per sentence in `script`, in narration
    order - `len(result) == len(split_sentences(script))` is guaranteed by
    `_align_terms_to_sentence_count`, regardless of what the LLM actually
    returned, so callers never have to defend against a mismatched count."""
    sentences = split_sentences(script)

    if not sentences:
        return []

    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))

    _prompt = (
        _base_prompt
        + f"""
You have decided on the title for your video: "{title}".

The script has been split into {len(sentences)} sentences, in narration order:
{numbered}

Generate EXACTLY {len(sentences)} Pexels stock-video search queries, one per
sentence, IN THE SAME ORDER. Each query must describe a concrete, literally
filmable scene that directly illustrates THAT SPECIFIC sentence's content -
use concrete nouns and actions, not the video's abstract topic. For example,
for the sentence "the market crashed overnight" use "stock market crash red
numbers screen", not "economy".

Do not repeat the same query for two consecutive sentences even if they're
topically similar - vary the shot (wide vs. close-up, different subject,
different action) so the footage doesn't feel repetitive.

Respond with JSON in the following format:
{{
    "search_terms": [<exactly {len(sentences)} strings, one per sentence above>]
}}
"""
    )

    try:
        response = _generate(_prompt, json_mode=True)
        terms = json.loads(response)["search_terms"]
    except Exception as e:
        logger.warning(f"get_search_terms LLM call failed, deriving terms from sentences: {e}")
        terms = []

    return _align_terms_to_sentence_count(terms, sentences)


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
    """Cheap, non-LLM fallback query: the sentence's own first ~6 significant
    words, punctuation stripped - used only when the LLM returned zero usable
    search terms at all."""
    words = re.findall(r"[A-Za-z0-9']+", sentence)
    return " ".join(words[:6]) or "abstract background"
