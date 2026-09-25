"""Bracket-order backtest: enter on a trigger, exit at a fixed take-profit target, a
stop-loss, or a max holding period -- whichever is hit first. This is a different
execution model from engine.py's signal-based strategies (which hold a position for
however long an indicator says to). "Sell at +15%" is literally a limit order with a
price target, not an indicator condition, so exits here are checked against each
day's HIGH/LOW (was the target/stop price touched intrabar), not just the close --
the realistic way a real limit/stop order actually fills, and something engine.py's
strategies never needed because they don't have a price target.

Only one position open at a time (matches the rest of this repo: long-only, no
leverage, full notional per trade). Entry is decided from data through day t's close
(no lookahead) and filled at day t+1's OPEN -- a different fill convention from
engine.py's "previous close" simplification, used here because a target order gives
a concrete reason to use the real next-bar open instead.

If both the take-profit and stop-loss are touched on the same day, the stop is
assumed to have hit first -- a deliberately pessimistic tie-break, not something
inferable from daily bars alone.

WARNING baked into the interface, not just the docstring: `stop_loss_pct=None`
disables the stop and leaves a losing trade's downside unbounded except by
`max_holding_bars` eventually forcing an exit at whatever the close happens to be
then -- a real risk if a trade opens right before a large, sustained decline.

`max_holding_bars` counts BARS, not calendar time -- 90 means 90 daily bars (90
days) when `df` is daily, but 90 five-minute bars (7.5 hours) if `df` is 5-minute.
Callers on a non-daily timeframe must convert their intended calendar duration to a
bar count themselves (e.g. "3 days" on 5m bars = 3 * 24 * 12 = 864).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .metrics import compute_metrics


@dataclass
class BracketResult:
    strategy_name: str
    equity_curve: pd.Series
    trades: pd.DataFrame
    metrics: dict


def run_bracket_backtest(df: pd.DataFrame, entry_signal: pd.Series, take_profit_pct: float,
                          stop_loss_pct: float | None = 0.10, max_holding_bars: int | None = 90,
                          initial_capital: float = 10_000.0, fee_bps: float = 5.0,
                          slippage_bps: float = 10.0, periods_per_year: float = 365.0,
                          strategy_name: str = "dip_buy_bracket") -> BracketResult:
    cost_rate = (fee_bps + slippage_bps) / 10_000.0
    n = len(df)
    opens, highs, lows, closes = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    entry_ok = entry_signal.to_numpy()

    equity_vals = [0.0] * n
    position_vals = [0] * n
    trades = []

    capital = initial_capital
    day = 0
    while day < n:
        equity_vals[day] = capital
        if entry_ok[day] and day + 1 < n:
            entry_idx = day + 1
            entry_price = opens[entry_idx]
            target_price = entry_price * (1 + take_profit_pct)
            stop_price = entry_price * (1 - stop_loss_pct) if stop_loss_pct is not None else None
            hold_deadline = min(entry_idx + max_holding_bars, n - 1) if max_holding_bars else n - 1

            exit_idx = exit_price = exit_reason = None
            j = entry_idx
            while j < n:
                hit_stop = stop_price is not None and lows[j] <= stop_price
                hit_target = highs[j] >= target_price
                if hit_stop:
                    exit_idx, exit_price, exit_reason = j, stop_price, "stop_loss"
                    break
                if hit_target:
                    exit_idx, exit_price, exit_reason = j, target_price, "take_profit"
                    break
                if j >= hold_deadline:
                    exit_idx, exit_price, exit_reason = j, closes[j], "max_holding_bars"
                    break
                equity_vals[j] = capital * (closes[j] / entry_price)
                position_vals[j] = 1
                j += 1
            else:
                exit_idx, exit_price, exit_reason = n - 1, closes[-1], "open_at_data_end"

            pnl_pct = (exit_price / entry_price - 1) - 2 * cost_rate
            trades.append({
                "entry_date": df.index[entry_idx], "entry_price": entry_price,
                "exit_date": df.index[exit_idx], "exit_price": exit_price,
                "exit_reason": exit_reason, "holding_bars": exit_idx - entry_idx,
                "pnl_pct": pnl_pct,
            })

            capital = capital * (1 + pnl_pct)
            equity_vals[exit_idx] = capital
            position_vals[exit_idx] = 1
            day = exit_idx + 1
        else:
            day += 1

    equity = pd.Series(equity_vals, index=df.index)
    position = pd.Series(position_vals, index=df.index)
    net_return = equity.pct_change().fillna(0)
    trades_df = pd.DataFrame(trades, columns=[
        "entry_date", "entry_price", "exit_date", "exit_price", "exit_reason", "holding_bars", "pnl_pct",
    ])
    metrics = compute_metrics(equity, net_return, position, trades_df, periods_per_year)
    metrics["avg_holding_bars"] = float(trades_df["holding_bars"].mean()) if len(trades_df) else float("nan")

    return BracketResult(strategy_name, equity, trades_df, metrics)
