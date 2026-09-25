"""Paper trading for the swing-scanner's stock candidates: multiple concurrent
positions (unlike the single-position ETH walk-forward paper trader), each with
its own ATR-based stop/target/timeout, no real orders anywhere in this module.

Position sizing: a FIXED fraction (`capital_per_trade_pct`) of the portfolio's
ORIGINAL total capital, not of current equity -- so position size doesn't grow or
shrink with performance. That's a simplifying choice, not a claim it's optimal;
it avoids the extra assumption a compounding sizing rule would add.

Exit priority when both trigger the same day: the stop wins the tie (matches
bracket_engine.py's crypto/SPY convention) -- pessimistic on purpose, not
inferable from daily OHLC alone. Cost is charged once, round-trip, at exit.

Every entry point that advances state by a calendar day is idempotent: calling
`advance_day` twice with the same date is a no-op the second time, so a routine
that fires more than once on the same day can't double-open or double-close a
position.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class StockPaperPortfolio:
    total_capital: float
    capital_per_trade_pct: float
    max_concurrent: int
    max_holding_days: int
    cost_rate: float  # one-way; charged twice (entry+exit) per trade
    cash: float
    open_positions: list = field(default_factory=list)  # each: symbol, entry_date, entry_price, stop_price, target_price, allocated_capital, days_held
    closed_trades: list = field(default_factory=list)
    last_run_date: str | None = None


def new_portfolio(total_capital: float = 10_000.0, capital_per_trade_pct: float = 0.10,
                   max_concurrent: int = 8, max_holding_days: int = 20,
                   cost_bps: float = 7.5) -> StockPaperPortfolio:
    return StockPaperPortfolio(
        total_capital=total_capital, capital_per_trade_pct=capital_per_trade_pct,
        max_concurrent=max_concurrent, max_holding_days=max_holding_days,
        cost_rate=cost_bps / 10_000.0, cash=total_capital,
    )


def save_portfolio(state: StockPaperPortfolio, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(asdict(state), f, indent=2, default=str)


def load_portfolio(path: str) -> StockPaperPortfolio | None:
    if not Path(path).exists():
        return None
    with open(path) as f:
        raw = json.load(f)
    return StockPaperPortfolio(**raw)


def _open_symbols(state: StockPaperPortfolio) -> set:
    return {p["symbol"] for p in state.open_positions}


def open_position(state: StockPaperPortfolio, symbol: str, date: str, entry_price: float,
                   stop_price: float, target_price: float) -> bool:
    """Returns True if the position was opened, False if skipped (already open,
    at capacity, or not enough cash)."""
    if symbol in _open_symbols(state):
        return False
    if len(state.open_positions) >= state.max_concurrent:
        return False
    allocation = state.total_capital * state.capital_per_trade_pct
    if allocation > state.cash:
        return False

    state.cash -= allocation
    state.open_positions.append({
        "symbol": symbol, "entry_date": date, "entry_price": entry_price,
        "stop_price": stop_price, "target_price": target_price,
        "allocated_capital": allocation, "days_held": 0,
    })
    return True


def _close(state: StockPaperPortfolio, pos: dict, exit_date: str, exit_price: float, exit_reason: str) -> None:
    pnl_pct = (exit_price / pos["entry_price"] - 1) - 2 * state.cost_rate
    proceeds = pos["allocated_capital"] * (1 + pnl_pct)
    state.cash += proceeds
    state.closed_trades.append({
        **pos, "exit_date": exit_date, "exit_price": exit_price,
        "exit_reason": exit_reason, "pnl_pct": pnl_pct, "proceeds": proceeds,
    })


def close_due_positions(state: StockPaperPortfolio, date: str, price_data: dict) -> None:
    """`price_data`: {symbol: {"high": ..., "low": ..., "close": ...}} for every
    currently open symbol. A symbol missing from price_data is left untouched
    (e.g. a data gap) rather than guessed at."""
    still_open = []
    for pos in state.open_positions:
        bar = price_data.get(pos["symbol"])
        if bar is None:
            still_open.append(pos)
            continue
        pos["days_held"] += 1
        if bar["low"] <= pos["stop_price"]:
            _close(state, pos, date, pos["stop_price"], "stop_loss")
        elif bar["high"] >= pos["target_price"]:
            _close(state, pos, date, pos["target_price"], "take_profit")
        elif pos["days_held"] >= state.max_holding_days:
            _close(state, pos, date, bar["close"], "max_holding_days")
        else:
            still_open.append(pos)
    state.open_positions = still_open


def portfolio_equity(state: StockPaperPortfolio, current_prices: dict | None = None) -> float:
    """Mark-to-market equity: cash plus each open position's current value. If
    `current_prices` omits a symbol (or is None), that position is valued at its
    allocated capital (flat), not guessed -- an approximation, not a lookahead."""
    current_prices = current_prices or {}
    equity = state.cash
    for pos in state.open_positions:
        price = current_prices.get(pos["symbol"])
        if price is None:
            equity += pos["allocated_capital"]
        else:
            equity += pos["allocated_capital"] * (price / pos["entry_price"])
    return equity


def advance_day(state: StockPaperPortfolio, date: str, price_data: dict,
                 new_candidates: list) -> StockPaperPortfolio:
    """`price_data`: {symbol: {high, low, close}} for every open symbol (for exit
    checks). `new_candidates`: [{symbol, entry_price, stop_price, target_price}, ...]
    for today's fresh scanner signals not already held. Idempotent per date."""
    if state.last_run_date == date:
        return state

    close_due_positions(state, date, price_data)
    for c in new_candidates:
        open_position(state, c["symbol"], date, c["entry_price"], c["stop_price"], c["target_price"])

    state.last_run_date = date
    return state
