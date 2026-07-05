# 💼 Job Feed

A self-refreshing job dashboard. A scheduled job pulls postings from several
sources every hour, dedupes them into a single database, and a Streamlit
dashboard lets you filter and browse them with new listings flagged.

```
  ┌─────────────────────┐   hourly    ┌──────────────┐   commits   ┌──────────────────┐
  │  GitHub Actions cron │───────────▶ │ fetch_jobs.py │──────────▶ │ jobs.db (in repo) │
  └─────────────────────┘             └──────────────┘             └────────┬─────────┘
        (runs 24/7)                                                          │ reads
                                                              ┌──────────────▼──────────────┐
                                                              │  Streamlit dashboard (cloud)  │
                                                              └──────────────────────────────┘
```

## Sources

| Source | Type | API key needed |
|---|---|---|
| **Adzuna** | Aggregator (broad, good India coverage) | Yes — free |
| **Jooble** | Aggregator | Yes — free |
| **RemoteOK** | Remote-only feed | No |
| **Remotive** | Remote-only feed | No |
| **WeWorkRemotely** | Remote-only feed (RSS) | No |

> **Why not LinkedIn / Indeed / Naukri?** They don't offer open job-search
> APIs, and scraping them violates their terms and breaks whenever they change
> their markup. The aggregators above already surface a large share of what
> those boards list.

---

## Setup (one time, ~15 min)

### 1. Get your API keys (free)

- **Adzuna** → https://developer.adzuna.com/ → register an app. You get an
  **App ID** and an **App Key**.
- **Jooble** → https://jooble.org/api/about → request an API key.

### 2. Put the repo on GitHub

Create a new repo and push these files (or fork if this is already a repo).

### 3. Add the keys as GitHub Actions secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**.
Add three:

| Name | Value |
|---|---|
| `ADZUNA_APP_ID` | your Adzuna App ID |
| `ADZUNA_APP_KEY` | your Adzuna App Key |
| `JOOBLE_API_KEY` | your Jooble key |

The dashboard itself needs **no** secrets — it only reads the committed `jobs.db`.

### 4. Kick off the first fetch

Repo → **Actions → Fetch jobs → Run workflow**. After a minute it commits a
`jobs.db` to the repo. It then re-runs automatically every hour.

### 5. Deploy the dashboard

Go to **https://share.streamlit.io** → sign in with GitHub → **New app** →
pick this repo, branch `main`, main file `dashboard.py` → **Deploy**.
You get a public URL you can open on any device, including your phone.

Each hourly commit updates `jobs.db`; Streamlit Cloud redeploys the app with
the fresh data automatically. (You can also hit **Reboot** in Streamlit Cloud,
or **🔄 Reload data** in the app, to force a refresh.)

---

## Customize

Everything you'll normally change lives in **`config.yaml`**:

- `keywords` — one search runs per keyword. Tune to your target roles.
- `locations` — used by Adzuna + Jooble. More locations = more API calls.
- `adzuna_country` — `in`, `us`, `gb`, …
- `retention_days` — how long a stale posting stays before it's pruned.
- `new_within_hours` — default "NEW" window in the dashboard.
- `sources` — toggle any source on/off.

Commit the change; the next hourly run picks it up.

---

## Run locally (optional)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then paste your keys into .env
python fetch_jobs.py        # fetch once into jobs.db
streamlit run dashboard.py  # open the dashboard
```

---

## Good to know

- **Schedule timing.** GitHub's scheduled runs are best-effort and can be
  delayed several minutes under load. It's "about hourly", not to-the-second.
- **60-day inactivity.** GitHub disables scheduled workflows on repos with no
  commits for 60 days — but this workflow commits `jobs.db` on every run, so it
  keeps itself alive.
- **Repo visibility.** For the simplest Streamlit Cloud setup the repo can be
  public; only public job listings and your `config.yaml` keywords are exposed
  (your API keys stay in Secrets, never committed). Private repos also work on
  Streamlit Cloud if you prefer.
- **API limits.** Free Adzuna/Jooble tiers are generous for a handful of
  keywords hourly. If you add many keywords/locations and hit a limit, trim
  them or disable a source in `config.yaml`.
- **Duplicates across sources.** The same role may appear from more than one
  source — that's intentional, so you can see everywhere it's listed. Within a
  source, postings are deduped by a stable ID.

## Files

```
config.yaml                     what to fetch (edit this)
fetch_jobs.py                   entry point — runs all sources, writes jobs.db
dashboard.py                    Streamlit dashboard
requirements.txt
.github/workflows/fetch-jobs.yml  hourly schedule + manual trigger
jobfeed/
  config.py                     loads config + credentials
  db.py                         SQLite storage, upsert, pruning
  sources.py                    one fetcher per source
```
