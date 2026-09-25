"""Run the synthetic (Black-Scholes) options bracket backtest and a stop-loss/cost
sensitivity sweep, using already-fetched real underlying data and entry signals.

This CLI does NOT fetch its own inputs. Unlike cli.py/walk_forward_cli.py/
bracket_cli.py, it can't be self-contained: computing the real 4h/5m entry signals
and each trade's target contract requires live Robinhood MCP tool calls (see
trading_bot/options/synthetic_bracket.py's docstring), which only an agent session
can make, not a plain Python script. Point this at CSVs already produced that way:

    --underlying-4h   4h OHLC bars for the underlying (for the realized-vol estimate)
    --underlying-5m   5m OHLC bars for the underlying (for entry timing + price path)
    --entries         columns: fill_time, spy_price (or equivalent)
    --targets         columns: fill_time, strike, expiry

Example:
    python -m trading_bot.synthetic_options_cli \
        --underlying-4h data_cache_options/SPY_4h.csv \
        --underlying-5m data_cache_options/SPY_5m.csv \
        --entries data_cache_options/SPY_call_entries.csv \
        --targets data_cache_options/SPY_call_targets.csv
"""
import argparse
import dataclasses
from pathlib import Path

import pandas as pd

from .options.synthetic_bracket import realized_vol, run_synthetic_bracket


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--underlying-4h", required=True)
    parser.add_argument("--underlying-5m", required=True)
    parser.add_argument("--entries", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--take-profit-pct", type=float, default=0.10)
    parser.add_argument("--stop-loss-grid", type=float, nargs="+", default=[0.15, 0.20, 0.30, 0.50])
    parser.add_argument("--cost-rate-grid", type=float, nargs="+", default=[0.0, 0.005, 0.01, 0.03])
    parser.add_argument("--rate", type=float, default=0.045)
    parser.add_argument("--vol-window-days", type=int, default=20)
    parser.add_argument("--option-type", default="call", choices=["call", "put"])
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument("--out-dir", default="reports_out_synth_options")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    df_4h = pd.read_csv(args.underlying_4h, index_col=0, parse_dates=True)
    df_5m = pd.read_csv(args.underlying_5m, index_col=0, parse_dates=True)
    daily_close = df_4h["close"].resample("1D").last().dropna()
    vol = realized_vol(daily_close, window_days=args.vol_window_days)

    entries = pd.read_csv(args.entries, parse_dates=["fill_time"])
    targets = pd.read_csv(args.targets, parse_dates=["fill_time"])
    merged = entries.merge(targets[["fill_time", "expiry", "strike"]], on="fill_time")
    merged["strike"] = merged["strike"].astype(float)

    rows = []
    best = None
    for cost in args.cost_rate_grid:
        for stop in args.stop_loss_grid:
            trades, equity = run_synthetic_bracket(
                df_5m, merged, vol, take_profit_pct=args.take_profit_pct,
                stop_loss_pct=stop, rate=args.rate, cost_rate=cost,
                option_type=args.option_type, initial_capital=args.initial_capital,
            )
            trades_df = pd.DataFrame([dataclasses.asdict(t) for t in trades])
            win_rate = float((trades_df["pnl_pct"] > 0).mean()) if len(trades_df) else float("nan")
            total_return = equity.iloc[-1] / args.initial_capital - 1
            rows.append({
                "cost_rate": cost, "stop_loss_pct": stop, "num_trades": len(trades_df),
                "win_rate": win_rate, "final_capital": equity.iloc[-1], "total_return": total_return,
            })
            if best is None or (cost, stop) == (args.cost_rate_grid[0], args.stop_loss_grid[0]):
                best = (cost, stop, trades_df, equity)

    grid = pd.DataFrame(rows)
    pd.set_option("display.float_format", lambda x: f"{x:0.4f}")
    print(f"Take-profit fixed at {args.take_profit_pct:.0%}. Sensitivity grid (cost_rate is ONE-WAY, "
          f"i.e. charged twice per round trip):\n")
    print(grid.to_string(index=False))
    grid.to_csv(out_dir / "sensitivity_grid.csv", index=False)

    _, _, base_trades_df, base_equity = best
    base_trades_df.to_csv(out_dir / "base_case_trades.csv", index=False)
    base_equity.to_csv(out_dir / "base_case_equity.csv")
    print(f"\nSaved sensitivity grid and base-case ({args.cost_rate_grid[0]:.1%} cost, "
          f"{args.stop_loss_grid[0]:.0%} stop) trade log to {out_dir}/")


if __name__ == "__main__":
    main()
