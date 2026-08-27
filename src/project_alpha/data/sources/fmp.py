"""Financial Modeling Prep Free client (section 6: fondamentaux secondaire,
comparaison/normalisation des etats financiers). Free tier: 250 calls/day."""

from __future__ import annotations

import requests

from project_alpha.config import SETTINGS
from project_alpha.data.sources.base import require_key

_BASE = "https://financialmodelingprep.com/api/v3"


def key_metrics(ticker: str, limit: int = 4) -> list[dict]:
    key = require_key(SETTINGS.fmp_api_key, "FMP", "FMP_API_KEY")
    resp = requests.get(
        f"{_BASE}/key-metrics/{ticker}",
        params={"limit": limit, "apikey": key},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def income_statement(ticker: str, limit: int = 4) -> list[dict]:
    key = require_key(SETTINGS.fmp_api_key, "FMP", "FMP_API_KEY")
    resp = requests.get(
        f"{_BASE}/income-statement/{ticker}",
        params={"limit": limit, "apikey": key},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
