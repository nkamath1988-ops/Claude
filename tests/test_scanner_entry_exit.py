import pytest

from trading_bot.scanner.entry_exit import suggest_entry_exit


def _row(**overrides):
    cols = {
        "Close": "100.0", "Last": "100.0", "Average true range": "2.0",
        "RSI": "42.0", "Average directional index (14)": "25.0",
    }
    cols.update(overrides)
    return {"ticker": "TEST", "columns": cols}


def test_entry_uses_close_not_last():
    s = suggest_entry_exit(_row(Close="100.0", Last="110.0"))
    assert s.entry_price == pytest.approx(100.0)
    assert s.drift_pct == pytest.approx(0.10)


def test_default_stop_and_target_multiples():
    s = suggest_entry_exit(_row(Close="100.0", **{"Average true range": "2.0"}))
    assert s.stop_price == pytest.approx(100.0 - 1.5 * 2.0)
    assert s.target_price == pytest.approx(100.0 + 3.0 * 2.0)
    assert s.stop_pct == pytest.approx(-0.03)
    assert s.target_pct == pytest.approx(0.06)


def test_reward_risk_ratio_reflects_multiples():
    s = suggest_entry_exit(_row(), atr_stop_mult=1.0, atr_target_mult=2.0)
    assert s.reward_risk_ratio == pytest.approx(2.0)


def test_stop_always_below_entry_and_target_always_above():
    for atr in [0.5, 2.0, 10.0]:
        s = suggest_entry_exit(_row(**{"Average true range": str(atr)}))
        assert s.stop_price < s.entry_price < s.target_price


def test_zero_drift_when_last_equals_close():
    s = suggest_entry_exit(_row(Close="50.0", Last="50.0"))
    assert s.drift_pct == pytest.approx(0.0)
