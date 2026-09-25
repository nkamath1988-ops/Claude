"""Advance (or bootstrap) a paper-trading state by one day against real, current
market data. Places no orders -- logs what the walk-forward-selected strategy
would have done. Safe to run more than once on the same day (idempotent).

Example (run daily, e.g. via a scheduled trigger):
    python -m trading_bot.paper_trading_cli --symbol ETHUSD --state-file paper_trading_state/ETHUSD_sma_crossover.json
"""
import argparse

from .data.fetch import fetch_klines
from .paper_trading.engine import advance, load_state, new_state, save_state
from .strategies.sma_crossover import SmaCrossover

DEFAULT_GRID = {"fast": [5, 10, 20], "slow": [30, 50, 100, 150]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="ETHUSD")
    parser.add_argument("--start", default="2020-01-01", help="history start; must match the validated backtest's start date")
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--train-days", type=int, default=365)
    parser.add_argument("--test-days", type=int, default=90)
    parser.add_argument("--fee-bps", type=float, default=5.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    args = parser.parse_args()

    df = fetch_klines(args.symbol, "1d", args.start)

    state = load_state(args.state_file)
    if state is None:
        state = new_state(args.symbol, args.fee_bps, args.slippage_bps,
                           args.train_days, args.test_days, args.initial_capital)
        print(f"No existing state at {args.state_file} -- bootstrapping new paper-trading run.")

    was_new_day = state.last_date != str(df.index[-1].date())
    state = advance(state, df, SmaCrossover, DEFAULT_GRID)
    save_state(state, args.state_file)

    print(f"\n=== {args.symbol} paper trading, as of {state.last_date} ===")
    print(f"Current params in effect: {state.current_params}")
    print(f"Position: {'LONG' if state.position == 1 else 'FLAT'}")
    print(f"Paper equity: ${state.equity:,.2f} (started at ${args.initial_capital:,.2f})")
    print(f"Total paper trades logged: {len(state.trade_log)}")
    if not was_new_day:
        print("(No new data since last run -- state unchanged, this was a no-op check.)")
    if state.trade_log:
        print(f"Most recent trade: {state.trade_log[-1]}")


if __name__ == "__main__":
    main()
