"""Command-line entry point.

    project-alpha analyze --tickers AAPL,SIE.DE,MC.PA
    project-alpha analyze --tickers AAPL --save --out newsletter.md
    project-alpha backtest --tickers AAPL,MSFT,SIE.DE --start 2020-01-01 --out backtest.md
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from project_alpha import __version__
from project_alpha.backtest.historical import fetch_and_run
from project_alpha.data.models import MarketRegime, Signal
from project_alpha.data.storage import Warehouse
from project_alpha.pipeline import analyze_ticker
from project_alpha.reporting.backtest_report import render_backtest_report
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
    analyze.add_argument(
        "--capital", type=float, default=500.0, help="Portfolio value in EUR/USD for position sizing (default: 500)"
    )

    backtest = sub.add_parser(
        "backtest", help="Replay the technical/risk signal engine over real historical prices"
    )
    backtest.add_argument("--tickers", required=True, help="Comma-separated tickers, e.g. AAPL,MSFT,SIE.DE")
    backtest.add_argument("--start", default="2020-01-01", help="Start date, ISO format (default: 2020-01-01)")
    backtest.add_argument("--end", default=None, help="End date, ISO format (default: today)")
    backtest.add_argument(
        "--benchmark", default="^GSPC", help="Benchmark ticker for alpha, e.g. ^GSPC, ^STOXX, ^FCHI (empty to skip)"
    )
    backtest.add_argument("--out", help="Write the backtest report markdown to this file instead of stdout")
    backtest.add_argument(
        "--capital", type=float, default=500.0, help="Starting capital in EUR/USD for the equity curve (default: 500)"
    )
    backtest.add_argument(
        "--trained",
        dest="trained",
        action="store_true",
        default=False,
        help=(
            "Use the ML-fitted weights from `train-weights` instead of the hand-picked "
            "heuristic: the full Technical+Risk+Fundamental+Valuation model for tickers with "
            "SEC filings (ml/full_weights.json, if trained with --extended), falling back to "
            "Technical+Risk (ml/technical_risk_weights.json) otherwise - e.g. every European "
            "ticker. Opt-in, not the default: out-of-sample validation on the base model shows "
            "only a weak edge (AUC ~0.55) - treat results from this flag as experimental."
        ),
    )
    backtest.add_argument(
        "--no-trained",
        dest="trained",
        action="store_false",
        help="Use the original hand-picked Technical(15)/Risk(10) heuristic (default)",
    )

    train_weights = sub.add_parser(
        "train-weights",
        help="Fit the Technical/Risk entry weights on real history (requires the 'ml' extra)",
    )
    train_weights.add_argument(
        "--tickers", help="Comma-separated training universe (default: built-in US+EU large-cap list)"
    )
    train_weights.add_argument("--start", default="2012-01-01", help="Start date, ISO format (default: 2012-01-01)")
    train_weights.add_argument("--end", default=None, help="End date, ISO format (default: today)")
    train_weights.add_argument(
        "--cutoff",
        default="2023-01-01",
        help="Chronological train/test split date, ISO format (default: 2023-01-01)",
    )
    train_weights.add_argument("--out", help="Where to save the trained weights JSON (default: ml/technical_risk_weights.json)")
    train_weights.add_argument(
        "--extended",
        action="store_true",
        help=(
            "Also fetch SEC EDGAR point-in-time fundamentals and fit a second, "
            "Technical+Risk+Fundamental+Valuation model (US filers only - see "
            "data/sources/sec_edgar_fundamentals.py); saved to ml/full_weights.json"
        ),
    )

    return parser


def run_analyze(args: argparse.Namespace) -> int:
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    regime = MarketRegime(args.regime)
    warehouse = Warehouse() if args.save else None

    recommendations = []
    for ticker in tickers:
        try:
            rec = analyze_ticker(ticker, regime=regime, portfolio_value=args.capital)
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


def run_backtest(args: argparse.Namespace) -> int:
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]

    score_fn = None
    if args.trained:
        from project_alpha.data.sources.sec_edgar_fundamentals import point_in_time_fundamentals
        from project_alpha.ml.scoring import EXTENDED_WEIGHTS_PATH, WeightsNotFound, load_weights, make_hybrid_score_fn

        try:
            base_weights = load_weights()
        except WeightsNotFound as exc:
            logging.warning("%s Falling back to the hand-picked heuristic.", exc)
            base_weights = None

        if base_weights is not None:
            full_weights = None
            try:
                full_weights = load_weights(str(EXTENDED_WEIGHTS_PATH))
            except WeightsNotFound:
                pass  # no full model trained yet - hybrid falls back to base_weights for every ticker

            fundamentals_by_ticker = {}
            if full_weights is not None:
                for ticker in tickers:
                    df = point_in_time_fundamentals(ticker)
                    if not df.empty:
                        fundamentals_by_ticker[ticker] = df

            score_fn = make_hybrid_score_fn(base_weights, full_weights, fundamentals_by_ticker)

    result = fetch_and_run(
        tickers, start=args.start, end=args.end, benchmark_ticker=args.benchmark or None,
        starting_capital=args.capital, score_fn=score_fn,
        entry_model="ml-trained (experimental)" if score_fn is not None else "heuristic",
    )
    report = render_backtest_report(result)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
    else:
        print(report)

    return 0


def run_train_weights(args: argparse.Namespace) -> int:
    from pathlib import Path

    from project_alpha.ml.dataset import EXTENDED_FEATURE_NAMES, build_dataset
    from project_alpha.ml.train import (
        DEFAULT_WEIGHTS_PATH,
        EXTENDED_WEIGHTS_PATH,
        TRAINING_UNIVERSE,
        fetch_training_fundamentals,
        fetch_training_price_data,
        save_weights,
        train_and_evaluate,
    )

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()] if args.tickers else TRAINING_UNIVERSE
    price_data = fetch_training_price_data(tickers, args.start, args.end)

    fundamentals_by_ticker = fetch_training_fundamentals(tickers) if args.extended else None
    dataset = build_dataset(price_data, fundamentals_by_ticker=fundamentals_by_ticker)

    base_result = train_and_evaluate(dataset, args.cutoff)
    base_path = Path(args.out) if args.out else DEFAULT_WEIGHTS_PATH
    save_weights(base_result, base_path)
    print("=== Technical + Risk (all tickers) ===")
    print(json.dumps(base_result["metrics"], indent=2))
    print(json.dumps(base_result["normalized_weights_pct"], indent=2))
    print(f"Weights saved to {base_path}")

    if args.extended:
        try:
            full_result = train_and_evaluate(dataset, args.cutoff, feature_names=EXTENDED_FEATURE_NAMES)
        except ValueError as exc:
            print(f"Skipped the extended model: {exc}")
        else:
            save_weights(full_result, EXTENDED_WEIGHTS_PATH)
            print("=== Technical + Risk + Fundamental + Valuation (US filers only) ===")
            print(json.dumps(full_result["metrics"], indent=2))
            print(json.dumps(full_result["normalized_weights_pct"], indent=2))
            print(f"Weights saved to {EXTENDED_WEIGHTS_PATH}")

    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "analyze":
        return run_analyze(args)
    if args.command == "backtest":
        return run_backtest(args)
    if args.command == "train-weights":
        return run_train_weights(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
