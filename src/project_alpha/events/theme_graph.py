"""Theme graph (section 3): evenement -> theme -> chaine de valeur ->
entreprises exposees.

V0 implementation: a static, hand-maintained mapping loaded from a small
dict (extend or externalize to YAML as the universe grows). This is
intentionally simple - discovering exposure automatically from event text
is V3 (LLM research agent) scope.
"""

from __future__ import annotations

from project_alpha.data.models import CompanyExposure, Event

# theme -> [(ticker, exposure_weight, rationale)]
THEME_EXPOSURE: dict[str, list[tuple[str, float, str]]] = {
    "energy_transition": [
        ("ENR.DE", 0.9, "Grid/turbine equipment exposure"),
    ],
    "ai_infrastructure": [
        ("NVDA", 0.9, "AI accelerator supplier"),
        ("MSFT", 0.5, "Hyperscaler AI capex"),
    ],
}


def exposures_for_event(event: Event) -> list[CompanyExposure]:
    theme = event.theme
    if theme is None or theme not in THEME_EXPOSURE:
        return []
    return [
        CompanyExposure(event_id=event.id, ticker=ticker, exposure_weight=weight, rationale=rationale)
        for ticker, weight, rationale in THEME_EXPOSURE[theme]
    ]
