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
