"""Choosing the footage for every scene, end to end.

This is the stage that replaced "one query per sentence, take the first result".
For each narration line it now:

  1. reads the brief (utils/storyboard.py) - subject, action, location, mood
  2. runs *several* different queries, building a pool of candidates
  3. scores and rejects (utils/clip_quality.py) - nothing weak survives
  4. rejects anything too similar to the shot already chosen for the previous
     scene, so consecutive cuts don't repeat
  5. frames it (utils/framing.py) and looks at the real output frame
  6. sends that frame to the editor review (utils/editor_review.py)
  7. if the review fails, searches again with the reviewer's own suggested
     queries and repeats

A scene that never passes is left explicitly unresolved rather than filled with
whatever scored least badly. The old pipeline's last-resort "generic B-roll"
fallback is gone: unrelated footage is the failure being fixed, so silently
inserting it would defeat the whole stage.
"""

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Set

from config import TEMP_PATH
from utils.clip_quality import (
    Candidate,
    ClipScore,
    looks_like,
    perceptual_signature,
    rank_candidates,
)
from utils.downloads import delete_media_file, download_file
from utils.editor_review import Review, review_clip
from utils.framing import frame_clip
from utils.storyboard import SceneBrief

logger = logging.getLogger(__name__)

# How many rounds of search-score-review one scene gets before we give up on it.
MAX_ROUNDS = 3

# Candidates downloaded per query. Wide enough that scoring has a real choice,
# small enough that a 12-scene video doesn't download hundreds of files.
CANDIDATES_PER_QUERY = 4


@dataclass
class SceneSelection:
    """The outcome for one scene."""

    brief: SceneBrief
    clip_path: Optional[Path] = None
    score: Optional[ClipScore] = None
    review: Optional[Review] = None
    crop_mode: str = "-"
    subject_retained: float = 1.0
    # The exact plan the reviewer saw. Reused verbatim at render time so the
    # finished shot is the shot that was approved, not a re-derived guess.
    framing_plan: object = None
    queries_tried: List[str] = field(default_factory=list)
    rounds: int = 0

    @property
    def resolved(self) -> bool:
        return self.clip_path is not None

    def table_row(self) -> dict:
        reason = "no usable footage found"
        if self.review is not None:
            reason = self.review.reason or self.review.summary()
        elif self.score is not None:
            reason = self.score.explain()

        return {
            "sentence": self.brief.sentence,
            "queries": self.queries_tried[:3],
            "clip": self.clip_path.name if self.clip_path else "-",
            "reason": reason,
            "crop_mode": self.crop_mode,
            "score": f"{self.score.total:.2f}" if self.score else "-",
        }


# A search backend: query -> list of Candidate (already downloaded and on disk).
SearchFn = Callable[[str, int, Set[str]], List[Candidate]]


def _default_search(query: str, limit: int, used_ids: Set[str]) -> List[Candidate]:
    """Pexels-backed search returning downloaded, deduplicated candidates.

    Imported lazily so this module can be exercised, and unit-tested, without a
    provider configured.
    """
    from utils.video import _search_pexels_video_records

    candidates: List[Candidate] = []
    for record in _search_pexels_video_records(query, per_page=max(limit * 2, 8)):
        if len(candidates) >= limit:
            break
        if record["id"] in used_ids:
            continue

        dest = TEMP_PATH / f"{uuid.uuid4()}.mp4"
        if not download_file(record["url"], dest):
            continue

        used_ids.add(record["id"])
        candidates.append(
            Candidate(
                path=dest,
                query=query,
                provider="pexels",
                provider_id=record["id"],
                width=record["width"],
                height=record["height"],
                duration=record["duration"],
                tags=record.get("tags", ""),
            )
        )

    return candidates


def _gather(
    queries: Sequence[str], search: SearchFn, used_ids: Set[str], per_query: int
) -> List[Candidate]:
    """Run every query and pool the results.

    Several queries per scene is the point: a single query's top results all
    come from the same corner of the library, and choosing between them isn't
    really a choice.
    """
    pool: List[Candidate] = []
    for query in queries:
        try:
            pool.extend(search(query, per_query, used_ids))
        except Exception as e:
            logger.warning(f"Search failed for '{query}': {e}")
    return pool


def select_scene(
    brief: SceneBrief,
    search: SearchFn,
    used_ids: Set[str],
    previous_signature=None,
    canvas: tuple = (1080, 1920),
    max_rounds: int = MAX_ROUNDS,
    per_query: int = CANDIDATES_PER_QUERY,
    reviewer=review_clip,
) -> SceneSelection:
    """Find, frame and approve one scene's footage."""
    from moviepy.editor import VideoFileClip

    selection = SceneSelection(brief=brief)
    queries = list(brief.queries)

    for round_index in range(1, max_rounds + 1):
        selection.rounds = round_index
        if not queries:
            break

        selection.queries_tried.extend(q for q in queries if q not in selection.queries_tried)
        pool = _gather(queries, search, used_ids, per_query)
        ranked = rank_candidates(pool, brief.concept_terms(), brief.allow_generic)

        rejected_paths = {c.path for c in pool} - {c.path for c, _ in ranked}

        for candidate, score in ranked:
            # Continuity: a shot that looks like the previous scene's makes the
            # cut read as a glitch, however well it scores on its own.
            if previous_signature is not None and looks_like(
                previous_signature, perceptual_signature(candidate.path)
            ):
                logger.info(f"Skipping {candidate.path.name}: too similar to the previous scene")
                rejected_paths.add(candidate.path)
                continue

            clip = None
            try:
                clip = VideoFileClip(str(candidate.path)).without_audio()
                framed, plan = frame_clip(clip, canvas[0], canvas[1])
                frame = framed.get_frame(min(0.5, max(framed.duration - 0.05, 0)))
                review = reviewer(
                    brief, frame, score=score, crop_mode=plan.mode.value
                )
            except Exception as e:
                logger.warning(f"Could not frame/review {candidate.path.name}: {e}")
                rejected_paths.add(candidate.path)
                continue
            finally:
                if clip is not None:
                    clip.close()

            if review.approved:
                selection.clip_path = candidate.path
                selection.score = score
                selection.review = review
                selection.crop_mode = plan.mode.value
                selection.subject_retained = plan.subject_retained
                selection.framing_plan = plan
                # Everything else this round is dead weight on disk.
                for path in rejected_paths:
                    delete_media_file(path)
                for other, _ in ranked:
                    if other.path != candidate.path:
                        delete_media_file(other.path)
                return selection

            logger.info(f"Editor rejected {candidate.path.name}: {review.reason}")
            rejected_paths.add(candidate.path)
            selection.review = review
            # The reviewer usually knows what should have been searched for.
            queries = [q for q in review.better_queries if q not in selection.queries_tried]

        for path in rejected_paths:
            delete_media_file(path)

        if not queries:
            break

        logger.info(
            f"Scene {brief.index + 1} round {round_index} found nothing usable; "
            f"retrying with {queries[:3]}"
        )

    logger.warning(
        f"Scene {brief.index + 1} unresolved after {selection.rounds} rounds: "
        f"{brief.sentence[:60]!r}"
    )
    return selection


def direct_scenes(
    briefs: Sequence[SceneBrief],
    search: SearchFn = _default_search,
    canvas: tuple = (1080, 1920),
    reviewer=review_clip,
) -> List[SceneSelection]:
    """Pick footage for every scene, keeping consecutive shots distinct."""
    used_ids: Set[str] = set()
    selections: List[SceneSelection] = []
    previous_signature = None

    for brief in briefs:
        selection = select_scene(
            brief,
            search,
            used_ids,
            previous_signature=previous_signature,
            canvas=canvas,
            reviewer=reviewer,
        )
        selections.append(selection)

        if selection.clip_path is not None:
            previous_signature = perceptual_signature(selection.clip_path)

    resolved = sum(1 for s in selections if s.resolved)
    logger.info(f"Visual direction complete: {resolved}/{len(selections)} scenes resolved")
    return selections


def unresolved_scenes(selections: Sequence[SceneSelection]) -> List[SceneSelection]:
    """Scenes that never found footage good enough to use."""
    return [s for s in selections if not s.resolved]


def framing_report(selections: Sequence[SceneSelection]) -> str:
    """How each resolved scene was framed, and how much subject survived."""
    lines = []
    for i, selection in enumerate(selections, start=1):
        if not selection.resolved:
            lines.append(f"{i:>2}. UNRESOLVED - {selection.brief.sentence[:60]}")
            continue
        lines.append(
            f"{i:>2}. {selection.crop_mode:<9} subject kept {selection.subject_retained:.0%} "
            f"score {selection.score.total:.2f}  {selection.brief.summary()[:44]}"
        )
    return "\n".join(lines)
