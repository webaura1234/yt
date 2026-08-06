# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation and Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp example.env .env
# Edit .env with your API keys and credentials

# Initial YouTube OAuth setup (run once)
python upload_video.py

# Update/refresh OAuth credentials
python update_tokens.py
```

### Running the Application
```bash
# One-time execution
RUN_ONCE=true python main.py

# Scheduled execution with cron
CRON_SCHEDULE="0 */6 * * *" python main.py

# Run with Docker
docker compose up

# Testing stock video functionality
python test.py
```

### Web Dashboard
```bash
# Start both the FastAPI backend (:8000) and Next.js frontend (:3000)
./run.sh

# Skip dependency installation on repeat runs
./run.sh --no-install

# Override ports
API_PORT=8100 WEB_PORT=3100 ./run.sh
```
The dashboard boots without API keys configured (Settings writes them to `.env`),
so `config.GEMINI_API_KEY` must never be enforced at import time - use
`config.require_gemini_api_key()` at the point of use instead.

### Project Structure & Configuration
- `config.py` - Central configuration with environment variables and API keys
- `main.py` - Entry point with scheduler and video generation orchestration
- `requirements.txt` - Python dependencies
- `utils/` - Core functionality modules
- `credentials/` - YouTube OAuth credentials (client_secrets.json, tokens.json)
- `music/` - Background music files (.mp3)
- `cartoon_cache/` - Generated scene artwork, cached by prompt hash (gitignored)
- `fonts/telugu_bold.ttf` - Noto Sans Telugu Bold (OFL-1.1), required for subtitles
- `secondary_video/` - Secondary video content (.mp4)
- `temp/` - Temporary files during processing
- `output/` - Final generated videos organized by date

## Architecture Overview

This is a **Telugu educational comedy engine for children aged 5-12**. It
produces original, safe, funny cartoon Shorts that teach one real concept each,
for YouTube Kids. It is not a general-purpose Shorts generator, and changes
should not push it back toward being one.

Non-negotiables, enforced in code rather than left to prompts:
- **Telugu.** Scripts, titles, descriptions and subtitles are Telugu. Subtitle
  rendering needs both a Telugu font and shaping - see `check_subtitle_font_support`.
- **Child-safe.** `utils/safety.py` gates every generated string. Adult,
  political, violent, horror and controversial material is rejected and
  regenerated, never edited down.
- **Made for kids.** `config.MADE_FOR_KIDS` is a COPPA declaration set
  unconditionally on upload, not a toggle.

### Core Pipeline (main.py)
1. **Topic** - a learning area from `POSSIBLE_TOPICS`, specialized by an LLM
   call into one concrete lesson a child would ask about
2. **Script** - conversational Telugu comedy narration starring the recurring
   cast, structured hook -> silly mistake -> real answer -> aha -> ending
3. **Art direction** - one cartoon-illustration prompt per sentence
4. **Artwork** - each prompt drawn by the image model, cached by prompt hash
5. **Render** - artwork + Ken Burns + word-timed animated Telugu captions
6. **Upload** - Telugu metadata, Education category, made-for-kids declared

### Key Modules

**utils/characters.py** - The recurring cast. Fixed data, not model-invented, so
children recognise the same characters and the illustrator draws them the same
way every time. `cast_for_topic()` is deterministic in the topic.

**utils/safety.py** - The kid-safety gate. `assert_safe`/`is_safe`/`find_unsafe`
over an English word-boundary blocklist and a Telugu substring blocklist (Telugu
is agglutinative, so stems appear with suffixes attached). A floor, not a
substitute for human review before publishing.

**utils/llm.py** - Telugu text generation
- `_generate()` - Gemini first, OpenAI only as a configured fallback
- `_generate_safe()` - regenerates when the safety gate rejects output
- `get_topic()`, `get_titles()`, `get_script()`, `get_description()`
- `get_visual_prompts()` - one cartoon prompt per sentence (replaced the old
  `get_search_terms()` stock-footage search)

**utils/cartoon.py** - Per-sentence artwork
- `generate_scene_images()` - one drawing per sentence, cached by prompt hash;
  the dominant per-video cost
- Falls back to a generated pattern card rather than aborting a video

**utils/video.py** - Rendering
- `check_subtitle_font_support()` - fails loudly if Telugu can't render
- `combine_scene_images()` - the default background path, artwork + Ken Burns
- `combine_videos()` - legacy stock-footage path, kept only to replay old jobs
- `create_karaoke_subtitles()` - animated word-by-word Telugu captions

**utils/audio.py** - Voice
- `generate_voiceover()` - Gemini TTS, with `TELUGU_KIDS_DELIVERY` steering an
  energetic children's-storyteller performance

**utils/yt.py** - Platform upload functionality
- `auto_upload()` - YouTube upload with OAuth 2.0 authentication
- Uses `upload_video.py` script for actual upload process

### Environment Variables
Key configurations in `.env`:
- `GEMINI_API_KEY` - **Required.** Default provider for text generation and TTS
- `GEMINI_TEXT_MODEL` - Text-generation model (default: `gemini-3.1-flash-lite`)
- `OPENAI_API_KEY_AUTO_YT_SHORTS` - Optional fallback text-generation provider
- `PEXELS_API_KEY` - Stock video sourcing
- `ASSEMBLY_AI_API_KEY` - Subtitle generation
- `CRON_SCHEDULE` - Automated execution timing
- `RUN_ONCE` - Single execution mode
- `VIDEO_COUNT` - Number of videos per run
- `NO_UPLOAD` - Disable platform uploads
- `NOTIFY_ON_SUCCESS` - Success notifications via Apprise

### Execution Modes
- **Scheduled Mode**: Uses APScheduler with cron expressions for automated generation
- **One-time Mode**: Single execution when `RUN_ONCE=true`
- **Docker Mode**: Containerized execution with volume mounts for credentials and content

The system is designed for unattended operation, with comprehensive error
handling and notification systems. Unattended does not mean unreviewed: the
safety gate is a mechanical floor, and content for children should be watched by
a person before it is made public.