"""
Step 1 — TMDB enrichment
Fetches: tmdb_id, synopsis, budget, revenue, runtime, genres,
         release_date, original_language, popularity, vote_average, vote_count
         + cast top-5, director

Output: data/01_tmdb.csv
"""

import time
import json
import logging
from pathlib import Path

import requests
import pandas as pd

# ── local imports ─────────────────────────────────────────────────────────────
from Scripts.nominees_ground_truth import OSCAR_BEST_PICTURE
from Scripts.config import TMDB_API_KEY, DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"
SLEEP    = 0.25


# ── helpers ───────────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = {}) -> dict:
    """Thin wrapper with retry on 429. Usa api_key como query param."""
    url = f"{BASE_URL}/{endpoint}"
    all_params = {"api_key": TMDB_API_KEY, **params}
    for attempt in range(4):
        resp = requests.get(url, params=all_params, timeout=10)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 5))
            log.warning(f"Rate limited, sleeping {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Failed after retries: {url}")


def search_movie(title: str, ceremony_year: int) -> int | None:
    """
    Return TMDB movie_id para un titulo dado.
    Release year = ceremony_year - 1.
    Prueba año exacto primero, luego +/-1.
    """
    release_year = ceremony_year - 1
    for year in [release_year, release_year - 1, release_year + 1]:
        data = _get("search/movie", {"query": title, "year": year, "language": "en-US"})
        results = data.get("results", [])
        if results:
            for r in results:
                if r["title"].lower() == title.lower():
                    return r["id"]
            return results[0]["id"]
    log.warning(f"Not found: {title!r} ({ceremony_year})")
    return None


def fetch_movie_details(tmdb_id: int) -> dict:
    """Trae detalles completos + credits en una sola request."""
    details = _get(f"movie/{tmdb_id}", {"language": "en-US", "append_to_response": "credits"})

    credits   = details.get("credits", {})
    cast_top5 = [c["name"] for c in credits.get("cast", [])[:5]]
    director  = next(
        (c["name"] for c in credits.get("crew", []) if c["job"] == "Director"),
        None
    )
    genres = [g["name"] for g in details.get("genres", [])]

    return {
        "tmdb_id"             : tmdb_id,
        "tmdb_title"          : details.get("title"),
        "synopsis"            : details.get("overview"),
        "tagline"             : details.get("tagline"),
        "budget"              : details.get("budget"),
        "revenue"             : details.get("revenue"),
        "runtime_min"         : details.get("runtime"),
        "release_date"        : details.get("release_date"),
        "original_language"   : details.get("original_language"),
        "genres"              : json.dumps(genres),
        "tmdb_popularity"     : details.get("popularity"),
        "tmdb_vote_avg"       : details.get("vote_average"),
        "tmdb_vote_count"     : details.get("vote_count"),
        "director"            : director,
        "cast_top5"           : json.dumps(cast_top5),
        "production_companies": json.dumps(
            [c["name"] for c in details.get("production_companies", [])[:3]]
        ),
    }


# ── main ──────────────────────────────────────────────────────────────────────

def build_tmdb_df() -> pd.DataFrame:
    Path(DATA_DIR).mkdir(exist_ok=True)
    out_path = Path(DATA_DIR) / "01_tmdb.csv"

    # resume support: saltea los ya fetcheados
    if out_path.exists():
        existing  = pd.read_csv(out_path)
        done_keys = set(zip(existing["ceremony_year"], existing["nominated_title"]))
        log.info(f"Resumiendo — {len(done_keys)} registros ya fetcheados")
    else:
        existing  = pd.DataFrame()
        done_keys = set()

    records = []
    for ceremony_year, title, won in OSCAR_BEST_PICTURE:
        if (ceremony_year, title) in done_keys:
            continue

        log.info(f"Fetching [{ceremony_year}] {title!r}")
        tmdb_id = search_movie(title, ceremony_year)

        row = {
            "ceremony_year"   : ceremony_year,
            "nominated_title" : title,
            "won_best_picture": int(won),
        }

        if tmdb_id:
            try:
                details = fetch_movie_details(tmdb_id)
                row.update(details)
            except Exception as e:
                log.error(f"Details failed para {title!r}: {e}")
        else:
            row["tmdb_id"] = None

        records.append(row)
        time.sleep(SLEEP)

    df_new = pd.DataFrame(records)
    df = pd.concat([existing, df_new], ignore_index=True) if not existing.empty else df_new
    df.to_csv(out_path, index=False)
    log.info(f"Guardado {len(df)} filas -> {out_path}")
    return df


if __name__ == "__main__":
    df = build_tmdb_df()
    print(df[["ceremony_year", "nominated_title", "won_best_picture", "tmdb_id", "synopsis"]].head(10))