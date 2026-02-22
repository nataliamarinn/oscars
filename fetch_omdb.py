"""
Step 2 — OMDB enrichment
Fetches: imdb_id, imdb_rating, imdb_votes, rt_score, metacritic_score,
         box_office_usd, rated (PG/R/etc), awards_text

Requires: data/01_tmdb.csv
Output:   data/02_omdb.csv
"""

import time
import re
import logging
from pathlib import Path

import requests
import pandas as pd

from config import OMDB_API_KEY, DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "http://www.omdbapi.com/"
SLEEP    = 0.15


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_int(val: str | None) -> int | None:
    if not val or val == "N/A":
        return None
    return int(re.sub(r"[^0-9]", "", val)) or None


def _parse_float(val: str | None) -> float | None:
    if not val or val == "N/A":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def fetch_omdb(title: str, year: int) -> dict:
    """
    year = release year of the film (ceremony_year - 1).
    OMDB returns Ratings list: [{Source, Value}, ...] which includes RT.
    """
    params = {
        "t"      : title,
        "y"      : year,
        "apikey" : OMDB_API_KEY,
        "type"   : "movie",
    }
    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get("Response") == "False":
        # retry without year constraint
        params.pop("y")
        resp = requests.get(BASE_URL, params=params, timeout=10)
        data = resp.json()
        if data.get("Response") == "False":
            log.warning(f"OMDB miss: {title!r} ({year})")
            return {}

    # ── parse ratings list ────────────────────────────────────────────────
    ratings: dict[str, str] = {
        r["Source"]: r["Value"]
        for r in data.get("Ratings", [])
    }
    rt_raw   = ratings.get("Rotten Tomatoes", None)
    rt_score = _parse_int(rt_raw.replace("%", "") if rt_raw else None)

    return {
        "imdb_id"        : data.get("imdbID"),
        "imdb_rating"    : _parse_float(data.get("imdbRating")),
        "imdb_votes"     : _parse_int(data.get("imdbVotes")),
        "metacritic"     : _parse_int(data.get("Metascore")),
        "rt_score"       : rt_score,
        "box_office_usd" : _parse_int(data.get("BoxOffice")),
        "rated"          : data.get("Rated"),
        "omdb_awards"    : data.get("Awards"),
        "country"        : data.get("Country"),
        "language"       : data.get("Language"),
    }


# ── main ──────────────────────────────────────────────────────────────────────

def build_omdb_df() -> pd.DataFrame:
    tmdb_path = Path(DATA_DIR) / "01_tmdb.csv"
    assert tmdb_path.exists(), "Correr fetch_tmdb.py primero"
    base_df = pd.read_csv(tmdb_path)

    out_path = Path(DATA_DIR) / "02_omdb.csv"
    done_titles: set = set()
    if out_path.exists():
        existing    = pd.read_csv(out_path)
        done_titles = set(zip(existing["ceremony_year"], existing["nominated_title"]))
        log.info(f"Resumiendo — {len(done_titles)} registros ya fetcheados")
    else:
        existing = pd.DataFrame()

    records = []
    for _, row in base_df.iterrows():
        key = (row["ceremony_year"], row["nominated_title"])
        if key in done_titles:
            continue

        release_year = int(row["ceremony_year"]) - 1
        title        = row["nominated_title"]

        # prefer TMDB title for OMDB search (handles accented chars etc.)
        search_title = row.get("tmdb_title") or title
        log.info(f"OMDB [{row['ceremony_year']}] {search_title!r}")

        omdb_data = fetch_omdb(search_title, release_year)
        rec = {
            "ceremony_year"  : row["ceremony_year"],
            "nominated_title": title,
            **omdb_data,
        }
        records.append(rec)
        time.sleep(SLEEP)

    df_new = pd.DataFrame(records)
    df = pd.concat([existing, df_new], ignore_index=True) if not existing.empty else df_new
    df.to_csv(out_path, index=False)
    log.info(f"Guardado {len(df)} filas -> {out_path}")
    return df


if __name__ == "__main__":
    df = build_omdb_df()
    print(df[["ceremony_year", "nominated_title", "imdb_rating", "rt_score", "box_office_usd"]].head(10))