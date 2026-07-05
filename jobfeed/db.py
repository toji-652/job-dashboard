"""SQLite storage for job postings."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    source      TEXT,
    title       TEXT,
    company     TEXT,
    location    TEXT,
    remote      INTEGER DEFAULT 0,
    url         TEXT,
    description TEXT,
    salary      TEXT,
    posted_at   TEXT,        -- ISO date from the source (may be NULL)
    first_seen  TEXT,        -- when our fetcher first saw it (UTC)
    last_seen   TEXT,        -- most recent fetch that saw it (UTC)
    tags        TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    run_at  TEXT,
    source  TEXT,
    fetched INTEGER,
    new     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_jobs_last_seen  ON jobs(last_seen);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


@contextmanager
def connect(db_path: str):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db(db_path: str) -> None:
    with connect(db_path) as con:
        con.executescript(SCHEMA)


def existing_ids(con, ids: list[str]) -> set[str]:
    """Return the subset of ids already present in the jobs table."""
    found: set[str] = set()
    chunk = 500
    for i in range(0, len(ids), chunk):
        part = ids[i : i + chunk]
        placeholders = ",".join("?" * len(part))
        rows = con.execute(
            f"SELECT id FROM jobs WHERE id IN ({placeholders})", part
        ).fetchall()
        found.update(r[0] for r in rows)
    return found


def upsert_jobs(con, jobs: list[dict]) -> int:
    """Insert new jobs and refresh existing ones. Returns the count of NEW jobs.

    first_seen is set on insert and preserved on update (not in the DO UPDATE
    clause), so it always reflects the first time we ever saw a posting.
    """
    if not jobs:
        return 0
    ts = now_iso()
    already = existing_ids(con, [j["id"] for j in jobs])
    new_count = 0
    for j in jobs:
        if j["id"] not in already:
            new_count += 1
        con.execute(
            """
            INSERT INTO jobs
                (id, source, title, company, location, remote, url,
                 description, salary, posted_at, first_seen, last_seen, tags)
            VALUES
                (:id, :source, :title, :company, :location, :remote, :url,
                 :description, :salary, :posted_at, :first_seen, :last_seen, :tags)
            ON CONFLICT(id) DO UPDATE SET
                last_seen   = excluded.last_seen,
                title       = excluded.title,
                company     = excluded.company,
                location    = excluded.location,
                remote      = excluded.remote,
                url         = excluded.url,
                description = excluded.description,
                salary      = excluded.salary,
                posted_at   = excluded.posted_at,
                tags        = excluded.tags
            """,
            {
                "id": j["id"],
                "source": j["source"],
                "title": j.get("title", ""),
                "company": j.get("company", ""),
                "location": j.get("location", ""),
                "remote": 1 if j.get("remote") else 0,
                "url": j.get("url", ""),
                "description": j.get("description", ""),
                "salary": j.get("salary"),
                "posted_at": j.get("posted_at"),
                "first_seen": ts,
                "last_seen": ts,
                "tags": j.get("tags"),
            },
        )
    return new_count


def record_run(con, source: str, fetched: int, new: int) -> None:
    con.execute(
        "INSERT INTO runs (run_at, source, fetched, new) VALUES (?, ?, ?, ?)",
        (now_iso(), source, fetched, new),
    )


def prune(con, retention_days: int) -> int:
    """Delete stale postings and old run records. Returns postings deleted."""
    cur = con.execute("DELETE FROM jobs WHERE last_seen < ?", (_cutoff(retention_days),))
    deleted = cur.rowcount
    con.execute("DELETE FROM runs WHERE run_at < ?", (_cutoff(14),))
    return deleted
