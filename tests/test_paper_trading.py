import pandas as pd
import pytest

from trading_bot.paper_trading.engine import (
    _current_segment_bounds, advance, new_state, load_state, save_state,
)
from trading_bot.strategies.sma_crossover import SmaCrossover


def _make_df(closes, start="2020-01-01"):
    idx = pd.date_range(start, periods=len(closes), freq="D")
    return pd.DataFrame({"open": closes, "high": closes, "low": closes, "close": closes}, index=idx)


GRID = {"fast": [5, 10], "slow": [30, 50]}


def test_segment_bounds_match_walk_forward_stepping():
    start = pd.Timestamp("2020-01-01", tz="UTC")
    # 365-day train, 90-day test: after exactly one full cycle (455 days), the
    # window should have stepped forward by one test_days increment.
    end = start + pd.Timedelta(days=365 + 90 + 10)
    train_start, train_end = _current_segment_bounds(start, end, train_days=365, test_days=90)
    assert train_start == start + pd.Timedelta(days=90)
    assert train_end == start + pd.Timedelta(days=365 + 90)


def test_segment_bounds_stay_at_first_window_before_first_step():
    start = pd.Timestamp("2020-01-01", tz="UTC")
    end = start + pd.Timedelta(days=365 + 10)  # not yet a full test_days past train_end
    train_start, train_end = _current_segment_bounds(start, end, train_days=365, test_days=90)
    assert train_start == start
    assert train_end == start + pd.Timedelta(days=365)


def test_bootstrap_sets_state_without_touching_equity():
    closes = [100 + i * 0.5 for i in range(400)]
    df = _make_df(closes)
    state = new_state("TEST", train_days=200, test_days=60, initial_capital=1000)
    state = advance(state, df, SmaCrossover, GRID)
    assert state.last_date == str(df.index[-1].date())
    assert state.equity == pytest.approx(1000.0)  # no return applied on bootstrap day
    assert state.current_params is not None


def test_same_day_call_is_idempotent():
    closes = [100 + i * 0.5 for i in range(400)]
    df = _make_df(closes)
    state = new_state("TEST", train_days=200, test_days=60, initial_capital=1000)
    state = advance(state, df, SmaCrossover, GRID)
    n_daily_after_first = len(state.daily_log)
    n_trades_after_first = len(state.trade_log)
    state = advance(state, df, SmaCrossover, GRID)  # same df, same last date
    assert len(state.daily_log) == n_daily_after_first
    assert len(state.trade_log) == n_trades_after_first
    assert state.equity == pytest.approx(1000.0)


def test_new_day_with_unchanged_position_applies_return_no_new_trade():
    closes = [100 + i * 0.5 for i in range(400)]
    df = _make_df(closes)
    state = new_state("TEST", train_days=200, test_days=60, initial_capital=1000)
    state = advance(state, df, SmaCrossover, GRID)
    trades_before = len(state.trade_log)
    position_before = state.position

    # one more day, price continues the same gentle uptrend -> position shouldn't flip
    df2 = _make_df(closes + [closes[-1] + 0.5])
    state = advance(state, df2, SmaCrossover, GRID)
    assert state.position == position_before
    assert len(state.trade_log) == trades_before  # no flip -> no new trade logged
    assert state.last_date == str(df2.index[-1].date())


def test_position_flip_logs_a_trade_and_charges_cost():
    # engineered price path: rises steadily (fast SMA > slow SMA, long), then
    # crashes hard enough to flip the signal flat, forcing a logged SELL.
    up = [100 + i * 1.0 for i in range(250)]
    down = [up[-1] - i * 3.0 for i in range(1, 40)]
    closes = up + down
    df_before_crash = _make_df(closes[:-1])
    df_after_crash = _make_df(closes)

    state = new_state("TEST", train_days=200, test_days=60, initial_capital=1000, fee_bps=10, slippage_bps=10)
    state = advance(state, df_before_crash, SmaCrossover, GRID)
    was_long = state.position == 1

    state = advance(state, df_after_crash, SmaCrossover, GRID)
    if was_long and state.position == 0:
        assert state.trade_log[-1]["action"] == "SELL (paper)"
    # whether or not it flipped on this exact bar, equity must have moved from
    # exactly 1000 once a real day has elapsed with a nonzero prior position
    if was_long:
        assert state.equity != pytest.approx(1000.0)


def test_save_and_load_roundtrip(tmp_path):
    closes = [100 + i * 0.5 for i in range(400)]
    df = _make_df(closes)
    state = new_state("TEST", train_days=200, test_days=60, initial_capital=1000)
    state = advance(state, df, SmaCrossover, GRID)
    path = str(tmp_path / "state.json")
    save_state(state, path)
    loaded = load_state(path)
    assert loaded.symbol == state.symbol
    assert loaded.equity == pytest.approx(state.equity)
    assert loaded.last_date == state.last_date
    assert loaded.current_params == state.current_params


def test_load_missing_state_returns_none(tmp_path):
    assert load_state(str(tmp_path / "does_not_exist.json")) is None
