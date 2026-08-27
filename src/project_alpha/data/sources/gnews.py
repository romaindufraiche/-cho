"""GNews Free client (section 6: news generaliste, complement de couverture)."""

from __future__ import annotations

import requests

from project_alpha.config import SETTINGS
from project_alpha.data.sources.base import require_key

_BASE = "https://gnews.io/api/v4"


def search(query: str, lang: str = "en", max_results: int = 10) -> list[dict]:
    key = require_key(SETTINGS.gnews_api_key, "GNews", "GNEWS_API_KEY")
    resp = requests.get(
        f"{_BASE}/search",
        params={"q": query, "lang": lang, "max": max_results, "apikey": key},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("articles", [])
