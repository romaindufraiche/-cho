"""Markdown report for a `UniverseBacktestResult` (section 9)."""

from __future__ import annotations

from project_alpha.backtest.historical import UniverseBacktestResult
from project_alpha.backtest.metrics import signal_precision, target_hit_rate

CAVEAT = (
    "Ce backtest ne fait varier que les modules Technical/Momentum et Risk "
    "(25/100 du poids total) ; Catalyst, Fundamental, Expectations, "
    "Valuation et Smart Money restent neutres (50/100) car leurs donnees "
    "point-in-time ne sont pas disponibles via la source gratuite utilisee "
    "ici. Voir backtest/historical.py pour le detail."
)


def render_backtest_report(result: UniverseBacktestResult) -> str:
    m = result.metrics
    lines = [
        f"# Backtest {m.start.isoformat()} -> {m.end.isoformat()}",
        "",
    ]
    if not result.equity_curve.empty:
        start_capital = result.equity_curve.iloc[0]
        end_capital = result.equity_curve.iloc[-1]
        lines.append(
            f"- Capital: {start_capital:.2f} -> {end_capital:.2f} "
            f"({end_capital - start_capital:+.2f})"
        )
    lines += [
        f"- Trades: {m.n_trades}",
        f"- CAGR: {m.cagr}",
    ]
    if m.benchmark:
        lines.append(f"- Alpha vs {m.benchmark}: {m.alpha_vs_benchmark}")
    lines += [
        f"- Precision du signal (win rate): {signal_precision(result.trades)}",
        f"- Taux d'objectif atteint: {target_hit_rate(result.trades)}",
        f"- Avg win / avg loss: {m.avg_win_pct} / {m.avg_loss_pct}",
        f"- Expectancy: {m.expectancy}",
        f"- Profit factor: {m.profit_factor}",
        f"- Max drawdown: {m.max_drawdown}",
        f"- Volatilite (annualisee): {m.volatility}",
        f"- Sharpe / Sortino: {m.sharpe} / {m.sortino}",
        "",
        "## Trades par ticker",
    ]
    for ticker, n in sorted(result.trades_per_ticker.items()):
        lines.append(f"- {ticker}: {n}")
    lines += ["", "---", CAVEAT]
    return "\n".join(lines)
