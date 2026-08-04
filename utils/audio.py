import base64
import json
import logging
import mimetypes
import random
import requests
import struct
import time
import uuid
import wave
from pathlib import Path
from typing import Optional, Tuple

from moviepy.editor import AudioFileClip

from config import (
    BACKGROUND_SONGS_PATH,
    GEMINI_API_KEY,
    GEMINI_API_KEY_HELP,
    GEMINI_TTS_MODEL,
    TEMP_PATH,
)
from utils.downloads import (
    attribution_credit_line,
    dedupe_folder,
    delete_media_file,
    download_file,
    write_attribution,
)

logger = logging.getLogger(__name__)

# Royalty-free (CC BY 3.0) tracks by Kevin MacLeod, incompetech.com - used only as an
# automatic fallback when music/ has no local files. Verified working direct-download URLs.
_FALLBACK_TRACKS = [
    ("Monkeys Spinning Monkeys", "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Monkeys%20Spinning%20Monkeys.mp3"),
    ("Fluffing a Duck", "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Fluffing%20a%20Duck.mp3"),
    ("Wallpaper", "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wallpaper.mp3"),
    ("Local Forecast - Elevator", "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Local%20Forecast%20-%20Elevator.mp3"),
    ("Life of Riley", "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Life%20of%20Riley.mp3"),
    ("Carefree", "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3"),
    ("Sneaky Snitch", "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Sneaky%20Snitch.mp3"),
    ("Wholesome", "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wholesome.mp3"),
]


def save_binary_file(file_path: Path, data: bytes):
    """Save binary data to a file."""
    with open(file_path, "wb") as f:
        f.write(data)


def convert_to_wav(audio_data: bytes, mime_type: str, speed: float = 1.15) -> bytes:
    """Converts audio data to WAV format with proper header and adjusts playback speed.

    Args:
        audio_data: The raw audio data as a bytes object.
        mime_type: Mime type of the audio data.
        speed: Speed multiplier for playback (e.g., 1.05 for 1.05x speed).

    Returns:
        A bytes object representing the WAV file.
    """
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    original_sample_rate = parameters["rate"]
    # Adjust sample rate to change playback speed
    sample_rate = int(original_sample_rate * speed)
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",  # ChunkID
        chunk_size,  # ChunkSize
        b"WAVE",  # Format
        b"fmt ",  # Subchunk1ID
        16,  # Subchunk1Size
        1,  # AudioFormat (PCM)
        num_channels,  # NumChannels
        sample_rate,  # SampleRate
        byte_rate,  # ByteRate
        block_align,  # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",  # Subchunk2ID
        data_size,  # Subchunk2Size
    )
    return header + audio_data


def parse_audio_mime_type(mime_type: str) -> dict[str, int]:
    """Parse bits per sample and rate from an audio MIME type string.

    Args:
        mime_type: The audio MIME type string (e.g., "audio/L16;rate=24000").

    Returns:
        A dictionary with "bits_per_sample" and "rate" keys.
    """
    bits_per_sample = 16
    rate = 24000

    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass

    return {"bits_per_sample": bits_per_sample, "rate": rate}


# Gemini TTS prebuilt voices available via speechConfig.voiceConfig.prebuiltVoiceConfig.
# "Fenrir" and "Puck" have been verified with real API calls; the rest are Google's
# documented prebuilt voice names but not individually tested here.
AVAILABLE_VOICES = [
    "Fenrir", "Puck", "Charon", "Kore", "Zephyr",
    "Aoede", "Leda", "Orus", "Callirrhoe",
]

DEFAULT_VOICE = "Fenrir"

# Free-tier quota errors (HTTP 429) shouldn't be retried on the same short backoff
# used for transient 5xx errors - Google tells us exactly how long to wait via
# error.details[].retryDelay, and that can be tens of seconds. Cap how long we're
# willing to sleep for; beyond this it's not worth blocking the caller and we
# should fail fast with the quota message intact instead.
_MAX_QUOTA_RETRY_DELAY_SECONDS = 60.0


def _quota_retry_delay_seconds(response: requests.Response) -> Optional[float]:
    """Extract Google's suggested retry delay (e.g. "53.45s") from a 429 response
    body, if present. Returns None if the response doesn't carry one."""
    try:
        details = response.json().get("error", {}).get("details", [])
    except (json.JSONDecodeError, AttributeError):
        return None

    for detail in details:
        if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
            delay = detail.get("retryDelay", "")
            try:
                return float(delay.rstrip("s"))
            except ValueError:
                return None

    return None


def generate_voiceover(text: str, voice: str = DEFAULT_VOICE, retries: int = 3) -> Path:
    """Generate voiceover audio using Google Gemini TTS REST API.

    Args:
        text: The text to convert to speech.
        voice: Gemini prebuilt voice name (see AVAILABLE_VOICES).
        retries: Number of attempts before giving up on transient (5xx/network)
            failures, retried with a short backoff. A 429 quota error is handled
            separately: retried once after Google's own suggested delay if it's
            short enough to be worth waiting for, otherwise raised immediately
            with the quota message intact rather than silently retried.

    Returns:
        Path to the generated audio file.
    """
    if not GEMINI_API_KEY:
        raise ValueError(GEMINI_API_KEY_HELP)

    audio_id = uuid.uuid4()
    audio_path = TEMP_PATH / f"{audio_id}.wav"

    # Prepare the REST API request
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_TTS_MODEL}:generateContent"

    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}

    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "temperature": 0.8,
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
            },
        },
    }

    last_error: Optional[Exception] = None
    quota_wait_used = False
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()

            response_data = response.json()

            # Extract the audio data from the response
            if (
                "candidates" in response_data
                and response_data["candidates"]
                and "content" in response_data["candidates"][0]
                and "parts" in response_data["candidates"][0]["content"]
                and response_data["candidates"][0]["content"]["parts"]
            ):
                part = response_data["candidates"][0]["content"]["parts"][0]

                if "inlineData" in part and "data" in part["inlineData"]:
                    # Decode the base64 audio data
                    audio_data = base64.b64decode(part["inlineData"]["data"])
                    mime_type = part["inlineData"].get("mimeType", "audio/wav")

                    # Convert to WAV if needed
                    file_extension = mimetypes.guess_extension(mime_type)
                    if file_extension is None or file_extension != ".wav":
                        audio_data = convert_to_wav(audio_data, mime_type)

                    save_binary_file(audio_path, audio_data)
                else:
                    raise Exception("No audio data found in API response")
            else:
                raise Exception("Invalid response structure from Gemini TTS API")

            return audio_path

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                quota_message = e.response.json().get("error", {}).get("message", str(e))
                delay = _quota_retry_delay_seconds(e.response)
                if (
                    delay is not None
                    and delay <= _MAX_QUOTA_RETRY_DELAY_SECONDS
                    and not quota_wait_used
                ):
                    quota_wait_used = True
                    logger.warning(
                        f"Gemini TTS quota exceeded, waiting {delay:.1f}s (Google's "
                        f"suggested retry delay) before one retry: {quota_message}"
                    )
                    time.sleep(delay)
                    continue

                # Either no usable delay, the delay is too long to block on, or
                # we already waited once - this is a real quota cap, not a
                # transient failure, so fail fast with the quota message intact
                # instead of burning through the remaining generic retries.
                raise Exception(f"Gemini TTS quota exceeded: {quota_message}") from e

            last_error = Exception(f"API request failed: {e}")
        except requests.exceptions.RequestException as e:
            last_error = Exception(f"API request failed: {e}")
        except json.JSONDecodeError as e:
            last_error = Exception(f"Failed to parse API response: {e}")
        except Exception as e:
            last_error = Exception(f"TTS generation failed: {e}")

        logger.warning(f"Gemini TTS attempt {attempt}/{retries} failed: {last_error}")
        if attempt < retries:
            time.sleep(1.5 * attempt)

    raise last_error


def _generate_placeholder_song(dest: Path, duration: float = 60.0, sample_rate: int = 44100) -> None:
    """Last-resort local fallback (silent track) so the pipeline never crashes for lack
    of background music, even when fully offline and no track could be downloaded."""
    num_samples = int(duration * sample_rate)
    with wave.open(str(dest), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(b"\x00\x00" * num_samples)


def _validate_audio_file(path: Path, min_duration: float = 3.0) -> bool:
    """Reject corrupt/undecodable files and clips too short to be usable background music."""
    try:
        clip = AudioFileClip(str(path))
        duration = clip.duration
        clip.close()
    except Exception as e:
        logger.warning(f"Invalid/corrupt audio file {path.name}: {e}")
        return False

    if not duration or duration < min_duration:
        logger.warning(f"Rejecting {path.name}: duration too short ({duration}s)")
        return False

    return True


_FALLBACK_TRACK_URLS = dict(_FALLBACK_TRACKS)


def _backfill_known_attribution(path: Path) -> None:
    """Older cache entries (downloaded before attribution tracking existed) have no
    sidecar. If the filename matches a known catalog track, write its required CC BY
    credit now instead of silently under-attributing it."""
    if attribution_credit_line(path) is not None:
        return
    url = _FALLBACK_TRACK_URLS.get(path.stem)
    if not url:
        return
    write_attribution(
        path,
        source="incompetech",
        license="CC BY 3.0",
        attribution_required=True,
        credit=(
            f'Music: "{path.stem}" by Kevin MacLeod (incompetech.com) '
            "— Licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/)"
        ),
        url=url,
    )


def _pick_valid_cached_song(folder: Path) -> Optional[Path]:
    """Pick a random cached track, validating it and pruning any invalid/corrupt files found."""
    candidates = list(folder.glob("*.mp3")) + list(folder.glob("*.wav"))
    random.shuffle(candidates)

    for path in candidates:
        if _validate_audio_file(path):
            _backfill_known_attribution(path)
            return path
        logger.warning(f"Removing invalid cached audio file {path.name}")
        delete_media_file(path)

    return None


def _ensure_background_music() -> None:
    BACKGROUND_SONGS_PATH.mkdir(parents=True, exist_ok=True)
    dedupe_folder(BACKGROUND_SONGS_PATH, {".mp3", ".wav"})

    if _pick_valid_cached_song(BACKGROUND_SONGS_PATH):
        return  # reuse the local cache, no need to hit the network

    logger.info("No valid background music cached locally, downloading royalty-free tracks...")

    candidates = _FALLBACK_TRACKS.copy()
    random.shuffle(candidates)

    downloaded = 0
    for name, url in candidates:
        dest = BACKGROUND_SONGS_PATH / f"{name}.mp3"
        if download_file(url, dest) and _validate_audio_file(dest):
            write_attribution(
                dest,
                source="incompetech",
                license="CC BY 3.0",
                attribution_required=True,
                credit=(
                    f'Music: "{name}" by Kevin MacLeod (incompetech.com) '
                    "— Licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/)"
                ),
                url=url,
            )
            downloaded += 1
            logger.info(f"Cached background track '{name}' (CC BY 3.0, Kevin MacLeod - incompetech.com)")
            if downloaded >= 3:
                break
        else:
            delete_media_file(dest)

    if downloaded == 0:
        logger.warning(
            "Could not download any royalty-free music (offline or source unavailable); "
            "generating a silent placeholder track instead"
        )
        placeholder = BACKGROUND_SONGS_PATH / "placeholder_silence.wav"
        _generate_placeholder_song(placeholder)
        write_attribution(placeholder, source="generated", license="N/A", attribution_required=False)


def get_random_background_song() -> Tuple[Path, Optional[str]]:
    """Returns (path_to_track, credit_line_or_None). credit_line is non-None only when the
    track's license requires attribution (e.g. Incompetech's CC BY 3.0)."""
    _ensure_background_music()

    path = _pick_valid_cached_song(BACKGROUND_SONGS_PATH)
    if path is None:
        # Final safety net: everything got pruned as invalid between ensure() and now.
        path = BACKGROUND_SONGS_PATH / f"placeholder_{uuid.uuid4()}.wav"
        _generate_placeholder_song(path)
        write_attribution(path, source="generated", license="N/A", attribution_required=False)

    return path, attribution_credit_line(path)
