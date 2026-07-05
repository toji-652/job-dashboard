"""Load configuration from config.yaml and credentials from the environment."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

# Load a local .env if present (used for local testing; ignored in CI where
# secrets come from GitHub Actions). Silently continue if python-dotenv is absent.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"

DEFAULTS = {
    "keywords": ["data engineer"],
    "locations": ["India"],
    "adzuna_country": "in",
    "retention_days": 30,
    "new_within_hours": 24,
    "max_results_per_query": 50,
    "sources": {
        "adzuna": True,
        "jooble": True,
        "remoteok": True,
        "remotive": True,
        "weworkremotely": True,
    },
}


def load_config() -> dict:
    """Return config.yaml merged over sensible defaults."""
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            user_cfg = yaml.safe_load(fh) or {}
        for key, value in user_cfg.items():
            if key == "sources" and isinstance(value, dict):
                merged = dict(DEFAULTS["sources"])
                merged.update(value)
                cfg["sources"] = merged
            else:
                cfg[key] = value
    return cfg


# Credentials — set as GitHub Actions secrets, or in a local .env file.
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY", "")

# Where the SQLite database lives. Defaults to jobs.db in the repo root.
DB_PATH = os.getenv("DB_PATH", str(ROOT / "jobs.db"))
