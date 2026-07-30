import logging
import math
import os
import random
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

import assemblyai as aai
import cv2
import numpy as np
import requests
from moviepy.audio.fx.all import volumex
from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx.all import crop, freeze

from config import (
    ASSEMBLY_AI_API_KEY,
    ENABLE_SECONDARY_OVERLAY,
    ENABLE_SUBJECT_AWARE_CROP,
    MAX_SHOT_DURATION,
    MIN_SHOT_DURATION,
    OUTPUT_PATH,
    PEXELS_API_KEY,
    SECONDARY_CONTENT_PATH,
    SHOT_EFFECT_INTENSITY,
    TEMP_PATH,
    VIDEO_TRANSITION_DURATION,
)
from utils.audio import get_random_background_song
from utils.downloads import (
    attribution_credit_line,
    dedupe_folder,
    delete_media_file,
    download_file,
    write_attribution,
)
from utils.text import align_sentences_to_word_times, split_sentences

logger = logging.getLogger(__name__)

# Canvas dimensions for the final Shorts-style output: a single full-screen
# background video, no letterboxing or stacked/split regions by default.
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920
LOWER_THIRD_HEIGHT = CANVAS_HEIGHT // 3

# Generic b-roll queries used ONLY when no script-derived keywords are available
# (e.g. the function is called standalone). Normal operation searches Pexels using
# keywords extracted from the generated script/title instead of this fixed list.
_SECONDARY_VIDEO_SEARCH_TERMS = [
    "abstract background",
    "ocean waves",
    "clouds timelapse",
    "nature forest",
    "city night timelapse",
    "underwater coral",
    "starry sky space",
    "waterfall",
]


def generate_word_timestamps(audio_path: Path) -> List[dict]:
    """Generate word-level timestamps using AssemblyAI"""
    aai.settings.api_key = ASSEMBLY_AI_API_KEY

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(str(audio_path))

    # Extract word-level timestamps
    words = []
    if transcript.words:
        for word in transcript.words:
            words.append({
                'text': word.text,
                'start': word.start / 1000.0,  # Convert from ms to seconds
                'end': word.end / 1000.0,      # Convert from ms to seconds
                'confidence': getattr(word, 'confidence', 1.0)
            })
    
    return words


_face_cascade: Optional["cv2.CascadeClassifier"] = None


def _get_face_cascade() -> "cv2.CascadeClassifier":
    """Lazily loads OpenCV's bundled frontal-face Haar cascade (ships with the
    opencv-python-headless wheel - no extra model download)."""
    global _face_cascade
    if _face_cascade is None:
        cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        _face_cascade = cv2.CascadeClassifier(cascade_path)
    return _face_cascade


def _detect_face_center(frame: np.ndarray) -> Optional[Tuple[float, float]]:
    """Runs Haar-cascade frontal-face detection on one RGB frame (as returned by
    VideoFileClip.get_frame(t)); returns the (x, y) pixel center of the LARGEST
    detected face, or None if no face is found."""
    cascade = _get_face_cascade()
    if cascade.empty():
        return None

    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))

    if len(faces) == 0:
        return None

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return (x + w / 2.0, y + h / 2.0)


def _sample_subject_center(
    clip: VideoFileClip, sample_fracs: Tuple[float, ...] = (0.1, 0.5, 0.9)
) -> Optional[Tuple[float, float]]:
    """Samples a few frames across the clip's duration, runs face detection on
    each, and averages the center across frames where a face WAS found
    (stabilizes against one noisy/no-face frame). Returns None if no face was
    found in any sampled frame - the caller then falls back to a plain center
    crop, unchanged from the original behavior."""
    duration = clip.duration or 0
    if duration <= 0:
        return None

    centers = []
    for frac in sample_fracs:
        t = min(frac * duration, max(duration - 0.01, 0))
        try:
            frame = clip.get_frame(t)
        except Exception:
            continue
        center = _detect_face_center(frame)
        if center is not None:
            centers.append(center)

    if not centers:
        return None

    avg_x = sum(c[0] for c in centers) / len(centers)
    avg_y = sum(c[1] for c in centers) / len(centers)
    return (avg_x, avg_y)


def _compute_crop_box(
    source_w: float,
    source_h: float,
    target_w: float,
    target_h: float,
    subject_center: Optional[Tuple[float, float]] = None,
) -> Tuple[float, float, float, float]:
    """Pure math (no I/O/moviepy) - computes a cover-crop box preserving the
    target aspect ratio from ANY source aspect ratio (generalizes the original
    crop math, which only worked correctly when the source was wider than the
    target). Returns (crop_w, crop_h, x_center, y_center); when `subject_center`
    is given, the box is centered on it, clamped so it never extends past the
    source's bounds."""
    target_ratio = target_w / target_h
    source_ratio = source_w / source_h

    if source_ratio > target_ratio:
        crop_h = source_h
        crop_w = source_h * target_ratio
    else:
        crop_w = source_w
        crop_h = source_w / target_ratio

    if subject_center is not None:
        x_center, y_center = subject_center
    else:
        x_center, y_center = source_w / 2.0, source_h / 2.0

    half_w, half_h = crop_w / 2.0, crop_h / 2.0
    x_center = min(max(x_center, half_w), source_w - half_w)
    y_center = min(max(y_center, half_h), source_h - half_h)

    return crop_w, crop_h, x_center, y_center


def subject_aware_crop(
    clip: VideoFileClip, target_width: int = CANVAS_WIDTH, target_height: int = CANVAS_HEIGHT
) -> VideoFileClip:
    """Cover-crops `clip` to exactly (target_width, target_height). When
    ENABLE_SUBJECT_AWARE_CROP is on and a face is detected, the crop is centered
    on it so the main subject stays in frame; otherwise falls back to a plain
    center crop (the original behavior, generalized to any source aspect
    ratio)."""
    subject_center = None
    if ENABLE_SUBJECT_AWARE_CROP:
        try:
            subject_center = _sample_subject_center(clip)
        except Exception as e:
            logger.warning(f"Subject detection failed, falling back to center crop: {e}")

    crop_w, crop_h, x_center, y_center = _compute_crop_box(
        clip.w, clip.h, target_width, target_height, subject_center
    )

    cropped = crop(
        clip, width=int(crop_w), height=int(crop_h), x_center=x_center, y_center=y_center
    )
    return cropped.resize((target_width, target_height))


_SHOT_EFFECTS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "static"]


def _assign_effect(shot_index: int) -> str:
    """Deterministic (no randomness, fully reproducible): cycles through
    _SHOT_EFFECTS by shot_index, so consecutive shots never repeat the same
    effect until the palette wraps around."""
    return _SHOT_EFFECTS[shot_index % len(_SHOT_EFFECTS)]


def _apply_shot_effect(
    clip: VideoFileClip, effect: str, intensity: float = SHOT_EFFECT_INTENSITY
) -> VideoFileClip:
    """`clip` must already be cropped/resized to exactly (CANVAS_WIDTH,
    CANVAS_HEIGHT). Returns a CompositeVideoClip of the same size and duration
    with the requested Ken Burns-style effect applied - the oversized/moving
    source always fully covers the canvas throughout (no edges revealed)."""
    w0, h0 = CANVAS_WIDTH, CANVAS_HEIGHT
    duration = clip.duration or 0

    if effect == "static" or duration <= 0:
        sized = clip
        return CompositeVideoClip(
            [sized.set_position((0, 0))], size=(w0, h0)
        ).set_duration(clip.duration)

    if effect in ("zoom_in", "zoom_out"):
        if effect == "zoom_in":
            def scale_at(t):
                return 1.0 + intensity * min(t / duration, 1.0)
        else:
            def scale_at(t):
                return (1.0 + intensity) - intensity * min(t / duration, 1.0)

        def pos_at(t):
            s = scale_at(t)
            return ((w0 - w0 * s) / 2.0, (h0 - h0 * s) / 2.0)

        sized = clip.resize(scale_at)
        return CompositeVideoClip(
            [sized.set_position(pos_at)], size=(w0, h0)
        ).set_duration(duration)

    # pan_left / pan_right: fixed overscan for travel room; the oversized clip
    # slides horizontally while staying vertically centered, always fully
    # covering the canvas.
    scale = 1.0 + intensity
    sized = clip.resize(scale)
    slack = max(sized.w - w0, 0.0)
    y_fixed = (h0 - sized.h) / 2.0

    if effect == "pan_left":
        def pos_at(t):
            return (-slack * min(t / duration, 1.0), y_fixed)
    else:  # pan_right

        def pos_at(t):
            return (-slack * (1 - min(t / duration, 1.0)), y_fixed)

    return CompositeVideoClip([sized.set_position(pos_at)], size=(w0, h0)).set_duration(duration)


def _split_sentence_into_subshots(
    duration: float, min_shot: float = MIN_SHOT_DURATION, max_shot: float = MAX_SHOT_DURATION
) -> List[float]:
    """Sentences whose narrated duration fits within max_shot stay a single shot
    (short sentences aren't force-split). Longer sentences are split into
    multiple bounded-length (min_shot..max_shot-ish) shots for faster-paced
    editing."""
    if duration <= 0:
        return [0.0]
    if duration <= max_shot:
        return [duration]

    n_shots = math.ceil(duration / max_shot)
    if n_shots > 1 and duration / n_shots < min_shot:
        n_shots -= 1
    n_shots = max(n_shots, 1)

    shot_len = duration / n_shots
    return [shot_len] * n_shots


def _pick_subshot_source(scene_clip_paths: List[Path], shot_index: int) -> Path:
    """Cycles through a scene's distinct candidate pool by index, preferring a
    new distinct clip per sub-shot when the pool has enough candidates."""
    return scene_clip_paths[shot_index % len(scene_clip_paths)]


def _pick_subclip_start(raw_duration: float, shot_duration: float, reuse_index: int) -> float:
    """Only matters when the same source clip is reused for a second/third
    sub-shot (candidate pool exhausted): deterministically varies the start
    offset via a golden-ratio-stepped fraction of the available slack, so
    repeated reuse samples visually distinct segments instead of always
    replaying from frame 0."""
    slack = max(raw_duration - shot_duration, 0.0)
    if slack <= 0 or reuse_index <= 0:
        return 0.0
    golden_frac = (reuse_index * 0.618033988749895) % 1.0
    return golden_frac * slack


def _align_candidates_to_sentence_count(
    candidates: List[List[Path]], sentences: List[str]
) -> List[List[Path]]:
    """Pads/truncates the per-scene candidate pools to match len(sentences) -
    handles the script having been edited after search_terms/candidates were
    generated (the dashboard's SCRIPT_READY edit flow), so the two can drift
    apart again by render time. Non-empty pools are round-robin reused when
    padding; truncates extras when there are more scenes than sentences."""
    if len(candidates) >= len(sentences):
        return candidates[: len(sentences)]

    non_empty = [c for c in candidates if c]
    aligned = list(candidates)
    while len(aligned) < len(sentences):
        aligned.append(non_empty[len(aligned) % len(non_empty)] if non_empty else [])

    return aligned


def combine_videos(
    scene_candidates: List[List[Path]], script: str, words: List[dict], audio_duration: float
) -> Path:
    """Builds the single full-screen (CANVAS_WIDTH x CANVAS_HEIGHT) background
    video. Every sentence in `script` gets its own timed slot (from
    align_sentences_to_word_times), split into 1-2.5s sub-shots pulled from
    that sentence's own candidate pool in `scene_candidates` - each sub-shot is
    subject-aware cropped and given a deterministic zoom/pan/static effect.
    Sub-shots within the same sentence are hard cuts; different sentences
    crossfade into each other."""
    video_id = uuid.uuid4()
    combined_video_path = TEMP_PATH / f"{video_id}.mp4"

    sentences = split_sentences(script) or ["."]
    aligned_candidates = _align_candidates_to_sentence_count(scene_candidates, sentences)
    times = align_sentences_to_word_times(sentences, words, audio_duration)

    global_shot_index = 0
    sentence_clips = []

    for candidates, (start, end) in zip(aligned_candidates, times):
        duration = max(end - start, 0.1)

        if not candidates:
            # No usable footage at all for this sentence (every fallback in
            # fetch_scene_candidates failed) - use a placeholder for its slot
            # rather than dropping the sentence's timing entirely.
            placeholder_path = TEMP_PATH / f"{uuid.uuid4()}_placeholder.mp4"
            _generate_placeholder_secondary_clip(placeholder_path, duration=duration)
            candidates = [placeholder_path]

        shot_durations = _split_sentence_into_subshots(duration)
        sub_shot_clips = []

        for j, shot_duration in enumerate(shot_durations):
            source_path = _pick_subshot_source(candidates, j)
            reuse_index = j // len(candidates)

            raw = VideoFileClip(str(source_path)).without_audio()
            if raw.duration and raw.duration < shot_duration:
                # Source too short for this sub-shot - loop it just enough
                # (ceil, never zero) rather than the old equal-share division's
                # `int(x)` which could silently become 0 and crash.
                loops = math.ceil(shot_duration / raw.duration)
                raw = concatenate_videoclips([raw] * loops)

            start_offset = _pick_subclip_start(raw.duration, shot_duration, reuse_index)
            shot = raw.subclip(start_offset, start_offset + shot_duration).set_fps(30)
            shot = subject_aware_crop(shot, CANVAS_WIDTH, CANVAS_HEIGHT)
            shot = _apply_shot_effect(shot, _assign_effect(global_shot_index))

            sub_shot_clips.append(shot)
            global_shot_index += 1

        sentence_clip = (
            concatenate_videoclips(sub_shot_clips) if len(sub_shot_clips) > 1 else sub_shot_clips[0]
        )
        sentence_clips.append(sentence_clip)

    # Crossfade BETWEEN sentences (the existing transition mechanism, applied
    # at the sentence level instead of per raw clip); sub-shots within a
    # sentence stay hard cuts (no crossfadein called on them above).
    shortest_sentence_duration = min(c.duration for c in sentence_clips)
    transition = min(VIDEO_TRANSITION_DURATION, shortest_sentence_duration / 4)

    if len(sentence_clips) > 1 and transition > 0:
        transitioned = [sentence_clips[0]] + [
            c.crossfadein(transition) for c in sentence_clips[1:]
        ]
        final_clip = concatenate_videoclips(
            transitioned, method="compose", padding=-transition
        )
    else:
        final_clip = concatenate_videoclips(sentence_clips)

    # Guard against the visual track ending slightly before the narration
    # (e.g. alignment fallback landed just short of audio_duration): freeze the
    # last frame to close the gap rather than leaving a black tail.
    if final_clip.duration < audio_duration:
        final_clip = freeze(final_clip, t="end", total_duration=audio_duration)

    final_clip = final_clip.set_fps(30)
    final_clip.write_videofile(
        str(combined_video_path),
        threads=os.cpu_count(),
        temp_audiofile=str(TEMP_PATH / f"{video_id}.mp3"),
    )

    return combined_video_path


def create_karaoke_subtitles(words: List[dict], video_duration: float) -> List[TextClip]:
    """Create karaoke-style word-by-word subtitle clips with highlighting, positioned
    in the lower third (not screen-center) so they read like captions over a
    full-screen background rather than sitting in the middle of the footage."""
    subtitle_clips = []

    for word_idx, word in enumerate(words):
        # Find when the next word starts (or video ends)
        next_word_start = words[word_idx + 1]['start'] if word_idx + 1 < len(words) else video_duration

        # Create highlighted word clip that disappears when next word starts
        highlighted_clip = (
            TextClip(
                word['text'],
                font="fonts/bold_font.ttf",
                fontsize=118,
                color="#FFFF00",  # Bright yellow
                stroke_color="black",
                stroke_width=6,
            )
            .set_start(word['start'])
            .set_end(min(next_word_start, word['end'] + 0.3))
            .set_pos(("center", 0.74), relative=True)
        )

        subtitle_clips.append(highlighted_clip)

    return subtitle_clips


def create_lower_third_backdrop(duration: float, max_opacity: float = 0.65) -> ImageClip:
    """A semi-transparent vertical gradient (transparent at the top edge of the band,
    darker toward the bottom) behind the lower-third subtitles, for readability
    without a hard-edged box sitting on top of the footage."""
    gradient = np.zeros((LOWER_THIRD_HEIGHT, CANVAS_WIDTH, 4), dtype=np.uint8)
    alpha = np.linspace(0, max_opacity * 255, LOWER_THIRD_HEIGHT).astype(np.uint8)
    gradient[:, :, 3] = alpha[:, np.newaxis]

    return (
        ImageClip(gradient)
        .set_duration(duration)
        .set_pos((0, CANVAS_HEIGHT - LOWER_THIRD_HEIGHT))
    )


def generate_video(
    scene_candidates: List[List[Path]],
    tts_path: Path,
    script: str,
    search_terms: Optional[List[str]] = None,
) -> Tuple[Path, List[str]]:
    """Generate video with karaoke-style word-by-word subtitles.

    `scene_candidates` is one candidate-clip-pool per sentence in `script`
    (see utils.scenes.fetch_scene_candidates / utils.stock_videos.get_stock_videos).

    Returns (output_path, credits) - credits is a list of attribution lines that must
    accompany the video per the licenses of any assets that require it (e.g. CC BY
    background music); empty when nothing used requires attribution.
    """
    audio = AudioFileClip(str(tts_path))

    # Word-level timestamps are needed by combine_videos (to time each sentence's
    # shots against the actual narration), so this now runs before it - still
    # exactly one AssemblyAI call per video, just resequenced.
    words = generate_word_timestamps(tts_path)

    combined_video_path = combine_videos(scene_candidates, script, words, audio.duration)

    # Create karaoke subtitle clips
    subtitle_clips = create_karaoke_subtitles(words, audio.duration)

    # Gradient backdrop behind the lower-third subtitles for readability, then the
    # subtitles themselves on top - all layered over the single full-screen background.
    backdrop = create_lower_third_backdrop(audio.duration)
    video_clips = [VideoFileClip(str(combined_video_path)), backdrop]
    video_clips.extend(subtitle_clips)

    result = CompositeVideoClip(video_clips)

    # Add the audio
    audio = AudioFileClip(str(tts_path))
    music_path, music_credit = get_random_background_song()
    music = AudioFileClip(str(music_path))

    music = music.set_duration(audio.duration)

    audio = CompositeAudioClip([audio, volumex(music, 0.07)])

    result = result.set_audio(audio)

    # The secondary-clip overlay is opt-in only (config-gated) - the default render is
    # a clean, single full-screen background video with no stacked/split media regions.
    video_credit = None
    if ENABLE_SECONDARY_OVERLAY:
        secondary_clip, video_credit = get_secondary_video_clip(result.duration, keywords=search_terms)

        secondary_video = secondary_clip.resize(
            (result.w, int(secondary_clip.h / secondary_clip.w * result.w))
        )

        secondary_video_position = ("center", result.h - secondary_video.h - 160)

        result = CompositeVideoClip(
            [result, secondary_video.set_pos(secondary_video_position)]
        )

    video_id = uuid.uuid4()

    output_video_path = OUTPUT_PATH / f"{video_id}.mp4"

    result.write_videofile(
        str(output_video_path),
        threads=os.cpu_count(),
        temp_audiofile=str(TEMP_PATH / f"{video_id}.mp3"),
    )

    credits = [c for c in (music_credit, video_credit) if c]

    return output_video_path, credits


def _extract_keywords(search_terms: Optional[List[str]]) -> List[str]:
    """Script-derived search terms drive the secondary-video search when available;
    otherwise fall back to a fixed generic list so the function stays safely callable."""
    keywords = [t.strip() for t in (search_terms or []) if t and t.strip()]
    if not keywords:
        keywords = _SECONDARY_VIDEO_SEARCH_TERMS.copy()
    random.shuffle(keywords)
    return keywords


def _search_pexels_video_candidates(
    query: str, per_page: int = 5, orientation: Optional[str] = "landscape"
) -> List[str]:
    """Returns candidate direct-download URLs matching `query`, highest-
    resolution file per result first. orientation="landscape" (default)
    preserves the original behavior - used by the secondary-overlay path,
    composited as a bottom strip, so wide source clips are required.
    orientation=None (used by the primary per-scene fetch path) drops both
    Pexels' own orientation filter and the wide-file-only selection, so
    portrait source footage is eligible too - the primary path cover-crops to
    9:16 regardless of source orientation."""
    if not PEXELS_API_KEY:
        return []

    headers = {"Authorization": PEXELS_API_KEY}
    url = "https://api.pexels.com/videos/search"
    params = {"query": query, "per_page": per_page}
    if orientation:
        params["orientation"] = orientation

    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        response = r.json()
    except Exception as e:
        logger.warning(f"Pexels search failed for '{query}': {e}")
        return []

    candidates = []
    for video in response.get("videos", []):
        best_file = None
        for file in video.get("video_files", []):
            w, h = file.get("width", 0), file.get("height", 0)
            if orientation and w < h:
                continue
            if "https://" not in file.get("link", ""):
                continue
            if best_file is None or w > best_file.get("width", 0):
                best_file = file
        if best_file:
            candidates.append(best_file["link"])

    return candidates


def _validate_video_file(
    path: Path, min_duration: float = 1.0, min_width: int = 640, require_landscape: bool = True
) -> bool:
    """Reject corrupt/undecodable files and low-resolution footage.
    require_landscape=True (default) preserves the original behavior - also
    rejects portrait-oriented clips (wrong shape for the secondary-overlay
    bottom strip). require_landscape=False (used by the primary per-scene
    fetch path) drops the orientation rejection and instead requires
    min(w, h) >= 480, accepting either orientation while still rejecting
    genuinely low-res footage."""
    try:
        clip = VideoFileClip(str(path))
        w, h = clip.size
        duration = clip.duration
        clip.close()
    except Exception as e:
        logger.warning(f"Invalid/corrupt video file {path.name}: {e}")
        return False

    if not duration or duration < min_duration:
        logger.warning(f"Rejecting {path.name}: duration too short ({duration}s)")
        return False
    if not w or not h:
        logger.warning(f"Rejecting {path.name}: invalid dimensions ({w}x{h})")
        return False

    if require_landscape:
        if h > w:
            logger.warning(f"Rejecting {path.name}: not landscape orientation ({w}x{h})")
            return False
        if w < min_width:
            logger.warning(f"Rejecting {path.name}: resolution too low ({w}x{h})")
            return False
    elif min(w, h) < 480:
        logger.warning(f"Rejecting {path.name}: resolution too low ({w}x{h})")
        return False

    return True


def _pick_valid_cached_video(folder: Path) -> Optional[Path]:
    """Pick a random cached clip, validating it and pruning any invalid/corrupt files found."""
    candidates = list(folder.glob("*.mp4"))
    random.shuffle(candidates)

    for path in candidates:
        if _validate_video_file(path):
            return path
        logger.warning(f"Removing invalid cached video file {path.name}")
        delete_media_file(path)

    return None


def _generate_placeholder_secondary_clip(dest: Path, duration: float = 12.0) -> None:
    """Last-resort local fallback (a plain dark clip) so the pipeline never crashes for
    lack of secondary video content, even when offline and Pexels has no results."""
    clip = ColorClip(size=(1080, 600), color=(18, 18, 24), duration=duration).set_fps(30)
    clip.write_videofile(str(dest), codec="libx264", audio=False, logger=None)


def _fetch_new_secondary_video(keywords: List[str], max_keywords: int = 6) -> Optional[Path]:
    """Search Pexels using script-derived keywords and download+validate the first
    matching clip. Returns None (without raising) if nothing usable was found -
    callers fall back to cache, then to a generated placeholder."""
    for keyword in keywords[:max_keywords]:
        for video_url in _search_pexels_video_candidates(keyword):
            dest = SECONDARY_CONTENT_PATH / f"{uuid.uuid4()}.mp4"
            if download_file(video_url, dest) and _validate_video_file(dest):
                write_attribution(
                    dest,
                    source="pexels",
                    license="Pexels License (https://www.pexels.com/license/)",
                    attribution_required=False,
                    query=keyword,
                    url=video_url,
                )
                logger.info(f"Cached new secondary video for keyword '{keyword}' from Pexels")
                return dest
            delete_media_file(dest)

    return None


def _ensure_secondary_video(keywords: Optional[List[str]] = None) -> None:
    SECONDARY_CONTENT_PATH.mkdir(parents=True, exist_ok=True)
    dedupe_folder(SECONDARY_CONTENT_PATH, {".mp4"})

    search_keywords = _extract_keywords(keywords)
    if _fetch_new_secondary_video(search_keywords):
        return

    if list(SECONDARY_CONTENT_PATH.glob("*.mp4")):
        logger.warning(
            "Pexels unavailable or returned no results for this topic's keywords; "
            "falling back to previously cached secondary video assets"
        )
        return

    logger.warning(
        "No cached secondary video available and live fetch failed; "
        "generating a placeholder background clip instead"
    )
    placeholder = SECONDARY_CONTENT_PATH / "placeholder.mp4"
    _generate_placeholder_secondary_clip(placeholder)
    write_attribution(placeholder, source="generated", license="N/A", attribution_required=False)


def get_secondary_video_clip(
    duration, keywords: Optional[List[str]] = None
) -> Tuple[VideoFileClip, Optional[str]]:
    """Returns (clip, credit_line_or_None). Fetches topically-relevant footage from Pexels
    using `keywords` (typically the script's search terms); Pexels' license doesn't
    require attribution, so credit_line is normally None."""
    _ensure_secondary_video(keywords)

    video_path = _pick_valid_cached_video(SECONDARY_CONTENT_PATH)
    if video_path is None:
        # Final safety net: everything got pruned as invalid between ensure() and now.
        video_path = SECONDARY_CONTENT_PATH / f"placeholder_{uuid.uuid4()}.mp4"
        _generate_placeholder_secondary_clip(video_path)
        write_attribution(video_path, source="generated", license="N/A", attribution_required=False)

    video = VideoFileClip(str(video_path)).without_audio()

    # Cached/fetched clips may be shorter than what's needed - loop until long enough.
    if video.duration < duration:
        loops = int(duration // video.duration) + 1
        video = concatenate_videoclips([video] * loops)

    start_time = random.uniform(0, max(video.duration - duration, 0))

    clip = video.subclip(start_time, start_time + duration)

    clip = clip.set_fps(30)

    return clip, attribution_credit_line(video_path)
