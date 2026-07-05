"""Streamlit dashboard for browsing fetched job postings.

Run locally:  streamlit run dashboard.py
On Streamlit Community Cloud, set this file as the app entry point.
"""
from __future__ import annotations

import html
import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

DB_PATH = os.getenv("DB_PATH", "jobs.db")

st.set_page_config(page_title="Job Feed", page_icon="💼", layout="wide")

CARD_CSS = """
<style>
.card {
    border: 1px solid rgba(128,128,128,0.25);
    background: rgba(128,128,128,0.06);
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 12px;
}
.card-top { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.card a.title {
    font-size: 1.05rem; font-weight: 700; text-decoration: none;
    line-height: 1.3;
}
.card a.title:hover { text-decoration: underline; }
.card .meta { font-size: 0.85rem; opacity: 0.8; margin: 4px 0 8px; }
.card .desc { font-size: 0.88rem; opacity: 0.75; line-height: 1.45; }
.src {
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.4px; padding: 2px 8px; border-radius: 20px;
    color: #fff;
}
.src-adzuna         { background:#5b8def; }
.src-jooble         { background:#e2711d; }
.src-remoteok       { background:#8e44ad; }
.src-remotive       { background:#16a085; }
.src-weworkremotely { background:#c0392b; }
.new-badge {
    font-size: 0.65rem; font-weight: 800; letter-spacing: 0.5px;
    padding: 2px 8px; border-radius: 20px;
    background:#2ecc71; color:#06301a;
}
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_data(path: str):
    con = sqlite3.connect(path)
    jobs = pd.read_sql_query("SELECT * FROM jobs", con)
    try:
        last = pd.read_sql_query("SELECT MAX(run_at) AS t FROM runs", con)["t"].iloc[0]
    except Exception:
        last = None
    con.close()
    return jobs, last


def parse_iso(value):
    if not value or pd.isna(value):
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except Exception:
        return None


def humanize(dt):
    if dt is None:
        return "unknown"
    mins = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins} min ago"
    if mins < 1440:
        return f"{mins // 60} hr ago"
    return f"{mins // 1440} d ago"


def field(row, key):
    """Safe cell value: '' for NaN/None."""
    val = row.get(key)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val)


# --------------------------------------------------------------- guard clauses
if not os.path.exists(DB_PATH):
    st.title("💼 Job Feed")
    st.info(
        "No data yet — the hourly fetcher hasn't created the database. "
        "Trigger the **Fetch jobs** GitHub Action manually (Actions tab → "
        "Run workflow), wait a minute, then reload."
    )
    st.stop()

jobs, last_run = load_data(DB_PATH)

st.title("💼 Job Feed")

if jobs.empty:
    st.info("The database is empty so far — it'll fill up on the next fetch.")
    st.stop()

jobs["first_seen_dt"] = jobs["first_seen"].map(parse_iso)
now = datetime.now(timezone.utc)

# ------------------------------------------------------------------- sidebar
st.sidebar.header("Filters")
kw = st.sidebar.text_input("Search title / company")
all_sources = sorted(jobs["source"].dropna().unique())
picked = st.sidebar.multiselect("Sources", all_sources, default=all_sources)
loc_filter = st.sidebar.text_input("Location contains")
remote_only = st.sidebar.checkbox("Remote only")
added_within = st.sidebar.selectbox(
    "Added within", ["Any time", "24 hours", "3 days", "7 days"], index=0
)
new_hours = st.sidebar.slider("Mark 'NEW' if added within (hrs)", 1, 72, 24)
sort_by = st.sidebar.selectbox("Sort by", ["Newest added", "Newest posted"])

# -------------------------------------------------------------------- filter
df = jobs[jobs["source"].isin(picked)].copy()
if kw:
    mask = df["title"].str.contains(kw, case=False, na=False) | df[
        "company"
    ].str.contains(kw, case=False, na=False)
    df = df[mask]
if loc_filter:
    df = df[df["location"].str.contains(loc_filter, case=False, na=False)]
if remote_only:
    df = df[df["remote"] == 1]
if added_within != "Any time":
    hrs = {"24 hours": 24, "3 days": 72, "7 days": 168}[added_within]
    df = df[df["first_seen_dt"].map(
        lambda d: d is not None and (now - d).total_seconds() <= hrs * 3600
    )]

if sort_by == "Newest added":
    df = df.sort_values("first_seen", ascending=False)
else:
    df = df.sort_values("posted_at", ascending=False, na_position="last")

# ------------------------------------------------------------------- metrics
new_count = int(df["first_seen_dt"].map(
    lambda d: d is not None and (now - d).total_seconds() <= new_hours * 3600
).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Matching jobs", len(df))
c2.metric(f"New (≤{new_hours}h)", new_count)
c3.metric("Sources", df["source"].nunique())
c4.metric("Last refreshed", humanize(parse_iso(last_run)))

shown = min(len(df), 200)
st.caption(f"Total in database: {len(jobs)} · showing {shown} of {len(df)} matches")

# --------------------------------------------------------------------- cards
for _, row in df.head(200).iterrows():
    fs = row["first_seen_dt"]
    is_new = fs is not None and (now - fs).total_seconds() <= new_hours * 3600
    source = field(row, "source")
    src_html = f'<span class="src src-{html.escape(source)}">{html.escape(source)}</span>'
    badge = '<span class="new-badge">NEW</span>' if is_new else ""

    title = html.escape(field(row, "title") or "(untitled)")
    url = html.escape(field(row, "url") or "#", quote=True)
    company = html.escape(field(row, "company") or "—")
    location = html.escape(field(row, "location") or "—")

    bits = []
    if row["remote"] == 1:
        bits.append("🌐 remote")
    if field(row, "salary"):
        bits.append("💰 " + html.escape(field(row, "salary")))
    if field(row, "posted_at"):
        bits.append("posted " + html.escape(field(row, "posted_at")))
    extra = (" · " + " · ".join(bits)) if bits else ""

    desc = html.escape(field(row, "description")[:280])

    st.markdown(
        f"""
<div class="card">
  <div class="card-top">{src_html}{badge}</div>
  <a class="title" href="{url}" target="_blank" rel="noopener">{title}</a>
  <div class="meta">🏢 {company} · 📍 {location}{extra}</div>
  <div class="desc">{desc}</div>
</div>
""",
        unsafe_allow_html=True,
    )

if st.button("🔄 Reload data"):
    st.cache_data.clear()
    st.rerun()
