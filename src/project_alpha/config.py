"""Centralized configuration loaded from environment / .env.

Following the "cout nul" (zero cost) principle from the cahier des charges,
every external data source is optional: the system must degrade gracefully
(skip a module, mark a feature "unavailable") rather than fail hard when a
key is missing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _data_dir() -> Path:
    raw = os.getenv("PROJECT_ALPHA_DATA_DIR", "./data/warehouse")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=_data_dir)

    sec_edgar_user_agent: str = os.getenv(
        "SEC_EDGAR_USER_AGENT", "Project Alpha personal-use unset@example.com"
    )
    fred_api_key: str | None = os.getenv("FRED_API_KEY") or None
    massive_api_key: str | None = os.getenv("MASSIVE_API_KEY") or None
    twelve_data_api_key: str | None = os.getenv("TWELVE_DATA_API_KEY") or None
    finnhub_api_key: str | None = os.getenv("FINNHUB_API_KEY") or None
    gnews_api_key: str | None = os.getenv("GNEWS_API_KEY") or None
    fmp_api_key: str | None = os.getenv("FMP_API_KEY") or None
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None

    # Versioning stamped on every recommendation (section 7: "Versionnage").
    data_version: str = "v0.1"
    scoring_version: str = "v0.1"
    model_version: str = "v0.1"
    prompt_version: str = "v0.1"


SETTINGS = Settings()
