import pandas as pd
import pytest

from trading_bot.backtest.engine import run_backtest
from trading_bot.strategies.base import Strategy


def _make_df(closes):
    idx = pd.date_range("2021-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({"open": closes, "high": closes, "low": closes, "close": closes}, index=idx)


class AlwaysFlat(Strategy):
    name = "always_flat"

    def generate_signals(self, df):
        return pd.Series(0, index=df.index)


class AlwaysLong(Strategy):
    name = "always_long"

    def generate_signals(self, df):
        return pd.Series(1, index=df.index)


class OneShotLong(Strategy):
    """Long from day `entry` to day `exit_` (inclusive), flat otherwise."""

    name = "one_shot_long"

    def __init__(self, entry, exit_):
        self.entry, self.exit_ = entry, exit_

    def generate_signals(self, df):
        sig = pd.Series(0, index=df.index)
        sig.iloc[self.entry:self.exit_ + 1] = 1
        return sig


def test_always_flat_never_trades_and_equity_is_flat():
    df = _make_df([100, 105, 95, 120, 80])
    result = run_backtest(df, AlwaysFlat(), initial_capital=1000, fee_bps=0, slippage_bps=0)
    assert result.metrics["num_trades"] == 0
    assert (result.equity_curve == 1000).all()
    assert result.metrics["exposure"] == 0.0


def test_always_long_matches_buy_and_hold_return_with_zero_costs():
    closes = [100, 110, 121, 108.9]
    df = _make_df(closes)
    result = run_backtest(df, AlwaysLong(), initial_capital=1000, fee_bps=0, slippage_bps=0)
    # signal.shift(1) means day 0 is flat (no prior signal to act on); day1..end long.
    expected_final = 1000 * (closes[-1] / closes[0])
    assert result.equity_curve.iloc[-1] == pytest.approx(expected_final, rel=1e-9)


def test_first_bar_is_always_flat_regardless_of_strategy():
    # position[0] = signal[-1] which doesn't exist, so it must default to flat (0)
    # no matter what the strategy signals on bar 0 itself -- there is no prior bar
    # whose close-of-day decision could have put you in a position for bar 0.
    df = _make_df([100, 200, 50])
    result = run_backtest(df, AlwaysLong(), initial_capital=1000, fee_bps=0, slippage_bps=0)
    assert result.equity_curve.iloc[0] == pytest.approx(1000.0, rel=1e-9)


def test_round_trip_trade_pays_entry_and_exit_cost():
    closes = [100, 100, 150, 150, 150]
    df = _make_df(closes)
    fee_bps, slip_bps = 10.0, 20.0  # 0.30% round-trip-leg cost each way
    strat = OneShotLong(entry=1, exit_=2)  # long during day1 and day2, flat elsewhere
    result = run_backtest(df, strat, initial_capital=1000, fee_bps=fee_bps, slippage_bps=slip_bps)
    assert result.metrics["num_trades"] == 1
    trade = result.trades.iloc[0]
    cost_rate = (fee_bps + slip_bps) / 10_000.0
    # entry/exit prices use prior-close convention: entry uses close[entry-1]=100,
    # exit uses close[exit-1]=100 too (since signal drops to 0 the day AFTER exit_).
    expected_pnl = (trade["exit_price"] / trade["entry_price"] - 1) - 2 * cost_rate
    assert trade["pnl_pct"] == pytest.approx(expected_pnl, rel=1e-9)


def test_max_drawdown_is_negative_or_zero_and_matches_definition():
    df = _make_df([100, 200, 50, 50])
    result = run_backtest(df, AlwaysLong(), initial_capital=1000, fee_bps=0, slippage_bps=0)
    equity = result.equity_curve
    manual_dd = (equity / equity.cummax() - 1).min()
    assert result.metrics["max_drawdown"] == pytest.approx(manual_dd)
    assert result.metrics["max_drawdown"] <= 0
