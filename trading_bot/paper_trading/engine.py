"""Paper trading: log what the walk-forward-selected strategy WOULD trade against
real incoming data, with no order placement anywhere in this module. Deliberately
reuses backtest/walk_forward.py's parameter-selection and backtest/engine.py's
position logic rather than reimplementing them, so paper trading can't silently
drift from what was actually validated.

Per the parameter-drift finding (see README): this uses the QUARTERLY-RESELECTING
walk-forward logic, not a fixed "best" parameter set found in hindsight. Locking in
whichever setting looked best on past data would be exactly the look-ahead bias
walk-forward validation exists to avoid -- this module intentionally keeps
re-selecting live, the same way the validated backtest did.

Each call to `advance` is idempotent for a given date: calling it twice with the
same latest bar does not double-log a trade. State persists as JSON so a daily
scheduled run can pick up where the previous one left off.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from ..backtest.engine import compute_position
from ..backtest.walk_forward import _select_best_params
from ..strategies.base import Strategy


@dataclass
class PaperTradingState:
    symbol: str
    fee_bps: float
    slippage_bps: float
    train_days: int
    test_days: int
    position: int = 0
    current_params: dict | None = None
    last_close: float | None = None
    last_date: str | None = None
    equity: float = 10_000.0
    trade_log: list = field(default_factory=list)
    daily_log: list = field(default_factory=list)


def new_state(symbol: str, fee_bps: float = 5.0, slippage_bps: float = 10.0,
              train_days: int = 365, test_days: int = 90,
              initial_capital: float = 10_000.0) -> PaperTradingState:
    return PaperTradingState(symbol=symbol, fee_bps=fee_bps, slippage_bps=slippage_bps,
                              train_days=train_days, test_days=test_days, equity=initial_capital)


def save_state(state: PaperTradingState, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(asdict(state), f, indent=2, default=str)


def load_state(path: str) -> PaperTradingState | None:
    if not Path(path).exists():
        return None
    with open(path) as f:
        raw = json.load(f)
    return PaperTradingState(**raw)


def _current_segment_bounds(history_start: pd.Timestamp, history_end: pd.Timestamp,
                             train_days: int, test_days: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The most recent [train_start, train_end) window whose test segment has
    already begun as of `history_end` -- i.e. "what would the walk-forward have
    selected for the segment we're currently inside of". Mirrors
    backtest/walk_forward.py's own boundary stepping exactly, so a live day never
    computes a segment the historical walk-forward wouldn't also have produced."""
    train_start = history_start
    train_end = train_start + pd.Timedelta(days=train_days)
    while train_end + pd.Timedelta(days=test_days) <= history_end:
        train_start += pd.Timedelta(days=test_days)
        train_end += pd.Timedelta(days=test_days)
    return train_start, train_end


def advance(state: PaperTradingState, df: pd.DataFrame, strategy_cls: type[Strategy],
            param_grid: dict, periods_per_year: float = 365.0) -> PaperTradingState:
    """`df` is the full real price history through the most recent available close.
    Re-selects parameters for whichever segment "today" falls into (same logic as
    the historical walk-forward), computes today's position, and updates the paper
    P&L by exactly one day if this is genuinely a new day since the last call."""
    history_start, history_end = df.index.min(), df.index.max()
    train_start, train_end = _current_segment_bounds(
        history_start, history_end, state.train_days, state.test_days)

    train_df = df.loc[train_start:train_end]
    cost_rate = (state.fee_bps + state.slippage_bps) / 10_000.0
    best_params, best_score = _select_best_params(
        train_df, strategy_cls, param_grid, state.fee_bps, state.slippage_bps, periods_per_year)

    strategy = strategy_cls(**best_params)
    position_series = compute_position(df, strategy)
    new_position = int(position_series.iloc[-1])
    new_close = float(df["close"].iloc[-1])
    new_date = str(df.index[-1].date())

    if state.last_date == new_date:
        return state  # already processed today; idempotent no-op

    if state.last_date is None:
        # Bootstrap: establish the starting position with no return/cost applied yet.
        if new_position == 1:
            state.trade_log.append({
                "date": new_date, "action": "INITIAL_ENTRY", "price": new_close,
                "params": best_params,
            })
        state.daily_log.append({
            "date": new_date, "close": new_close, "position": new_position,
            "params": best_params, "equity": state.equity, "note": "bootstrap",
        })
    else:
        day_return = new_close / state.last_close - 1
        turnover = abs(new_position - state.position)
        cost = turnover * cost_rate
        day_net_return = state.position * day_return - cost
        state.equity = state.equity * (1 + day_net_return)

        if turnover > 0:
            action = "BUY (paper)" if new_position > state.position else "SELL (paper)"
            state.trade_log.append({
                "date": new_date, "action": action, "price": new_close,
                "params": best_params, "equity_after": state.equity,
            })
        state.daily_log.append({
            "date": new_date, "close": new_close, "position": new_position,
            "params": best_params, "equity": state.equity,
        })

    state.position = new_position
    state.current_params = best_params
    state.last_close = new_close
    state.last_date = new_date
    return state
