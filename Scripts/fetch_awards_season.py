"""
Step 3 — Awards Season scraper (Wikipedia)
Scrapes Best Film / Best Picture equivalents from:
  - BAFTA (Best Film)
  - Golden Globes Drama
  - Golden Globes Comedy/Musical
  - Golden Globes Animation
  - Critics Choice (Best Picture)
  - PGA (Best Theatrical Motion Picture)
  - WGA (Best Adapted Screenplay)
  - WGA (Best Original Screenplay)

Regla: la primera película listada por año en cada tabla es la ganadora.

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

SLEEP   = 0.5
HEADERS = {"User-Agent": "Mozilla/5.0 (OscarDatasetResearch/1.0)"}


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
#  Scraper genérico
# ─────────────────────────────────────────────────────────────────────────────

SKIP_TEXTS = {"film", "película", "year", "año", "titre", ""}


def scrape_award_from_url(
    url: str,
    award_name: str,
    years: list[int],
    year_offset: int = 0,
) -> list[dict]:
    """
    Parsea la primera wikitable de la URL dada.

    Dos variantes de tabla Wikipedia:
      1) Año + ganadora en la misma fila (año con rowspan):
         | 2021 | Nomadland   |  ← ganadora
         |      | Promising.. |  ← nominada

      2) Año como fila de header separada:
         | 2021 (colspan) |
         | Nomadland      |  ← primera fila = ganadora
         | Promising..    |  ← nominada
    """
    soup = _wiki_soup_url(url)
    records = []
    current_year = None
    first_in_year = False

    for row in soup.select("table.wikitable tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        first_text = _clean(cells[0].get_text())
        m = re.search(r"(19|20)\d{2}", first_text)

        if m:
            year = int(m.group()) + year_offset

            # ¿Hay film válido en esta misma fila?
            if len(cells) >= 2:
                film = _clean(cells[1].get_text())
                if film.lower() not in SKIP_TEXTS:
                    # Variante 1: año + ganadora en misma fila
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

            # Variante 2: fila solo con año (sin film)
            current_year = year
            first_in_year = True

        else:
            # Fila sin año → nominada (o primera=ganadora si first_in_year)
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
        "https://en.wikipedia.org/wiki/BAFTA_Award_for_Best_Film",
        "BAFTA_best_film", years,
    )


def scrape_gg_drama(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://en.wikipedia.org/wiki/Golden_Globe_Award_for_Best_Motion_Picture_%E2%80%93_Drama",
        "GG_drama", years,
    )


def scrape_gg_comedy(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://en.wikipedia.org/wiki/Golden_Globe_Award_for_Best_Motion_Picture_%E2%80%93_Musical_or_Comedy",
        "GG_comedy", years,
    )


def scrape_gg_animation(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://en.wikipedia.org/wiki/Golden_Globe_Award_for_Best_Animated_Feature_Film",
        "GG_animation", years,
    )


def scrape_critics_choice(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://en.wikipedia.org/wiki/Critics%27_Choice_Movie_Award_for_Best_Picture",
        "CCA_best_picture", years,
    )


def scrape_pga(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://en.wikipedia.org/wiki/Producers_Guild_of_America_Award_for_Best_Theatrical_Motion_Picture",
        "PGA_best_picture", years,
    )


def scrape_wga_adapted(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://en.wikipedia.org/wiki/Writers_Guild_of_America_Award_for_Best_Adapted_Screenplay",
        "WGA_adapted", years,
    )


def scrape_wga_original(years: list[int]) -> list[dict]:
    return scrape_award_from_url(
        "https://en.wikipedia.org/wiki/Writers_Guild_of_America_Award_for_Best_Original_Screenplay",
        "WGA_original", years,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Pivot: flat records → wide df
# ─────────────────────────────────────────────────────────────────────────────

def pivot_awards(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df

    df = df.groupby(["ceremony_year", "film", "award"])["won"].max().reset_index()

    # Sin fill_value: NaN = no nominada, 0 = nominada/perdió, 1 = ganó
    wide = df.pivot_table(
        index=["ceremony_year", "film"],
        columns="award",
        values="won",
        aggfunc="max",
    ).reset_index()
    wide.columns.name = None

    for award in df["award"].unique():
        if award in wide.columns:
            wide[f"{award}_nominated"] = wide[award].notna().astype(int)
            wide[f"{award}_won"]       = wide[award].fillna(0).astype(int)
            wide.drop(columns=[award], inplace=True)

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
        records += fn(years)

    log.info(f"Total raw award rows: {len(records)}")

    wide = pivot_awards(records)
    wide.to_csv(out_path, index=False)
    log.info(f"Saved {len(wide)} rows → {out_path}")
    return wide


if __name__ == "__main__":
    from Scripts.config import YEARS
    df = build_awards_season_df(YEARS)
    print(df.head(10))
    print(df.columns.tolist())
