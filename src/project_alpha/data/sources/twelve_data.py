"""Twelve Data Free client (section 6: prix Europe/multi-marches, cross-check
against the primary US price feed). Free tier: 800 credits/day, 8/minute."""

from __future__ import annotations

import requests

from project_alpha.config import SETTINGS
from project_alpha.data.sources.base import require_key

_BASE = "https://api.twelvedata.com"


def time_series(symbol: str, interval: str = "1day", outputsize: int = 100) -> dict:
    key = require_key(SETTINGS.twelve_data_api_key, "Twelve Data", "TWELVE_DATA_API_KEY")
    resp = requests.get(
        f"{_BASE}/time_series",
        params={"symbol": symbol, "interval": interval, "outputsize": outputsize, "apikey": key},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
