"""The dashboard's two-stage flow, where the storyboard has to survive SQLite."""

import asyncio

import pytest

from api.jobs import pipeline
from utils.storyboard import SceneBrief


def _brief(index=0, sentence="చంద్రుడు ఆకారం మారుస్తాడు."):
    return SceneBrief(
        index=index,
        sentence=sentence,
        subject="moon",
        action="changing phase",
        location="night sky",
        objects=["crescent"],
        shot_style="time lapse",
        queries=["real moon phases time lapse", "crescent moon night sky"],
    )


def test_scene_brief_survives_a_json_round_trip():
    original = _brief()

    restored = SceneBrief.from_dict(original.to_dict())

    assert restored.subject == original.subject
    assert restored.action == original.action
    assert restored.location == original.location
    assert restored.objects == original.objects
    assert restored.shot_style == original.shot_style
    assert restored.queries == original.queries
    assert restored.sentence == original.sentence


def test_from_dict_tolerates_a_payload_missing_newer_fields():
    # A job stored before a field existed should still render, not raise.
    restored = SceneBrief.from_dict({"index": 2, "sentence": "One line.", "subject": "cat"})

    assert restored.index == 2
    assert restored.subject == "cat"
    assert restored.queries, "a brief with no stored queries must rebuild some"


def test_briefs_for_uses_the_stored_storyboard_without_calling_the_llm(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("stage 2 must not re-analyse a stored storyboard")

    monkeypatch.setattr(pipeline, "build_storyboard", explode)

    job = {"storyboard": [_brief().to_dict()], "title": "t", "script": "s"}
    briefs = pipeline._briefs_for(job)

    assert len(briefs) == 1
    assert briefs[0].subject == "moon"


def test_briefs_for_rebuilds_for_a_job_created_before_storyboards(monkeypatch):
    # A job paused at script_ready before this deploy must still be renderable.
    rebuilt = [_brief()]
    monkeypatch.setattr(pipeline, "build_storyboard", lambda title, script, generate: rebuilt)

    briefs = pipeline._briefs_for({"storyboard": None, "title": "t", "script": "One. Two."})

    assert briefs == rebuilt


def test_script_stage_persists_the_storyboard_and_flat_queries(monkeypatch, tmp_path):
    from api import db as db_module
    from api.jobs import store

    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "jobs.db")
    db_module.init_db()

    monkeypatch.setattr(pipeline, "get_titles", lambda topic: ["ఒక శీర్షిక"])
    monkeypatch.setattr(pipeline, "get_most_engaging_titles", lambda titles, n: titles[:n])
    monkeypatch.setattr(pipeline, "get_script", lambda title, topic: "ఒక వాక్యం.")
    monkeypatch.setattr(pipeline, "get_description", lambda title, script: "వివరణ")
    monkeypatch.setattr(pipeline, "build_storyboard", lambda title, script, generate: [_brief()])

    job = store.create_job("Space, Planets and Stars")

    async def noop(stage, message):
        return None

    asyncio.run(
        pipeline.run_script_stage(job["id"], "Space, Planets and Stars", noop, lambda: False)
    )

    saved = store.get_job(job["id"])
    assert saved["stage"] == "script_ready"
    assert saved["storyboard"][0]["subject"] == "moon"
    # search_terms stays populated for the existing UI, holding each scene's
    # first query rather than the old bag-of-keywords string.
    assert saved["search_terms"] == ["real moon phases time lapse"]


def test_render_stage_refuses_to_render_when_no_scene_resolved(monkeypatch, tmp_path):
    from api import db as db_module
    from api.jobs import store
    from utils.visual_director import SceneSelection

    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "jobs.db")
    db_module.init_db()

    # Every scene unresolved: rendering would produce a video of nothing that
    # matches the narration, which is the failure this stage exists to prevent.
    monkeypatch.setattr(
        pipeline, "direct_scenes", lambda briefs: [SceneSelection(brief=b) for b in briefs]
    )
    monkeypatch.setattr(pipeline, "generate_voiceover", lambda script, voice: tmp_path / "v.wav")

    job = store.create_job("Space, Planets and Stars")
    store.update_job(
        job["id"], title="t", script="ఒక వాక్యం.", storyboard=[_brief().to_dict()]
    )

    async def noop(stage, message):
        return None

    with pytest.raises(RuntimeError, match="refusing to render"):
        asyncio.run(
            pipeline.run_render_stage(
                job["id"], store.get_job(job["id"]), None, noop, lambda: False
            )
        )
