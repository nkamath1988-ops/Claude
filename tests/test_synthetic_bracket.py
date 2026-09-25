import numpy as np
import pandas as pd
import pytest

from trading_bot.options.synthetic_bracket import realized_vol, run_synthetic_bracket


def test_realized_vol_no_lookahead():
    # flat for 40 days, then a huge one-day jump on day 41: the jump must not leak
    # into vol values computed at or before day 40.
    closes = [100.0] * 40 + [200.0] + [200.0] * 10
    idx = pd.date_range("2026-01-01", periods=len(closes), freq="D")
    s = pd.Series(closes, index=idx)
    vol = realized_vol(s, window_days=20)
    assert (vol.iloc[:40].dropna() == 0).all()  # perfectly flat window -> zero vol
    assert vol.iloc[40] > 0  # the jump day itself shows nonzero vol
    assert pd.isna(vol.iloc[:19]).all()  # not enough window yet


def test_realized_vol_matches_known_annualized_value():
    rng = np.random.default_rng(0)
    daily_sigma = 0.01
    log_rets = rng.normal(0, daily_sigma, 500)
    closes = 100 * np.exp(np.cumsum(log_rets))
    idx = pd.date_range("2026-01-01", periods=500, freq="D")
    s = pd.Series(closes, index=idx)
    vol = realized_vol(s, window_days=250, periods_per_year=252)
    expected_annualized = daily_sigma * (252 ** 0.5)
    assert vol.iloc[-1] == pytest.approx(expected_annualized, rel=0.15)


def _make_underlying(prices, freq_minutes=5, start="2026-01-05 14:30"):
    idx = pd.date_range(start, periods=len(prices), freq=f"{freq_minutes}min", tz="UTC")
    return pd.DataFrame({"open": prices, "high": prices, "low": prices, "close": prices}, index=idx)


def test_take_profit_triggers_when_underlying_rallies_enough():
    # ATM call, 10 days out, low vol: a sizable rally should hit +10% premium target
    prices = [500.0] * 20 + [515.0] * 300  # jump up and hold
    underlying = _make_underlying(prices)
    entries = pd.DataFrame([{
        "fill_time": underlying.index[0], "strike": 500.0, "expiry": "2026-01-15",
    }])
    daily_vol = pd.Series([0.15], index=[underlying.index[0].normalize()])
    trades, equity = run_synthetic_bracket(underlying, entries, daily_vol,
                                            take_profit_pct=0.10, stop_loss_pct=0.50)
    assert len(trades) == 1
    assert trades[0].exit_reason == "take_profit"
    assert trades[0].pnl_pct > 0


def test_stop_loss_triggers_when_underlying_drops_enough():
    prices = [500.0] * 20 + [470.0] * 300  # sharp drop and hold
    underlying = _make_underlying(prices)
    entries = pd.DataFrame([{
        "fill_time": underlying.index[0], "strike": 500.0, "expiry": "2026-01-15",
    }])
    daily_vol = pd.Series([0.15], index=[underlying.index[0].normalize()])
    trades, equity = run_synthetic_bracket(underlying, entries, daily_vol,
                                            take_profit_pct=0.10, stop_loss_pct=0.50)
    assert len(trades) == 1
    assert trades[0].exit_reason == "stop_loss"
    assert trades[0].pnl_pct < 0


def test_no_trigger_forces_exit_at_expiry():
    # flat underlying, but expiry far enough out (10 days) that ~1.4 days of pure
    # theta decay within the fetched window isn't enough to move a wide +/-70% band
    prices = [500.0] * 400
    underlying = _make_underlying(prices)
    entries = pd.DataFrame([{
        "fill_time": underlying.index[0], "strike": 500.0, "expiry": "2026-01-15",
    }])
    daily_vol = pd.Series([0.10], index=[underlying.index[0].normalize()])
    trades, equity = run_synthetic_bracket(underlying, entries, daily_vol,
                                            take_profit_pct=0.70, stop_loss_pct=0.70)
    assert len(trades) == 1
    assert trades[0].exit_reason == "expired_or_data_end"


def test_overlapping_signal_is_skipped_until_prior_trade_actually_exits():
    prices = [500.0] * 20 + [515.0] * 300
    underlying = _make_underlying(prices)
    entries = pd.DataFrame([
        {"fill_time": underlying.index[0], "strike": 500.0, "expiry": "2026-01-15"},
        {"fill_time": underlying.index[5], "strike": 500.0, "expiry": "2026-01-15"},  # overlaps trade 1
    ])
    daily_vol = pd.Series([0.15], index=[underlying.index[0].normalize()])
    trades, equity = run_synthetic_bracket(underlying, entries, daily_vol,
                                            take_profit_pct=0.10, stop_loss_pct=0.50)
    assert len(trades) == 1  # second signal was skipped, not opened as a separate trade
