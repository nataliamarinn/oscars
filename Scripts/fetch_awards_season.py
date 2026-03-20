"""
Step 3 — Awards Season scraper (Wikipedia)
Scrapes Best Film / Best Picture equivalents from:
  - BAFTA (Best Film)
  - Golden Globes Drama
  - Golden Globes Comedy/Musical
  - Golden Globes Animation
  - Critics Choice Awards (Best Picture)
  - Producers Guild (PGA)
  - WGA Adapted Screenplay
  - WGA Original Screenplay

Winner detection: "first film listed per year is the winner".

Output: data/03_awards_season.csv
"""

import time
import logging
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import pandas as pd

from Scripts.config import DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SLEEP   = 0.4
HEADERS = {"User-Agent": "Mozilla/5.0 (OscarDatasetResearch/1.0)"}

SKIP_TEXTS = {"film", "película", "year", "año", ""}


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _wiki_soup_url(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    time.sleep(SLEEP)
    return BeautifulSoup(r.text, "html.parser")


def _clean(text: str) -> str:
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"[†‡§*]", "", text)
    return text.strip().rstrip(".")


# ─────────────────────────────────────────────────────────────────────────────
#  Generic scraper — handles both Wikipedia table variants
# ─────────────────────────────────────────────────────────────────────────────

def scrape_award_from_url(
    url: str,
    award_name: str,
    years: list[int],
    year_offset: int = 0,
) -> list[dict]:
    """
    Scrape a Wikipedia award table using "first film per year = winner" logic.

    Handles two table structures:
      Variant 1 — Year and winner on the same row (year cell has rowspan):
        | 2021 (rowspan) | Nomadland (winner) |
        |                | Promising Young Woman |

      Variant 2 — Year as a separate header row:
        | 2021 (colspan) |
        | Nomadland (first film = winner) |
        | Promising Young Woman |
    """
    soup = _wiki_soup_url(url)
    records = []
    current_year = None
    first_in_year = False  # True when we still need to emit the winner (variant 2)

    for row in soup.select("table.wikitable tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        first_text = _clean(cells[0].get_text())
        m = re.search(r"(19|20)\d{2}", first_text)

        if m:
            year = int(m.group()) + year_offset

            # Is there a film title in this same row?
            if len(cells) >= 2:
                film = _clean(cells[1].get_text())
                if film.lower() not in SKIP_TEXTS:
                    # Variant 1: year + winner on same row
                    current_year = year
                    first_in_year = False
                    if current_year in years:
                        records.append({
                            "ceremony_year": current_year,
                            "film": film,
                            "award": award_name,
                            "won": 1,
                        })
                    continue

            # Variant 2: row contains only the year
            current_year = year
            first_in_year = True

        else:
            # Film row (no year in first cell)
            if current_year is None or current_year not in years:
                continue

            film = _clean(cells[0].get_text())
            if film.lower() in SKIP_TEXTS:
                continue

            won = 1 if first_in_year else 0
            first_in_year = False
            records.append({
                "ceremony_year": current_year,
                "film": film,
                "award": award_name,
                "won": won,
            })

    return records


# ─────────────────────────────────────────────────────────────────────────────
#  Award wrappers
# ─────────────────────────────────────────────────────────────────────────────

def scrape_bafta_best_film(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://es.wikipedia.org/wiki/Anexo:BAFTA_a_la_mejor_pel%C3%ADcula",
        "BAFTA_best_film",
        years,
    )


def scrape_gg_drama(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://es.wikipedia.org/wiki/Anexo:Globo_de_Oro_a_la_mejor_pel%C3%ADcula_dram%C3%A1tica",
        "GG_drama",
        years,
    )


def scrape_gg_comedy(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://es.wikipedia.org/wiki/Anexo:Globo_de_Oro_a_la_mejor_pel%C3%ADcula_-_Comedia_o_musical",
        "GG_comedy",
        years,
    )


def scrape_gg_animation(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://es.wikipedia.org/wiki/Anexo:Globo_de_Oro_a_la_mejor_pel%C3%ADcula_animada",
        "GG_animation",
        years,
    )


def scrape_critics_choice(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://en.wikipedia.org/wiki/Critics%27_Choice_Movie_Award_for_Best_Picture",
        "CCA_best_picture",
        years,
    )


def scrape_pga(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://es.wikipedia.org/wiki/Premios_del_Sindicato_de_Productores_de_Estados_Unidos",
        "PGA_best_picture",
        years,
    )


def scrape_wga_adapted(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://en.wikipedia.org/wiki/Writers_Guild_of_America_Award_for_Best_Adapted_Screenplay",
        "WGA_adapted",
        years,
    )


def scrape_wga_original(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://en.wikipedia.org/wiki/Writers_Guild_of_America_Award_for_Best_Original_Screenplay",
        "WGA_original",
        years,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Pivot: one row per film with _won / _nominated columns
# ─────────────────────────────────────────────────────────────────────────────

def pivot_awards(records: list[dict]) -> pd.DataFrame:
    """
    Input: flat list of {ceremony_year, film, award, won}
    Output: wide df with columns like BAFTA_best_film_won, BAFTA_best_film_nominated, ...
    """
    df = pd.DataFrame(records)
    if df.empty:
        return df

    df = df.groupby(["ceremony_year", "film", "award"])["won"].max().reset_index()

    wide = df.pivot_table(
        index=["ceremony_year", "film"],
        columns="award",
        values="won",
        aggfunc="max",
        fill_value=0,
    ).reset_index()

    wide.columns.name = None
    for award in df["award"].unique():
        if award in wide.columns:
            wide[f"{award}_nominated"] = 1
            wide.rename(columns={award: f"{award}_won"}, inplace=True)

    return wide


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def build_awards_season_df(years: list[int]) -> pd.DataFrame:
    Path(DATA_DIR).mkdir(exist_ok=True)
    out_path = Path(DATA_DIR) / "03_awards_season.csv"

    scrapers = [
        ("BAFTA",          scrape_bafta_best_film),
        ("GG Drama",       scrape_gg_drama),
        ("GG Comedy",      scrape_gg_comedy),
        ("GG Animation",   scrape_gg_animation),
        ("Critics Choice", scrape_critics_choice),
        ("PGA",            scrape_pga),
        ("WGA Adapted",    scrape_wga_adapted),
        ("WGA Original",   scrape_wga_original),
    ]

    records = []
    for name, fn in scrapers:
        log.info(f"Scraping {name}...")
        try:
            rows = fn(years)
            log.info(f"  {name}: {len(rows)} rows")
            records += rows
        except Exception as e:
            log.error(f"  {name} failed: {e}")

    log.info(f"Total raw award rows: {len(records)}")

    wide = pivot_awards(records)
    wide.to_csv(out_path, index=False)
    log.info(f"Saved {len(wide)} rows -> {out_path}")
    return wide


if __name__ == "__main__":
    from Scripts.config import YEARS
    df = build_awards_season_df(YEARS)
    print(df.head())
    print(df.columns.tolist())
