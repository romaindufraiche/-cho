"""Command-line entry point.

    project-alpha analyze --tickers AAPL,SIE.DE,MC.PA
    project-alpha analyze --tickers AAPL --save --out newsletter.md
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from project_alpha import __version__
from project_alpha.data.models import MarketRegime, Signal
from project_alpha.data.storage import Warehouse
from project_alpha.pipeline import analyze_ticker
from project_alpha.reporting.newsletter import render_newsletter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="project-alpha")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Run the daily analysis pipeline and print a newsletter")
    analyze.add_argument("--tickers", required=True, help="Comma-separated tickers, e.g. AAPL,SIE.DE")
    analyze.add_argument(
        "--regime",
        choices=[r.value for r in MarketRegime],
        default=MarketRegime.NEUTRAL.value,
        help="Market regime override (default: neutral)",
    )
    analyze.add_argument("--save", action="store_true", help="Persist prices and recommendations to the warehouse")
    analyze.add_argument("--out", help="Write the newsletter markdown to this file instead of stdout")

    return parser


def run_analyze(args: argparse.Namespace) -> int:
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    regime = MarketRegime(args.regime)
    warehouse = Warehouse() if args.save else None

    recommendations = []
    for ticker in tickers:
        try:
            rec = analyze_ticker(ticker, regime=regime)
        except Exception:
            logging.exception("failed to analyze %s", ticker)
            continue
        if rec is None:
            continue
        recommendations.append(rec)
        if warehouse is not None:
            warehouse.append_recommendation(rec)

    top_opportunities = [
        r for r in recommendations if r.signal in (Signal.BUY, Signal.BUY_ON_DIP)
    ]
    not_yet_buyable = [r for r in recommendations if r.signal == Signal.BUY_ON_DIP]
    traps = [
        r
        for r in recommendations
        if r.signal in (Signal.WATCH, Signal.NO_TRADE) and r.score.quality_score >= 70
    ]

    newsletter = render_newsletter(
        as_of=date.today(),
        regime=regime,
        top_opportunities=top_opportunities,
        traps=traps,
        not_yet_buyable=not_yet_buyable,
        positions_to_manage=[],
        track_record=None,
    )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(newsletter)
    else:
        print(newsletter)

    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "analyze":
        return run_analyze(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
