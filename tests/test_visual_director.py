import json

import numpy as np
import pytest
from moviepy.editor import VideoClip

from utils.clip_quality import Candidate
from utils.editor_review import Review, _heuristic_review, review_clip
from utils.storyboard import SceneBrief, build_storyboard, storyboard_table
from utils.visual_director import direct_scenes, select_scene, unresolved_scenes


@pytest.fixture(scope="module")
def clip_factory(tmp_path_factory):
    directory = tmp_path_factory.mktemp("director")
    made = {}

    def make(key: str, seed: int = 7):
        # Re-create on demand: the director deletes candidates it rejects, which
        # is correct in production (every download is its own temp file) but
        # would leave this shared fixture pointing at a deleted path.
        if key in made and made[key].exists():
            return made[key]
        path = directory / f"{key}.mp4"

        def maker(t):
            frame = (
                np.random.RandomState(seed + int(t * 15))
                .randint(0, 255, (1080, 1920, 3))
                .astype(np.uint8)
            )
            frame[300:700, 700:1200] = (seed % 255, 200, 120)
            return frame

        VideoClip(maker, duration=1.5).set_fps(15).write_videofile(
            str(path), codec="libx264", audio=False, logger=None
        )
        made[key] = path
        return path

    return make


def _brief(index=0, sentence="The moon changes shape.", **kwargs):
    defaults = dict(
        subject="moon",
        action="changing phase",
        location="night sky",
        objects=["crescent"],
        shot_style="time lapse",
        queries=["real moon phases time lapse"],
    )
    defaults.update(kwargs)
    return SceneBrief(index=index, sentence=sentence, **defaults)


def _search_factory(clip_factory):
    def search(query, limit, used_ids):
        key = query.replace(" ", "_")[:16]
        return [
            Candidate(
                path=clip_factory(key, seed=abs(hash(key)) % 200),
                query=query,
                provider_id=str(abs(hash(key)) % 9999),
                width=1920,
                height=1080,
                duration=1.5,
                tags=query,
            )
        ]

    return search


def _approve(*args, **kwargs):
    return Review(
        approved=True,
        represents_sentence=True,
        subject_visible=True,
        confidence=0.9,
        reason="shows the subject clearly",
        reviewed_by_vision=True,
    )


def test_a_scene_resolves_when_the_editor_approves(clip_factory):
    selection = select_scene(_brief(), _search_factory(clip_factory), set(), reviewer=_approve)

    assert selection.resolved
    assert selection.crop_mode in ("crop", "fit-blur")
    assert selection.framing_plan is not None


def test_editor_rejection_triggers_a_re_search_with_its_own_suggestions(clip_factory):
    seen = []

    def reviewer(brief, frame, score=None, crop_mode="crop"):
        seen.append(1)
        approved = len(seen) >= 3
        return Review(
            approved=approved,
            represents_sentence=approved,
            subject_visible=True,
            confidence=0.9,
            reason="good" if approved else "not the subject",
            better_queries=[f"better query {len(seen)}"],
            reviewed_by_vision=True,
        )

    selection = select_scene(_brief(), _search_factory(clip_factory), set(), reviewer=reviewer)

    assert selection.rounds > 1, "a rejected pool must trigger another search"
    assert len(selection.queries_tried) > 1
    assert any("better query" in q for q in selection.queries_tried)


def test_a_scene_that_never_passes_is_left_unresolved(clip_factory):
    # Critically NOT filled with the least-bad clip: unrelated footage is the
    # failure this stage exists to remove, so a silent fallback would defeat it.
    def always_reject(brief, frame, score=None, crop_mode="crop"):
        return Review(approved=False, reason="unrelated", reviewed_by_vision=True)

    selection = select_scene(
        _brief(), _search_factory(clip_factory), set(), reviewer=always_reject
    )

    assert not selection.resolved
    assert selection.clip_path is None


def test_direct_scenes_reports_which_scenes_failed(clip_factory):
    def reject_second(brief, frame, score=None, crop_mode="crop"):
        if brief.index == 1:
            return Review(approved=False, reason="unrelated", reviewed_by_vision=True)
        return _approve()

    briefs = [_brief(0), _brief(1, "Plants drink water.", subject="plant", queries=["macro roots"])]
    selections = direct_scenes(briefs, search=_search_factory(clip_factory), reviewer=reject_second)

    failed = unresolved_scenes(selections)
    assert len(failed) == 1
    assert failed[0].brief.index == 1


def test_consecutive_scenes_do_not_reuse_a_near_identical_shot(clip_factory):
    # Both briefs search the same term, so without the continuity check they
    # would land on the same footage and the cut would read as a glitch.
    briefs = [_brief(0), _brief(1, "Another line.", queries=["real moon phases time lapse"])]
    selections = direct_scenes(briefs, search=_search_factory(clip_factory), reviewer=_approve)

    paths = [s.clip_path for s in selections if s.resolved]
    assert len(set(paths)) == len(paths), "the same clip was used twice in a row"


def test_storyboard_table_is_emitted_before_rendering(clip_factory):
    selections = direct_scenes(
        [_brief()], search=_search_factory(clip_factory), reviewer=_approve
    )
    table = storyboard_table([s.table_row() for s in selections])

    for heading in ("SENTENCE", "QUERIES", "SELECTED CLIP", "WHY IT MATCHES", "CROP", "SCORE"):
        assert heading in table


def test_build_storyboard_extracts_concepts_and_multiple_queries():
    payload = {
        "scenes": [
            {
                "subject": "moon",
                "action": "changing phase",
                "location": "night sky",
                "time_of_day": "night",
                "emotion": "wonder",
                "objects": ["crescent"],
                "shot_style": "time lapse",
                "queries": ["real moon phases time lapse", "crescent moon night sky"],
                "allow_generic": [],
            }
        ]
    }

    briefs = build_storyboard("t", "The moon changes shape.", generate=lambda p, json_mode: json.dumps(payload))

    assert len(briefs) == 1
    brief = briefs[0]
    assert brief.subject == "moon"
    assert brief.shot_style == "time lapse"
    # Never a single bare query: the pool has to offer a real choice.
    assert len(brief.queries) >= 4


def test_build_storyboard_never_searches_the_bare_topic_word():
    payload = {"scenes": [{"subject": "moon", "queries": ["real moon phases time lapse"]}]}
    briefs = build_storyboard("t", "The moon changes shape.", generate=lambda p, json_mode: json.dumps(payload))

    assert "moon" not in briefs[0].queries, "the bare topic word is exactly the bad query"


def test_build_storyboard_still_returns_a_brief_per_sentence_when_the_llm_fails():
    def boom(prompt, json_mode=False):
        raise RuntimeError("provider down")

    briefs = build_storyboard("t", "One thing. Two things. Three things.", generate=boom)

    assert len(briefs) == 3
    assert all(brief.queries for brief in briefs)


def test_heuristic_review_does_not_claim_to_have_judged_meaning():
    class _Score:
        total = 0.8
        composition = 0.5

    review = _heuristic_review(_brief(), _Score())

    assert review.approved
    assert not review.reviewed_by_vision
    assert not review.represents_sentence, "must not claim a meaning check it never did"


def test_review_falls_back_to_the_heuristic_without_a_vision_model(monkeypatch):
    import utils.editor_review as module

    monkeypatch.setattr(module, "_call_vision", lambda prompt, png: None)

    class _Score:
        total = 0.9
        composition = 0.6

    review = review_clip(_brief(), np.zeros((64, 64, 3), dtype=np.uint8), score=_Score())

    assert not review.reviewed_by_vision
    assert "no vision model" in review.reason


def test_review_rejects_when_the_model_says_the_subject_is_cropped(monkeypatch):
    import utils.editor_review as module

    monkeypatch.setattr(
        module,
        "_call_vision",
        lambda prompt, png: {
            "represents_sentence": True,
            "subject_visible": True,
            "important_content_cropped": True,
            "confidence": 0.9,
            "reason": "the moon is cut off at the top",
            "better_queries": ["full moon centred"],
        },
    )

    review = review_clip(_brief(), np.zeros((64, 64, 3), dtype=np.uint8))

    assert not review.approved
    assert review.better_queries == ["full moon centred"]


def test_review_rejects_low_confidence_approvals(monkeypatch):
    import utils.editor_review as module

    monkeypatch.setattr(
        module,
        "_call_vision",
        lambda prompt, png: {
            "represents_sentence": True,
            "subject_visible": True,
            "important_content_cropped": False,
            "confidence": 0.2,
            "reason": "might be the moon",
            "better_queries": [],
        },
    )

    assert not review_clip(_brief(), np.zeros((64, 64, 3), dtype=np.uint8)).approved


def test_query_decoration_does_not_repeat_a_modifier_already_present():
    # "seed sprouting time lapse" must not become "time lapse seed sprouting
    # time lapse" - that reads as keyword spam to a stock library and returns
    # worse results than the query the model actually wrote.
    payload = {
        "scenes": [
            {
                "subject": "seed",
                "shot_style": "time lapse",
                "queries": ["seed sprouting time lapse", "real soil close up"],
            }
        ]
    }
    briefs = build_storyboard("t", "One line.", generate=lambda p, json_mode: json.dumps(payload))

    for query in briefs[0].queries:
        assert query.count("time lapse") <= 1, query
        assert query.count("real ") <= 1, query
