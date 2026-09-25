"""Walk-forward validation: repeatedly pick a strategy's parameters using only past
data, apply that fixed choice to the next unseen period, then roll forward and repeat
-- chaining the unseen ("out-of-sample") segments into one continuous equity curve.

This exists because a single in-sample backtest over one historical window only shows
how well a fixed, hand-picked parameter choice happened to fit that one window. This
repo's own history makes the point directly: sma_crossover_20_50 beat buy-and-hold's
Sharpe on a 2020-2025 backtest and then lost far worse than buy-and-hold over the
2021-11..2022-11 bear market when both used those same fixed parameters (see README).
Walk-forward re-selects parameters periodically using only prior data, so the result
is not "how did one guess happen to do" but "does this strategy FAMILY, re-optimized
the way you'd actually have to run it live, hold up out-of-sample."

Design notes on correctness (the parts that are easy to get subtly wrong):
- Parameter selection for the segment starting at `test_start` uses ONLY
  `df.loc[train_start:train_end]`, i.e. data strictly before that segment.
- A strategy's signal at each bar within a test segment is computed from a context
  that includes all prior history (`df.loc[:test_end]`), not just the test segment in
  isolation -- otherwise every segment would restart with a cold rolling window and
  falsely look flat/inactive for its first `lookback` bars, which never happens live.
- Segments are half-open: `[test_start, test_end)`. The boundary date belongs to the
  NEXT segment, whose (possibly different) freshly-selected parameters actually govern
  it -- it is never scored under two different parameter sets nor dropped.
- Transaction cost at the first bar of a new segment is charged against the ACTUAL
  position carried out of the previous segment (whatever that segment's own strategy
  held), not against what the new segment's strategy would hypothetically have held
  the day before -- the position you are really flipping out of is the real one.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ..strategies.base import Strategy
from .engine import compute_position, extract_trades, run_backtest
from .metrics import compute_metrics


@dataclass
class WalkForwardResult:
    strategy_family: str
    equity_curve: pd.Series
    segment_log: pd.DataFrame
    metrics: dict


def _score(metrics: dict) -> float:
    sharpe = metrics.get("sharpe_ratio")
    if sharpe is not None and pd.notna(sharpe):
        return sharpe
    total_return = metrics.get("total_return")
    return total_return if total_return is not None and pd.notna(total_return) else float("-inf")


def _select_best_params(train_df: pd.DataFrame, factory: Callable[..., Strategy], param_grid: dict,
                         fee_bps: float, slippage_bps: float, periods_per_year: float) -> tuple[dict | None, float]:
    keys = list(param_grid.keys())
    best_params, best_score = None, float("-inf")
    for values in itertools.product(*param_grid.values()):
        params = dict(zip(keys, values))
        try:
            strategy = factory(**params)
        except ValueError:
            continue  # e.g. an sma_crossover candidate with fast >= slow
        result = run_backtest(train_df, strategy, initial_capital=1.0, fee_bps=fee_bps,
                               slippage_bps=slippage_bps, periods_per_year=periods_per_year)
        score = _score(result.metrics)
        if score > best_score:
            best_score, best_params = score, params
    return best_params, best_score


def run_walk_forward(df: pd.DataFrame, strategy_family: str, factory: Callable[..., Strategy],
                      param_grid: dict, train_days: int = 365, test_days: int = 90,
                      initial_capital: float = 10_000.0, fee_bps: float = 5.0,
                      slippage_bps: float = 10.0, periods_per_year: float = 365.0) -> WalkForwardResult:
    cost_rate = (fee_bps + slippage_bps) / 10_000.0
    history_start, history_end = df.index.min(), df.index.max()

    train_start = history_start
    train_end = train_start + pd.Timedelta(days=train_days)

    capital = initial_capital
    actual_prev_position = 0.0

    equity_pieces, position_pieces, return_pieces, segment_rows = [], [], [], []

    while True:
        test_start = train_end
        if test_start >= history_end:
            break
        test_end = min(test_start + pd.Timedelta(days=test_days), history_end)

        train_df = df.loc[train_start:train_end]
        if len(train_df) < 30:
            break

        best_params, best_score = _select_best_params(
            train_df, factory, param_grid, fee_bps, slippage_bps, periods_per_year)
        if best_params is None:
            break
        strategy = factory(**best_params)

        context_df = df.loc[:test_end]
        position_full = compute_position(context_df, strategy)
        asset_return_full = context_df["close"].pct_change().fillna(0)

        is_last_segment = test_end >= history_end
        position_test = position_full.loc[test_start:test_end]
        asset_return_test = asset_return_full.loc[test_start:test_end]
        if not is_last_segment:
            position_test = position_test.iloc[:-1]
            asset_return_test = asset_return_test.iloc[:-1]

        turnover_test = position_test.diff().abs()
        turnover_test.iloc[0] = abs(position_test.iloc[0] - actual_prev_position)

        net_return_test = position_test * asset_return_test - turnover_test * cost_rate
        segment_equity = capital * (1 + net_return_test).cumprod()

        equity_pieces.append(segment_equity)
        position_pieces.append(position_test)
        return_pieces.append(net_return_test)
        segment_rows.append({
            "train_start": train_start, "train_end": train_end,
            "test_start": position_test.index.min(), "test_end": position_test.index.max(),
            "params": best_params, "in_sample_score": best_score,
        })

        capital = segment_equity.iloc[-1]
        actual_prev_position = position_test.iloc[-1]
        train_start += pd.Timedelta(days=test_days)
        train_end += pd.Timedelta(days=test_days)

    equity_curve = pd.concat(equity_pieces)
    position_all = pd.concat(position_pieces)
    net_return_all = pd.concat(return_pieces)
    assert not equity_curve.index.duplicated().any(), "walk-forward segments must not overlap"

    trades = extract_trades(df, position_all, cost_rate)
    metrics = compute_metrics(equity_curve, net_return_all, position_all, trades, periods_per_year)

    return WalkForwardResult(strategy_family, equity_curve, pd.DataFrame(segment_rows), metrics)
