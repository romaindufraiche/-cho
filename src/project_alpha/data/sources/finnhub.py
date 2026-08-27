"""Finnhub Free client (section 6: news, calendrier, fundamentals, market
data). Free tier: 60 calls/minute for personal use."""

from __future__ import annotations

import requests

from project_alpha.config import SETTINGS
from project_alpha.data.sources.base import require_key

_BASE = "https://finnhub.io/api/v1"


def _get(path: str, params: dict) -> dict | list:
    key = require_key(SETTINGS.finnhub_api_key, "Finnhub", "FINNHUB_API_KEY")
    resp = requests.get(f"{_BASE}/{path}", params={**params, "token": key}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def company_news(ticker: str, date_from: str, date_to: str) -> list[dict]:
    return _get("company-news", {"symbol": ticker, "from": date_from, "to": date_to})  # type: ignore[return-value]


def earnings_calendar(date_from: str, date_to: str, symbol: str | None = None) -> dict:
    params = {"from": date_from, "to": date_to}
    if symbol:
        params["symbol"] = symbol
    return _get("calendar/earnings", params)  # type: ignore[return-value]


def insider_transactions(ticker: str) -> dict:
    return _get("stock/insider-transactions", {"symbol": ticker})  # type: ignore[return-value]
