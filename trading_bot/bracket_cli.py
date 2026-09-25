"""Backtest a dip-buy strategy with a fixed take-profit target, stop-loss, and max
holding period -- "buy after a pullback, sell at +X%" -- against buy-and-hold over
the same period.

Example:
    python -m trading_bot.bracket_cli --symbols BTCUSD ETHUSD --take-profit-pct 0.15
"""
import argparse
from pathlib import Path

import pandas as pd

from .backtest.bracket_engine import run_bracket_backtest
from .backtest.engine import run_backtest
from .data.fetch import fetch_klines
from .strategies.buy_and_hold import BuyAndHold
from .strategies.dip_buy_bracket import dip_buy_entry_signal

_PERIODS_PER_YEAR = {"1h": 365 * 24, "4h": 365 * 6, "1d": 365}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", default=["BTCUSD", "ETHUSD"])
    parser.add_argument("--interval", default="1d", choices=sorted(_PERIODS_PER_YEAR))
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--lookback-days", type=int, default=20,
                         help="trailing window used to define the recent high for the dip-buy trigger")
    parser.add_argument("--pullback-pct", type=float, default=0.10,
                         help="buy when price is down at least this much from the trailing high")
    parser.add_argument("--take-profit-pct", type=float, default=0.15,
                         help="sell target, e.g. 0.15 = 15%% (your ask was 10-20%%; default is the midpoint)")
    parser.add_argument("--stop-loss-pct", type=float, default=0.10,
                         help="sell if price falls this much from entry; pass a negative number to disable (NOT recommended: unbounded downside)")
    parser.add_argument("--max-holding-days", type=int, default=90,
                         help="force an exit at the close after this many days if neither target nor stop has hit; pass 0 to disable (NOT recommended: a trade can then sit open indefinitely)")
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument("--fee-bps", type=float, default=5.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--out-dir", default="reports_out_bracket")
    args = parser.parse_args()

    stop_loss_pct = None if args.stop_loss_pct < 0 else args.stop_loss_pct
    max_holding_days = None if args.max_holding_days == 0 else args.max_holding_days

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    periods_per_year = _PERIODS_PER_YEAR[args.interval]

    for symbol in args.symbols:
        print(f"\n=== {symbol} dip-buy bracket "
              f"(pullback>={args.pullback_pct:.0%} of {args.lookback_days}d high, "
              f"target=+{args.take_profit_pct:.0%}, stop={'off' if stop_loss_pct is None else f'-{stop_loss_pct:.0%}'}, "
              f"max_hold={'off' if max_holding_days is None else f'{max_holding_days}d'}) ===")
        df = fetch_klines(symbol, args.interval, args.start, args.end)

        entry_signal = dip_buy_entry_signal(df, args.lookback_days, args.pullback_pct)
        bracket = run_bracket_backtest(
            df, entry_signal, args.take_profit_pct, stop_loss_pct, max_holding_days,
            args.initial_capital, args.fee_bps, args.slippage_bps, periods_per_year,
            strategy_name=f"dip_buy_{args.pullback_pct:.0%}_tp{args.take_profit_pct:.0%}")
        bh = run_backtest(df, BuyAndHold(), args.initial_capital, args.fee_bps,
                           args.slippage_bps, periods_per_year)

        table = pd.DataFrame({bracket.strategy_name: bracket.metrics, "buy_and_hold": bh.metrics}).T
        pd.set_option("display.float_format", lambda x: f"{x:0.4f}")
        print(table)
        table.to_csv(out_dir / f"{symbol}_{args.interval}_bracket_comparison.csv")
        bracket.trades.to_csv(out_dir / f"{symbol}_{args.interval}_bracket_trades.csv", index=False)

        if len(bracket.trades):
            print(f"\n{len(bracket.trades)} trades. Exit reasons:")
            print(bracket.trades["exit_reason"].value_counts().to_string())
        else:
            print("\nNo trades triggered over this period with these parameters.")

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(bh.equity_curve.index, bh.equity_curve.values / bh.equity_curve.iloc[0], label="buy_and_hold")
        ax.plot(bracket.equity_curve.index, bracket.equity_curve.values / bracket.equity_curve.iloc[0],
                label=bracket.strategy_name)
        ax.set_yscale("log")
        ax.set_ylabel("Equity (normalized, log scale)")
        ax.set_title(f"{symbol} dip-buy bracket vs buy-and-hold")
        ax.legend()
        ax.grid(True, which="both", alpha=0.3)
        plot_path = out_dir / f"{symbol}_{args.interval}_bracket_equity.png"
        fig.savefig(plot_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved chart to {plot_path}")


if __name__ == "__main__":
    main()
