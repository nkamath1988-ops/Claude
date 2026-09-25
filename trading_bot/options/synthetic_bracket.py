"""Synthetic options bracket backtest: real underlying price history, model option
prices.

Why this exists: SPY/SPX historical option premiums are unusable in this environment
for any period that overlaps real underlying intraday data. Two things were verified
empirically (see the repo's README): the equity underlying (get_equity_historicals)
is genuine only from 2025-11-03 onward -- everything before that is a flat,
zero-volume placeholder despite not always being flagged as such -- while option
premium histories (get_option_historicals) were confirmed genuine for a contract
expiring June 2025, but flat/frozen for every contract checked expiring December
2025 or later (five separate contracts, spanning Dec 2025 through Sept 2026). Those
two "real" windows do not overlap, so a backtest that needs both real signals and
real option prices in the same period cannot be built from this data source as it
stands today.

This module instead prices each trade's option leg with Black-Scholes off the REAL
underlying price path (genuine from Nov 2025 onward), using a volatility estimate
computed from that same real underlying data. That makes the entry/exit *timing*
and the underlying price path real; the option premium at every point is a model
output, not a measured price. Concretely, this model:

- Estimates volatility as trailing 20-trading-day realized volatility of the
  underlying as of each trade's entry (a common rough proxy for implied vol, not a
  measurement of it -- real implied vol differs from realized vol, especially
  around anticipated events).
- Holds that volatility FIXED for the life of each trade ("sticky vol"): it reprices
  the option every bar as the underlying moves and time passes, but never lets vol
  itself change. Real options see implied vol expand and crush constantly -- often
  the dominant driver of a short-dated option's P&L around news -- and none of that
  is captured here.
- Uses European exercise (exact for SPX, an approximation for SPY, which is
  American-style; the difference is small for a short-dated, not-deep-ITM call).
- Ignores the bid-ask spread entirely (there's no historical spread to measure) and
  instead charges `cost_rate` as a flat round-trip-leg assumption, exactly like
  bracket_engine.py's crypto/equity trades -- a guess, not a fact, same caveat as
  there.

Treat every result from this module as "what would happen if the market priced this
option exactly at its Black-Scholes fair value under a fixed, retrospectively
estimated volatility" -- a reasonable stress test of the entry/exit logic, not a
claim about what real premiums would have done.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .black_scholes import price as bs_price


def realized_vol(underlying_close: pd.Series, window_days: int = 20, periods_per_year: int = 252) -> pd.Series:
    """Trailing annualized realized volatility of daily closes, indexed by date.
    Uses only data through each date (rolling), so no lookahead."""
    log_returns = np.log(underlying_close / underlying_close.shift(1))
    return log_returns.rolling(window_days).std() * (periods_per_year ** 0.5)


@dataclass
class SyntheticTrade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    strike: float
    expiry: pd.Timestamp
    iv_used: float
    entry_underlying: float
    exit_underlying: float
    entry_premium: float
    exit_premium: float
    exit_reason: str
    pnl_pct: float


def run_synthetic_bracket(underlying_5m: pd.DataFrame, entries: pd.DataFrame,
                           daily_vol: pd.Series, take_profit_pct: float = 0.10,
                           stop_loss_pct: float | None = 0.50, rate: float = 0.045,
                           cost_rate: float = 0.03, option_type: str = "call",
                           initial_capital: float = 10_000.0) -> tuple[list[SyntheticTrade], pd.Series]:
    """`entries` needs columns fill_time, spy_price (or equivalent underlying price at
    entry), strike, expiry (all as produced by the CLI's signal + target resolution
    step). Trades are processed in fill_time order with one position at a time: a
    signal whose fill_time falls before the previous trade's actual exit is skipped.
    """
    entries = entries.sort_values("fill_time").reset_index(drop=True)
    capital = initial_capital
    in_position_until = None
    trades: list[SyntheticTrade] = []
    equity_points = [(underlying_5m.index[0], capital)]

    for _, row in entries.iterrows():
        fill_time = row["fill_time"]
        if in_position_until is not None and fill_time < in_position_until:
            continue

        expiry = pd.Timestamp(row["expiry"], tz="UTC") + pd.Timedelta(hours=21)  # ~market close UTC
        strike = row["strike"]

        vol_asof = daily_vol.loc[:fill_time.normalize()]
        if vol_asof.empty or pd.isna(vol_asof.iloc[-1]):
            continue
        iv = float(vol_asof.iloc[-1])

        path = underlying_5m.loc[fill_time:expiry]
        if path.empty:
            continue

        entry_underlying = path["close"].iloc[0]
        years = (expiry - fill_time).total_seconds() / (365 * 86400)
        entry_premium = bs_price(entry_underlying, strike, years, rate, iv, option_type)
        if entry_premium <= 0.01:
            continue  # would-be-worthless entry; not a real trade signal

        target = entry_premium * (1 + take_profit_pct)
        stop = entry_premium * (1 - stop_loss_pct) if stop_loss_pct else None

        exit_ts = exit_underlying = exit_premium = exit_reason = None
        for ts, bar in path.iterrows():
            years_left = (expiry - ts).total_seconds() / (365 * 86400)
            for test_price, label in ((bar["low"], "low"), (bar["high"], "high")):
                model_price = bs_price(test_price, strike, years_left, rate, iv, option_type)
                if stop is not None and label == "low" and model_price <= stop:
                    exit_ts, exit_underlying, exit_premium, exit_reason = ts, test_price, stop, "stop_loss"
                    break
                if label == "high" and model_price >= target:
                    exit_ts, exit_underlying, exit_premium, exit_reason = ts, test_price, target, "take_profit"
                    break
            if exit_ts is not None:
                break

        if exit_ts is None:
            last_ts = path.index[-1]
            years_left = max((expiry - last_ts).total_seconds() / (365 * 86400), 0.0)
            exit_underlying = path["close"].iloc[-1]
            exit_premium = bs_price(exit_underlying, strike, years_left, rate, iv, option_type)
            exit_ts, exit_reason = last_ts, "expired_or_data_end"

        pnl_pct = (exit_premium / entry_premium - 1) - 2 * cost_rate
        capital = capital * (1 + pnl_pct)
        equity_points.append((exit_ts, capital))

        trades.append(SyntheticTrade(
            entry_date=fill_time, exit_date=exit_ts, strike=strike, expiry=expiry, iv_used=iv,
            entry_underlying=entry_underlying, exit_underlying=exit_underlying,
            entry_premium=entry_premium, exit_premium=exit_premium,
            exit_reason=exit_reason, pnl_pct=pnl_pct,
        ))
        in_position_until = exit_ts

    equity_curve = pd.Series(dict(equity_points)).sort_index()
    return trades, equity_curve
