import os

# config.py fails fast if these are missing; tests never make real API calls with them.
os.environ.setdefault("OPENAI_API_KEY_AUTO_YT_SHORTS", "test-openai-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
