"""FRED / ALFRED client (section 6: macro US - taux, inflation, emploi, PIB)."""

from __future__ import annotations

import requests

from project_alpha.config import SETTINGS
from project_alpha.data.sources.base import SourceUnavailable, require_key

_BASE = "https://api.stlouisfed.org/fred"


def get_series(series_id: str, limit: int = 100) -> list[dict]:
    """Fetches recent observations for a FRED series (e.g. 'FEDFUNDS',
    'CPIAUCSL', 'UNRATE', 'GDP')."""
    key = require_key(SETTINGS.fred_api_key, "FRED", "FRED_API_KEY")
    resp = requests.get(
        f"{_BASE}/series/observations",
        params={
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("observations", [])


def latest_value(series_id: str) -> float | None:
    try:
        obs = get_series(series_id, limit=1)
    except SourceUnavailable:
        return None
    if not obs or obs[0].get("value") in (None, "."):
        return None
    return float(obs[0]["value"])
