import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).parent / "jobs.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    stage TEXT NOT NULL,
    title TEXT,
    script TEXT,
    description TEXT,
    search_terms_json TEXT,
    storyboard_json TEXT,
    voice TEXT,
    video_path TEXT,
    youtube_video_id TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# Columns added after the first release. CREATE TABLE IF NOT EXISTS won't add a
# column to a table that already exists, so an existing jobs.db would keep the
# old shape and every write touching the new column would fail.
_ADDED_COLUMNS = (("storyboard_json", "TEXT"),)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(_SCHEMA)
        _apply_migrations(conn)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a database was first created.

    Idempotent: checks the live table shape rather than tracking a version, so
    running it on a fresh database (where _SCHEMA already created everything)
    is a no-op.
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    for column, column_type in _ADDED_COLUMNS:
        if column not in existing:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {column_type}")


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
