"""
Step 4 — Merge all sources into master dataset
Joins: 01_tmdb + 02_omdb + 03_awards_season
Adds: engineered features ready for modeling

Output: data/master_dataset.csv
"""

import re
import json
import logging
from pathlib import Path

import pandas as pd
import numpy as np
from rapidfuzz import process, fuzz   # pip install rapidfuzz

from Scripts.config import DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Fuzzy merge helper
# ─────────────────────────────────────────────────────────────────────────────

def fuzzy_match_films(
    left: pd.DataFrame,
    right: pd.DataFrame,
    threshold: int = 82,
) -> pd.DataFrame:
    right = right.copy()
    right["nominated_title"] = None

    for year in left["ceremony_year"].unique():
        left_titles  = left.loc[left["ceremony_year"] == year, "nominated_title"].tolist()
        right_mask   = right["ceremony_year"] == year
        right_titles = right.loc[right_mask, "film"].tolist()

        for r_title in right_titles:
            match, score, _ = process.extractOne(
                r_title, left_titles, scorer=fuzz.token_sort_ratio
            )
            if score >= threshold:
                right.loc[(right["ceremony_year"] == year) & (right["film"] == r_title),
                          "nominated_title"] = match

    return right


# ─────────────────────────────────────────────────────────────────────────────
#  Feature engineering
# ─────────────────────────────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # ── Budget & Revenue (millones, log) ──────────────────────────────────
    df["budget_m"]    = pd.to_numeric(df["budget"], errors="coerce").replace(0, np.nan) / 1e6
    df["revenue_m"]   = pd.to_numeric(df["revenue"], errors="coerce").replace(0, np.nan) / 1e6
    df["log_budget"]  = np.log1p(df["budget_m"])
    df["log_revenue"] = np.log1p(df["revenue_m"])
    df["roi"]         = df["revenue_m"] / df["budget_m"]

    # ── IMDB votes (log) ──────────────────────────────────────────────────
    df["log_imdb_votes"] = np.log1p(pd.to_numeric(df["imdb_votes"], errors="coerce"))

    # ── Release month ─────────────────────────────────────────────────────
    df["release_month"] = pd.to_datetime(df["release_date"], errors="coerce").dt.month
    df["is_q4_release"] = df["release_month"].isin([10, 11, 12]).astype(int)

    # ── Idioma ────────────────────────────────────────────────────────────
    df["is_english"] = (df["original_language"] == "en").astype(int)

    # ── Awards season: total wins / noms ─────────────────────────────────
    award_won_cols = [c for c in df.columns if c.endswith("_won")]
    award_nom_cols = [c for c in df.columns if c.endswith("_nominated")]
    df["total_precursor_wins"] = df[award_won_cols].sum(axis=1) if award_won_cols else 0
    df["total_precursor_noms"] = df[award_nom_cols].sum(axis=1) if award_nom_cols else 0

    # ── Oscar wins desde texto OMDB ───────────────────────────────────────
    def _extract_oscar_wins(text) -> int:
        if not text or pd.isna(text):
            return 0
        m = re.search(r"Won (\d+) Oscar", str(text))
        return int(m.group(1)) if m else 0

    df["omdb_oscar_wins"] = df["omdb_awards"].apply(_extract_oscar_wins)

    # ── Genre flags ───────────────────────────────────────────────────────
    def _has_genre(genres_json, genre: str) -> int:
        if not genres_json or pd.isna(genres_json):
            return 0
        try:
            return int(genre in json.loads(genres_json))
        except Exception:
            return 0

    for genre in ["Drama", "Comedy", "Biography", "History", "Romance", "Thriller", "War"]:
        df[f"genre_{genre.lower()}"] = df["genres"].apply(lambda g: _has_genre(g, genre))

    # ── Critic composite ──────────────────────────────────────────────────
    df["rt_norm"]         = pd.to_numeric(df["rt_score"], errors="coerce")
    df["imdb_norm"]       = pd.to_numeric(df["imdb_rating"], errors="coerce") * 10
    df["metacritic_norm"] = pd.to_numeric(df["metacritic"], errors="coerce")
    df["critic_composite"] = df[["rt_norm", "imdb_norm", "metacritic_norm"]].mean(axis=1)

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def build_master() -> pd.DataFrame:
    data_dir = Path(DATA_DIR)

    tmdb_df   = pd.read_csv(data_dir / "01_tmdb.csv")
    omdb_df   = pd.read_csv(data_dir / "02_omdb.csv")
    awards_df = pd.read_csv(data_dir / "03_awards_season.csv")

    log.info(f"Shapes: TMDB={tmdb_df.shape}, OMDB={omdb_df.shape}, Awards={awards_df.shape}")

    # ── Merge TMDB + OMDB ─────────────────────────────────────────────────
    df = tmdb_df.merge(
        omdb_df,
        on=["ceremony_year", "nominated_title"],
        how="left",
        suffixes=("_tmdb", "_omdb"),
    )
    log.info(f"Tras merge TMDB+OMDB: {df.shape}")

    # ── Fuzzy merge awards season ─────────────────────────────────────────
    awards_matched = fuzzy_match_films(df, awards_df)
    awards_matched = awards_matched.dropna(subset=["nominated_title"])
    awards_matched = awards_matched.drop(columns=["film"])

    df = df.merge(
        awards_matched,
        on=["ceremony_year", "nominated_title"],
        how="left",
    )
    log.info(f"Tras merge awards: {df.shape}")

    # ── Fill NaN award cols con 0 ─────────────────────────────────────────
    award_cols = [c for c in df.columns if c.endswith("_won") or c.endswith("_nominated")]
    df[award_cols] = df[award_cols].fillna(0).astype(int)

    # ── Feature engineering ───────────────────────────────────────────────
    df = engineer_features(df)

    # ── Guardar solo CSV ──────────────────────────────────────────────────
    out_csv = data_dir / "master_dataset.csv"
    df.to_csv(out_csv, index=False)
    log.info(f"Master dataset guardado: {df.shape[0]} filas x {df.shape[1]} cols")
    log.info(f"  -> {out_csv}")

    return df


if __name__ == "__main__":
    df = build_master()
    print("\n── Columnas ──")
    print(df.dtypes.to_string())
    print("\n── Primeras 5 filas (cols clave) ──")
    key_cols = [
        "ceremony_year", "nominated_title", "won_best_picture",
        "imdb_rating", "rt_score", "metacritic",
        "budget_m", "revenue_m",
        "total_precursor_wins", "critic_composite",
    ]
    print(df[[c for c in key_cols if c in df.columns]].head())