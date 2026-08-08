import pytest

from api import db as db_module
from api.jobs import store


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point the jobs DB at a throwaway file per test so tests never touch the real
    api/jobs.db and don't interfere with each other."""
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test_jobs.db")
    db_module.init_db()
    yield


def test_create_job_starts_pending():
    job = store.create_job("Ancient Egypt")
    assert job["stage"] == store.JobStage.PENDING.value
    assert job["topic"] == "Ancient Egypt"
    assert job["search_terms"] is None


def test_get_job_returns_none_for_unknown_id():
    assert store.get_job("does-not-exist") is None


def test_update_job_persists_fields_and_serializes_search_terms():
    job = store.create_job("Ancient Egypt")
    updated = store.update_job(
        job["id"],
        stage=store.JobStage.SCRIPT_READY,
        title="A title",
        search_terms=["pyramids", "pharaoh"],
    )

    assert updated["stage"] == "script_ready"
    assert updated["title"] == "A title"
    assert updated["search_terms"] == ["pyramids", "pharaoh"]

    refetched = store.get_job(job["id"])
    assert refetched["search_terms"] == ["pyramids", "pharaoh"]


def test_update_job_bumps_updated_at():
    job = store.create_job("Ancient Egypt")
    updated = store.update_job(job["id"], title="new title")
    assert updated["updated_at"] >= job["updated_at"]


def test_list_jobs_orders_most_recent_first():
    first = store.create_job("Topic A")
    second = store.create_job("Topic B")

    jobs = store.list_jobs()
    ids = [j["id"] for j in jobs]

    assert ids.index(second["id"]) < ids.index(first["id"])


def test_update_job_with_no_fields_returns_current_state():
    job = store.create_job("Ancient Egypt")
    assert store.update_job(job["id"]) == store.get_job(job["id"])


def test_update_job_persists_the_storyboard_across_stages():
    # The dashboard analyses the script in one request and renders in another,
    # so the shot plan has to survive a round trip through SQLite.
    job = store.create_job("Space, Planets and Stars")
    storyboard = [
        {
            "index": 0,
            "sentence": "చంద్రుడు ఆకారం మారుస్తాడు.",
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

    updated = store.update_job(job["id"], storyboard=storyboard)
    refetched = store.get_job(job["id"])

    assert updated["storyboard"] == storyboard
    assert refetched["storyboard"] == storyboard


def test_a_job_without_a_storyboard_reads_back_as_none():
    job = store.create_job("Fun Mathematics and Number Tricks")

    assert job["storyboard"] is None


def test_migration_adds_the_storyboard_column_to_an_existing_database(tmp_path, monkeypatch):
    """A jobs.db created before storyboards must gain the column, not break.

    CREATE TABLE IF NOT EXISTS silently does nothing when the table already
    exists, so without an explicit migration an older database would keep the
    old shape and every write touching the new column would fail.
    """
    import sqlite3

    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    # Build the pre-migration table by hand, exactly as the old schema had it.
    legacy = sqlite3.connect(db_path)
    legacy.executescript(
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY, topic TEXT NOT NULL, stage TEXT NOT NULL,
            title TEXT, script TEXT, description TEXT, search_terms_json TEXT,
            voice TEXT, video_path TEXT, youtube_video_id TEXT, error TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO jobs (id, topic, stage, created_at, updated_at)
        VALUES ('old-job', 'Old Topic', 'script_ready', '2026-01-01', '2026-01-01');
        """
    )
    legacy.commit()
    legacy.close()

    db_module.init_db()

    # The old row still reads, and the new column is now writable.
    old = store.get_job("old-job")
    assert old["topic"] == "Old Topic"
    assert old["storyboard"] is None

    store.update_job("old-job", storyboard=[{"index": 0, "sentence": "hi"}])
    assert store.get_job("old-job")["storyboard"] == [{"index": 0, "sentence": "hi"}]


def test_init_db_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "twice.db")

    db_module.init_db()
    db_module.init_db()

    job = store.create_job("Nature, Plants and the Weather")
    assert store.get_job(job["id"]) is not None
