from pathlib import Path

import numpy as np
import pytest
from moviepy.editor import VideoClip

from utils.clip_quality import (
    Candidate,
    looks_like,
    matched_generic_category,
    orientation_score,
    perceptual_signature,
    quality_score,
    rank_candidates,
    score_candidate,
    semantic_relevance,
)

CONCEPTS = ["moon", "changing phase", "night sky", "crescent"]


def _write(dest: Path, maker, duration: float = 2.0) -> Path:
    VideoClip(maker, duration=duration).set_fps(15).write_videofile(
        str(dest), codec="libx264", audio=False, logger=None
    )
    return dest


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    directory = tmp_path_factory.mktemp("clips")

    def moving(t):
        frame = np.random.RandomState(int(t * 15)).randint(0, 255, (360, 640, 3)).astype(np.uint8)
        frame[100:260, int(60 + t * 120) : int(200 + t * 120)] = (250, 230, 40)
        return frame

    return {
        "moving": _write(directory / "moving.mp4", moving),
        "static": _write(directory / "static.mp4", lambda t: np.full((360, 640, 3), 128, np.uint8)),
        "black": _write(directory / "black.mp4", lambda t: np.zeros((360, 640, 3), np.uint8)),
    }


def _candidate(path, query, **kwargs):
    defaults = dict(width=640, height=360, duration=2.0, provider_id="1", tags=query)
    defaults.update(kwargs)
    return Candidate(path=path, query=query, **defaults)


def test_a_static_clip_is_rejected(clips):
    # A still frame dressed up as footage is the single most common way a
    # generated video looks broken.
    score = score_candidate(_candidate(clips["static"], "moon night sky"), CONCEPTS)

    assert score.rejected
    assert any("still" in reason for reason in score.reasons)


def test_an_almost_black_clip_is_rejected(clips):
    score = score_candidate(_candidate(clips["black"], "moon night sky"), CONCEPTS)

    assert score.rejected


def test_generic_broll_is_rejected_when_the_narration_is_not_about_it(clips):
    score = score_candidate(_candidate(clips["moving"], "people walking city street"), CONCEPTS)

    assert score.rejected
    assert any("generic b-roll" in reason for reason in score.reasons)


def test_generic_footage_is_allowed_when_the_narration_is_about_it(clips):
    # A video about laptops is entitled to a laptop.
    score = score_candidate(
        _candidate(clips["moving"], "laptop keyboard close up"),
        ["laptop", "typing"],
        allow_generic=["laptop"],
    )

    assert not score.rejected


def test_ultrawide_sources_are_rejected_as_uncroppable(clips):
    score = score_candidate(
        _candidate(clips["moving"], "moon crescent night sky", width=2560, height=640), CONCEPTS
    )

    assert score.rejected
    assert any("9:16" in reason for reason in score.reasons)


def test_a_relevant_moving_clip_survives(clips):
    score = score_candidate(
        _candidate(clips["moving"], "real moon phases time lapse", tags="moon phases crescent night sky"),
        CONCEPTS,
    )

    assert not score.rejected
    assert score.total > 0.5


def test_ranking_returns_only_survivors_best_first(clips):
    candidates = [
        _candidate(clips["static"], "moon", provider_id="1"),
        _candidate(clips["black"], "moon night sky", provider_id="2"),
        _candidate(
            clips["moving"],
            "real moon phases time lapse",
            provider_id="3",
            tags="moon phases crescent night sky",
        ),
        _candidate(clips["moving"], "people walking city", provider_id="4"),
    ]

    ranked = rank_candidates(candidates, CONCEPTS)

    assert len(ranked) == 1
    assert ranked[0][0].query == "real moon phases time lapse"


def test_an_empty_pool_ranks_to_nothing_rather_than_a_least_bad_pick():
    # Callers must treat this as "search again", never as "use what we have".
    assert rank_candidates([], CONCEPTS) == []


def test_portrait_scores_better_than_ultrawide_for_a_vertical_canvas():
    assert orientation_score(1080, 1920) > orientation_score(1920, 1080)
    assert orientation_score(1920, 1080) > orientation_score(2560, 640)


def test_quality_rewards_resolution_and_usable_length():
    assert quality_score(1920, 1080, 5.0) > quality_score(320, 180, 5.0)
    assert quality_score(1920, 1080, 5.0) > quality_score(1920, 1080, 1.1)


def test_relevance_is_neutral_rather_than_confident_without_concept_terms():
    # Non-Latin narration gives no lexical signal; claiming a perfect match
    # would promote clips on evidence that does not exist.
    candidate = _candidate(Path("x.mp4"), "anything at all")

    assert semantic_relevance(candidate, []) == 0.5


def test_relevance_rises_with_concept_overlap():
    weak = _candidate(Path("x.mp4"), "sky", tags="sky")
    strong = _candidate(Path("x.mp4"), "crescent moon night sky", tags="moon phase crescent night sky")

    assert semantic_relevance(strong, CONCEPTS) > semantic_relevance(weak, CONCEPTS)


def test_generic_category_detection_respects_the_allow_list():
    assert matched_generic_category("busy city traffic") == "city traffic"
    assert matched_generic_category("busy city traffic", allow=["city traffic"]) is None


def test_near_identical_clips_are_recognised_so_cuts_do_not_repeat(clips):
    signature = perceptual_signature(clips["moving"])

    assert looks_like(signature, signature)
    assert not looks_like(signature, perceptual_signature(clips["black"]))
