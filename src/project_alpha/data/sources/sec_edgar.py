"""SEC EDGAR client (section 6: fundamentals US - 10-K, 10-Q, 8-K, XBRL,
company facts, ownership filings).

No API key required, but SEC requires a descriptive User-Agent identifying
the requester. See https://www.sec.gov/os/webmaster-faq#developers
"""

from __future__ import annotations

import requests

from project_alpha.config import SETTINGS

_BASE = "https://data.sec.gov"
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"


def _headers() -> dict:
    return {"User-Agent": SETTINGS.sec_edgar_user_agent}


def lookup_cik(ticker: str) -> str | None:
    """Resolves a ticker to a zero-padded 10-digit CIK via SEC's public
    ticker map. Cheap enough to call each time; callers should cache."""
    resp = requests.get(_TICKER_MAP_URL, headers=_headers(), timeout=15)
    resp.raise_for_status()
    for entry in resp.json().values():
        if entry.get("ticker", "").upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    return None


def get_company_facts(cik: str) -> dict:
    """Raw XBRL company facts (all reported concepts, e.g. Revenues,
    NetIncomeLoss, ...). Callers extract the concepts they need."""
    url = f"{_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_submissions(cik: str) -> dict:
    """Recent filings metadata (10-K, 10-Q, 8-K, ...) for a company."""
    url = f"{_BASE}/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_concept(facts: dict, concept: str, taxonomy: str = "us-gaap") -> list[dict]:
    """Flattens a single XBRL concept (e.g. 'Revenues') into a list of
    {end, val, form, fy, fp} rows, most recent first."""
    try:
        units = facts["facts"][taxonomy][concept]["units"]
    except KeyError:
        return []
    rows: list[dict] = []
    for unit_rows in units.values():
        rows.extend(unit_rows)
    rows.sort(key=lambda r: r.get("end", ""), reverse=True)
    return rows
