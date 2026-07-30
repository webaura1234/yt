from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
from api.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "CREDENTIALS_PATH", tmp_path / "credentials")
    monkeypatch.setattr(config, "BACKGROUND_SONGS_PATH", tmp_path / "music")
    monkeypatch.setattr(config, "SECONDARY_CONTENT_PATH", tmp_path / "secondary_video")
    monkeypatch.setattr(config, "OUTPUT_PATH", tmp_path / "output")
    monkeypatch.setattr(config, "TEMP_PATH", tmp_path / "temp")

    with TestClient(app) as c:
        yield c


def test_youtube_status_false_when_credentials_dir_missing(client: TestClient):
    res = client.get("/api/stats")
    assert res.status_code == 200
    assert res.json()["youtube"] == {"configured": False, "authorized": False}


def test_youtube_status_configured_but_not_authorized(client: TestClient):
    creds_dir = config.CREDENTIALS_PATH
    creds_dir.mkdir(parents=True)
    (creds_dir / "client_secrets.json").write_text("{}")

    res = client.get("/api/stats")
    assert res.json()["youtube"] == {"configured": True, "authorized": False}


def test_youtube_status_configured_and_authorized(client: TestClient):
    creds_dir = config.CREDENTIALS_PATH
    creds_dir.mkdir(parents=True)
    (creds_dir / "client_secrets.json").write_text("{}")
    (creds_dir / "tokens.json").write_text("{}")

    res = client.get("/api/stats")
    assert res.json()["youtube"] == {"configured": True, "authorized": True}
