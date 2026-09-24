"""Run and compare backtests for BTC/ETH across a set of strategies.

Example:
    python -m trading_bot.cli --symbols BTCUSDT ETHUSDT --interval 1d --start 2020-01-01
"""
import argparse
from pathlib import Path

import pandas as pd

from .backtest.engine import run_backtest
from .data.fetch import fetch_klines
from .reports.summary import build_comparison_table, plot_equity_curves
from .strategies import ALL_STRATEGIES

_PERIODS_PER_YEAR = {"1m": 365 * 24 * 60, "5m": 365 * 24 * 12, "15m": 365 * 24 * 4,
                      "1h": 365 * 24, "4h": 365 * 6, "1d": 365}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", default=["BTCUSD", "ETHUSD"])
    parser.add_argument("--interval", default="1d", choices=sorted(_PERIODS_PER_YEAR))
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument("--fee-bps", type=float, default=5.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--out-dir", default="reports_out")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    periods_per_year = _PERIODS_PER_YEAR[args.interval]

    for symbol in args.symbols:
        print(f"\n=== {symbol} ({args.interval}, {args.start} to {args.end or 'now'}) ===")
        df = fetch_klines(symbol, args.interval, args.start, args.end)
        print(f"{len(df)} bars fetched.")

        results = [
            run_backtest(df, strategy, args.initial_capital, args.fee_bps,
                         args.slippage_bps, periods_per_year)
            for strategy in ALL_STRATEGIES
        ]

        table = build_comparison_table(results)
        pd.set_option("display.float_format", lambda x: f"{x:0.4f}")
        print(table)
        table.to_csv(out_dir / f"{symbol}_{args.interval}_comparison.csv")

        plot_path = out_dir / f"{symbol}_{args.interval}_equity_curves.png"
        plot_equity_curves(results, str(plot_path), title=f"{symbol} ({args.interval})")
        print(f"Saved equity curve chart to {plot_path}")

        for r in results:
            r.trades.to_csv(out_dir / f"{symbol}_{args.interval}_{r.strategy_name}_trades.csv", index=False)


if __name__ == "__main__":
    main()
