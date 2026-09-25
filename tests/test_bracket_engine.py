import pandas as pd
import pytest

from trading_bot.backtest.bracket_engine import run_bracket_backtest
from trading_bot.strategies.dip_buy_bracket import dip_buy_entry_signal


def _df(opens, highs, lows, closes):
    idx = pd.date_range("2022-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes}, index=idx)


def _flat_signal(df, true_on):
    sig = pd.Series(False, index=df.index)
    sig.iloc[true_on] = True
    return sig


def test_entry_fills_at_next_bar_open_not_signal_bar_price():
    n = 10
    opens = [100.0] * n
    highs = [100.0] * n
    lows = [100.0] * n
    closes = [100.0] * n
    opens[5] = 77.0  # distinctive fill price on the bar AFTER the signal
    df = _df(opens, highs, lows, closes)
    signal = _flat_signal(df, true_on=4)  # signal fires on day 4
    result = run_bracket_backtest(df, signal, take_profit_pct=0.50, stop_loss_pct=None,
                                   max_holding_bars=None, fee_bps=0, slippage_bps=0)
    assert result.trades.iloc[0]["entry_price"] == pytest.approx(77.0)
    assert result.trades.iloc[0]["entry_date"] == df.index[5]


def test_take_profit_exits_at_target_price_when_high_touches_it():
    n = 10
    opens = [100.0] * n
    highs = [100.0] * n
    lows = [100.0] * n
    closes = [100.0] * n
    highs[3] = 116.0  # entry at day1 open=100, target = 115 (15%), touched day3
    df = _df(opens, highs, lows, closes)
    signal = _flat_signal(df, true_on=0)
    result = run_bracket_backtest(df, signal, take_profit_pct=0.15, stop_loss_pct=0.10,
                                   max_holding_bars=None, fee_bps=0, slippage_bps=0)
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "take_profit"
    assert trade["exit_price"] == pytest.approx(115.0)
    assert trade["exit_date"] == df.index[3]


def test_stop_loss_exits_at_stop_price_when_low_touches_it():
    n = 10
    opens = [100.0] * n
    highs = [100.0] * n
    lows = [100.0] * n
    closes = [100.0] * n
    lows[2] = 88.0  # entry at open=100, stop = 90 (10%), touched day2
    df = _df(opens, highs, lows, closes)
    signal = _flat_signal(df, true_on=0)
    result = run_bracket_backtest(df, signal, take_profit_pct=0.20, stop_loss_pct=0.10,
                                   max_holding_bars=None, fee_bps=0, slippage_bps=0)
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "stop_loss"
    assert trade["exit_price"] == pytest.approx(90.0)
    assert trade["exit_date"] == df.index[2]


def test_stop_wins_the_tiebreak_when_both_touched_same_day():
    n = 10
    opens = [100.0] * n
    highs = [100.0] * n
    lows = [100.0] * n
    closes = [100.0] * n
    highs[2] = 130.0  # target(115) AND stop(90) both touched on the same wide-range day
    lows[2] = 80.0
    df = _df(opens, highs, lows, closes)
    signal = _flat_signal(df, true_on=0)
    result = run_bracket_backtest(df, signal, take_profit_pct=0.15, stop_loss_pct=0.10,
                                   max_holding_bars=None, fee_bps=0, slippage_bps=0)
    assert result.trades.iloc[0]["exit_reason"] == "stop_loss"


def test_max_holding_bars_forces_exit_at_close_when_neither_touched():
    n = 10
    opens = [100.0] * n
    highs = [104.0] * n  # never reaches the 15% target
    lows = [98.0] * n    # never reaches the 10% stop
    closes = [102.0] * n
    df = _df(opens, highs, lows, closes)
    signal = _flat_signal(df, true_on=0)
    result = run_bracket_backtest(df, signal, take_profit_pct=0.15, stop_loss_pct=0.10,
                                   max_holding_bars=3, fee_bps=0, slippage_bps=0)
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "max_holding_bars"
    assert trade["holding_bars"] == 3
    assert trade["exit_price"] == pytest.approx(102.0)


def test_cost_is_charged_once_round_trip_at_exit():
    n = 5
    opens = [100.0] * n
    highs = [116.0] * n
    lows = [100.0] * n
    closes = [100.0] * n
    df = _df(opens, highs, lows, closes)
    signal = _flat_signal(df, true_on=0)
    fee_bps, slip_bps = 10.0, 20.0
    result = run_bracket_backtest(df, signal, take_profit_pct=0.15, stop_loss_pct=0.10,
                                   max_holding_bars=None, initial_capital=1000,
                                   fee_bps=fee_bps, slippage_bps=slip_bps)
    cost_rate = (fee_bps + slip_bps) / 10_000.0
    trade = result.trades.iloc[0]
    expected_pnl = (trade["exit_price"] / trade["entry_price"] - 1) - 2 * cost_rate
    assert trade["pnl_pct"] == pytest.approx(expected_pnl)
    assert result.equity_curve.iloc[-1] == pytest.approx(1000 * (1 + expected_pnl))


def test_no_lookahead_signal_after_last_two_bars_cannot_open_a_trade():
    n = 5
    df = _df([100.0] * n, [100.0] * n, [100.0] * n, [100.0] * n)
    signal = _flat_signal(df, true_on=n - 1)  # fires on the very last bar: no next bar to fill at
    result = run_bracket_backtest(df, signal, take_profit_pct=0.15, stop_loss_pct=0.10,
                                   max_holding_bars=None, fee_bps=0, slippage_bps=0)
    assert len(result.trades) == 0


def test_dip_buy_entry_signal_triggers_only_after_real_pullback():
    closes = [100] * 20 + [89] + [100] * 5  # 20-day high=100, an 11% dip on day 20
    df = _df(closes, closes, closes, closes)
    signal = dip_buy_entry_signal(df, lookback_days=20, pullback_pct=0.10)
    assert signal.iloc[20] == True
    assert not signal.iloc[:20].any()
