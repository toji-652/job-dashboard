"""Fetchers for each job source. Each returns a list of normalized job dicts.

Normalized schema (keys):
    id, source, title, company, location, remote, url,
    description, salary, posted_at, tags
"""
from __future__ import annotations

import hashlib
import html
import re
import time

import requests

TIMEOUT = 25
UA = "Mozilla/5.0 (compatible; JobFeed/1.0)"
REMOTE_FEED_CAP = 200  # max rows to keep per remote feed after keyword filtering


def _id(source: str, key: str) -> str:
    return hashlib.sha1(f"{source}:{key}".encode("utf-8")).hexdigest()[:16]


def _clean(text: str | None, limit: int = 600) -> str:
    """Strip HTML, unescape entities, collapse whitespace, truncate."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(text))
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _matches(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(k.lower() in lowered for k in keywords)


# --------------------------------------------------------------------- Adzuna
def fetch_adzuna(keywords, locations, country, app_id, app_key, per_query):
    if not (app_id and app_key):
        raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY not set")
    out = []
    for kw in keywords:
        for loc in locations:
            url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": min(int(per_query), 50),
                "what": kw,
                "where": loc,
                "content-type": "application/json",
                "sort_by": "date",
            }
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            for j in resp.json().get("results", []):
                loc_name = (j.get("location") or {}).get("display_name", "")
                salary = None
                lo, hi = j.get("salary_min"), j.get("salary_max")
                if lo or hi:
                    salary = f"{int(lo) if lo else ''}–{int(hi) if hi else ''}".strip("–")
                out.append({
                    "id": _id("adzuna", str(j.get("id") or j.get("redirect_url"))),
                    "source": "adzuna",
                    "title": _clean(j.get("title"), 300),
                    "company": _clean((j.get("company") or {}).get("display_name"), 200),
                    "location": loc_name,
                    "remote": "remote" in (loc_name + " " + (j.get("title") or "")).lower(),
                    "url": j.get("redirect_url", ""),
                    "description": _clean(j.get("description")),
                    "salary": salary,
                    "posted_at": (j.get("created") or "")[:10] or None,
                    "tags": (j.get("category") or {}).get("label"),
                })
    return out


# --------------------------------------------------------------------- Jooble
def fetch_jooble(keywords, locations, api_key, per_query):
    if not api_key:
        raise RuntimeError("JOOBLE_API_KEY not set")
    endpoint = f"https://jooble.org/api/{api_key}"
    out = []
    for kw in keywords:
        for loc in locations:
            resp = requests.post(
                endpoint, json={"keywords": kw, "location": loc}, timeout=TIMEOUT
            )
            resp.raise_for_status()
            for j in resp.json().get("jobs", [])[: int(per_query)]:
                loc_name = j.get("location", "")
                out.append({
                    "id": _id("jooble", str(j.get("id") or j.get("link"))),
                    "source": "jooble",
                    "title": _clean(j.get("title"), 300),
                    "company": _clean(j.get("company"), 200),
                    "location": loc_name,
                    "remote": "remote" in (loc_name + " " + (j.get("title") or "")).lower(),
                    "url": j.get("link", ""),
                    "description": _clean(j.get("snippet")),
                    "salary": (j.get("salary") or None),
                    "posted_at": (j.get("updated") or "")[:10] or None,
                    "tags": j.get("type") or None,
                })
    return out


# ------------------------------------------------------------------- RemoteOK
def fetch_remoteok(keywords, per_query):
    resp = requests.get(
        "https://remoteok.com/api", headers={"User-Agent": UA}, timeout=TIMEOUT
    )
    resp.raise_for_status()
    out = []
    for j in resp.json():
        # The first element is a legal/metadata object without "position".
        if not isinstance(j, dict) or "position" not in j:
            continue
        blob = " ".join([
            j.get("position", ""),
            j.get("company", ""),
            " ".join(j.get("tags", []) or []),
            j.get("description", "") or "",
        ])
        if not _matches(blob, keywords):
            continue
        salary = None
        lo, hi = j.get("salary_min"), j.get("salary_max")
        if lo or hi:
            salary = f"{lo or ''}–{hi or ''}".strip("–")
        out.append({
            "id": _id("remoteok", str(j.get("id") or j.get("slug") or j.get("url"))),
            "source": "remoteok",
            "title": _clean(j.get("position"), 300),
            "company": _clean(j.get("company"), 200),
            "location": j.get("location") or "Remote",
            "remote": True,
            "url": j.get("url", ""),
            "description": _clean(j.get("description")),
            "salary": salary,
            "posted_at": (j.get("date") or "")[:10] or None,
            "tags": ", ".join(j.get("tags", []) or []) or None,
        })
    return out[:REMOTE_FEED_CAP]


# ------------------------------------------------------------------- Remotive
def fetch_remotive(keywords, per_query):
    out, seen = [], set()
    for kw in keywords:
        resp = requests.get(
            "https://remotive.com/api/remote-jobs",
            params={"search": kw, "limit": int(per_query)},
            headers={"User-Agent": UA},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        for j in resp.json().get("jobs", []):
            jid = _id("remotive", str(j.get("id") or j.get("url")))
            if jid in seen:
                continue
            seen.add(jid)
            out.append({
                "id": jid,
                "source": "remotive",
                "title": _clean(j.get("title"), 300),
                "company": _clean(j.get("company_name"), 200),
                "location": j.get("candidate_required_location") or "Remote",
                "remote": True,
                "url": j.get("url", ""),
                "description": _clean(j.get("description")),
                "salary": (j.get("salary") or None),
                "posted_at": (j.get("publication_date") or "")[:10] or None,
                "tags": ", ".join(j.get("tags", []) or []) or None,
            })
    return out[:REMOTE_FEED_CAP]


# ------------------------------------------------------------- WeWorkRemotely
def fetch_weworkremotely(keywords, per_query):
    import feedparser  # local import so it's only needed when this source is on

    feed = feedparser.parse("https://weworkremotely.com/remote-jobs.rss")
    out = []
    for e in feed.entries:
        title_raw = e.get("title", "")
        summary = e.get("summary", "")
        if not _matches(f"{title_raw} {summary}", keywords):
            continue
        # WWR titles are formatted like "Company: Job Title".
        if ":" in title_raw:
            company, _, title = title_raw.partition(":")
            company, title = company.strip(), title.strip()
        else:
            company, title = "", title_raw.strip()
        posted = None
        if getattr(e, "published_parsed", None):
            posted = time.strftime("%Y-%m-%d", e.published_parsed)
        out.append({
            "id": _id("weworkremotely", e.get("id") or e.get("link", "")),
            "source": "weworkremotely",
            "title": _clean(title or title_raw, 300),
            "company": _clean(company, 200),
            "location": "Remote",
            "remote": True,
            "url": e.get("link", ""),
            "description": _clean(summary),
            "salary": None,
            "posted_at": posted,
            "tags": None,
        })
    return out[:REMOTE_FEED_CAP]
