"""ECB Data Portal (SDW) client (section 6: macro Europe - taux BCE,
inflation, credit, FX). Open REST API, no key required."""

from __future__ import annotations

import requests

_BASE = "https://data-api.ecb.europa.eu/service/data"


def get_series(flow_ref: str, series_key: str, last_n: int = 20) -> list[dict]:
    """Fetches an ECB SDW series, e.g. flow_ref='FM', series_key for the
    deposit facility rate, returned as JSON via the SDMX-JSON format."""
    url = f"{_BASE}/{flow_ref}/{series_key}"
    resp = requests.get(
        url,
        params={"lastNObservations": last_n, "format": "jsondata"},
        headers={"Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
