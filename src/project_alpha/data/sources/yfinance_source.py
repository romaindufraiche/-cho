"""Prototype price/fundamentals source (section 6: "Prototype -> yfinance,
exploration et controle; pas source de verite production").

No API key required - this is what lets `project-alpha analyze` work out of
the box. Do not treat this as the production source of truth; SEC EDGAR /
Massive / Twelve Data are the intended production sources once configured.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import requests
import yfinance as yf

from project_alpha.data.models import Company, PriceBar, Region

# yfinance's default transport (curl_cffi, used for browser TLS
# impersonation) gets its connections reset by some corporate/CI egress
# proxies. A plain `requests` session works fine against Yahoo's endpoints
# and sidesteps that, so every yf.Ticker() call below shares one.
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "Mozilla/5.0"})


def fetch_price_history(ticker: str, period: str = "2y") -> list[PriceBar]:
    hist = yf.Ticker(ticker, session=_SESSION).history(period=period, auto_adjust=False)
    return _bars_from_history(ticker, hist)


def fetch_price_history_range(ticker: str, start: str, end: str | None = None) -> list[PriceBar]:
    """Fetches OHLCV between `start` and `end` (ISO dates, end defaults to
    today). Used by the historical backtest (section 9), which needs a full
    2015/2020-today window rather than a relative lookback period."""
    hist = yf.Ticker(ticker, session=_SESSION).history(start=start, end=end, auto_adjust=False)
    return _bars_from_history(ticker, hist)


def _bars_from_history(ticker: str, hist) -> list[PriceBar]:
    bars: list[PriceBar] = []
    for idx, row in hist.iterrows():
        bars.append(
            PriceBar(
                ticker=ticker,
                dt=idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10]),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
                provider="yfinance",
            )
        )
    return bars


def fetch_company_profile(ticker: str) -> Company:
    info = yf.Ticker(ticker, session=_SESSION).info or {}
    country = (info.get("country") or "").lower()
    region = Region.US if country in {"united states", "usa"} else Region.EUROPE
    return Company(
        ticker=ticker,
        name=info.get("shortName") or info.get("longName") or ticker,
        region=region,
        sector=info.get("sector"),
        industry=info.get("industry"),
        currency=info.get("currency", "USD"),
        exchange=info.get("exchange"),
        beta=info.get("beta"),
    )


def fetch_valuation_snapshot(ticker: str) -> dict:
    """Returns raw multiples from yfinance `info`; used as a stand-in for
    FMP/SEC-derived ValuationFeatures until those sources are wired in."""
    info = yf.Ticker(ticker, session=_SESSION).info or {}
    return {
        "pe_ratio": info.get("trailingPE"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "price_to_fcf": _price_to_fcf(info),
    }


def _price_to_fcf(info: dict) -> float | None:
    price = info.get("currentPrice")
    fcf = info.get("freeCashflow")
    shares = info.get("sharesOutstanding")
    if not price or not fcf or not shares or fcf <= 0:
        return None
    return price / (fcf / shares)


def fetch_fundamentals_snapshot(ticker: str) -> dict:
    info = yf.Ticker(ticker, session=_SESSION).info or {}
    return {
        "revenue_growth_yoy": info.get("revenueGrowth"),
        "gross_margin": info.get("grossMargins"),
        "operating_margin": info.get("operatingMargins"),
        "free_cash_flow": info.get("freeCashflow"),
        "net_debt_to_ebitda": _net_debt_to_ebitda(info),
        "roic": None,  # not exposed by yfinance; requires SEC/FMP data
    }


def _net_debt_to_ebitda(info: dict) -> float | None:
    total_debt = info.get("totalDebt")
    cash = info.get("totalCash")
    ebitda = info.get("ebitda")
    if total_debt is None or cash is None or not ebitda:
        return None
    return (total_debt - cash) / ebitda


def prices_to_dataframe(bars: list[PriceBar]) -> pd.DataFrame:
    df = pd.DataFrame([b.model_dump() for b in bars])
    if df.empty:
        return df
    df["dt"] = pd.to_datetime(df["dt"])
    return df.set_index("dt").sort_index()
