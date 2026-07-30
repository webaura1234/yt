from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
from api.main import app
from utils.downloads import write_attribution


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "BACKGROUND_SONGS_PATH", tmp_path / "music")
    monkeypatch.setattr(config, "SECONDARY_CONTENT_PATH", tmp_path / "secondary_video")

    with TestClient(app) as c:
        yield c


def test_list_media_empty_when_folders_missing(client: TestClient):
    res = client.get("/api/media")
    assert res.status_code == 200
    assert res.json() == {"music": [], "secondary_video": []}


def test_list_media_returns_files_with_attribution(client: TestClient):
    music_dir = config.BACKGROUND_SONGS_PATH
    music_dir.mkdir(parents=True)
    track = music_dir / "song.mp3"
    track.write_bytes(b"fake mp3 bytes")
    write_attribution(
        track,
        source="incompetech",
        license="CC BY 3.0",
        attribution_required=True,
        credit='Music: "Song" by Kevin MacLeod',
        url="https://incompetech.com/song",
    )

    # A non-audio file in the same folder should be ignored.
    (music_dir / "notes.txt").write_text("ignore me")

    res = client.get("/api/media")
    assert res.status_code == 200
    body = res.json()

    assert len(body["music"]) == 1
    item = body["music"][0]
    assert item["filename"] == "song.mp3"
    assert item["category"] == "music"
    assert item["size_bytes"] == len(b"fake mp3 bytes")
    assert item["attribution_required"] is True
    assert item["credit"] == 'Music: "Song" by Kevin MacLeod'
    assert item["license"] == "CC BY 3.0"
    assert body["secondary_video"] == []


def test_dedupe_media_removes_duplicate_files(client: TestClient):
    music_dir = config.BACKGROUND_SONGS_PATH
    music_dir.mkdir(parents=True)
    (music_dir / "a.mp3").write_bytes(b"identical bytes")
    (music_dir / "b.mp3").write_bytes(b"identical bytes")
    (music_dir / "c.mp3").write_bytes(b"different bytes")

    res = client.post("/api/media/dedupe")
    assert res.status_code == 200
    assert res.json() == {"music_removed": 1, "secondary_video_removed": 0}

    remaining = sorted(p.name for p in music_dir.iterdir())
    assert len(remaining) == 2


def test_delete_media_removes_file_and_attribution_sidecar(client: TestClient):
    music_dir = config.BACKGROUND_SONGS_PATH
    music_dir.mkdir(parents=True)
    track = music_dir / "song.mp3"
    track.write_bytes(b"fake mp3 bytes")
    write_attribution(track, source="x", license="CC BY 3.0", attribution_required=True, credit="c")

    res = client.delete("/api/media/music/song.mp3")
    assert res.status_code == 204

    assert not track.exists()
    assert not (music_dir / "song.mp3.attribution.json").exists()


def test_delete_media_404_for_unknown_category(client: TestClient):
    res = client.delete("/api/media/bogus-category/whatever.mp3")
    assert res.status_code == 404


def test_delete_media_404_for_missing_file(client: TestClient):
    config.BACKGROUND_SONGS_PATH.mkdir(parents=True)
    res = client.delete("/api/media/music/does-not-exist.mp3")
    assert res.status_code == 404


def test_delete_media_404_for_wrong_extension(client: TestClient):
    music_dir = config.BACKGROUND_SONGS_PATH
    music_dir.mkdir(parents=True)
    (music_dir / "notes.txt").write_text("not audio")

    res = client.delete("/api/media/music/notes.txt")
    assert res.status_code == 404
    assert (music_dir / "notes.txt").exists()
