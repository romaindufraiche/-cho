"""Newsletter / sortie utilisateur (section 11): the weekly human-facing
output. Renders to Markdown so it can be emailed, saved, or piped into a
static site without any extra templating dependency.
"""

from __future__ import annotations

from datetime import date

from project_alpha.data.models import (
    BacktestMetrics,
    MarketRegime,
    Position,
    Recommendation,
    Signal,
)
from project_alpha.signals.pricing import reward_risk_ratio

DISCLAIMER = (
    "Document a usage personnel. Les elements ci-dessus sont generes automatiquement "
    "a partir de donnees et de regles deterministes ; ils ne constituent pas un conseil "
    "en investissement."
)


def render_newsletter(
    as_of: date,
    regime: MarketRegime,
    top_opportunities: list[Recommendation],
    traps: list[Recommendation],
    not_yet_buyable: list[Recommendation],
    positions_to_manage: list[tuple[Position, Signal, str]],
    track_record: BacktestMetrics | None,
) -> str:
    lines: list[str] = []
    lines.append(f"# Project Alpha - Revue du {as_of.isoformat()}")
    lines.append("")
    lines.append(f"**Market Regime**: {regime.value.upper().replace('_', '-')}")
    lines.append("")

    lines.append("## Top Opportunities")
    if not top_opportunities:
        lines.append("_Aucune idee ne franchit le seuil cette semaine - NO TRADE est un resultat valide._")
    for rec in top_opportunities[:4]:
        lines.append(_render_opportunity(rec))
    lines.append("")

    lines.append("## Le piege de la semaine")
    lines.append("_Excellente entreprise, mauvais prix ou attentes deja integrees._")
    if not traps:
        lines.append("_Rien a signaler._")
    for rec in traps:
        lines.append(f"- **{rec.ticker}** — {rec.thesis_summary or 'voir score detaille'}")
    lines.append("")

    lines.append("## Pas encore achetable")
    lines.append("_These interessante, prix trop eleve pour l'instant._")
    if not not_yet_buyable:
        lines.append("_Rien a signaler._")
    for rec in not_yet_buyable:
        lines.append(f"- **{rec.ticker}** — {rec.why_now or ''}")
    lines.append("")

    lines.append("## Positions a gerer")
    if not positions_to_manage:
        lines.append("_Aucune position ouverte._")
    for position, signal, reason in positions_to_manage:
        lines.append(f"- **{position.ticker}**: {signal.value} ({reason})")
    lines.append("")

    lines.append("## Track record")
    if track_record is None:
        lines.append("_Pas encore de backtest/paper trading enregistre._")
    else:
        lines.append(_render_track_record(track_record))
    lines.append("")

    lines.append("---")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def _render_opportunity(rec: Recommendation) -> str:
    zone = rec.price_zone
    rr = reward_risk_ratio(rec.current_price, zone) if rec.current_price and zone else None
    header = f"### {rec.signal.value} — {rec.ticker} (score {rec.score.weighted_total_score}/100)"
    parts = [header]
    if zone:
        parts.append(
            f"- Cours: {rec.current_price} | Zone d'achat: {zone.buy_zone_low}-{zone.buy_zone_high} "
            f"| Stop: {zone.stop} | Target base: {zone.target_base} | Target bull: {zone.target_bull}"
        )
        if rr is not None:
            parts.append(f"- Ratio rendement/risque: {rr}")
    if rec.position_sizing:
        ps = rec.position_sizing
        parts.append(
            f"- Taille suggeree: {ps.shares} titres (~{ps.position_value} EUR) "
            f"| Risque: {ps.risk_amount} EUR ({ps.risk_pct * 100:.2f}% du capital)"
        )
    parts.append(
        f"- Quality/Opportunity/Price: {rec.score.quality_score}/{rec.score.opportunity_score}/{rec.score.price_score}"
    )
    if rec.why_now:
        parts.append(f"- Pourquoi maintenant ? {rec.why_now}")
    if rec.invalidation:
        parts.append(f"- Invalidation: {rec.invalidation}")
    return "\n".join(parts)


def _render_track_record(metrics: BacktestMetrics) -> str:
    bench = f" (vs {metrics.benchmark})" if metrics.benchmark else ""
    alpha = f", alpha {metrics.alpha_vs_benchmark}" if metrics.alpha_vs_benchmark is not None else ""
    return (
        f"CAGR {metrics.cagr}{alpha}{bench} | Win rate {metrics.win_rate} | "
        f"Max drawdown {metrics.max_drawdown} | Sharpe {metrics.sharpe} | "
        f"Trades: {metrics.n_trades}"
    )
