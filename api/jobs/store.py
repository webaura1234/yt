import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from api.db import db_session, get_connection


class JobStage(str, Enum):
    PENDING = "pending"
    GENERATING_SCRIPT = "generating_script"
    SCRIPT_READY = "script_ready"  # paused: waiting for the user to edit/continue
    FETCHING_MEDIA = "fetching_media"
    RENDERING = "rendering"
    RENDERED = "rendered"
    PUBLISHING = "publishing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict[str, Any]:
    data = dict(row)
    data["search_terms"] = json.loads(data.pop("search_terms_json") or "null")
    # storyboard_json is absent on rows read from a pre-migration database.
    data["storyboard"] = json.loads(data.pop("storyboard_json", None) or "null")
    return data


def create_job(topic: str) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    now = _now()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO jobs (id, topic, stage, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, topic, JobStage.PENDING.value, now, now),
        )
    return get_job(job_id)


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_jobs(limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def update_job(job_id: str, **fields: Any) -> dict[str, Any]:
    if not fields:
        return get_job(job_id)

    if "search_terms" in fields:
        fields["search_terms_json"] = json.dumps(fields.pop("search_terms"))

    if "storyboard" in fields:
        fields["storyboard_json"] = json.dumps(fields.pop("storyboard"))

    if "stage" in fields and isinstance(fields["stage"], JobStage):
        fields["stage"] = fields["stage"].value

    fields["updated_at"] = _now()

    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [job_id]

    with db_session() as conn:
        conn.execute(f"UPDATE jobs SET {columns} WHERE id = ?", values)

    return get_job(job_id)
