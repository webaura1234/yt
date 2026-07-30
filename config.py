import os
from pathlib import Path

import dotenv

dotenv.load_dotenv()

POSSIBLE_TOPICS = [
    # "NASA Facts",
    "Controversial Events",
    # "Bold Predictions",
    "Controversial Actions by Celebrities",
    "Controversial Actions by Well Known Companies",
    "Controversial Science Facts",
    "Controversial Historical Mysteries",
    "Controversial Tech Milestones",
    "Controversial Cultural Oddities",
    "Controversial Psychological Phenomena",
    "Controversial Space Exploration Events",
    "Controvercies around Cryptocurrency and Blockchain",
    "Controversial Laws",
    "Controversial Secrets of Successful People",
    "Controversial Eco-Friendly movements",
    "Controversial World Records",
]


# OpenAI is an optional fallback text-generation provider, only used when Gemini
# (the default) fails or isn't configured. No key required to run the pipeline.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY_AUTO_YT_SHORTS")

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL")

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1")

GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

# Default text-generation model for scripts/titles/descriptions/search terms.
# NOTE: previously defaulted to the "gemini-flash-latest" alias to avoid a
# hardcoded version going stale - but that alias currently resolves to a very
# new model (gemini-3.6-flash) with a free tier of only 20 requests/day, which
# real usage exhausts almost immediately. Pinned to gemini-3.1-flash-lite
# instead, which has a much more usable free-tier quota (verified directly
# against the API). Revisit this pin periodically as models change; override
# via GEMINI_TEXT_MODEL if your account's quota differs.
GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.1-flash-lite")

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

ASSEMBLY_AI_API_KEY = os.environ.get("ASSEMBLY_AI_API_KEY")

NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

TEMP_PATH = Path("temp")

os.makedirs(TEMP_PATH, exist_ok=True)

OUTPUT_PATH = Path("output")

os.makedirs(OUTPUT_PATH, exist_ok=True)

BACKGROUND_SONGS_PATH = Path("music")

SECONDARY_CONTENT_PATH = Path("secondary_video")

CREDENTIALS_PATH = Path("credentials")

CRON_SCHEDULE = os.environ.get("CRON_SCHEDULE", "31 4 * * *")

RUN_ONCE = os.environ.get("RUN_ONCE", "false").lower() == "true"

VIDEO_COUNT = int(os.environ.get("VIDEO_COUNT", "1"))

APPRISE_URL = os.environ.get("APPRISE_URL")

# Required: Gemini is the default provider for both text generation (scripts,
# titles, descriptions) and TTS voiceover.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set")

NO_UPLOAD = os.environ.get("NO_UPLOAD", "false").lower() == "true"

NOTIFY_ON_SUCCESS = os.environ.get("NOTIFY_ON_SUCCESS", "false").lower() == "true"

# Default render is a single full-screen background video (clean, cinematic Shorts
# style) - no secondary clip/split-screen overlay. Set to "true" to bring back the
# old bottom-strip secondary-video overlay as an opt-in style.
ENABLE_SECONDARY_OVERLAY = (
    os.environ.get("ENABLE_SECONDARY_OVERLAY", "false").lower() == "true"
)

# Crossfade duration (seconds) between consecutive stock-footage clips, used instead
# of hard cuts.
VIDEO_TRANSITION_DURATION = float(os.environ.get("VIDEO_TRANSITION_DURATION", "0.4"))

# Subject-aware 9:16 cropping (face-detection-based) instead of a blind center crop.
# Kill-switch for rollback, mirroring ENABLE_SECONDARY_OVERLAY's pattern.
ENABLE_SUBJECT_AWARE_CROP = (
    os.environ.get("ENABLE_SUBJECT_AWARE_CROP", "true").lower() == "true"
)

# Per-sentence sub-shot duration bounds (seconds). Sentences whose narrated
# duration exceeds MAX_SHOT_DURATION are split into multiple shorter shots for
# faster-paced editing; shorter sentences stay a single shot.
MIN_SHOT_DURATION = float(os.environ.get("MIN_SHOT_DURATION", "1.0"))
MAX_SHOT_DURATION = float(os.environ.get("MAX_SHOT_DURATION", "2.5"))

# How many distinct validated Pexels candidates to keep per script sentence (one
# Pexels search per sentence regardless of this number - it only controls how many
# of that search's results we keep, for ranking/sub-shot variety/dedup fallback).
SCENE_CANDIDATES_PER_SCENE = int(os.environ.get("SCENE_CANDIDATES_PER_SCENE", "3"))

# Ken Burns zoom/pan overscan, as a fraction of canvas size (e.g. 0.15 = clip is
# rendered 15% larger than the canvas to give the pan/zoom room to move without
# revealing an edge).
SHOT_EFFECT_INTENSITY = float(os.environ.get("SHOT_EFFECT_INTENSITY", "0.15"))
