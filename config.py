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
# "gemini-flash-latest" is a Google-maintained alias that always points at the
# current recommended Flash model, avoiding a hardcoded version that later gets
# retired for new accounts.
GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest")

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

ASSEMBLY_AI_API_KEY = os.environ.get("ASSEMBLY_AI_API_KEY")

NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

TEMP_PATH = Path("temp")

os.makedirs(TEMP_PATH, exist_ok=True)

OUTPUT_PATH = Path("output")

os.makedirs(OUTPUT_PATH, exist_ok=True)

BACKGROUND_SONGS_PATH = Path("music")

SECONDARY_CONTENT_PATH = Path("secondary_video")

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
