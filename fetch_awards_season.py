
"""
Step 3 — Awards Season scraper (Wikipedia)
Scrapes Best Film / Best Picture / Best Motion Picture equivalent from:
  - SAG Awards (Outstanding Cast in a Motion Picture)
  - BAFTA (Best Film)
  - Golden Globes (Best Motion Picture — Drama + Comedy/Musical)
  - Critics Choice Awards (Best Picture)
  - Producers Guild (PGA Award for Theatrical Motion Pictures)

For each award we track: nominee, won (1/0), ceremony_year.
Then merge with our base df to produce per-film award features.

Output: data/03_awards_season.parquet
"""

import time
import logging
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import pandas as pd

from config import DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SLEEP   = 0.4
HEADERS = {"User-Agent": "Mozilla/5.0 (OscarDatasetResearch/1.0)"}


# ─────────────────────────────────────────────────────────────────────────────
#  Wikipedia scraping helpers
# ─────────────────────────────────────────────────────────────────────────────

def _wiki_soup(page_title: str) -> BeautifulSoup:
    url = f"https://en.wikipedia.org/wiki/{page_title}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    time.sleep(SLEEP)
    return BeautifulSoup(r.text, "html.parser")


def _extract_wikitable_rows(soup: BeautifulSoup) -> list[BeautifulSoup]:
    """Return all <tr> rows from the first wikitable on the page."""
    table = soup.find("table", class_="wikitable")
    if not table:
        return []
    return table.find_all("tr")


def _clean(text: str) -> str:
    return re.sub(r"\[.*?\]", "", text).strip()


# ─────────────────────────────────────────────────────────────────────────────
#  Award-specific parsers
#  Each returns a list of dicts: {ceremony_year, film, won}
# ─────────────────────────────────────────────────────────────────────────────

def scrape_bafta_best_film(years: list[int]) -> list[dict]:
    """
    Wikipedia page: 'BAFTA_Award_for_Best_Film'
    Table cols: Year | Film | Director | Production company | Ref
    Winner row has background colour or bold — we detect via <b> tag.
    """
    soup = _wiki_soup("BAFTA_Award_for_Best_Film")
    records = []
    current_year = None

    for row in soup.select("table.wikitable tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        # year column
        year_text = _clean(cells[0].get_text())
        if re.fullmatch(r"(19|20)\d{2}", year_text):
            current_year = int(year_text) + 1   # BAFTA year → ceremony year
        if current_year is None or current_year not in years:
            continue

        # film title — usually 2nd cell
        if len(cells) < 2:
            continue
        film = _clean(cells[1].get_text())
        if not film or film.lower() in ("film", "year"):
            continue

        # winner = bold text in the film cell
        won = bool(cells[1].find("b") or row.get("style", "").startswith("background"))
        records.append({"ceremony_year": current_year, "film": film, "award": "BAFTA_best_film", "won": int(won)})

    return records


def scrape_sag_outstanding_cast(years: list[int]) -> list[dict]:
    """
    Wikipedia page: 'Screen_Actors_Guild_Award_for_Outstanding_Cast_in_a_Motion_Picture'
    """
    soup = _wiki_soup("Screen_Actors_Guild_Award_for_Outstanding_Performance_by_a_Cast_in_a_Motion_Picture")
    records = []
    current_year = None

    for row in soup.select("table.wikitable tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        year_text = _clean(cells[0].get_text())
        if re.fullmatch(r"(19|20)\d{2}", year_text):
            # SAG year = ceremony year
            current_year = int(year_text)
        if current_year is None or current_year not in years:
            continue
        if len(cells) < 2:
            continue
        film = _clean(cells[1].get_text())
        if not film or film.lower() in ("film", "year"):
            continue
        won = bool(cells[1].find("b") or row.get("style", ""))
        records.append({"ceremony_year": current_year, "film": film, "award": "SAG_outstanding_cast", "won": int(won)})

    return records


def scrape_golden_globes_drama(years: list[int]) -> list[dict]:
    """
    Wikipedia: 'Golden_Globe_Award_for_Best_Motion_Picture_–_Drama'
    """
    soup = _wiki_soup("Golden_Globe_Award_for_Best_Motion_Picture_–_Drama")
    records = []
    current_year = None

    for row in soup.select("table.wikitable tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        year_text = _clean(cells[0].get_text())
        # e.g. "2024" or "2024 (81st)"
        m = re.search(r"(20\d{2})", year_text)
        if m:
            current_year = int(m.group(1))
        if current_year is None or current_year not in years:
            continue
        if len(cells) < 2:
            continue
        film = _clean(cells[1].get_text())
        if not film or film.lower() in ("film", "year"):
            continue
        won = bool(cells[1].find("b"))
        records.append({"ceremony_year": current_year, "film": film, "award": "GG_drama", "won": int(won)})

    return records


def scrape_golden_globes_comedy(years: list[int]) -> list[dict]:
    soup = _wiki_soup("Golden_Globe_Award_for_Best_Motion_Picture_–_Musical_or_Comedy")
    records = []
    current_year = None

    for row in soup.select("table.wikitable tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        m = re.search(r"(20\d{2})", _clean(cells[0].get_text()))
        if m:
            current_year = int(m.group(1))
        if current_year is None or current_year not in years:
            continue
        if len(cells) < 2:
            continue
        film = _clean(cells[1].get_text())
        if not film or film.lower() in ("film", "year"):
            continue
        won = bool(cells[1].find("b"))
        records.append({"ceremony_year": current_year, "film": film, "award": "GG_comedy", "won": int(won)})

    return records


def scrape_critics_choice(years: list[int]) -> list[dict]:
    """
    Wikipedia: 'Critics_Choice_Movie_Award_for_Best_Picture'
    """
    soup = _wiki_soup("Critics%27_Choice_Movie_Award_for_Best_Picture")
    records = []
    current_year = None

    for row in soup.select("table.wikitable tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        m = re.search(r"(20\d{2})", _clean(cells[0].get_text()))
        if m:
            current_year = int(m.group(1))
        if current_year is None or current_year not in years:
            continue
        if len(cells) < 2:
            continue
        film = _clean(cells[1].get_text())
        if not film or film.lower() in ("film", "year"):
            continue
        won = bool(cells[1].find("b"))
        records.append({"ceremony_year": current_year, "film": film, "award": "CCA_best_picture", "won": int(won)})

    return records


def scrape_pga(years: list[int]) -> list[dict]:
    """
    Wikipedia: 'Producers_Guild_of_America_Award_for_Best_Theatrical_Motion_Picture'
    """
    soup = _wiki_soup("Producers_Guild_of_America_Award_for_Best_Theatrical_Motion_Picture")
    records = []
    current_year = None

    for row in soup.select("table.wikitable tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        m = re.search(r"(20\d{2})", _clean(cells[0].get_text()))
        if m:
            current_year = int(m.group(1))
        if current_year is None or current_year not in years:
            continue
        if len(cells) < 2:
            continue
        film = _clean(cells[1].get_text())
        if not film or film.lower() in ("film", "year"):
            continue
        won = bool(cells[1].find("b"))
        records.append({"ceremony_year": current_year, "film": film, "award": "PGA_best_picture", "won": int(won)})

    return records


# ─────────────────────────────────────────────────────────────────────────────
#  Merge: pivot wide so each film gets one row of award flags
# ─────────────────────────────────────────────────────────────────────────────

def pivot_awards(records: list[dict]) -> pd.DataFrame:
    """
    Input: flat list of {ceremony_year, film, award, won}
    Output: wide df with columns like bafta_nominated, bafta_won, sag_nominated, ...
    """
    df = pd.DataFrame(records)
    if df.empty:
        return df

    # one row per (year, film, award), keep max won (some films appear multiple times)
    df = df.groupby(["ceremony_year", "film", "award"])["won"].max().reset_index()

    # pivot
    wide = df.pivot_table(
        index=["ceremony_year", "film"],
        columns="award",
        values="won",
        aggfunc="max",
        fill_value=0,
    ).reset_index()

    # add _nominated columns (1 for any appearance)
    # (they all appear if they're in the table, won or not)
    wide.columns.name = None
    for award in df["award"].unique():
        if award in wide.columns:
            wide[f"{award}_nominated"] = 1  # if they appear they were nominated
            wide.rename(columns={award: f"{award}_won"}, inplace=True)

    return wide


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def build_awards_season_df(years: list[int]) -> pd.DataFrame:
    Path(DATA_DIR).mkdir(exist_ok=True)
    out_path = Path(DATA_DIR) / "03_awards_season.csv"

    log.info("Scraping BAFTA...")
    records = scrape_bafta_best_film(years)

    log.info("Scraping SAG...")
    records += scrape_sag_outstanding_cast(years)

    log.info("Scraping Golden Globes Drama...")
    records += scrape_golden_globes_drama(years)

    log.info("Scraping Golden Globes Comedy/Musical...")
    records += scrape_golden_globes_comedy(years)

    log.info("Scraping Critics Choice...")
    records += scrape_critics_choice(years)

    log.info("Scraping PGA...")
    records += scrape_pga(years)

    log.info(f"Total raw award rows: {len(records)}")

    wide = pivot_awards(records)
    wide.to_csv(out_path, index=False)
    log.info(f"Saved {len(wide)} rows → {out_path}")
    return wide


if __name__ == "__main__":
    from config import YEARS
    df = build_awards_season_df(YEARS)
    print(df.head())
    print(df.columns.tolist())