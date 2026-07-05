#!/usr/bin/env python3
"""Fetch job postings from all enabled sources and store them in SQLite.

Run hourly by GitHub Actions. Can also be run locally:  python fetch_jobs.py
"""
from __future__ import annotations

import sys
import traceback

from jobfeed import config, db, sources


def main() -> int:
    cfg = config.load_config()
    db_path = config.DB_PATH
    db.init_db(db_path)

    kws = cfg["keywords"]
    locs = cfg["locations"]
    per_query = int(cfg["max_results_per_query"])
    enabled = cfg["sources"]

    # (name, callable) for each enabled source.
    tasks = []
    if enabled.get("adzuna"):
        tasks.append(("adzuna", lambda: sources.fetch_adzuna(
            kws, locs, cfg["adzuna_country"],
            config.ADZUNA_APP_ID, config.ADZUNA_APP_KEY, per_query)))
    if enabled.get("jooble"):
        tasks.append(("jooble", lambda: sources.fetch_jooble(
            kws, locs, config.JOOBLE_API_KEY, per_query)))
    if enabled.get("remoteok"):
        tasks.append(("remoteok", lambda: sources.fetch_remoteok(kws, per_query)))
    if enabled.get("remotive"):
        tasks.append(("remotive", lambda: sources.fetch_remotive(kws, per_query)))
    if enabled.get("weworkremotely"):
        tasks.append(("weworkremotely",
                      lambda: sources.fetch_weworkremotely(kws, per_query)))

    total_new = 0
    with db.connect(db_path) as con:
        for name, fetch in tasks:
            try:
                jobs = fetch()
                new = db.upsert_jobs(con, jobs)
                db.record_run(con, name, len(jobs), new)
                total_new += new
                print(f"[{name}] fetched {len(jobs)}, new {new}")
            except Exception as exc:  # one bad source shouldn't stop the rest
                db.record_run(con, name, 0, 0)
                print(f"[{name}] ERROR: {exc}", file=sys.stderr)
                traceback.print_exc()
        deleted = db.prune(con, int(cfg["retention_days"]))
        print(f"pruned {deleted} stale postings")

    print(f"done — new this run: {total_new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
