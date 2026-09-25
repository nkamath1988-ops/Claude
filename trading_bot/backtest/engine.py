"""Backtest engine: long-only, single-asset, no leverage or shorting (matches what a
spot crypto account on Robinhood can actually do).

Execution model: a strategy's signal at bar t is computed from data through bar t's
close, but is only acted on starting bar t+1 (`position = signal.shift(1)`) so there
is no lookahead. For simplicity, the assumed fill price for both the return calculation
and the trade log is the *previous* bar's close — an optimistic simplification common in
research backtests (it ignores intrabar movement), which is exactly why `slippage_bps`
exists: it is a deliberate, separate cost meant to claw back some of that optimism, not
a real order-book slippage model. Treat these results as a strategy comparison under a
consistent set of assumptions, not as a prediction of live P&L.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..strategies.base import Strategy
from .metrics import compute_metrics


@dataclass
class BacktestResult:
    strategy_name: str
    equity_curve: pd.Series
    trades: pd.DataFrame
    metrics: dict


def compute_position(df: pd.DataFrame, strategy: Strategy) -> pd.Series:
    """The position held during each bar of `df`: strategy's signal at bar t (computed
    from data through t) only takes effect starting bar t+1. Exposed separately from
    run_backtest so walk-forward validation can compute a strategy's signal over a full
    historical context (so rolling/ewm indicators are already warmed up) while only
    scoring a later sub-window -- see backtest/walk_forward.py."""
    signal = strategy.generate_signals(df)
    return signal.shift(1).fillna(0)


def extract_trades(df: pd.DataFrame, position: pd.Series, cost_rate: float) -> pd.DataFrame:
    exec_price = df["close"].shift(1)
    trades = []
    entry_idx = None
    prev = 0
    for idx, pos in position.items():
        if prev == 0 and pos == 1:
            entry_idx = idx
        elif prev == 1 and pos == 0 and entry_idx is not None:
            entry_price, exit_price = exec_price.loc[entry_idx], exec_price.loc[idx]
            if pd.notna(entry_price) and pd.notna(exit_price) and entry_price != 0:
                trades.append({
                    "entry_date": entry_idx, "exit_date": idx,
                    "entry_price": entry_price, "exit_price": exit_price,
                    "pnl_pct": (exit_price / entry_price - 1) - 2 * cost_rate,
                    "open": False,
                })
            entry_idx = None
        prev = pos

    if prev == 1 and entry_idx is not None:
        entry_price = exec_price.loc[entry_idx]
        exit_price = df["close"].iloc[-1]
        if pd.notna(entry_price) and entry_price != 0:
            trades.append({
                "entry_date": entry_idx, "exit_date": None,
                "entry_price": entry_price, "exit_price": exit_price,
                "pnl_pct": (exit_price / entry_price - 1) - cost_rate,
                "open": True,
            })

    return pd.DataFrame(trades, columns=["entry_date", "exit_date", "entry_price", "exit_price", "pnl_pct", "open"])


def run_backtest(df: pd.DataFrame, strategy: Strategy, initial_capital: float = 10_000.0,
                  fee_bps: float = 5.0, slippage_bps: float = 10.0,
                  periods_per_year: float = 365.0) -> BacktestResult:
    """Run `strategy` over `df` (must have an 'close'/'high'/'low' columns, sorted
    ascending by time). fee_bps/slippage_bps are round-trip-leg costs in basis points
    of notional, charged on every position change (entry AND exit each pay it once)."""
    position = compute_position(df, strategy)

    asset_return = df["close"].pct_change().fillna(0)
    gross_return = position * asset_return

    prev_position = position.shift(1).fillna(0)
    turnover = (position - prev_position).abs()
    cost_rate = (fee_bps + slippage_bps) / 10_000.0
    cost = turnover * cost_rate

    net_return = gross_return - cost
    equity = initial_capital * (1 + net_return).cumprod()

    trades = extract_trades(df, position, cost_rate)
    metrics = compute_metrics(equity, net_return, position, trades, periods_per_year)

    return BacktestResult(strategy.name, equity, trades, metrics)
