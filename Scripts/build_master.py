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

try:
    from config import DATA_DIR
except ImportError:
    from Scripts.config import DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Fechas históricas de las ceremonias de los Oscars ────────────────────────
CEREMONY_DATES = {
    1978: "1978-04-03",
    1979: "1979-04-09",
    1980: "1980-04-14",
    1981: "1981-03-31",
    1982: "1982-03-29",
    1983: "1983-04-11",
    1984: "1984-04-09",
    1985: "1985-03-25",
    1986: "1986-03-24",
    1987: "1987-03-30",
    1988: "1988-04-11",
    1989: "1989-03-29",
    1990: "1990-03-26",
    1991: "1991-03-25",
    1992: "1992-03-30",
    1993: "1993-03-29",
    1994: "1994-03-21",
    1995: "1995-03-27",
    1996: "1996-03-25",
    1997: "1997-03-24",
    1998: "1998-03-23",
    1999: "1999-03-21",
    2000: "2000-03-26",
    2001: "2001-03-25",
    2002: "2002-03-24",
    2003: "2003-03-23",
    2004: "2004-02-29",
    2005: "2005-02-27",
    2006: "2006-03-05",
    2007: "2007-02-25",
    2008: "2008-02-24",
    2009: "2009-02-22",
    2010: "2010-03-07",
    2011: "2011-02-27",
    2012: "2012-02-26",
    2013: "2013-02-24",
    2014: "2014-03-02",
    2015: "2015-02-22",
    2016: "2016-02-28",
    2017: "2017-02-26",
    2018: "2018-03-04",
    2019: "2019-02-24",
    2020: "2020-02-09",
    2021: "2021-04-25",
    2022: "2022-03-27",
    2023: "2023-03-12",
    2024: "2024-03-10",
    2025: "2025-03-02",
}


# ─────────────────────────────────────────────────────────────────────────────
#  Fuzzy merge helper
# ─────────────────────────────────────────────────────────────────────────────

def fuzzy_match_films(
    left: pd.DataFrame,
    right: pd.DataFrame,
    threshold: int = 82,
    year_slack: int = 1,
) -> pd.DataFrame:
    right = right.copy()
    right["nominated_title"] = None
    matched_count = 0

    for year in sorted(left["ceremony_year"].astype(int).unique()):
        left_titles = left.loc[left["ceremony_year"] == year, "nominated_title"].tolist()
        if not left_titles:
            continue

        for dy in range(-year_slack, year_slack + 1):
            search_year = year + dy
            mask = right["ceremony_year"].astype(int) == search_year
            unmatched_films = right.loc[mask & right["nominated_title"].isna(), "film"].tolist()

            for r_title in unmatched_films:
                result = process.extractOne(r_title, left_titles, scorer=fuzz.token_sort_ratio)
                if result is None:
                    continue
                match, score, _ = result
                if score >= threshold:
                    idx = mask & (right["film"] == r_title)
                    right.loc[idx, "nominated_title"] = match
                    right.loc[idx, "ceremony_year"] = year
                    matched_count += 1

    log.info(f"fuzzy_match_films: {matched_count} filas de awards emparejadas")
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
    df["is_english"]    = df["language"].str.contains("English", na=False).astype(int)
    df["main_language"] = df["language"].str.split(",").str[0].str.strip()

    # ── Awards season: total wins / noms ─────────────────────────────────
    award_won_cols = [c for c in df.columns if c.endswith("_won") and c != "won_best_picture"]
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

    # ── Días entre estreno y ceremonia ────────────────────────────────────
    release_dt  = pd.to_datetime(df["release_date"], errors="coerce")
    ceremony_dt = pd.to_datetime(df["ceremony_year"].map(CEREMONY_DATES), errors="coerce")
    df["days_to_ceremony"] = (ceremony_dt - release_dt).dt.days

    # ── Genre flags ───────────────────────────────────────────────────────
    TOP_GENRES = [
        "Drama", "Comedy", "Biography", "History", "Romance",
        "Thriller", "War", "Crime", "Music", "Adventure",
        "Mystery", "Western", "Science Fiction",
    ]

    def _parse_genres(genres_json) -> list:
        if not genres_json or pd.isna(genres_json):
            return []
        try:
            return json.loads(genres_json)
        except Exception:
            return []

    parsed = df["genres"].apply(_parse_genres)

    for genre in TOP_GENRES:
        col = "genre_" + genre.lower().replace(" ", "_")
        df[col] = parsed.apply(lambda gs, g=genre: int(g in gs))

    def _main_genre(gs: list) -> str:
        for g in TOP_GENRES:
            if g in gs:
                return g
        return gs[0] if gs else "Unknown"

    df["main_genre"] = parsed.apply(_main_genre)

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

    # Deduplicar: si un film matcheó desde varios años, quedarse con el max
    award_cols_aw = [c for c in awards_matched.columns
                     if c.endswith("_won") or c.endswith("_nominated")]
    awards_matched = awards_matched.groupby(
        ["ceremony_year", "nominated_title"], as_index=False
    )[award_cols_aw].max()

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

    # ── Guardar ───────────────────────────────────────────────────────────
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
        "days_to_ceremony",
    ]
    print(df[[c for c in key_cols if c in df.columns]].head())
