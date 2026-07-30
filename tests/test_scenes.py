from pathlib import Path

import pytest

import utils.scenes as scenes_module
from utils.scenes import Scene, _broaden_query, _extract_pexels_id, fetch_scene_candidates
from utils.stock_videos import get_stock_videos
from utils.video import _SECONDARY_VIDEO_SEARCH_TERMS


def _patch_pexels(monkeypatch, results_by_query: dict):
    def fake_search(query, per_page=8, orientation=None):
        return results_by_query.get(query, [])

    monkeypatch.setattr(scenes_module, "_search_pexels_video_candidates", fake_search)


def _patch_download_and_validate(monkeypatch, tmp_path):
    def fake_download(url, dest):
        dest.write_bytes(b"fake")
        return True

    def fake_validate(path, min_duration=1.0, min_width=480, require_landscape=False):
        return True

    monkeypatch.setattr(scenes_module, "PEXELS_API_KEY", "fake-key")
    monkeypatch.setattr(scenes_module, "TEMP_PATH", tmp_path)
    monkeypatch.setattr(scenes_module, "download_file", fake_download)
    monkeypatch.setattr(scenes_module, "_validate_video_file", fake_validate)


def test_extract_pexels_id_parses_video_file_url():
    url = "https://videos.pexels.com/video-files/12345/12345-hd.mp4"
    assert _extract_pexels_id(url) == "12345"


def test_extract_pexels_id_falls_back_to_full_url_when_no_match():
    assert _extract_pexels_id("not-a-real-url") == "not-a-real-url"


def test_broaden_query_keeps_trailing_words():
    assert _broaden_query("red stock market crash chart") == "crash chart"


def test_broaden_query_returns_unchanged_for_short_query():
    assert _broaden_query("crash chart") == "crash chart"


def test_fetch_scene_candidates_dedupes_pexels_ids_across_scenes(monkeypatch, tmp_path):
    _patch_download_and_validate(monkeypatch, tmp_path)

    shared_url = "https://videos.pexels.com/video-files/1/1-hd.mp4"
    other_url = "https://videos.pexels.com/video-files/2/2-hd.mp4"

    _patch_pexels(
        monkeypatch,
        {
            "scene one": [shared_url, other_url],
            "scene two": [shared_url],  # its only candidate is already claimed
        },
    )

    scenes = fetch_scene_candidates(["scene one", "scene two"], candidates_per_scene=1)

    assert len(scenes[0].clip_paths) == 1
    # scene two couldn't reuse the already-claimed clip, so it fell back to
    # borrowing from its adjacent scene instead of duplicating footage.
    assert scenes[1].clip_paths == scenes[0].clip_paths[:1]


def test_fetch_scene_candidates_falls_back_to_broadened_query_when_exact_query_empty(
    monkeypatch, tmp_path
):
    _patch_download_and_validate(monkeypatch, tmp_path)
    url = "https://videos.pexels.com/video-files/9/9-hd.mp4"

    _patch_pexels(
        monkeypatch,
        {
            "very specific unusual scene query": [],
            "scene query": [url],  # the broadened (last-2-words) form
        },
    )

    scenes = fetch_scene_candidates(["very specific unusual scene query"], candidates_per_scene=1)

    assert len(scenes[0].clip_paths) == 1


def test_fetch_scene_candidates_falls_back_to_adjacent_scene_pool(monkeypatch, tmp_path):
    _patch_download_and_validate(monkeypatch, tmp_path)
    url = "https://videos.pexels.com/video-files/5/5-hd.mp4"

    _patch_pexels(
        monkeypatch,
        {
            "first scene": [url],
            "empty scene query": [],
            "scene query": [],  # broadened form of "empty scene query" - also empty
        },
    )

    scenes = fetch_scene_candidates(["first scene", "empty scene query"], candidates_per_scene=1)

    assert scenes[1].clip_paths == scenes[0].clip_paths[:1]


def test_fetch_scene_candidates_falls_back_to_generic_broll_as_last_resort(monkeypatch, tmp_path):
    _patch_download_and_validate(monkeypatch, tmp_path)
    broll_url = "https://videos.pexels.com/video-files/7/7-hd.mp4"

    results = {term: [] for term in _SECONDARY_VIDEO_SEARCH_TERMS}
    results[_SECONDARY_VIDEO_SEARCH_TERMS[0]] = [broll_url]
    results["only scene"] = []
    results["scene"] = []  # broadened form of "only scene"

    _patch_pexels(monkeypatch, results)

    scenes = fetch_scene_candidates(["only scene"], candidates_per_scene=1)

    assert len(scenes[0].clip_paths) == 1


def test_get_stock_videos_does_not_raise_when_some_scenes_have_candidates(monkeypatch):
    def fake_fetch(search_terms, candidates_per_scene=3):
        return [Scene(query="a", clip_paths=[Path("a.mp4")]), Scene(query="b", clip_paths=[])]

    monkeypatch.setattr("utils.stock_videos.fetch_scene_candidates", fake_fetch)

    result = get_stock_videos(["a", "b"])

    assert result == [[Path("a.mp4")], []]


def test_get_stock_videos_raises_only_when_every_scene_is_empty(monkeypatch):
    def fake_fetch(search_terms, candidates_per_scene=3):
        return [Scene(query="a", clip_paths=[]), Scene(query="b", clip_paths=[])]

    monkeypatch.setattr("utils.stock_videos.fetch_scene_candidates", fake_fetch)

    with pytest.raises(Exception, match="No stock videos found"):
        get_stock_videos(["a", "b"])
