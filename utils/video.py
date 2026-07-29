import logging
import os
import random
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

import assemblyai as aai
import requests
import srt_equalizer
from moviepy.audio.fx.all import volumex
from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx.all import crop
from moviepy.video.tools.subtitles import SubtitlesClip

from config import (
    ASSEMBLY_AI_API_KEY,
    OUTPUT_PATH,
    PEXELS_API_KEY,
    SECONDARY_CONTENT_PATH,
    TEMP_PATH,
)
from utils.audio import get_random_background_song
from utils.downloads import (
    attribution_credit_line,
    dedupe_folder,
    delete_media_file,
    download_file,
    write_attribution,
)

logger = logging.getLogger(__name__)

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


def generate_subtitles(audio_path: Path) -> Path:
    """Legacy function for backward compatibility"""
    def equalize_subtitles(srt_path: str, max_chars: int = 10) -> None:
        srt_equalizer.equalize_srt_file(srt_path, srt_path, max_chars)

    aai.settings.api_key = ASSEMBLY_AI_API_KEY

    subtitles_id = uuid.uuid4()

    transcriber = aai.Transcriber()

    transcript = transcriber.transcribe(str(audio_path))

    # Save subtitles
    subtitles_path = TEMP_PATH / f"{subtitles_id}.srt"

    subtitles = transcript.export_subtitles_srt()

    with open(subtitles_path, "w") as f:
        f.write(subtitles)

    # Equalize subtitles
    equalize_subtitles(subtitles_path)

    return subtitles_path


def combine_videos(video_paths: List[Path], max_duration: int) -> Path:
    video_id = uuid.uuid4()
    combined_video_path = TEMP_PATH / f"{video_id}.mp4"

    clips = []
    for video_path in video_paths:
        clip = VideoFileClip(str(video_path))
        clip = clip.without_audio()
        # chain the clip to itself as many times as needed to be over max_duration / len(video_paths)
        clip = concatenate_videoclips([clip] * int(max_duration / len(video_paths)))

        clip = clip.subclip(0, max_duration / len(video_paths))
        clip = clip.set_fps(30)

        # Not all videos are same size,
        # so we need to resize them
        clip = crop(
            clip,
            width=int(clip.h / 1920 * 1080),
            height=clip.h,
            x_center=clip.w / 2,
            y_center=clip.h / 2,
        )
        clip = clip.resize((1080, 1920))

        clips.append(clip)

    final_clip = concatenate_videoclips(clips)
    final_clip = final_clip.set_fps(30)
    final_clip.write_videofile(
        str(combined_video_path),
        threads=os.cpu_count(),
        temp_audiofile=str(TEMP_PATH / f"{video_id}.mp3"),
    )

    return combined_video_path


def create_karaoke_subtitles(words: List[dict], video_duration: float) -> List[TextClip]:
    """Create karaoke-style word-by-word subtitle clips with highlighting"""
    subtitle_clips = []
    
    for word_idx, word in enumerate(words):
        # Find when the next word starts (or video ends)
        next_word_start = words[word_idx + 1]['start'] if word_idx + 1 < len(words) else video_duration
        
        # Create highlighted word clip that disappears when next word starts
        highlighted_clip = TextClip(
            word['text'],
            font="fonts/bold_font.ttf",
            fontsize=118,
            color="#FFFF00",  # Bright yellow
            stroke_color="black",
            stroke_width=6,
        ).set_start(word['start']).set_end(min(next_word_start, word['end'] + 0.3)).set_pos(("center", "center"))
        
        subtitle_clips.append(highlighted_clip)
    
    return subtitle_clips


def generate_video_with_karaoke(
    video_paths: List[Path], tts_path: Path, search_terms: Optional[List[str]] = None
) -> Tuple[Path, List[str]]:
    """Generate video with karaoke-style word-by-word subtitles.

    Returns (output_path, credits) - credits is a list of attribution lines that must
    accompany the video per the licenses of any assets that require it (e.g. CC BY
    background music); empty when nothing used requires attribution.
    """
    audio = AudioFileClip(str(tts_path))

    combined_video_path = combine_videos(video_paths, audio.duration)

    # Generate word-level timestamps
    words = generate_word_timestamps(tts_path)

    # Create karaoke subtitle clips
    subtitle_clips = create_karaoke_subtitles(words, audio.duration)

    # Combine video with karaoke subtitles
    video_clips = [VideoFileClip(str(combined_video_path))]
    video_clips.extend(subtitle_clips)

    result = CompositeVideoClip(video_clips)

    # Add the audio
    audio = AudioFileClip(str(tts_path))
    music_path, music_credit = get_random_background_song()
    music = AudioFileClip(str(music_path))

    music = music.set_duration(audio.duration)

    audio = CompositeAudioClip([audio, volumex(music, 0.07)])

    result = result.set_audio(audio)

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


def generate_video(
    video_paths: List[Path],
    tts_path: Path,
    search_terms: Optional[List[str]] = None,
    subtitles_path: Path = None,
) -> Tuple[Path, List[str]]:
    """Legacy function - now uses karaoke subtitles by default"""
    # Use new karaoke approach
    return generate_video_with_karaoke(video_paths, tts_path, search_terms)


def generate_video_legacy(
    video_paths: List[Path], tts_path: Path, subtitles_path: Path
) -> Path:
    """Original implementation kept for fallback"""
    audio = AudioFileClip(str(tts_path))

    combined_video_path = combine_videos(video_paths, audio.duration)

    generator = lambda txt: TextClip(
        txt,
        font=f"fonts/bold_font.ttf",
        fontsize=112,
        color="#FFFFFF",
        stroke_color="black",
        stroke_width=5,
    )

    # Burn the subtitles into the video
    subtitles = SubtitlesClip(str(subtitles_path), generator)
    result = CompositeVideoClip(
        [
            VideoFileClip(str(combined_video_path)),
            subtitles.set_pos(("center", "center")),
        ]
    )

    # Add the audio
    audio = AudioFileClip(str(tts_path))
    music_path, _ = get_random_background_song()
    music = AudioFileClip(str(music_path))

    music = music.set_duration(audio.duration)

    audio = CompositeAudioClip([audio, volumex(music, 0.07)])

    result = result.set_audio(audio)

    secondary_clip, _ = get_secondary_video_clip(result.duration)

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

    return output_video_path


def save_video(video_url: str) -> Path:
    video_id = uuid.uuid4()
    video_path = TEMP_PATH / f"{video_id}.mp4"

    if not download_file(video_url, video_path, retries=3):
        raise Exception(f"Failed to download stock video from {video_url} after retries")

    return video_path


def _extract_keywords(search_terms: Optional[List[str]]) -> List[str]:
    """Script-derived search terms drive the secondary-video search when available;
    otherwise fall back to a fixed generic list so the function stays safely callable."""
    keywords = [t.strip() for t in (search_terms or []) if t and t.strip()]
    if not keywords:
        keywords = _SECONDARY_VIDEO_SEARCH_TERMS.copy()
    random.shuffle(keywords)
    return keywords


def _search_pexels_video_candidates(query: str, per_page: int = 5) -> List[str]:
    """Returns candidate direct-download URLs for landscape footage matching `query`,
    highest resolution file per result first. Secondary video is composited as a
    bottom strip resized to the canvas width, so landscape (wide) source clips are
    what's expected here - see get_secondary_video_clip()."""
    if not PEXELS_API_KEY:
        return []

    headers = {"Authorization": PEXELS_API_KEY}
    url = "https://api.pexels.com/videos/search"
    params = {"query": query, "per_page": per_page, "orientation": "landscape"}

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
            if w >= h and "https://" in file.get("link", ""):
                if best_file is None or w > best_file.get("width", 0):
                    best_file = file
        if best_file:
            candidates.append(best_file["link"])

    return candidates


def _validate_video_file(path: Path, min_duration: float = 1.0, min_width: int = 640) -> bool:
    """Reject corrupt/undecodable files, portrait-oriented clips (wrong shape for the
    bottom-strip overlay), and low-resolution footage."""
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
    if not w or not h or h > w:
        logger.warning(f"Rejecting {path.name}: not landscape orientation ({w}x{h})")
        return False
    if w < min_width:
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
