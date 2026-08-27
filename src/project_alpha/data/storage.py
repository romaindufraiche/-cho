"""Local, zero-cost storage layer standing in for the target BigQuery
warehouse (section 7). Table/file names mirror the target BigQuery table
names so a later migration is a backend swap, not a schema redesign.

- Prices go to SQLite (fast range queries for backtesting).
- Recommendations/theses/positions are append-only JSONL logs: this makes
  "no retroactive modification" (section 15) a property of the storage
  format itself, not just a convention.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from project_alpha.config import SETTINGS
from project_alpha.data.models import PriceBar, Recommendation, Thesis

_PRICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    dt TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    provider TEXT,
    PRIMARY KEY (ticker, dt, provider)
)
"""


class Warehouse:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or SETTINGS.data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "project_alpha.db"
        self.recommendations_path = self.data_dir / "recommendations.jsonl"
        self.theses_path = self.data_dir / "theses.jsonl"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_PRICES_SCHEMA)

    # -- Prices --------------------------------------------------------
    def upsert_prices(self, bars: Iterable[PriceBar]) -> int:
        rows = [
            (b.ticker, b.dt.isoformat(), b.open, b.high, b.low, b.close, b.volume, b.provider)
            for b in bars
        ]
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO prices
                   (ticker, dt, open, high, low, close, volume, provider)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        return len(rows)

    def get_prices(self, ticker: str, provider: str = "yfinance") -> pd.DataFrame:
        with self._connect() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM prices WHERE ticker = ? AND provider = ? ORDER BY dt",
                conn,
                params=(ticker, provider),
                parse_dates=["dt"],
            )
        return df.set_index("dt") if not df.empty else df

    # -- Append-only logs ------------------------------------------------
    def append_recommendation(self, rec: Recommendation) -> None:
        _append_jsonl(self.recommendations_path, rec.model_dump(mode="json"))

    def read_recommendations(self) -> list[dict]:
        return _read_jsonl(self.recommendations_path)

    def append_thesis_event(self, thesis: Thesis) -> None:
        _append_jsonl(self.theses_path, thesis.model_dump(mode="json"))

    def read_theses(self) -> list[dict]:
        return _read_jsonl(self.theses_path)


def _append_jsonl(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
