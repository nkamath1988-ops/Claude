import pandas as pd

from trading_bot.strategies.donchian_breakout import DonchianBreakout
from trading_bot.strategies.rsi_reversion import RsiMeanReversion
from trading_bot.strategies.sma_crossover import SmaCrossover


def _df(highs, lows, closes):
    idx = pd.date_range("2021-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({"open": closes, "high": highs, "low": lows, "close": closes}, index=idx)


def test_sma_crossover_signal_is_binary_and_zero_before_slow_window_ready():
    closes = list(range(1, 41))
    df = _df(closes, closes, closes)
    strat = SmaCrossover(fast=5, slow=20)
    sig = strat.generate_signals(df)
    assert set(sig.unique()).issubset({0, 1})
    assert (sig.iloc[:19] == 0).all()  # slow SMA not yet defined for first 19 bars


def test_sma_crossover_rejects_fast_ge_slow():
    import pytest
    with pytest.raises(ValueError):
        SmaCrossover(fast=20, slow=20)


def test_rsi_reversion_buys_after_sustained_decline_and_sells_after_recovery():
    # steady decline then steady rally
    closes = list(range(100, 60, -1)) + list(range(60, 110))
    df = _df(closes, closes, closes)
    strat = RsiMeanReversion(period=14, oversold=30, overbought=60)
    sig = strat.generate_signals(df)
    assert sig.iloc[-1] == 0  # should have exited by the time price fully recovered
    assert sig.max() == 1     # should have entered a long at some point during the decline


def test_donchian_breakout_enters_on_new_high_and_exits_on_new_low():
    # flat, then a clean breakout above the prior 5-bar high, then a breakdown
    closes = [10, 10, 10, 10, 10, 20, 20, 20, 20, 20, 1, 1, 1, 1, 1]
    df = _df(closes, closes, closes)
    strat = DonchianBreakout(lookback=5)
    sig = strat.generate_signals(df)
    assert sig.iloc[5] == 1   # breaks above the 5-bar high of 10 on bar index 5
    assert sig.iloc[-1] == 0  # breaks below the 5-bar low after the crash
