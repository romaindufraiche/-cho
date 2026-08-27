"""Minimal event detector (section 3, V0 scope).

A deterministic keyword classifier over headlines - deliberately simple.
The cahier des charges' full vision (LLM-assisted event/theme extraction,
section 8) is V3 scope; this gives the pipeline a working, zero-cost
Event -> Theme -> Company seed today, with a clean interface the V3 LLM
research agent can later replace or augment without touching downstream
scoring/signal code.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from project_alpha.data.models import Event, EventCategory, SourceRef

_KEYWORDS: dict[EventCategory, list[str]] = {
    EventCategory.EARNINGS: ["earnings", "quarterly results", "q1", "q2", "q3", "q4", "eps"],
    EventCategory.GUIDANCE: ["guidance", "outlook raised", "outlook cut", "forecast"],
    EventCategory.CONTRACT: ["contract awarded", "wins contract", "order from", "deal with"],
    EventCategory.CAPEX: ["capex", "capital expenditure", "new plant", "factory investment"],
    EventCategory.MNA: ["acquisition", "merger", "acquires", "to buy", "takeover"],
    EventCategory.REGULATION: ["regulator", "antitrust", "fda approval", "sec investigation"],
    EventCategory.MACRO: ["interest rate", "inflation", "central bank", "gdp"],
    EventCategory.GEOPOLITICAL: ["sanctions", "tariff", "war", "export ban"],
    EventCategory.SUPPLY_SHOCK: ["shortage", "supply chain", "chip shortage"],
    EventCategory.SECTOR_DISRUPTION: ["disrupt", "breakthrough", "new technology"],
}


def classify_headline(headline: str) -> EventCategory | None:
    lower = headline.lower()
    for category, keywords in _KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return None


def detect_events(headlines: list[dict]) -> list[Event]:
    """`headlines` items look like {"headline": str, "url": str, "source":
    str, "published_at": datetime}. Returns one Event per classified
    headline; unclassified headlines are dropped (not every news item is a
    tradeable event)."""
    events: list[Event] = []
    for item in headlines:
        category = classify_headline(item["headline"])
        if category is None:
            continue
        events.append(
            Event(
                id=str(uuid.uuid4()),
                category=category,
                headline=item["headline"],
                detected_at=item.get("published_at") or datetime.utcnow(),
                sources=[
                    SourceRef(
                        source=item.get("source", "unknown"),
                        url=item.get("url"),
                        published_at=item.get("published_at"),
                    )
                ],
            )
        )
    return events
