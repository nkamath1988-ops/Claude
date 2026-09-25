"""Walk-forward validation: re-select each strategy family's parameters every
`--test-days`, using only the prior `--train-days`, and chain the resulting
out-of-sample segments into one equity curve per family. See
trading_bot/backtest/walk_forward.py for why this is the real test of whether a
strategy has edge, as opposed to a single fixed-parameter backtest.

Example:
    python -m trading_bot.walk_forward_cli --symbols BTCUSD ETHUSD --start 2020-01-01
"""
import argparse
from pathlib import Path

import pandas as pd

from .backtest.engine import run_backtest
from .backtest.walk_forward import run_walk_forward
from .data.fetch import fetch_klines
from .strategies.buy_and_hold import BuyAndHold
from .strategies.donchian_breakout import DonchianBreakout
from .strategies.rsi_reversion import RsiMeanReversion
from .strategies.sma_crossover import SmaCrossover

_PERIODS_PER_YEAR = {"1h": 365 * 24, "4h": 365 * 6, "1d": 365}

FAMILIES = {
    "sma_crossover": (SmaCrossover, {"fast": [5, 10, 20], "slow": [30, 50, 100, 150]}),
    "rsi_reversion": (RsiMeanReversion, {"period": [7, 14, 21], "oversold": [20, 30, 35], "overbought": [55, 60, 70]}),
    "donchian_breakout": (DonchianBreakout, {"lookback": [10, 20, 40, 60]}),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", default=["BTCUSD", "ETHUSD"])
    parser.add_argument("--interval", default="1d", choices=sorted(_PERIODS_PER_YEAR))
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--train-days", type=int, default=365)
    parser.add_argument("--test-days", type=int, default=90)
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument("--fee-bps", type=float, default=5.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--out-dir", default="reports_out_wf")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    periods_per_year = _PERIODS_PER_YEAR[args.interval]

    for symbol in args.symbols:
        print(f"\n=== {symbol} walk-forward (train={args.train_days}d, test={args.test_days}d) ===")
        df = fetch_klines(symbol, args.interval, args.start, args.end)

        wf_results = {}
        for family, (cls, grid) in FAMILIES.items():
            wf = run_walk_forward(df, family, cls, grid, args.train_days, args.test_days,
                                   args.initial_capital, args.fee_bps, args.slippage_bps, periods_per_year)
            wf_results[family] = wf
            wf.segment_log.to_csv(out_dir / f"{symbol}_{family}_segments.csv", index=False)

        # Buy-and-hold benchmark over the exact same out-of-sample span, for a fair comparison
        span_start = min(r.equity_curve.index.min() for r in wf_results.values())
        span_end = max(r.equity_curve.index.max() for r in wf_results.values())
        bh_result = run_backtest(df.loc[span_start:span_end], BuyAndHold(), args.initial_capital,
                                  args.fee_bps, args.slippage_bps, periods_per_year)

        rows = {"buy_and_hold (same span)": bh_result.metrics}
        rows.update({f"{name}_walk_forward": r.metrics for name, r in wf_results.items()})
        table = pd.DataFrame(rows).T[[
            "total_return", "cagr", "annualized_volatility", "sharpe_ratio",
            "max_drawdown", "num_trades", "win_rate", "exposure",
        ]]
        pd.set_option("display.float_format", lambda x: f"{x:0.4f}")
        print(table)
        table.to_csv(out_dir / f"{symbol}_walk_forward_comparison.csv")

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(bh_result.equity_curve.index, bh_result.equity_curve.values / bh_result.equity_curve.iloc[0],
                label="buy_and_hold (same span)")
        for name, r in wf_results.items():
            ax.plot(r.equity_curve.index, r.equity_curve.values / r.equity_curve.iloc[0], label=f"{name}_walk_forward")
        ax.set_yscale("log")
        ax.set_ylabel("Equity (normalized, log scale)")
        ax.set_title(f"{symbol} walk-forward out-of-sample")
        ax.legend()
        ax.grid(True, which="both", alpha=0.3)
        fig.savefig(out_dir / f"{symbol}_walk_forward_equity.png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved chart to {out_dir / f'{symbol}_walk_forward_equity.png'}")


if __name__ == "__main__":
    main()
